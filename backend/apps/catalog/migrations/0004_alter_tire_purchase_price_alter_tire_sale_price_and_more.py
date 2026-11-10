import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_alter_tire_min_stock_alert'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tire',
            name='purchase_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='قیمت خرید تایر نمی\u200cتواند منفی باشد.')], verbose_name='قیمت خرید (ریال/تومان)'),
        ),
        migrations.AlterField(
            model_name='tire',
            name='sale_price',
            field=models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='قیمت فروش تایر نمی\u200cتواند منفی باشد.')], verbose_name='قیمت فروش (ریال/تومان)'),
        ),
        migrations.AddConstraint(
            model_name='tire',
            constraint=models.CheckConstraint(condition=models.Q(('sale_price__gte', 0)), name='tire_sale_price_non_negative'),
        ),
        migrations.AddConstraint(
            model_name='tire',
            constraint=models.CheckConstraint(condition=models.Q(('purchase_price__gte', 0)), name='tire_purchase_price_non_negative'),
        ),
    ]
