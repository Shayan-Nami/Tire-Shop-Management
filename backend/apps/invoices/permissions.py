from rest_framework.permissions import BasePermission
from apps.accounts.models import UserRole

class SalesInvoicePermission(BasePermission):
    """
    مجوزهای دسترسی به فاکتور فروش (جلوگیری از BOLA/IDOR):
    - مشاهده (GET/HEAD/OPTIONS): مجاز برای همه کاربران احراز هویت شده (مدیر، انباردار، تکنسین)
      (فیلتر دسترسی اشیاء در get_queryset اعمال می‌شود تا تکنسین فقط فاکتورهای خودش را ببیند)
    - ایجاد (POST): فقط تکنسین و مدیر مجازند؛ انباردار مسدود است (403)
    - سایر متدها (PUT/PATCH/DELETE): مسدود
    """
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
