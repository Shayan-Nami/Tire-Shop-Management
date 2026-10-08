from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator

class Brand(models.Model):
    brand_id = models.AutoField(primary_key=True)
    brand_name = models.CharField(max_length=50, unique=True, verbose_name='نام برند')

    class Meta:
        db_table = 'Brand'
        verbose_name = 'برند'
        verbose_name_plural = 'برندها'

    def __str__(self):
        return self.brand_name

class Size(models.Model):
    size_id = models.AutoField(primary_key=True)
    size_name = models.CharField(max_length=50, unique=True, verbose_name='سایز تایر')

    class Meta:
        db_table = 'Size'
        verbose_name = 'سایز'
        verbose_name_plural = 'سایزها'

    def __str__(self):
        return self.size_name

class Tire(models.Model):
    tire_id = models.AutoField(primary_key=True)
    tire_name = models.CharField(max_length=150, verbose_name='نام و مدل تایر')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='tires', verbose_name='برند')
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name='tires', verbose_name='سایز')
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name='موجودی انبار')
    sale_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'), message='قیمت فروش تایر نمی‌تواند منفی باشد.')],
        verbose_name='قیمت فروش (ریال/تومان)'
    )
    purchase_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'), message='قیمت خرید تایر نمی‌تواند منفی باشد.')],
        verbose_name='قیمت خرید (ریال/تومان)'
    )
    min_stock_alert = models.PositiveIntegerField(default=5, verbose_name='حداقل موجودی جهت هشدار')

    class Meta:
        # نگهداری نام جدول Tier برای سازگاری کامل با اسکریپت‌های SQL قبلی
        db_table = 'Tier'
        verbose_name = 'تایر'
        verbose_name_plural = 'تایرها'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0),
                name='tire_stock_non_negative'
            ),
            models.CheckConstraint(
                condition=models.Q(sale_price__gte=0),
                name='tire_sale_price_non_negative'
            ),
            models.CheckConstraint(
                condition=models.Q(purchase_price__gte=0),
                name='tire_purchase_price_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.tire_name} ({self.brand.brand_name} - {self.size.size_name})"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.min_stock_alert

class StockMovementType(models.TextChoices):
    INITIAL_STOCK = 'INITIAL_STOCK', 'موجودی اولیه'
    PURCHASE = 'PURCHASE', 'ورود - خرید'
    PURCHASE_CANCEL = 'PURCHASE_CANCEL', 'خروج - لغو خرید'
    SALE = 'SALE', 'خروج - فروش'
    SALE_CANCEL = 'SALE_CANCEL', 'ورود - لغو فروش'
    SALE_RETURN = 'SALE_RETURN', 'ورود - مرجوعی از فروش'
    MANUAL_ADJUSTMENT = 'MANUAL_ADJUSTMENT', 'اصلاح دستی / انبارگردانی'

class StockMovement(models.Model):
    movement_id = models.BigAutoField(primary_key=True)
    tire = models.ForeignKey(
        Tire,
        on_delete=models.PROTECT,
        related_name='stock_movements',
        verbose_name='تایر'
    )
    quantity = models.IntegerField(
        verbose_name='تعداد گردش'
    )
    movement_type = models.CharField(
        max_length=25,
        choices=StockMovementType.choices,
        verbose_name='نوع گردش انبار'
    )
    balance_after = models.PositiveIntegerField(
        verbose_name='موجودی پس از گردش'
    )
    sales_invoice = models.ForeignKey(
        'invoices.SalesInvoice',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name='فاکتور فروش مربوطه'
    )
    purchase_invoice = models.ForeignKey(
        'invoices.PurchaseInvoice',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name='فاکتور خرید مربوطه'
    )
    sales_return = models.ForeignKey(
        'invoices.SalesReturn',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name='سند مرجوعی فروش مربوطه'
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='بهای تمام‌شده واحد در گردش'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name='کاربر ثبت‌کننده'
    )
    description = models.TextField(
        blank=True,
        verbose_name='شرح و دلیل گردش'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='زمان ثبت گردش'
    )

    class Meta:
        db_table = 'Stock_movement'
        verbose_name = 'گردش انبار'
        verbose_name_plural = 'دفتر گردش انبار'
        ordering = ['-created_at', '-movement_id']

    def __str__(self):
        sign = '+' if self.quantity > 0 else ''
        return f"گردش #{self.movement_id} - {self.tire.tire_name} ({sign}{self.quantity}) - {self.get_movement_type_display()}"


class StockProjectionRepair(models.Model):
    """Audit a projection rebuild without inventing physical stock movements."""

    tire = models.ForeignKey(Tire, on_delete=models.PROTECT, related_name='projection_repairs')
    stock_before = models.PositiveIntegerField()
    stock_after = models.PositiveIntegerField()
    last_movement = models.ForeignKey(
        StockMovement, on_delete=models.PROTECT, null=True, blank=True,
        related_name='projection_repairs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='stock_projection_repairs',
    )
    reason = models.TextField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['-created_at', '-pk']
