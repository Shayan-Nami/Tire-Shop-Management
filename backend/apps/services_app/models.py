from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator

class Service(models.Model):
    service_id = models.AutoField(primary_key=True)
    service_name = models.CharField(max_length=150, verbose_name='نام خدمت فنی')
    price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'), message='تعرفه خدمت نمی‌تواند منفی باشد.')],
        verbose_name='تعرفه خدمت (ریال/تومان)'
    )
    description = models.TextField(blank=True, verbose_name='توضیحات تکمیلی')

    class Meta:
        db_table = 'Services'
        verbose_name = 'خدمت فنی'
        verbose_name_plural = 'خدمات فنی'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name='service_price_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.service_name} ({self.price:,.0f})"
