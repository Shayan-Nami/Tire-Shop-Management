from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0007_backfill_purchase_invoice_payment_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='salesinvoice',
            name='payment_status',
            field=models.CharField(choices=[('UNPAID', 'پرداخت نشده (نسیه)'), ('PARTIAL', 'پرداخت ناقص (اقساطی)'), ('PAID', 'تسویه کامل')], default='UNPAID', max_length=20, verbose_name='وضعیت پرداخت'),
        ),
    ]
