from __future__ import annotations
from typing import Any
from decimal import Decimal
from django.db import models
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import ReceiptVoucher, PaymentVoucher, CustomerRefundVoucher
from .services import (
    DRAFT_RECEIPT_ERROR,
    create_receipt_voucher_service,
    create_payment_voucher_service,
    create_customer_refund_voucher_service
)
from apps.invoices.models import InvoiceStatus
from utils.jalali import format_jalali_date


class ReceiptVoucherSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source='sales_invoice.customer.full_name')
    jalali_date = serializers.SerializerMethodField()
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    cancelled_by_name = serializers.ReadOnlyField(source='cancelled_by.full_name')
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
            'customer_name', 'payment_method', 'reference_number', 'notes', 'created_by', 'created_by_name',
            'is_cancelled', 'cancelled_at', 'cancelled_by', 'cancelled_by_name',
            'cancellation_reason'
        ]
        read_only_fields = [
            'receipt_id', 'created_by', 'created_by_name', 'is_cancelled',
            'cancelled_at', 'cancelled_by', 'cancelled_by_name', 'cancellation_reason'
        ]

    @extend_schema_field(serializers.CharField)
    def get_jalali_date(self, obj: ReceiptVoucher) -> str:
        return format_jalali_date(obj.receipt_date)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        sales_invoice = attrs.get('sales_invoice') or (self.instance.sales_invoice if self.instance else None)
        amount = attrs.get('amount') if 'amount' in attrs else (self.instance.amount if self.instance else None)

        if sales_invoice:
            if sales_invoice.status == InvoiceStatus.CANCELLED:
                raise serializers.ValidationError({
                    "sales_invoice": "امکان ثبت سند دریافت وجه برای فاکتور لغو شده وجود ندارد."
                })
            if sales_invoice.status == InvoiceStatus.DRAFT:
                raise serializers.ValidationError({"sales_invoice": DRAFT_RECEIPT_ERROR})

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


class PaymentVoucherSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source='purchase_invoice.supplier.supplier_name')
    jalali_date = serializers.SerializerMethodField()
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    cancelled_by_name = serializers.ReadOnlyField(source='cancelled_by.full_name')
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
            'supplier_name', 'payment_method', 'reference_number', 'notes', 'created_by', 'created_by_name',
            'is_cancelled', 'cancelled_at', 'cancelled_by', 'cancelled_by_name',
            'cancellation_reason'
        ]
        read_only_fields = [
            'payment_id', 'created_by', 'created_by_name', 'is_cancelled',
            'cancelled_at', 'cancelled_by', 'cancelled_by_name', 'cancellation_reason'
        ]

    @extend_schema_field(serializers.CharField)
    def get_jalali_date(self, obj: PaymentVoucher) -> str:
        return format_jalali_date(obj.payment_date)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        purchase_invoice = attrs.get('purchase_invoice') or (self.instance.purchase_invoice if self.instance else None)
        amount = attrs.get('amount') if 'amount' in attrs else (self.instance.amount if self.instance else None)

        if purchase_invoice:
            if purchase_invoice.status == InvoiceStatus.CANCELLED:
                raise serializers.ValidationError({
                    "purchase_invoice": "امکان ثبت سند پرداخت وجه برای فاکتور خرید لغو شده وجود ندارد."
                })

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


class CustomerRefundVoucherSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source='sales_invoice.customer.full_name')
    jalali_date = serializers.SerializerMethodField()
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    cancelled_by_name = serializers.ReadOnlyField(source='cancelled_by.full_name')
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
            'sales_return', 'customer_name', 'payment_method', 'reference_number', 'notes',
            'created_by', 'created_by_name',
            'is_cancelled', 'cancelled_at', 'cancelled_by', 'cancelled_by_name',
            'cancellation_reason'
        ]
        read_only_fields = [
            'refund_id', 'created_by', 'created_by_name', 'is_cancelled',
            'cancelled_at', 'cancelled_by', 'cancelled_by_name', 'cancellation_reason'
        ]

    @extend_schema_field(serializers.CharField)
    def get_jalali_date(self, obj: CustomerRefundVoucher) -> str:
        return format_jalali_date(obj.refund_date)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        sales_invoice = attrs.get('sales_invoice') or (self.instance.sales_invoice if self.instance else None)
        amount = attrs.get('amount') if 'amount' in attrs else (self.instance.amount if self.instance else None)
        sales_return = attrs.get('sales_return')

        if sales_invoice:
            if sales_invoice.status == InvoiceStatus.CANCELLED:
                raise serializers.ValidationError({
                    "sales_invoice": "امکان ثبت استرداد وجه برای فاکتور فروش لغو شده وجود ندارد."
                })

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
