from __future__ import annotations
from typing import Any
from decimal import Decimal
from django.db import models
from django.utils import timezone
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import ReceiptVoucher, PaymentVoucher, CustomerRefundVoucher
from .services import (
    create_receipt_voucher_service,
    create_payment_voucher_service,
    create_customer_refund_voucher_service
)
from apps.invoices.models import InvoiceStatus
from utils.jalali import format_jalali_date


PAYMENT_METHOD_DISPLAY_MAP = {
    'POS': 'کارتخوان (POS)',
    'CASH': 'نقدی',
    'CARD_TO_CARD': 'کارت به کارت',
    'CHEQUE': 'چک',
    'BANK_TRANSFER': 'حواله بانکی',
}


class BaseVoucherSerializer(serializers.ModelSerializer):
    date_field_name: str = ''
    date_label: str = ''
    invoice_field_name: str = ''
    doc_label: str = ''

    jalali_date = serializers.SerializerMethodField()
    payment_method_display = serializers.SerializerMethodField()
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    cancelled_by_name = serializers.ReadOnlyField(source='cancelled_by.full_name')

    @extend_schema_field(serializers.CharField)
    def get_jalali_date(self, obj: Any) -> str:
        return format_jalali_date(getattr(obj, self.date_field_name, None))

    @extend_schema_field(serializers.CharField)
    def get_payment_method_display(self, obj: Any) -> str:
        raw = (getattr(obj, 'payment_method', '') or '').strip()
        return PAYMENT_METHOD_DISPLAY_MAP.get(raw, raw)

    def _validate_invoice_status_and_date(self, attrs: dict[str, Any], invoice: Any) -> None:
        if invoice is not None:
            if invoice.status == InvoiceStatus.CANCELLED:
                raise serializers.ValidationError({
                    self.invoice_field_name: f"امکان ثبت {self.doc_label} برای فاکتور لغو شده وجود ندارد."
                })
            if invoice.status == InvoiceStatus.DRAFT:
                raise serializers.ValidationError({
                    self.invoice_field_name: f"امکان ثبت {self.doc_label} برای فاکتور پیش‌نویس وجود ندارد. ابتدا فاکتور را تایید نمایید."
                })
            if invoice.status != InvoiceStatus.CONFIRMED:
                raise serializers.ValidationError({
                    self.invoice_field_name: f"امکان ثبت {self.doc_label} فقط برای فاکتورهای تایید شده (CONFIRMED) وجود دارد."
                })

        voucher_date = attrs.get(self.date_field_name)
        if voucher_date is not None:
            if voucher_date > timezone.now():
                raise serializers.ValidationError({
                    self.date_field_name: f"تاریخ {self.date_label} نمی‌تواند در آینده باشد."
                })
            if invoice is not None and voucher_date < invoice.invoice_date:
                raise serializers.ValidationError({
                    self.date_field_name: f"تاریخ {self.date_label} نمی‌تواند پیش از تاریخ صدور فاکتور باشد."
                })


class ReceiptVoucherSerializer(BaseVoucherSerializer):
    date_field_name = 'receipt_date'
    date_label = 'دریافت وجه'
    invoice_field_name = 'sales_invoice'
    doc_label = 'سند دریافت وجه'

    customer_name = serializers.ReadOnlyField(source='sales_invoice.customer.full_name')
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.01'),
        error_messages={'min_value': 'مبلغ سند دریافت باید بزرگتر از صفر باشد.'}
    )

    class Meta:
        model = ReceiptVoucher
        fields = [
            'receipt_id', 'receipt_date', 'jalali_date', 'amount', 'sales_invoice',
            'customer_name', 'payment_method', 'payment_method_display', 'reference_number',
            'notes', 'created_by', 'created_by_name',
            'is_cancelled', 'cancelled_at', 'cancelled_by', 'cancelled_by_name',
            'cancellation_reason'
        ]
        read_only_fields = [
            'receipt_id', 'created_by', 'created_by_name', 'is_cancelled',
            'cancelled_at', 'cancelled_by', 'cancelled_by_name', 'cancellation_reason'
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        sales_invoice = attrs.get('sales_invoice') or (self.instance.sales_invoice if self.instance else None)
        amount = attrs.get('amount') if 'amount' in attrs else (self.instance.amount if self.instance else None)

        self._validate_invoice_status_and_date(attrs, sales_invoice)

        if sales_invoice:
            existing_receipts = sales_invoice.receipts.filter(is_cancelled=False)
            if self.instance and self.instance.pk:
                existing_receipts = existing_receipts.exclude(pk=self.instance.pk)
            total_paid = existing_receipts.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            valid_refunds = sales_invoice.refunds.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            effective_paid = max(Decimal('0.00'), total_paid - valid_refunds)
            remaining = sales_invoice.net_amount - effective_paid

            if remaining <= 0:
                raise serializers.ValidationError({
                    "amount": "مجموع مبالغ دریافتی به سقف مبلغ کل فاکتور رسیده است و امکان ثبت دریافت جدید نیست."
                })
            if amount is not None and amount > remaining:
                raise serializers.ValidationError({
                    "amount": f"مبلغ سند ({amount:,.0f}) نمی‌تواند از مانده بدهی فاکتور ({remaining:,.0f}) بیشتر باشد."
                })

        return attrs

    def create(self, validated_data: dict[str, Any]) -> ReceiptVoucher:
        user = self.context['request'].user if 'request' in self.context else None
        return create_receipt_voucher_service(
            sales_invoice=validated_data['sales_invoice'],
            amount=validated_data['amount'],
            payment_method=validated_data.get('payment_method', 'کارتخوان / نقدی'),
            reference_number=validated_data.get('reference_number', ''),
            notes=validated_data.get('notes', ''),
            receipt_date=validated_data.get('receipt_date'),
            user=user
        )


class PaymentVoucherSerializer(BaseVoucherSerializer):
    date_field_name = 'payment_date'
    date_label = 'پرداخت وجه'
    invoice_field_name = 'purchase_invoice'
    doc_label = 'سند پرداخت وجه'

    supplier_name = serializers.ReadOnlyField(source='purchase_invoice.supplier.supplier_name')
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.01'),
        error_messages={'min_value': 'مبلغ سند پرداخت باید بزرگتر از صفر باشد.'}
    )

    class Meta:
        model = PaymentVoucher
        fields = [
            'payment_id', 'payment_date', 'jalali_date', 'amount', 'purchase_invoice',
            'supplier_name', 'payment_method', 'payment_method_display', 'reference_number',
            'notes', 'created_by', 'created_by_name',
            'is_cancelled', 'cancelled_at', 'cancelled_by', 'cancelled_by_name',
            'cancellation_reason'
        ]
        read_only_fields = [
            'payment_id', 'created_by', 'created_by_name', 'is_cancelled',
            'cancelled_at', 'cancelled_by', 'cancelled_by_name', 'cancellation_reason'
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        purchase_invoice = attrs.get('purchase_invoice') or (self.instance.purchase_invoice if self.instance else None)
        amount = attrs.get('amount') if 'amount' in attrs else (self.instance.amount if self.instance else None)

        self._validate_invoice_status_and_date(attrs, purchase_invoice)

        if purchase_invoice:
            existing_payments = purchase_invoice.payments.filter(is_cancelled=False)
            if self.instance and self.instance.pk:
                existing_payments = existing_payments.exclude(pk=self.instance.pk)
            total_paid = existing_payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            remaining = purchase_invoice.total_amount - total_paid

            if remaining <= 0:
                raise serializers.ValidationError({
                    "amount": "مجموع مبالغ پرداختی به سقف مبلغ کل فاکتور خرید رسیده است و امکان ثبت پرداخت جدید نیست."
                })
            if amount is not None and amount > remaining:
                raise serializers.ValidationError({
                    "amount": f"مبلغ سند پرداختی ({amount:,.0f}) نمی‌تواند از مانده بدهی فاکتور خرید ({remaining:,.0f}) بیشتر باشد."
                })

        return attrs

    def create(self, validated_data: dict[str, Any]) -> PaymentVoucher:
        user = self.context['request'].user if 'request' in self.context else None
        return create_payment_voucher_service(
            purchase_invoice=validated_data['purchase_invoice'],
            amount=validated_data['amount'],
            payment_method=validated_data.get('payment_method', 'حواله / چک'),
            reference_number=validated_data.get('reference_number', ''),
            notes=validated_data.get('notes', ''),
            payment_date=validated_data.get('payment_date'),
            user=user
        )


class CustomerRefundVoucherSerializer(BaseVoucherSerializer):
    date_field_name = 'refund_date'
    date_label = 'استرداد وجه'
    invoice_field_name = 'sales_invoice'
    doc_label = 'استرداد وجه'

    customer_name = serializers.ReadOnlyField(source='sales_invoice.customer.full_name')
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0.01'),
        error_messages={'min_value': 'مبلغ سند استرداد باید بزرگتر از صفر باشد.'}
    )

    class Meta:
        model = CustomerRefundVoucher
        fields = [
            'refund_id', 'refund_date', 'jalali_date', 'amount', 'sales_invoice',
            'sales_return', 'customer_name', 'payment_method', 'payment_method_display',
            'reference_number', 'notes', 'created_by', 'created_by_name',
            'is_cancelled', 'cancelled_at', 'cancelled_by', 'cancelled_by_name',
            'cancellation_reason'
        ]
        read_only_fields = [
            'refund_id', 'created_by', 'created_by_name', 'is_cancelled',
            'cancelled_at', 'cancelled_by', 'cancelled_by_name', 'cancellation_reason'
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        sales_invoice = attrs.get('sales_invoice') or (self.instance.sales_invoice if self.instance else None)
        amount = attrs.get('amount') if 'amount' in attrs else (self.instance.amount if self.instance else None)
        sales_return = attrs.get('sales_return')

        self._validate_invoice_status_and_date(attrs, sales_invoice)

        if sales_invoice:

            if sales_return and sales_return.sales_invoice_id != sales_invoice.pk:
                raise serializers.ValidationError({
                    "sales_return": "سند مرجوعی انتخاب‌شده متعلق به این فاکتور فروش نیست."
                })

            valid_received = sales_invoice.receipts.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            valid_refunds = sales_invoice.refunds.filter(is_cancelled=False)
            if self.instance and self.instance.pk:
                valid_refunds = valid_refunds.exclude(pk=self.instance.pk)
            total_refunded = valid_refunds.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            current_excess = (valid_received - total_refunded) - sales_invoice.net_amount

            if current_excess <= Decimal('0.00'):
                raise serializers.ValidationError({
                    "amount": "این فاکتور مازاد پرداختی قابل استرداد ندارد."
                })
            if amount is not None and amount > current_excess:
                raise serializers.ValidationError({
                    "amount": f"مبلغ استرداد ({amount:,.0f}) نمی‌تواند از مبلغ مازاد پرداختی ({current_excess:,.0f}) بیشتر باشد."
                })

        return attrs

    def create(self, validated_data: dict[str, Any]) -> CustomerRefundVoucher:
        user = self.context['request'].user if 'request' in self.context else None
        return create_customer_refund_voucher_service(
            sales_invoice=validated_data['sales_invoice'],
            amount=validated_data['amount'],
            sales_return=validated_data.get('sales_return'),
            payment_method=validated_data.get('payment_method', 'کارتخوان / نقدی'),
            reference_number=validated_data.get('reference_number', ''),
            notes=validated_data.get('notes', ''),
            refund_date=validated_data.get('refund_date'),
            user=user
        )


class CancelVoucherSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'ثبت دلیل / شرح ابطال الزامی است.',
            'blank': 'ثبت دلیل / شرح ابطال الزامی است.'
        }
    )
