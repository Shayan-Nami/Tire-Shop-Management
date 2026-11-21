from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.utils import datetime_from_epoch, datetime_to_epoch

from utils.persian import normalize_optional_digits, phone_validator
from utils.serializers import PersianNormalizedCharField
from .models import User
from .services import set_password_and_revoke_tokens

_SESSION_EXPIRED_MESSAGE = 'نشست شما منقضی شده است. لطفاً دوباره وارد شوید.'


def _validate_unique_user_phone(value: str | None, instance: User | None) -> str | None:
    norm = normalize_optional_digits(value)
    if not norm:
        return None
    qs = User.objects.filter(phone_number=norm)
    if instance:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise serializers.ValidationError("این شماره موبایل قبلاً برای کاربر دیگری ثبت شده است.")
    return norm


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user: User) -> RefreshToken:
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role
        token['full_name'] = user.full_name or user.username
        max_hours = getattr(settings, 'JWT_MAX_SESSION_HOURS', 12)
        session_exp = datetime_to_epoch(token.current_time + timedelta(hours=max_hours))
        token['session_exp'] = session_exp
        token['exp'] = min(int(token['exp']), session_exp)
        OutstandingToken.objects.filter(jti=token[api_settings.JTI_CLAIM]).update(
            expires_at=datetime_from_epoch(int(token['exp'])),
            token=str(token),
        )
        return token

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        data = super(TokenObtainPairSerializer, self).validate(attrs)
        refresh = self.get_token(self.user)
        access = refresh.access_token
        access['exp'] = min(int(access['exp']), int(refresh['session_exp']))
        data['refresh'] = str(refresh)
        data['access'] = str(access)
        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, self.user)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'full_name': self.user.full_name or self.user.username,
            'role': self.user.role,
            'phone_number': self.user.phone_number,
        }
        return data


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        refresh = self.token_class(attrs['refresh'])
        session_exp = self._resolve_and_check_session_exp(refresh)

        user = JWTAuthentication().get_user(refresh)
        if not api_settings.USER_AUTHENTICATION_RULE(user):
            raise AuthenticationFailed(self.error_messages['no_active_account'], 'no_active_account')

        access = refresh.access_token
        access['exp'] = min(int(access['exp']), session_exp)
        data: dict[str, Any] = {'access': str(access)}

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass

            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            refresh['session_exp'] = session_exp
            refresh['exp'] = min(int(refresh['exp']), session_exp)
            refresh.outstand()
            data['refresh'] = str(refresh)

        return data

    @staticmethod
    def _resolve_and_check_session_exp(refresh: RefreshToken) -> int:
        if 'session_exp' in refresh.payload:
            try:
                refresh.check_exp('session_exp')
            except TokenError as exc:
                raise InvalidToken(_SESSION_EXPIRED_MESSAGE) from exc
            return int(refresh.payload['session_exp'])

        max_hours = getattr(settings, 'JWT_MAX_SESSION_HOURS', 12)
        iat_epoch = int(refresh.payload.get('iat') or datetime_to_epoch(refresh.current_time))
        session_exp = iat_epoch + max_hours * 3600
        if datetime_from_epoch(session_exp) <= refresh.current_time:
            raise InvalidToken(_SESSION_EXPIRED_MESSAGE)
        return session_exp


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'phone_number', 'role', 'role_display', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class UserCreateUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    phone_number = PersianNormalizedCharField(
        max_length=20,
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[phone_validator],
        error_messages={'unique': 'این شماره موبایل قبلاً برای کاربر دیگری ثبت شده است.'},
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'full_name', 'phone_number', 'role', 'is_active']

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'وارد کردن کلمه عبور برای ایجاد کاربر الزامی است.'})

        request = self.context.get('request')
        if self.instance and request and getattr(request, 'user', None) == self.instance:
            if 'is_active' in attrs and attrs['is_active'] is False:
                raise serializers.ValidationError({'is_active': 'امکان غیرفعال‌سازی حساب کاربری جاری توسط خود کاربر وجود ندارد.'})
            if 'role' in attrs and attrs['role'] != self.instance.role:
                raise serializers.ValidationError({'role': 'امکان تغییر نقش حساب کاربری جاری توسط خود کاربر وجود ندارد.'})

        return attrs

    def validate_password(self, value: str) -> str:
        if value:
            user = self.instance
            if not user:
                username = None
                if hasattr(self, 'initial_data') and isinstance(self.initial_data, dict):
                    username = self.initial_data.get('username')
                user = User(username=username) if username else None
            validate_password(value, user=user)
        return value

    def validate_phone_number(self, value: str | None) -> str | None:
        return _validate_unique_user_phone(value, self.instance)

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    @transaction.atomic
    def update(self, instance: User, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            set_password_and_revoke_tokens(instance, password)
        return instance


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    phone_number = PersianNormalizedCharField(
        max_length=20,
        required=False,
        allow_null=True,
        allow_blank=True,
        validators=[phone_validator],
        error_messages={'unique': 'این شماره موبایل قبلاً برای کاربر دیگری ثبت شده است.'},
    )

    class Meta:
        model = User
        fields = ['full_name', 'phone_number']

    def validate_phone_number(self, value: str | None) -> str | None:
        return _validate_unique_user_phone(value, self.instance)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)

    def validate_old_password(self, value: str) -> str:
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("رمز عبور فعلی نادرست است.")
        return value

    def validate_new_password(self, value: str) -> str:
        user = self.context['request'].user
        validate_password(value, user=user)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs.get('old_password') == attrs.get('new_password'):
            raise serializers.ValidationError({'new_password': 'رمز عبور جدید نمی‌تواند مشابه رمز عبور فعلی باشد.'})
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True, help_text='توکن تجدید (Refresh Token) جهت قرارگیری در لیست سیاه')
