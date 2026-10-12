from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0011_backfill_invoice_numbers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='salesinvoice',
            name='invoice_number',
            field=models.CharField(
                db_index=True,
                max_length=32,
                unique=True,
                verbose_name='شماره فاکتور'
            ),
        ),
        migrations.AlterField(
            model_name='purchaseinvoice',
            name='invoice_number',
            field=models.CharField(
                db_index=True,
                max_length=32,
                unique=True,
                verbose_name='شماره فاکتور خرید'
            ),
        ),
    ]
