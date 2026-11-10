from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.settings import api_settings
from drf_spectacular.utils import extend_schema
from django.contrib.auth import get_user_model
from .serializers import (
    CustomTokenObtainPairSerializer, CustomTokenRefreshSerializer, UserSerializer, UserCreateUpdateSerializer,
    UserProfileUpdateSerializer, ChangePasswordSerializer, LogoutSerializer
)
from .permissions import IsManager
from .services import set_password_and_revoke_tokens
from utils.throttling import LoginIPRateThrottle, LoginUsernameRateThrottle, TokenRefreshRateThrottle

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginIPRateThrottle, LoginUsernameRateThrottle]

class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer
    throttle_classes = [TokenRefreshRateThrottle]

class CurrentUserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(request=UserProfileUpdateSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = UserProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

    @extend_schema(request=UserProfileUpdateSerializer, responses={200: UserSerializer})
    def put(self, request):
        return self.patch(request)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer, responses={200: dict})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        set_password_and_revoke_tokens(request.user, serializer.validated_data['new_password'])
        return Response({'detail': 'رمز عبور با موفقیت تغییر یافت.'}, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=LogoutSerializer, responses={200: dict})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            if str(token[api_settings.USER_ID_CLAIM]) != str(getattr(request.user, api_settings.USER_ID_FIELD)):
                raise TokenError('Refresh token does not belong to this user.')
            token.blacklist()
            return Response({'detail': 'خروج با موفقیت انجام شد و توکن در لیست سیاه قرار گرفت.'}, status=status.HTTP_200_OK)
        except TokenError:
            return Response({'detail': 'توکن نامعتبر یا منقضی شده است.'}, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    permission_classes = [IsManager]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return UserCreateUpdateSerializer
        return UserSerializer

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if obj.is_superuser and not request.user.is_superuser:
            self.permission_denied(
                request,
                message="شما اجازه دسترسی یا ویرایش حساب کاربری ارشد (Superuser) را ندارید."
            )

    def destroy(self, request, *args, **kwargs):
        user_to_delete = self.get_object()
        if user_to_delete.pk == request.user.pk:
            raise ValidationError({'detail': 'امکان حذف حساب کاربری جاری توسط خود کاربر وجود ندارد.'})
        return super().destroy(request, *args, **kwargs)
