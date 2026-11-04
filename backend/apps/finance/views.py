from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import ReceiptVoucher, PaymentVoucher, CustomerRefundVoucher
from .serializers import (
    ReceiptVoucherSerializer,
    PaymentVoucherSerializer,
    CustomerRefundVoucherSerializer,
    CancelVoucherSerializer
)
from .services import (
    cancel_receipt_voucher_service,
    cancel_payment_voucher_service,
    cancel_customer_refund_voucher_service
)
from apps.accounts.permissions import IsManager
from utils.mixins import ImmutableDocumentViewSetMixin


class ReceiptVoucherViewSet(ImmutableDocumentViewSetMixin, viewsets.ModelViewSet):
    immutable_document_name = 'سند دریافت وجه'
    queryset = ReceiptVoucher.objects.select_related(
        'sales_invoice__customer', 'created_by', 'cancelled_by'
    ).all().order_by('-receipt_date')
    serializer_class = ReceiptVoucherSerializer
    permission_classes = [IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['sales_invoice', 'is_cancelled']
    search_fields = ['sales_invoice__customer__full_name', 'reference_number', 'notes', 'cancellation_reason']
    http_method_names = ['get', 'post', 'head', 'options']

    @action(detail=True, methods=['post'], url_path='cancel', permission_classes=[IsManager])
    def cancel(self, request, pk=None):
        """ابطال سند دریافت وجه با ذکر دلیل الزامی"""
        voucher = self.get_object()
        serializer = CancelVoucherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cancelled_voucher = cancel_receipt_voucher_service(
            voucher=voucher,
            reason=serializer.validated_data['reason'],
            user=request.user
        )
        return Response(ReceiptVoucherSerializer(cancelled_voucher).data, status=status.HTTP_200_OK)


class PaymentVoucherViewSet(ImmutableDocumentViewSetMixin, viewsets.ModelViewSet):
    immutable_document_name = 'سند پرداخت وجه'
    queryset = PaymentVoucher.objects.select_related(
        'purchase_invoice__supplier', 'created_by', 'cancelled_by'
    ).all().order_by('-payment_date')
    serializer_class = PaymentVoucherSerializer
    permission_classes = [IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['purchase_invoice', 'is_cancelled']
    search_fields = ['purchase_invoice__supplier__supplier_name', 'reference_number', 'notes', 'cancellation_reason']
    http_method_names = ['get', 'post', 'head', 'options']

    @action(detail=True, methods=['post'], url_path='cancel', permission_classes=[IsManager])
    def cancel(self, request, pk=None):
        """ابطال سند پرداخت وجه با ذکر دلیل الزامی"""
        voucher = self.get_object()
        serializer = CancelVoucherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cancelled_voucher = cancel_payment_voucher_service(
            voucher=voucher,
            reason=serializer.validated_data['reason'],
            user=request.user
        )
        return Response(PaymentVoucherSerializer(cancelled_voucher).data, status=status.HTTP_200_OK)


class CustomerRefundVoucherViewSet(ImmutableDocumentViewSetMixin, viewsets.ModelViewSet):
    immutable_document_name = 'سند استرداد وجه'
    queryset = CustomerRefundVoucher.objects.select_related(
        'sales_invoice__customer', 'sales_return', 'created_by', 'cancelled_by'
    ).all().order_by('-refund_date')
    serializer_class = CustomerRefundVoucherSerializer
    permission_classes = [IsManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['sales_invoice', 'sales_return', 'is_cancelled']
    search_fields = ['sales_invoice__customer__full_name', 'reference_number', 'notes', 'cancellation_reason']
    http_method_names = ['get', 'post', 'head', 'options']

    @action(detail=True, methods=['post'], url_path='cancel', permission_classes=[IsManager])
    def cancel(self, request, pk=None):
        """ابطال سند استرداد وجه به مشتری با ذکر دلیل الزامی"""
        voucher = self.get_object()
        serializer = CancelVoucherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cancelled_voucher = cancel_customer_refund_voucher_service(
            voucher=voucher,
            reason=serializer.validated_data['reason'],
            user=request.user
        )
        return Response(CustomerRefundVoucherSerializer(cancelled_voucher).data, status=status.HTTP_200_OK)
