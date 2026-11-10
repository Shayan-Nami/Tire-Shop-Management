from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0005_purchaseinvoice_status_salesreturn_salesreturnitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseinvoice',
            name='payment_status',
            field=models.CharField(choices=[('UNPAID', 'پرداخت نشده (نسیه)'), ('PARTIAL', 'پرداخت ناقص (اقساطی)'), ('PAID', 'تسویه کامل')], default='UNPAID', max_length=20, verbose_name='وضعیت پرداخت'),
        ),
    ]
