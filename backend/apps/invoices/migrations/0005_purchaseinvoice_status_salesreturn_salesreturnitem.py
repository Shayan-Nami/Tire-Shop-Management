import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_initial_stock_movements'),
        ('invoices', '0004_backfill_sales_tire_unit_cost'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseinvoice',
            name='status',
            field=models.CharField(choices=[('DRAFT', 'پیش\u200cنویس'), ('CONFIRMED', 'تایید شده / نهایی'), ('CANCELLED', 'لغو شده')], default='CONFIRMED', max_length=20, verbose_name='وضعیت فاکتور خرید'),
        ),
        migrations.CreateModel(
            name='SalesReturn',
            fields=[
                ('sales_return_id', models.AutoField(primary_key=True, serialize=False)),
                ('return_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='تاریخ مرجوعی')),
                ('reason', models.TextField(verbose_name='علت مرجوعی')),
                ('total_refund_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='مبلغ کل استرداد نمی\u200cتواند منفی باشد.')], verbose_name='مبلغ کل استرداد')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ثبت سیستم')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_sales_returns', to=settings.AUTH_USER_MODEL, verbose_name='ثبت\u200cکننده مرجوعی')),
                ('sales_invoice', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='returns', to='invoices.salesinvoice', verbose_name='فاکتور فروش')),
            ],
            options={
                'verbose_name': 'مرجوعی فروش',
                'verbose_name_plural': 'مرجوعی\u200cهای فروش',
                'db_table': 'Sales_return',
            },
        ),
        migrations.CreateModel(
            name='SalesReturnItem',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('quantity', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1, message='تعداد مرجوعی باید حداقل ۱ باشد.')], verbose_name='تعداد مرجوعی')),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='قیمت واحد نمی\u200cتواند منفی باشد.')], verbose_name='قیمت واحد فروش در فاکتور')),
                ('unit_cost', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='بهای تمام\u200cشده واحد نمی\u200cتواند منفی باشد.')], verbose_name='بهای تمام\u200cشده واحد در فاکتور')),
                ('refund_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal('0.00'), message='مبلغ استرداد نمی\u200cتواند منفی باشد.')], verbose_name='مبلغ استرداد این قلم پس از سهم تخفیف')),
                ('sales_invoice_tire_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='return_items', to='invoices.salesinvoicetireitem', verbose_name='قلم تایر فاکتور فروش')),
                ('sales_return', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='invoices.salesreturn', verbose_name='سند مرجوعی')),
                ('tire', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='return_items', to='catalog.tire', verbose_name='تایر')),
            ],
            options={
                'verbose_name': 'قلم مرجوعی فروش',
                'verbose_name_plural': 'اقلام مرجوعی فروش',
                'db_table': 'SalesReturn_Items',
                'constraints': [models.CheckConstraint(condition=models.Q(('refund_amount__gte', 0)), name='sales_return_refund_amount_non_negative'), models.CheckConstraint(condition=models.Q(('unit_cost__gte', 0)), name='sales_return_unit_cost_non_negative')],
            },
        ),
    ]
