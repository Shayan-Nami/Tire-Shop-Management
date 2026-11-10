from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('invoices', '0014_alter_purchaseinvoicetireitem_unit_cost_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseinvoicetireitem',
            name='previous_purchase_price',
            field=models.DecimalField(
                max_digits=14,
                decimal_places=2,
                null=True,
                editable=False,
                help_text='Catalog purchase price before this purchase; NULL means unknown legacy history.',
            ),
        ),
    ]
