import django.core.validators
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0004_alter_customer_national_code_and_more'),
        ('invoices', '0012_alter_invoice_number_unique_not_null'),
        ('suppliers', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchaseinvoice',
            name='total_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='مبلغ کل خرید نمی\u200cتواند منفی باشد.')], verbose_name='مبلغ کل خرید'),
        ),
        migrations.AlterField(
            model_name='salesinvoice',
            name='discount_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='مبلغ تخفیف نمی\u200cتواند منفی باشد.')], verbose_name='مبلغ تخفیف'),
        ),
        migrations.AlterField(
            model_name='salesinvoice',
            name='discount_percent',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='درصد تخفیف نمی\u200cتواند منفی باشد.'), django.core.validators.MaxValueValidator(Decimal('100.00'), message='درصد تخفیف نمی\u200cتواند بیش از ۱۰۰ درصد باشد.')], verbose_name='درصد تخفیف'),
        ),
        migrations.AlterField(
            model_name='salesinvoice',
            name='total_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='مبلغ نهایی فاکتور نمی\u200cتواند منفی باشد.')], verbose_name='مبلغ نهایی فاکتور'),
        ),
        migrations.AddIndex(
            model_name='purchaseinvoice',
            index=models.Index(fields=['invoice_date'], name='purch_inv_date_idx'),
        ),
        migrations.AddIndex(
            model_name='purchaseinvoice',
            index=models.Index(fields=['status', 'payment_status'], name='purch_inv_status_idx'),
        ),
        migrations.AddIndex(
            model_name='salesinvoice',
            index=models.Index(fields=['invoice_date'], name='sales_inv_date_idx'),
        ),
        migrations.AddIndex(
            model_name='salesinvoice',
            index=models.Index(fields=['status', 'payment_status'], name='sales_inv_status_idx'),
        ),
    ]
