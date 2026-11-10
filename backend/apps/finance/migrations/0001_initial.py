import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('invoices', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentVoucher',
            fields=[
                ('payment_id', models.AutoField(primary_key=True, serialize=False)),
                ('payment_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='تاریخ پرداخت وجه')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='مبلغ پرداختی')),
                ('payment_method', models.CharField(blank=True, default='حواله / چک', max_length=50, verbose_name='روش پرداخت')),
                ('notes', models.TextField(blank=True, verbose_name='توضیحات سند')),
                ('purchase_invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='invoices.purchaseinvoice', verbose_name='فاکتور خرید مربوطه')),
            ],
            options={
                'verbose_name': 'سند پرداخت وجه',
                'verbose_name_plural': 'اسناد پرداخت وجه',
                'db_table': 'Payment_voucher',
            },
        ),
        migrations.CreateModel(
            name='ReceiptVoucher',
            fields=[
                ('receipt_id', models.AutoField(primary_key=True, serialize=False)),
                ('receipt_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='تاریخ دریافت وجه')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14, verbose_name='مبلغ دریافتی')),
                ('payment_method', models.CharField(blank=True, default='کارتخوان / نقدی', max_length=50, verbose_name='روش تسویه')),
                ('notes', models.TextField(blank=True, verbose_name='توضیحات سند')),
                ('sales_invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='receipts', to='invoices.salesinvoice', verbose_name='فاکتور فروش مربوطه')),
            ],
            options={
                'verbose_name': 'سند دریافت وجه',
                'verbose_name_plural': 'اسناد دریافت وجه',
                'db_table': 'Receipt_voucher',
            },
        ),
    ]
