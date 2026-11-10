from rest_framework.permissions import BasePermission
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
        return request.user.role in [UserRole.WAREHOUSE, UserRole.MANAGER] or request.user.is_superuser


from apps.invoices.permissions import SalesInvoicePermission as SalesInvoicePermission


class IsDocManagerOrDebug(BasePermission):
    message = 'دسترسی به مستندات سامانه در محیط پروداکشن منحصراً برای مدیران سیستم مجاز است.'

    def has_permission(self, request, view):
        from django.conf import settings
        import os
        if settings.DEBUG:
            return True
        if os.environ.get('ENABLE_DOCS_IN_PROD', 'False').lower() in ('true', '1', 'yes'):
            return True
        return bool(
            request.user and request.user.is_authenticated and (
                getattr(request.user, 'role', None) == UserRole.MANAGER or request.user.is_superuser
            )
        )

