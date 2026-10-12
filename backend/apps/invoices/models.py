from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.customers.models import Customer, Vehicle
from apps.catalog.models import Tire
from apps.services_app.models import Service
from apps.suppliers.models import Supplier

class InvoiceStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'پیش‌نویس'
    CONFIRMED = 'CONFIRMED', 'تایید شده / نهایی'
    CANCELLED = 'CANCELLED', 'لغو شده'

class PaymentStatus(models.TextChoices):
    UNPAID = 'UNPAID', 'پرداخت نشده (نسیه)'
    PARTIAL = 'PARTIAL', 'پرداخت ناقص (اقساطی)'
    PAID = 'PAID', 'تسویه کامل'

class InvoiceSequence(models.Model):
    doc_type = models.CharField(max_length=20, verbose_name='نوع سند')
    year = models.PositiveIntegerField(verbose_name='سال شمسی')
    last_number = models.PositiveIntegerField(default=0, verbose_name='آخرین شماره تخصیص‌یافته')

    class Meta:
        db_table = 'Invoice_Sequences'
        verbose_name = 'شمارنده اسناد و فاکتورها'
        verbose_name_plural = 'شمارنده‌های اسناد و فاکتورها'
        constraints = [
            models.UniqueConstraint(fields=['doc_type', 'year'], name='unique_doctype_year')
        ]

    def __str__(self):
        return f"{self.doc_type}-{self.year}: {self.last_number}"


class SalesInvoice(models.Model):
    sales_invoice_id = models.AutoField(primary_key=True)
    invoice_number = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name='شماره فاکتور'
    )
    invoice_date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ فاکتور')
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='sales_invoices',
        verbose_name='مشتری'
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_invoices',
        verbose_name='خودرو سرویس‌شده'
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'), message='مبلغ نهایی فاکتور نمی‌تواند منفی باشد.')],
        verbose_name='مبلغ نهایی فاکتور'
    )
    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'), message='مبلغ تخفیف نمی‌تواند منفی باشد.')],
        verbose_name='مبلغ تخفیف'
    )
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(Decimal('0.00'), message='درصد تخفیف نمی‌تواند منفی باشد.'),
            MaxValueValidator(Decimal('100.00'), message='درصد تخفیف نمی‌تواند بیش از ۱۰۰ درصد باشد.')
        ],
        verbose_name='درصد تخفیف'
    )
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.CONFIRMED,
        verbose_name='وضعیت فاکتور'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        verbose_name='وضعیت پرداخت'
    )
    notes = models.TextField(blank=True, verbose_name='توضیحات و یادداشت')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_sales_invoices',
        verbose_name='کاربر صادرکننده'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ آخرین ویرایش')

    class Meta:
        db_table = 'Sales_invoice'
        verbose_name = 'فاکتور فروش'
        verbose_name_plural = 'فاکتورهای فروش'
        indexes = [
            models.Index(fields=['invoice_date'], name='sales_inv_date_idx'),
            models.Index(fields=['status', 'payment_status'], name='sales_inv_status_idx'),
        ]

    @property
    def returned_amount(self) -> Decimal:
        """مجموع مبالغ مرجوعی فاکتور فروش (محاسباتی، بدون ذخیره در دیتابیس)"""
        if hasattr(self, 'returned_amount_annotated') and self.returned_amount_annotated is not None:
            return self.returned_amount_annotated
        total = self.returns.aggregate(total=models.Sum('total_refund_amount'))['total']
        return total or Decimal('0.00')

    @property
    def net_amount(self) -> Decimal:
        """مبلغ خالص فاکتور پس از کسر مرجوعی‌ها (محاسباتی)"""
        if hasattr(self, 'net_amount_annotated') and self.net_amount_annotated is not None:
            return self.net_amount_annotated
        return max(self.total_amount - self.returned_amount, Decimal('0.00'))

    @property
    def excess_amount(self) -> Decimal:
        """مبلغ مازاد پرداختی توسط مشتری که قابل استرداد است (محاسباتی)"""
        if hasattr(self, 'excess_amount_annotated') and self.excess_amount_annotated is not None:
            return self.excess_amount_annotated
        valid_received = self.receipts.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        valid_refunded = self.refunds.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        net_received = valid_received - valid_refunded
        return max(net_received - self.net_amount, Decimal('0.00'))

    @property
    def paid_amount(self) -> Decimal:
        """مبلغ خالص دریافتی فاکتور فروش پس از کسر استردادها (محاسباتی)"""
        if hasattr(self, 'paid_amount_annotated') and self.paid_amount_annotated is not None:
            return self.paid_amount_annotated
        valid_received = self.receipts.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        valid_refunded = self.refunds.filter(is_cancelled=False).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        return max(valid_received - valid_refunded, Decimal('0.00'))

    @property
    def remaining_amount(self) -> Decimal:
        """مانده بدهی فاکتور فروش (محاسباتی: net_amount - paid_amount)"""
        if hasattr(self, 'remaining_amount_annotated') and self.remaining_amount_annotated is not None:
            return self.remaining_amount_annotated
        return max(self.net_amount - self.paid_amount, Decimal('0.00'))

    def __str__(self):
        return f"فاکتور فروش #{self.sales_invoice_id} - {self.customer.full_name} ({self.get_status_display()})"


class SalesInvoiceTireItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    sales_invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,
        related_name='tire_items',
        verbose_name='فاکتور فروش'
    )
    tire = models.ForeignKey(
        Tire,
        on_delete=models.PROTECT,
        related_name='sales_items',
        verbose_name='تایر'
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='تعداد')
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'), message='قیمت واحد نمی‌تواند منفی باشد.')],
        verbose_name='قیمت واحد'
    )
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'), message='بهای تمام‌شده واحد نمی‌تواند منفی باشد.')],
        verbose_name='بهای تمام‌شده واحد (خرید)'
    )

    class Meta:
        db_table = 'SalesInvoice_TireItems'
        verbose_name = 'قلم تایر فاکتور فروش'
        verbose_name_plural = 'اقلام تایر فاکتور فروش'
        constraints = [
            models.UniqueConstraint(fields=['sales_invoice', 'tire'], name='unique_sales_tire_item'),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name='sales_tire_unit_cost_non_negative'
            )
        ]

    def save(self, *args, **kwargs):
        if not self.pk and (self.unit_cost is None or self.unit_cost == Decimal('0.00')) and self.tire_id:
            try:
                if self.tire and self.tire.purchase_price:
                    self.unit_cost = self.tire.purchase_price
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity}x {self.tire.tire_name} ({self.unit_price:,.0f} - بهای خرید: {self.unit_cost:,.0f})"

class SalesInvoiceServiceItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    sales_invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.CASCADE,
        related_name='service_items',
        verbose_name='فاکتور فروش'
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='sales_items',
        verbose_name='خدمت'
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='تعداد / دفعات')
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'), message='تعرفه واحد خدمت نمی‌تواند منفی باشد.')],
        verbose_name='تعرفه واحد'
    )

    class Meta:
        db_table = 'SalesInvoice_ServiceItems'
        verbose_name = 'قلم خدمت فاکتور فروش'
        verbose_name_plural = 'اقلام خدمات فاکتور فروش'
        constraints = [
            models.UniqueConstraint(fields=['sales_invoice', 'service'], name='unique_sales_service_item'),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name='sales_service_unit_price_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.quantity}x {self.service.service_name} ({self.unit_price:,.0f})"

class PurchaseInvoice(models.Model):
    purchase_invoice_id = models.AutoField(primary_key=True)
    invoice_number = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name='شماره فاکتور خرید'
    )
    invoice_date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ خرید')
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'), message='مبلغ کل خرید نمی‌تواند منفی باشد.')],
        verbose_name='مبلغ کل خرید'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchase_invoices',
        verbose_name='تأمین‌کننده'
    )
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.CONFIRMED,
        verbose_name='وضعیت فاکتور خرید'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        verbose_name='وضعیت پرداخت'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_purchase_invoices',
        verbose_name='ثبت‌کننده فاکتور'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ آخرین ویرایش')

    class Meta:
        db_table = 'Purchase_invoice'
        verbose_name = 'فاکتور خرید'
        verbose_name_plural = 'فاکتورهای خرید'
        indexes = [
            models.Index(fields=['invoice_date'], name='purch_inv_date_idx'),
            models.Index(fields=['status', 'payment_status'], name='purch_inv_status_idx'),
        ]

    def __str__(self):
        return f"فاکتور خرید #{self.purchase_invoice_id} - {self.supplier.supplier_name} ({self.get_status_display()})"

class PurchaseInvoiceTireItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    purchase_invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name='tire_items',
        verbose_name='فاکتور خرید'
    )
    tire = models.ForeignKey(
        Tire,
        on_delete=models.PROTECT,
        related_name='purchase_items',
        verbose_name='تایر خریداری شده'
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='تعداد')
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'), message='بهای خرید واحد نمی‌تواند منفی باشد.')],
        verbose_name='قیمت خرید واحد'
    )
    previous_purchase_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        editable=False,
        help_text='Catalog purchase price before this purchase; NULL means unknown legacy history.',
    )

    class Meta:
        db_table = 'PurchaseInvoice_TireItems'
        verbose_name = 'قلم تایر فاکتور خرید'
        verbose_name_plural = 'اقلام تایر فاکتور خرید'
        constraints = [
            models.UniqueConstraint(fields=['purchase_invoice', 'tire'], name='unique_purchase_tire_item'),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name='purchase_tire_unit_cost_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.quantity}x {self.tire.tire_name} (خرید: {self.unit_cost:,.0f})"

class SalesReturn(models.Model):
    sales_return_id = models.AutoField(primary_key=True)
    sales_invoice = models.ForeignKey(
        SalesInvoice,
        on_delete=models.PROTECT,
        related_name='returns',
        verbose_name='فاکتور فروش'
    )
    return_date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ مرجوعی')
    reason = models.TextField(verbose_name='علت مرجوعی')
    total_refund_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'), message='مبلغ کل استرداد نمی‌تواند منفی باشد.')],
        verbose_name='مبلغ کل استرداد'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_sales_returns',
        verbose_name='ثبت‌کننده مرجوعی'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان ثبت سیستم')

    class Meta:
        db_table = 'Sales_return'
        verbose_name = 'مرجوعی فروش'
        verbose_name_plural = 'مرجوعی‌های فروش'

    def __str__(self):
        return f"مرجوعی #{self.sales_return_id} از فاکتور #{self.sales_invoice_id}"

class SalesReturnItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    sales_return = models.ForeignKey(
        SalesReturn,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='سند مرجوعی'
    )
    sales_invoice_tire_item = models.ForeignKey(
        SalesInvoiceTireItem,
        on_delete=models.PROTECT,
        related_name='return_items',
        verbose_name='قلم تایر فاکتور فروش'
    )
    tire = models.ForeignKey(
        Tire,
        on_delete=models.PROTECT,
        related_name='return_items',
        verbose_name='تایر'
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1, message='تعداد مرجوعی باید حداقل ۱ باشد.')],
        verbose_name='تعداد مرجوعی'
    )
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'), message='قیمت واحد نمی‌تواند منفی باشد.')],
        verbose_name='قیمت واحد فروش در فاکتور'
    )
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'), message='بهای تمام‌شده واحد نمی‌تواند منفی باشد.')],
        verbose_name='بهای تمام‌شده واحد در فاکتور'
    )
    refund_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'), message='مبلغ استرداد نمی‌تواند منفی باشد.')],
        verbose_name='مبلغ استرداد این قلم پس از سهم تخفیف'
    )

    class Meta:
        db_table = 'SalesReturn_Items'
        verbose_name = 'قلم مرجوعی فروش'
        verbose_name_plural = 'اقلام مرجوعی فروش'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(refund_amount__gte=0),
                name='sales_return_refund_amount_non_negative'
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name='sales_return_unit_cost_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.quantity}x {self.tire.tire_name} (استرداد: {self.refund_amount:,.0f})"

class LegacyInvoiceItem(models.Model):
    """مدل جدول قدیمی Invoice_items جهت حفظ در دیتابیس بدون دخالت در میگریشن"""
    item_id = models.AutoField(primary_key=True)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'Invoice_items'

