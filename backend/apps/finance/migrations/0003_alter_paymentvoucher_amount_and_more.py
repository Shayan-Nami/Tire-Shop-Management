import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0002_alter_paymentvoucher_purchase_invoice_and_more'),
        ('invoices', '0002_purchaseinvoice_updated_at_salesinvoice_updated_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentvoucher',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.01'), message='مبلغ سند باید بیشتر از صفر باشد.')], verbose_name='مبلغ پرداختی'),
        ),
        migrations.AlterField(
            model_name='receiptvoucher',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.01'), message='مبلغ سند باید بیشتر از صفر باشد.')], verbose_name='مبلغ دریافتی'),
        ),
        migrations.AddConstraint(
            model_name='paymentvoucher',
            constraint=models.CheckConstraint(condition=models.Q(('amount__gt', 0)), name='payment_amount_positive'),
        ),
        migrations.AddConstraint(
            model_name='receiptvoucher',
            constraint=models.CheckConstraint(condition=models.Q(('amount__gt', 0)), name='receipt_amount_positive'),
        ),
    ]
