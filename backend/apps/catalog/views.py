from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F, Count
from .models import Brand, Size, Tire, StockMovement
from .serializers import (
    BrandSerializer, SizeSerializer, TireSerializer,
    StockAdjustmentSerializer, StockMovementSerializer
)
from .services import adjust_tire_stock_service
from apps.accounts.models import UserRole
from apps.accounts.permissions import ReadOnlyOrWarehouse, IsWarehouse

class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.annotate(tires_count=Count('tires')).order_by('brand_name')
    serializer_class = BrandSerializer
    permission_classes = [ReadOnlyOrWarehouse]
    filter_backends = [filters.SearchFilter]
    search_fields = ['brand_name']

class SizeViewSet(viewsets.ModelViewSet):
    queryset = Size.objects.annotate(tires_count=Count('tires')).order_by('size_name')
    serializer_class = SizeSerializer
    permission_classes = [ReadOnlyOrWarehouse]
    filter_backends = [filters.SearchFilter]
    search_fields = ['size_name']

class TireViewSet(viewsets.ModelViewSet):
    queryset = Tire.objects.select_related('brand', 'size').all().order_by('brand__brand_name', 'tire_name')
    serializer_class = TireSerializer
    permission_classes = [ReadOnlyOrWarehouse]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['brand', 'size']
    search_fields = ['tire_name', 'brand__brand_name', 'size__size_name']

    @property
    def ordering_fields(self):
        # جلوگیری از امکان مرتب‌سازی بر اساس قیمت خرید برای تکنسین‌ها
        fields = ['stock_quantity', 'sale_price', 'purchase_price']
        request = getattr(self, 'request', None)
        if request and hasattr(request, 'user') and getattr(request.user, 'role', None) == UserRole.TECHNICIAN:
            return ['stock_quantity', 'sale_price']
        return fields

    def get_ordering_fields(self):
        return self.ordering_fields

    @action(detail=False, methods=['get'], url_path='low-stock')
    def low_stock(self, request):
        """فهرست تایرهایی که موجودی آنها به حداقل یا کمتر از حداقل رسیده است"""
        low_stock_tires = Tire.objects.select_related('brand', 'size').filter(
            stock_quantity__lte=F('min_stock_alert')
        ).order_by('stock_quantity')
        page = self.paginate_queryset(low_stock_tires)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(low_stock_tires, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='adjust-stock', permission_classes=[IsWarehouse])
    def adjust_stock(self, request, pk=None):
        """اصلاح دستی و انبارگردانی موجودی تایر توسط انباردار یا مدیر با ثبت دلیل الزامی"""
        tire = self.get_object()
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        counted_qty = serializer.validated_data['counted_quantity']
        reason = serializer.validated_data['reason']

        movement = adjust_tire_stock_service(
            tire=tire,
            counted_quantity=counted_qty,
            reason=reason,
            user=request.user
        )
        tire.refresh_from_db()
        return Response({
            'message': f"موجودی تایر '{tire.tire_name}' با موفقیت به {tire.stock_quantity} اصلاح شد.",
            'movement_id': movement.movement_id,
            'difference': movement.quantity,
            'current_stock': tire.stock_quantity
        }, status=status.HTTP_200_OK)

class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    دفتر گردش انبار (کاملاً فقط‌خواندنی بدون امکان ویرایش، حذف یا ایجاد مستقیم)
    دسترسی منحصراً برای انباردار و مدیر مجاز است؛ تکنسین خطای ۴۰۳ دریافت می‌کند.
    """
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsWarehouse]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tire', 'movement_type', 'sales_invoice', 'purchase_invoice']
    search_fields = ['tire__tire_name', 'description']
    ordering_fields = ['created_at', 'quantity']

    def get_queryset(self):
        user = getattr(self.request, 'user', None) if hasattr(self, 'request') else None
        if not user or not user.is_authenticated:
            return StockMovement.objects.none()

        return StockMovement.objects.select_related(
            'tire__brand', 'tire__size', 'user', 'sales_invoice', 'purchase_invoice'
        ).all().order_by('-created_at', '-movement_id')


