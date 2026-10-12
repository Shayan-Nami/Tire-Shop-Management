from decimal import Decimal
from django.db import migrations, models


def backfill_purchase_payment_status(apps, schema_editor):
    PurchaseInvoice = apps.get_model('invoices', 'PurchaseInvoice')
    PaymentVoucher = apps.get_model('finance', 'PaymentVoucher')

    for invoice in PurchaseInvoice.objects.all():
        valid_payments = PaymentVoucher.objects.filter(
            purchase_invoice=invoice,
            is_cancelled=False
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        if invoice.total_amount == Decimal('0.00') or valid_payments >= invoice.total_amount:
            new_status = 'PAID'
        elif valid_payments > Decimal('0.00'):
            new_status = 'PARTIAL'
        else:
            new_status = 'UNPAID'

        invoice.payment_status = new_status
        invoice.save(update_fields=['payment_status'])


def reverse_backfill(apps, schema_editor):
    PurchaseInvoice = apps.get_model('invoices', 'PurchaseInvoice')
    PurchaseInvoice.objects.all().update(payment_status='UNPAID')


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0006_purchaseinvoice_payment_status'),
        ('finance', '0004_paymentvoucher_cancellation_reason_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_purchase_payment_status, reverse_backfill),
    ]
