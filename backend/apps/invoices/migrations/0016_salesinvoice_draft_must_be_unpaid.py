from django.db import migrations, models


def normalize_draft_sales_invoice_payment_status(apps, schema_editor):
    SalesInvoice = apps.get_model('invoices', 'SalesInvoice')
    (
        SalesInvoice.objects.using(schema_editor.connection.alias)
        .filter(status='DRAFT')
        .exclude(payment_status='UNPAID')
        .update(payment_status='UNPAID')
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0015_purchase_item_previous_purchase_price'),
    ]

    operations = [
        migrations.RunPython(normalize_draft_sales_invoice_payment_status, noop_reverse),
        migrations.AddConstraint(
            model_name='salesinvoice',
            constraint=models.CheckConstraint(
                condition=models.Q(('status__in', ['CONFIRMED', 'CANCELLED'])) | models.Q(('payment_status', 'UNPAID')),
                name='sales_invoice_draft_must_be_unpaid',
            ),
        ),
    ]
