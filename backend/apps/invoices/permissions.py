from rest_framework.permissions import BasePermission
from apps.accounts.models import UserRole

class SalesInvoicePermission(BasePermission):
    message = 'انباردار مجاز به صدور فاکتور فروش نیست.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        if request.method == 'POST':
            if request.user.role == UserRole.WAREHOUSE:
                self.message = 'انباردار مجاز به صدور فاکتور فروش نیست.'
                return False
            return request.user.role in [UserRole.MANAGER, UserRole.TECHNICIAN] or request.user.is_superuser
        return request.user.role == UserRole.MANAGER or request.user.is_superuser
