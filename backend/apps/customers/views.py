from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Customer, Vehicle
from .serializers import CustomerSerializer, VehicleSerializer
from apps.accounts.models import UserRole


class CustomerOrVehiclePermission(permissions.BasePermission):
    """
    مشاهده، ثبت و ویرایش مشتری و خودرو برای کاربران احراز هویت شده مجاز است؛
    اما حذف فیزیکی مشتری یا خودرو منحصراً در اختیار مدیر سیستم است.
    """
    message = 'حذف اطلاعات مشتری یا خودرو فقط توسط مدیر سیستم امکان‌پذیر است.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if view.action == 'destroy':
            return getattr(request.user, 'role', None) == UserRole.MANAGER or request.user.is_superuser
        return True


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.prefetch_related('vehicles').all().order_by('-customer_id')
    serializer_class = CustomerSerializer
    permission_classes = [CustomerOrVehiclePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['full_name', 'phone_number', 'national_code', 'vehicles__license_plate']
    ordering_fields = ['customer_id', 'full_name', 'created_at']

class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related('customer').all().order_by('-vehicle_id')
    serializer_class = VehicleSerializer
    permission_classes = [CustomerOrVehiclePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['customer']
    search_fields = ['license_plate', 'model', 'customer__full_name', 'customer__phone_number']
    ordering_fields = ['vehicle_id', 'model', 'year']
