from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Subquery, OuterRef, Value, F
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
import django_filters
from apps.finance.models import ReceiptVoucher, CustomerRefundVoucher
from .models import SalesInvoice, PurchaseInvoice, SalesReturn
from .serializers import (
    SalesInvoiceSerializer, SalesInvoiceCreateSerializer,
    PurchaseInvoiceSerializer, PurchaseInvoiceCreateSerializer,
    SalesReturnSerializer, SalesReturnCreateSerializer
)
from .services import (
    cancel_sales_invoice_service, cancel_purchase_invoice_service,
    confirm_sales_invoice_service
)
from apps.accounts.models import UserRole
from apps.invoices.permissions import SalesInvoicePermission
from apps.accounts.permissions import IsWarehouse, IsManager
from utils.jalali import parse_jalali_or_gregorian_date
from utils.mixins import ImmutableDocumentViewSetMixin


class InvoiceDateRangeFilterSet(django_filters.FilterSet):
    start_date = django_filters.CharFilter(method='filter_start_date')
    end_date = django_filters.CharFilter(method='filter_end_date')

    def _apply_date_bound(self, queryset, name: str, value: str | None, is_end: bool):
        if value is None or not str(value).strip():
            return queryset
        raw = str(value).strip()
        tehran_tz = timezone.get_current_timezone()

        parsed_date_str = parse_jalali_or_gregorian_date(raw)
        if parsed_date_str is not None:
            try:
                parsed_day = date.fromisoformat(parsed_date_str)
            except ValueError:
                raise ValidationError({name: 'فرمت تاریخ نامعتبر است.'})
            if is_end:
                bound_dt = timezone.make_aware(datetime.combine(parsed_day + timedelta(days=1), time.min), tehran_tz)
                return queryset.filter(invoice_date__lt=bound_dt)
            bound_dt = timezone.make_aware(datetime.combine(parsed_day, time.min), tehran_tz)
            return queryset.filter(invoice_date__gte=bound_dt)

        parsed_dt = parse_datetime(raw)
        if parsed_dt is not None:
            if timezone.is_naive(parsed_dt):
                parsed_dt = timezone.make_aware(parsed_dt, tehran_tz)
            lookup = 'invoice_date__lte' if is_end else 'invoice_date__gte'
            return queryset.filter(**{lookup: parsed_dt})

        raise ValidationError({name: 'فرمت تاریخ نامعتبر است.'})

    def filter_start_date(self, queryset, name, value):
        return self._apply_date_bound(queryset, name, value, is_end=False)

    def filter_end_date(self, queryset, name, value):
        return self._apply_date_bound(queryset, name, value, is_end=True)


class SalesInvoiceFilter(InvoiceDateRangeFilterSet):
    class Meta:
        model = SalesInvoice
        fields = ['invoice_number', 'customer', 'vehicle', 'status', 'payment_status', 'start_date', 'end_date']


class PurchaseInvoiceFilter(InvoiceDateRangeFilterSet):
    class Meta:
        model = PurchaseInvoice
        fields = ['supplier', 'status', 'payment_status', 'start_date', 'end_date']

class SalesInvoiceViewSet(ImmutableDocumentViewSetMixin, viewsets.ModelViewSet):
    immutable_document_name = 'فاکتور فروش'
    queryset = SalesInvoice.objects.all()

    def get_queryset(self):
        returned_subquery = SalesReturn.objects.filter(
            sales_invoice=OuterRef('pk')
        ).values('sales_invoice').annotate(
            total=Sum('total_refund_amount')
        ).values('total')

        receipts_subquery = ReceiptVoucher.objects.filter(
            sales_invoice=OuterRef('pk'),
            is_cancelled=False
        ).values('sales_invoice').annotate(
            total=Sum('amount')
        ).values('total')

        refunds_subquery = CustomerRefundVoucher.objects.filter(
            sales_invoice=OuterRef('pk'),
            is_cancelled=False
        ).values('sales_invoice').annotate(
            total=Sum('amount')
        ).values('total')

        if not hasattr(self, 'request') or not self.request or not hasattr(self.request, 'user') or not self.request.user.is_authenticated:
            return SalesInvoice.objects.none()

        user = self.request.user

        qs = SalesInvoice.objects.select_related(
            'customer', 'vehicle', 'created_by'
        ).prefetch_related(
            'tire_items__tire__brand',
            'tire_items__tire__size',
            'service_items__service'
        ).annotate(
            returned_amount_annotated=Coalesce(
                Subquery(returned_subquery, output_field=models.DecimalField(max_digits=14, decimal_places=2)),
                Value(Decimal('0.00'), output_field=models.DecimalField(max_digits=14, decimal_places=2))
            )
        ).annotate(
            net_amount_annotated=Greatest(
                F('total_amount') - F('returned_amount_annotated'),
                Value(Decimal('0.00'), output_field=models.DecimalField(max_digits=14, decimal_places=2)),
                output_field=models.DecimalField(max_digits=14, decimal_places=2)
            )
        ).annotate(
            valid_received_annotated=Coalesce(
                Subquery(receipts_subquery, output_field=models.DecimalField(max_digits=14, decimal_places=2)),
                Value(Decimal('0.00'), output_field=models.DecimalField(max_digits=14, decimal_places=2))
            ),
            valid_refunded_annotated=Coalesce(
                Subquery(refunds_subquery, output_field=models.DecimalField(max_digits=14, decimal_places=2)),
                Value(Decimal('0.00'), output_field=models.DecimalField(max_digits=14, decimal_places=2))
            )
        ).annotate(
            excess_amount_annotated=Greatest(
                (F('valid_received_annotated') - F('valid_refunded_annotated')) - F('net_amount_annotated'),
                Value(Decimal('0.00'), output_field=models.DecimalField(max_digits=14, decimal_places=2)),
                output_field=models.DecimalField(max_digits=14, decimal_places=2)
            )
        ).annotate(
            paid_amount_annotated=Greatest(
                F('valid_received_annotated') - F('valid_refunded_annotated'),
                Value(Decimal('0.00'), output_field=models.DecimalField(max_digits=14, decimal_places=2)),
                output_field=models.DecimalField(max_digits=14, decimal_places=2)
            )
        ).annotate(
            remaining_amount_annotated=Greatest(
                F('net_amount_annotated') - F('paid_amount_annotated'),
                Value(Decimal('0.00'), output_field=models.DecimalField(max_digits=14, decimal_places=2)),
                output_field=models.DecimalField(max_digits=14, decimal_places=2)
            )
        ).order_by('-invoice_date')

        if user.is_superuser or user.role in (UserRole.MANAGER, UserRole.WAREHOUSE):
            return qs
        elif user.role == UserRole.TECHNICIAN:
            return qs.filter(created_by=user)
        return SalesInvoice.objects.none()

    permission_classes = [SalesInvoicePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SalesInvoiceFilter
    search_fields = ['invoice_number', 'customer__full_name', 'customer__phone_number', 'customer__national_code', 'vehicle__license_plate']
    ordering_fields = ['invoice_date', 'total_amount', 'invoice_number']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action in ['create']:
            return SalesInvoiceCreateSerializer
        return SalesInvoiceSerializer

    @extend_schema(responses={201: SalesInvoiceSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        instance = self.get_queryset().get(pk=instance.pk)
        read_serializer = SalesInvoiceSerializer(instance, context={'request': request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: SalesInvoiceSerializer})
    @action(detail=True, methods=['post'], url_path='confirm', permission_classes=[SalesInvoicePermission])
    def confirm(self, request, pk=None):
        invoice = self.get_object()
        confirmed_invoice = confirm_sales_invoice_service(invoice, user=request.user)
        confirmed_invoice = self.get_queryset().get(pk=confirmed_invoice.pk)
        data = SalesInvoiceSerializer(confirmed_invoice, context={'request': request}).data
        response_payload = {
            'message': f'فاکتور شماره {confirmed_invoice.invoice_number} با موفقیت تایید و اقلام از انبار کسر شد.',
            'invoice': data,
            **data
        }
        return Response(response_payload, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PUT', detail='ویرایش مستقیم فاکتور فروش مجاز نیست.')

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PATCH', detail='ویرایش مستقیم فاکتور فروش مجاز نیست.')

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed('DELETE', detail='حذف فاکتور مجاز نیست. لطفاً از عملیات لغو استفاده کنید.')

    @extend_schema(request=None, responses={200: SalesInvoiceSerializer})
    @action(detail=True, methods=['post'], url_path='cancel', permission_classes=[IsManager])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        cancelled_invoice = cancel_sales_invoice_service(invoice, user=request.user)
        cancelled_invoice = self.get_queryset().get(pk=cancelled_invoice.pk)
        serializer = SalesInvoiceSerializer(cancelled_invoice, context={'request': request})
        return Response({
            'message': f'فاکتور شماره {cancelled_invoice.invoice_number} با موفقیت لغو شد و موجودی به انبار بازگشت.',
            'invoice': serializer.data
        }, status=status.HTTP_200_OK)

class PurchaseInvoiceViewSet(ImmutableDocumentViewSetMixin, viewsets.ModelViewSet):
    immutable_document_name = 'فاکتور خرید'
    queryset = PurchaseInvoice.objects.select_related(
        'supplier', 'created_by'
    ).prefetch_related(
        'tire_items__tire__brand',
        'tire_items__tire__size'
    ).all().order_by('-invoice_date')

    permission_classes = [IsWarehouse]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PurchaseInvoiceFilter
    search_fields = ['invoice_number', 'supplier__supplier_name', 'supplier__phone_number']
    ordering_fields = ['invoice_date', 'total_amount', 'invoice_number']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action in ['create']:
            return PurchaseInvoiceCreateSerializer
        return PurchaseInvoiceSerializer

    @extend_schema(responses={201: PurchaseInvoiceSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        instance = self.get_queryset().get(pk=instance.pk)
        read_serializer = PurchaseInvoiceSerializer(instance, context={'request': request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: PurchaseInvoiceSerializer})
    @action(detail=True, methods=['post'], url_path='cancel', permission_classes=[IsManager])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        cancelled_invoice = cancel_purchase_invoice_service(invoice, user=request.user)
        cancelled_invoice = self.get_queryset().get(pk=cancelled_invoice.pk)
        serializer = PurchaseInvoiceSerializer(cancelled_invoice, context={'request': request})
        return Response({
            'message': f'فاکتور خرید شماره {cancelled_invoice.invoice_number} با موفقیت لغو شد و اقلام از موجودی کسر گردید.',
            'invoice': serializer.data
        }, status=status.HTTP_200_OK)

class SalesReturnViewSet(ImmutableDocumentViewSetMixin, viewsets.ModelViewSet):
    immutable_document_name = 'سند مرجوعی'
    queryset = SalesReturn.objects.select_related(
        'sales_invoice__customer', 'created_by'
    ).prefetch_related(
        'items__tire__brand',
        'items__tire__size'
    ).all().order_by('-return_date', '-sales_return_id')
    permission_classes = [IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['sales_invoice']
    search_fields = ['sales_invoice__customer__full_name', 'reason']
    ordering_fields = ['return_date', 'total_refund_amount']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action in ['create']:
            return SalesReturnCreateSerializer
        return SalesReturnSerializer

    @extend_schema(responses={201: SalesReturnSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        instance = self.get_queryset().get(pk=instance.pk)
        read_serializer = SalesReturnSerializer(instance, context={'request': request})
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


