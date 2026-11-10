import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_stockmovement_sales_return'),
        ('invoices', '0012_alter_invoice_number_unique_not_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='purchase_invoice',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='stock_movements', to='invoices.purchaseinvoice', verbose_name='فاکتور خرید مربوطه'),
        ),
        migrations.AlterField(
            model_name='stockmovement',
            name='sales_invoice',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='stock_movements', to='invoices.salesinvoice', verbose_name='فاکتور فروش مربوطه'),
        ),
        migrations.AlterField(
            model_name='stockmovement',
            name='sales_return',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='stock_movements', to='invoices.salesreturn', verbose_name='سند مرجوعی فروش مربوطه'),
        ),
    ]
