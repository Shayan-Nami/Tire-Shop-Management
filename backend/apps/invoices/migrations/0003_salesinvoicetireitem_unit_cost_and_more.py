import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0004_alter_tire_purchase_price_alter_tire_sale_price_and_more'),
        ('invoices', '0002_purchaseinvoice_updated_at_salesinvoice_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesinvoicetireitem',
            name='unit_cost',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='بهای تمام\u200cشده واحد نمی\u200cتواند منفی باشد.')], verbose_name='بهای تمام\u200cشده واحد (خرید)'),
        ),
        migrations.AlterField(
            model_name='salesinvoicetireitem',
            name='unit_price',
            field=models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='قیمت واحد نمی\u200cتواند منفی باشد.')], verbose_name='قیمت واحد'),
        ),
        migrations.AddConstraint(
            model_name='salesinvoicetireitem',
            constraint=models.CheckConstraint(condition=models.Q(('unit_cost__gte', 0)), name='sales_tire_unit_cost_non_negative'),
        ),
    ]
