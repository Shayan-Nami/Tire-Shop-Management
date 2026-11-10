from __future__ import annotations
from typing import Any
from rest_framework import serializers
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from django.db import transaction
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.password_validation import validate_password
from utils.persian import normalize_digits
from .services import set_password_and_revoke_tokens


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user: User) -> RefreshToken:
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role
        token['full_name'] = user.full_name or user.username
        return token

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'full_name': self.user.full_name or self.user.username,
            'role': self.user.role,
            'phone_number': self.user.phone_number
        }
        return data

class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        refresh = self.token_class(attrs['refresh'])
        JWTAuthentication().get_user(refresh)
        return super().validate(attrs)


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'phone_number', 'role', 'role_display', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class UserCreateUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'full_name', 'phone_number', 'role', 'is_active']
        extra_kwargs = {
            'phone_number': {
                'error_messages': {
                    'unique': 'این شماره موبایل قبلاً برای کاربر دیگری ثبت شده است.'
                }
            }
        }

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        if 'phone_number' in data:
            if data['phone_number']:
                norm = normalize_digits(str(data['phone_number']).strip())
                data['phone_number'] = norm if norm else None
            else:
                data['phone_number'] = None
        return super().to_internal_value(data)

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
        if not value:
            return None
        norm = normalize_digits(str(value).strip())
        qs = User.objects.filter(phone_number=norm)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("این شماره موبایل قبلاً برای کاربر دیگری ثبت شده است.")
        return norm

    def create(self, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop('password', None)
        user = super().create(validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(update_fields=['password'])
        return user

    @transaction.atomic
    def update(self, instance: User, validated_data: dict[str, Any]) -> User:
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            set_password_and_revoke_tokens(instance, password)
        return instance


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'phone_number']

    def validate_phone_number(self, value: str | None) -> str | None:
        if not value:
            return None
        norm = normalize_digits(str(value).strip())
        qs = User.objects.filter(phone_number=norm)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("این شماره موبایل قبلاً برای کاربر دیگری ثبت شده است.")
        return norm


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
