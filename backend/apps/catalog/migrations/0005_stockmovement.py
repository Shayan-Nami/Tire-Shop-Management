import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0004_alter_tire_purchase_price_alter_tire_sale_price_and_more'),
        ('invoices', '0004_backfill_sales_tire_unit_cost'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('movement_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('quantity', models.IntegerField(verbose_name='تعداد گردش')),
                ('movement_type', models.CharField(choices=[('INITIAL_STOCK', 'موجودی اولیه'), ('PURCHASE', 'ورود - خرید'), ('PURCHASE_CANCEL', 'خروج - لغو خرید'), ('SALE', 'خروج - فروش'), ('SALE_CANCEL', 'ورود - لغو فروش'), ('SALE_RETURN', 'ورود - مرجوعی از فروش'), ('MANUAL_ADJUSTMENT', 'اصلاح دستی / انبارگردانی')], max_length=25, verbose_name='نوع گردش انبار')),
                ('balance_after', models.PositiveIntegerField(verbose_name='موجودی پس از گردش')),
                ('unit_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))], verbose_name='بهای تمام\u200cشده واحد در گردش')),
                ('description', models.TextField(blank=True, verbose_name='شرح و دلیل گردش')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='زمان ثبت گردش')),
                ('purchase_invoice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_movements', to='invoices.purchaseinvoice', verbose_name='فاکتور خرید مربوطه')),
                ('sales_invoice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_movements', to='invoices.salesinvoice', verbose_name='فاکتور فروش مربوطه')),
                ('tire', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_movements', to='catalog.tire', verbose_name='تایر')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_movements', to=settings.AUTH_USER_MODEL, verbose_name='کاربر ثبت\u200cکننده')),
            ],
            options={
                'verbose_name': 'گردش انبار',
                'verbose_name_plural': 'دفتر گردش انبار',
                'db_table': 'Stock_movement',
                'ordering': ['-created_at', '-movement_id'],
            },
        ),
    ]
