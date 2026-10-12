from decimal import Decimal
from django.db import migrations, models


def backfill_sales_payment_status(apps, schema_editor):
    SalesInvoice = apps.get_model('invoices', 'SalesInvoice')
    SalesReturn = apps.get_model('invoices', 'SalesReturn')
    ReceiptVoucher = apps.get_model('finance', 'ReceiptVoucher')
    CustomerRefundVoucher = apps.get_model('finance', 'CustomerRefundVoucher')

    for invoice in SalesInvoice.objects.all():
        total_returned = SalesReturn.objects.filter(
            sales_invoice=invoice
        ).aggregate(total=models.Sum('total_refund_amount'))['total'] or Decimal('0.00')

        net_amount = max(invoice.total_amount - total_returned, Decimal('0.00'))

        valid_receipts = ReceiptVoucher.objects.filter(
            sales_invoice=invoice,
            is_cancelled=False
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        valid_refunds = CustomerRefundVoucher.objects.filter(
            sales_invoice=invoice,
            is_cancelled=False
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

        effective_paid = max(Decimal('0.00'), valid_receipts - valid_refunds)

        if net_amount == Decimal('0.00'):
            new_status = 'PAID'
        elif effective_paid == Decimal('0.00'):
            new_status = 'UNPAID'
        elif effective_paid < net_amount:
            new_status = 'PARTIAL'
        else:
            new_status = 'PAID'

        invoice.payment_status = new_status
        invoice.save(update_fields=['payment_status'])


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0008_alter_salesinvoice_payment_status'),
        ('finance', '0004_paymentvoucher_cancellation_reason_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_sales_payment_status, reverse_backfill),
    ]
