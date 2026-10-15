from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from apps.invoices.models import SalesInvoice, PurchaseInvoice


class ReceiptVoucher(models.Model):
    receipt_id = models.AutoField(primary_key=True)
    receipt_date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ دریافت وجه')
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), message='مبلغ سند باید بیشتر از صفر باشد.')],
        verbose_name='مبلغ دریافتی'
    )
    sales_invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.PROTECT,
        related_name='receipts',
        verbose_name='فاکتور فروش مربوطه'
    )
    payment_method = models.CharField(max_length=50, default='کارتخوان / نقدی', blank=True, verbose_name='روش تسویه')
    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name='شماره پیگیری / مرجع')
    notes = models.TextField(blank=True, verbose_name='توضیحات سند')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_receipt_vouchers',
        verbose_name='کاربر صادرکننده'
    )

    # فیلدهای ابطال سند
    is_cancelled = models.BooleanField(default=False, db_index=True, verbose_name='ابطال شده')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ و زمان ابطال')
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_receipt_vouchers',
        verbose_name='کاربر ابطال‌کننده'
    )
    cancellation_reason = models.TextField(blank=True, verbose_name='علت ابطال')

    class Meta:
        db_table = 'Receipt_voucher'
        verbose_name = 'سند دریافت وجه'
        verbose_name_plural = 'اسناد دریافت وجه'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='receipt_amount_positive'
            )
        ]

    def __str__(self):
        status = " (ابطال‌شده)" if self.is_cancelled else ""
        return f"سند دریافت #{self.receipt_id} - مبلغ: {self.amount:,.0f} (فاکتور #{self.sales_invoice_id}){status}"


class PaymentVoucher(models.Model):
    payment_id = models.AutoField(primary_key=True)
    payment_date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ پرداخت وجه')
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), message='مبلغ سند باید بیشتر از صفر باشد.')],
        verbose_name='مبلغ پرداختی'
    )
    purchase_invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='فاکتور خرید مربوطه'
    )
    payment_method = models.CharField(max_length=50, default='حواله / چک', blank=True, verbose_name='روش پرداخت')
    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name='شماره پیگیری / مرجع')
    notes = models.TextField(blank=True, verbose_name='توضیحات سند')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_payment_vouchers',
        verbose_name='کاربر صادرکننده'
    )

    # فیلدهای ابطال سند
    is_cancelled = models.BooleanField(default=False, db_index=True, verbose_name='ابطال شده')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ و زمان ابطال')
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_payment_vouchers',
        verbose_name='کاربر ابطال‌کننده'
    )
    cancellation_reason = models.TextField(blank=True, verbose_name='علت ابطال')

    class Meta:
        db_table = 'Payment_voucher'
        verbose_name = 'سند پرداخت وجه'
        verbose_name_plural = 'اسناد پرداخت وجه'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='payment_amount_positive'
            )
        ]

    def __str__(self):
        status = " (ابطال‌شده)" if self.is_cancelled else ""
        return f"سند پرداخت #{self.payment_id} - مبلغ: {self.amount:,.0f} (فاکتور خرید #{self.purchase_invoice_id}){status}"


class CustomerRefundVoucher(models.Model):
    refund_id = models.AutoField(primary_key=True)
    refund_date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ استرداد وجه')
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), message='مبلغ سند باید بیشتر از صفر باشد.')],
        verbose_name='مبلغ استردادی'
    )
    sales_invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.PROTECT,
        related_name='refunds',
        verbose_name='فاکتور فروش مربوطه'
    )
    sales_return = models.ForeignKey(
        'invoices.SalesReturn',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_vouchers',
        verbose_name='سند مرجوعی عطف'
    )
    payment_method = models.CharField(max_length=50, default='کارتخوان / نقدی', blank=True, verbose_name='روش استرداد')
    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name='شماره پیگیری / مرجع')
    notes = models.TextField(blank=True, verbose_name='توضیحات سند')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_customer_refunds',
        verbose_name='کاربر صادرکننده'
    )

    # فیلدهای ابطال سند
    is_cancelled = models.BooleanField(default=False, db_index=True, verbose_name='ابطال شده')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ و زمان ابطال')
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_customer_refunds',
        verbose_name='کاربر ابطال‌کننده'
    )
    cancellation_reason = models.TextField(blank=True, verbose_name='علت ابطال')

    class Meta:
        db_table = 'Customer_refund_voucher'
        verbose_name = 'سند استرداد وجه به مشتری'
        verbose_name_plural = 'اسناد استرداد وجه به مشتری'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='customer_refund_amount_positive'
            )
        ]

    def __str__(self):
        status = " (ابطال‌شده)" if self.is_cancelled else ""
        return f"سند استرداد #{self.refund_id} - مبلغ: {self.amount:,.0f} (فاکتور فروش #{self.sales_invoice_id}){status}"
