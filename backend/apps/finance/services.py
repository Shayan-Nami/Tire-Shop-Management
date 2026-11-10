from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.invoices.models import SalesInvoice, PurchaseInvoice, SalesReturn

from decimal import Decimal, InvalidOperation
from django.db import transaction, models
from django.utils import timezone
from utils.domain import DomainValidationError as ValidationError, validate_money
from .models import ReceiptVoucher, PaymentVoucher, CustomerRefundVoucher
from apps.invoices.models import InvoiceStatus, SalesInvoice, PurchaseInvoice, PaymentStatus


DRAFT_RECEIPT_ERROR = "امکان ثبت سند دریافت وجه برای فاکتور پیش‌نویس وجود ندارد. ابتدا فاکتور را تایید کنید."


@transaction.atomic
def sync_sales_invoice_payment_status(invoice_or_id: SalesInvoice | int) -> str:
    invoice_id = invoice_or_id.pk if hasattr(invoice_or_id, 'pk') else int(invoice_or_id)
    invoice = SalesInvoice.objects.select_for_update().get(pk=invoice_id)

    valid_received = invoice.receipts.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    valid_refunded = invoice.refunds.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    effective_paid = max(Decimal('0.00'), valid_received - valid_refunded)
    net_amount = invoice.net_amount

    if net_amount == Decimal('0.00'):
        new_status = PaymentStatus.PAID
    elif effective_paid == Decimal('0.00'):
        new_status = PaymentStatus.UNPAID
    elif effective_paid < net_amount:
        new_status = PaymentStatus.PARTIAL
    else:
        new_status = PaymentStatus.PAID

    if invoice.payment_status != new_status:
        invoice.payment_status = new_status
        invoice.save(update_fields=['payment_status', 'updated_at'])

    return new_status


@transaction.atomic
def sync_purchase_invoice_payment_status(invoice_or_id: PurchaseInvoice | int) -> str:
    invoice_id = invoice_or_id.pk if hasattr(invoice_or_id, 'pk') else int(invoice_or_id)
    invoice = PurchaseInvoice.objects.select_for_update().get(pk=invoice_id)

    valid_paid = invoice.payments.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    if invoice.total_amount == Decimal('0.00') or valid_paid >= invoice.total_amount:
        new_status = PaymentStatus.PAID
    elif valid_paid > Decimal('0.00'):
        new_status = PaymentStatus.PARTIAL
    else:
        new_status = PaymentStatus.UNPAID

    if invoice.payment_status != new_status:
        invoice.payment_status = new_status
        invoice.save(update_fields=['payment_status', 'updated_at'])

    return new_status


def create_receipt_voucher_service(sales_invoice: SalesInvoice, amount: Decimal, payment_method: str = 'کارتخوان / نقدی', notes: str = '', receipt_date: datetime | None = None, user: User | None = None, reference_number: str = '') -> ReceiptVoucher:
    if sales_invoice.status == InvoiceStatus.CANCELLED:
        raise ValidationError("امکان ثبت سند دریافت وجه برای فاکتور لغو شده وجود ندارد.")
    if sales_invoice.status != InvoiceStatus.CONFIRMED:
        raise ValidationError(DRAFT_RECEIPT_ERROR)

    if amount is None:
        raise ValidationError("مبلغ سند دریافت الزامی است.")
    try:
        amount_dec = validate_money(amount)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("مبلغ سند دریافت نامعتبر است.")

    if amount_dec <= Decimal('0.00'):
        raise ValidationError("مبلغ سند دریافت باید بزرگتر از صفر باشد.")

    invoice_id = sales_invoice.pk if hasattr(sales_invoice, 'pk') else int(sales_invoice)

    with transaction.atomic():
        invoice = SalesInvoice.objects.select_for_update().get(pk=invoice_id)
        if invoice.status == InvoiceStatus.CANCELLED:
            raise ValidationError("امکان ثبت سند دریافت وجه برای فاکتور لغو شده وجود ندارد.")
        if invoice.status != InvoiceStatus.CONFIRMED:
            raise ValidationError(DRAFT_RECEIPT_ERROR)

        valid_received = invoice.receipts.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        valid_refunded = invoice.refunds.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        effective_paid = max(Decimal('0.00'), valid_received - valid_refunded)
        remaining = invoice.net_amount - effective_paid

        if remaining <= Decimal('0.00'):
            raise ValidationError("مجموع مبالغ دریافتی به سقف مبلغ کل فاکتور رسیده است و امکان ثبت دریافت جدید نیست.")

        if amount_dec > remaining:
            raise ValidationError(f"مبلغ سند ({amount_dec:,.0f}) نمی‌تواند از مانده بدهی فاکتور ({remaining:,.0f}) بیشتر باشد.")

        kwargs = {
            'sales_invoice': invoice,
            'amount': amount_dec,
            'payment_method': payment_method or 'کارتخوان / نقدی',
            'reference_number': reference_number or '',
            'notes': notes or '',
            'created_by': user,
        }
        if receipt_date:
            kwargs['receipt_date'] = receipt_date

        voucher = ReceiptVoucher.objects.create(**kwargs)
        sync_sales_invoice_payment_status(invoice)
        return voucher


def cancel_receipt_voucher_service(voucher: ReceiptVoucher, reason: str, user: User | None=None) -> ReceiptVoucher:
    if not reason or not str(reason).strip():
        raise ValidationError("ثبت علت ابطال سند الزامی است.")

    with transaction.atomic():
        parent_id = ReceiptVoucher.objects.values_list('sales_invoice_id', flat=True).get(pk=voucher.pk)
        invoice = SalesInvoice.objects.select_for_update().get(pk=parent_id)
        v = ReceiptVoucher.objects.select_for_update().get(pk=voucher.pk)
        if v.is_cancelled:
            raise ValidationError("این سند دریافت وجه قبلاً ابطال شده است.")


        valid_receipts_after = invoice.receipts.filter(is_cancelled=False).exclude(pk=v.pk).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        valid_refunds = invoice.refunds.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        if valid_receipts_after < valid_refunds:
            raise ValidationError(
                f"امکان ابطال این سند دریافت وجه وجود ندارد؛ زیرا مجموع دریافتی‌های فاکتور ({valid_receipts_after:,.0f}) از مجموع استردادهای ثبت‌شده ({valid_refunds:,.0f}) کمتر خواهد شد. ابتدا اسناد استرداد وجه مربوطه را ابطال نمایید."
            )

        v.is_cancelled = True
        v.cancelled_at = timezone.now()
        v.cancelled_by = user
        v.cancellation_reason = str(reason).strip()
        v.save(update_fields=['is_cancelled', 'cancelled_at', 'cancelled_by', 'cancellation_reason'])

        sync_sales_invoice_payment_status(invoice)
        return v


def create_payment_voucher_service(purchase_invoice: PurchaseInvoice, amount: Decimal, payment_method: str = 'حواله / چک', notes: str = '', payment_date: datetime | None = None, user: User | None = None, reference_number: str = '') -> PaymentVoucher:
    if purchase_invoice.status == InvoiceStatus.CANCELLED:
        raise ValidationError("امکان ثبت سند پرداخت وجه برای فاکتور خرید لغو شده وجود ندارد.")

    if amount is None:
        raise ValidationError("مبلغ سند پرداخت الزامی است.")
    try:
        amount_dec = validate_money(amount)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("مبلغ سند پرداخت نامعتبر است.")

    if amount_dec <= Decimal('0.00'):
        raise ValidationError("مبلغ سند پرداخت باید بزرگتر از صفر باشد.")

    invoice_id = purchase_invoice.pk if hasattr(purchase_invoice, 'pk') else int(purchase_invoice)

    with transaction.atomic():
        invoice = PurchaseInvoice.objects.select_for_update().get(pk=invoice_id)
        if invoice.status == InvoiceStatus.CANCELLED:
            raise ValidationError("امکان ثبت سند پرداخت وجه برای فاکتور خرید لغو شده وجود ندارد.")

        valid_paid = invoice.payments.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        remaining = invoice.total_amount - valid_paid

        if remaining <= Decimal('0.00'):
            raise ValidationError("مجموع مبالغ پرداختی به سقف مبلغ کل فاکتور خرید رسیده است و امکان ثبت پرداخت جدید نیست.")

        if amount_dec > remaining:
            raise ValidationError(f"مبلغ سند پرداختی ({amount_dec:,.0f}) نمی‌تواند از مانده بدهی فاکتور خرید ({remaining:,.0f}) بیشتر باشد.")

        kwargs = {
            'purchase_invoice': invoice,
            'amount': amount_dec,
            'payment_method': payment_method or 'حواله / چک',
            'reference_number': reference_number or '',
            'notes': notes or '',
            'created_by': user,
        }
        if payment_date:
            kwargs['payment_date'] = payment_date

        voucher = PaymentVoucher.objects.create(**kwargs)
        sync_purchase_invoice_payment_status(invoice)
        return voucher


def cancel_payment_voucher_service(voucher: PaymentVoucher, reason: str, user: User | None=None) -> PaymentVoucher:
    if not reason or not str(reason).strip():
        raise ValidationError("ثبت علت ابطال سند الزامی است.")

    with transaction.atomic():
        parent_id = PaymentVoucher.objects.values_list('purchase_invoice_id', flat=True).get(pk=voucher.pk)
        invoice = PurchaseInvoice.objects.select_for_update().get(pk=parent_id)
        v = PaymentVoucher.objects.select_for_update().get(pk=voucher.pk)
        if v.is_cancelled:
            raise ValidationError("این سند پرداخت وجه قبلاً ابطال شده است.")


        v.is_cancelled = True
        v.cancelled_at = timezone.now()
        v.cancelled_by = user
        v.cancellation_reason = str(reason).strip()
        v.save(update_fields=['is_cancelled', 'cancelled_at', 'cancelled_by', 'cancellation_reason'])

        sync_purchase_invoice_payment_status(invoice)
        return v


def create_customer_refund_voucher_service(sales_invoice: SalesInvoice, amount: Decimal, sales_return: SalesReturn | None = None, payment_method: str = 'کارتخوان / نقدی', notes: str = '', refund_date: datetime | None = None, user: User | None = None, reference_number: str = '') -> CustomerRefundVoucher:
    if sales_invoice.status == InvoiceStatus.CANCELLED:
        raise ValidationError("امکان ثبت استرداد وجه برای فاکتور فروش لغو شده وجود ندارد.")

    if amount is None:
        raise ValidationError("مبلغ سند استرداد وجه الزامی است.")
    try:
        amount_dec = validate_money(amount)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("مبلغ سند استرداد وجه نامعتبر است.")

    if amount_dec <= Decimal('0.00'):
        raise ValidationError("مبلغ سند استرداد وجه باید بزرگتر از صفر باشد.")

    invoice_id = sales_invoice.pk if hasattr(sales_invoice, 'pk') else int(sales_invoice)

    with transaction.atomic():
        invoice = SalesInvoice.objects.select_for_update().get(pk=invoice_id)
        if invoice.status == InvoiceStatus.CANCELLED:
            raise ValidationError("امکان ثبت استرداد وجه برای فاکتور فروش لغو شده وجود ندارد.")

        if sales_return and sales_return.sales_invoice_id != invoice.pk:
            raise ValidationError("سند مرجوعی انتخاب‌شده متعلق به این فاکتور فروش نیست.")

        valid_received = invoice.receipts.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        valid_refunded = invoice.refunds.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        net_received = valid_received - valid_refunded
        current_excess = net_received - invoice.net_amount

        if current_excess <= Decimal('0.00'):
            raise ValidationError("این فاکتور مازاد پرداختی قابل استرداد ندارد.")

        if amount_dec > current_excess:
            raise ValidationError(f"مبلغ استرداد ({amount_dec:,.0f}) نمی‌تواند از مبلغ مازاد پرداختی ({current_excess:,.0f}) بیشتر باشد.")

        kwargs = {
            'sales_invoice': invoice,
            'sales_return': sales_return,
            'amount': amount_dec,
            'payment_method': payment_method or 'کارتخوان / نقدی',
            'reference_number': reference_number or '',
            'notes': notes or '',
            'created_by': user,
        }
        if refund_date:
            kwargs['refund_date'] = refund_date

        voucher = CustomerRefundVoucher.objects.create(**kwargs)
        sync_sales_invoice_payment_status(invoice)
        return voucher


def cancel_customer_refund_voucher_service(voucher: CustomerRefundVoucher, reason: str, user: User | None=None) -> CustomerRefundVoucher:
    if not reason or not str(reason).strip():
        raise ValidationError("ثبت علت ابطال سند الزامی است.")

    with transaction.atomic():
        parent_id = CustomerRefundVoucher.objects.values_list('sales_invoice_id', flat=True).get(pk=voucher.pk)
        invoice = SalesInvoice.objects.select_for_update().get(pk=parent_id)
        v = CustomerRefundVoucher.objects.select_for_update().get(pk=voucher.pk)
        if v.is_cancelled:
            raise ValidationError("این سند استرداد وجه قبلاً ابطال شده است.")


        v.is_cancelled = True
        v.cancelled_at = timezone.now()
        v.cancelled_by = user
        v.cancellation_reason = str(reason).strip()
        v.save(update_fields=['is_cancelled', 'cancelled_at', 'cancelled_by', 'cancellation_reason'])

        sync_sales_invoice_payment_status(invoice)
        return v
