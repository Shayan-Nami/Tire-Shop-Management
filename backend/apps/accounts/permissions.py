from django.conf import settings
from rest_framework.permissions import BasePermission

from apps.invoices.permissions import SalesInvoicePermission as SalesInvoicePermission
from .models import UserRole


class IsManager(BasePermission):
    message = 'این بخش فقط برای مدیران سیستم مجاز است.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
            request.user.role == UserRole.MANAGER or request.user.is_superuser
        ))


class IsWarehouse(BasePermission):
    message = 'این بخش برای انباردار یا مدیر سیستم مجاز است.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
            request.user.role in [UserRole.WAREHOUSE, UserRole.MANAGER] or request.user.is_superuser
        ))


class IsTechnician(BasePermission):
    message = 'این بخش برای تکنسین یا مدیر سیستم مجاز است.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
            request.user.role in [UserRole.TECHNICIAN, UserRole.MANAGER] or request.user.is_superuser
        ))


class ReadOnlyOrManager(BasePermission):
    message = 'تغییرات فقط توسط مدیر سیستم امکان‌پذیر است.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.role == UserRole.MANAGER or request.user.is_superuser


class ReadOnlyOrWarehouse(BasePermission):
    message = 'تغییرات انبار فقط توسط انباردار یا مدیر سیستم امکان‌پذیر است.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        if request.method == 'DELETE':
            return request.user.role == UserRole.MANAGER or request.user.is_superuser
        return request.user.role in [UserRole.WAREHOUSE, UserRole.MANAGER] or request.user.is_superuser


class IsDocManagerOrDebug(BasePermission):
    message = 'دسترسی به مستندات سامانه در محیط پروداکشن منحصراً برای مدیران سیستم مجاز است.'

    def has_permission(self, request, view):
        if settings.DEBUG:
            return True
        if getattr(settings, 'ENABLE_DOCS_IN_PROD', False):
            return True
        return bool(
            request.user and request.user.is_authenticated and (
                getattr(request.user, 'role', None) == UserRole.MANAGER or request.user.is_superuser
            )
        )
