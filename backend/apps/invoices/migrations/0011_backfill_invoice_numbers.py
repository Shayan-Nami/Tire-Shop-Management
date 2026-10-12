from django.db import migrations, transaction


def get_jalali_year_from_date(dt):
    if not dt:
        return 1405
    gy, gm, gd = dt.year, dt.month, dt.day
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = (gy + 1) if (gm > 2) else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += ((days - 1) // 365)
    return jy


def backfill_invoice_numbers(apps, schema_editor):
    SalesInvoice = apps.get_model('invoices', 'SalesInvoice')
    PurchaseInvoice = apps.get_model('invoices', 'PurchaseInvoice')
    InvoiceSequence = apps.get_model('invoices', 'InvoiceSequence')

    # ۱. تخصیص شماره پیوسته به فاکتورهای فروش موجود بر اساس ترتیب تاریخ و شناسه
    sales_invoices = SalesInvoice.objects.filter(
        models_q_filter(invoice_number__isnull=True)
    ).order_by('invoice_date', 'sales_invoice_id')

    for inv in sales_invoices:
        year = get_jalali_year_from_date(inv.invoice_date)
        with transaction.atomic():
            seq, _ = InvoiceSequence.objects.select_for_update().get_or_create(
                doc_type='SALES',
                year=year,
                defaults={'last_number': 0}
            )
            seq.last_number += 1
            seq.save(update_fields=['last_number'])
            inv.invoice_number = f"S-{year}-{seq.last_number:05d}"
            inv.save(update_fields=['invoice_number'])

    # ۲. تخصیص شماره پیوسته به فاکتورهای خرید موجود بر اساس ترتیب تاریخ و شناسه
    purchase_invoices = PurchaseInvoice.objects.filter(
        models_q_filter(invoice_number__isnull=True)
    ).order_by('invoice_date', 'purchase_invoice_id')

    for inv in purchase_invoices:
        year = get_jalali_year_from_date(inv.invoice_date)
        with transaction.atomic():
            seq, _ = InvoiceSequence.objects.select_for_update().get_or_create(
                doc_type='PURCHASE',
                year=year,
                defaults={'last_number': 0}
            )
            seq.last_number += 1
            seq.save(update_fields=['last_number'])
            inv.invoice_number = f"P-{year}-{seq.last_number:05d}"
            inv.save(update_fields=['invoice_number'])


def models_q_filter(**kwargs):
    from django.db.models import Q
    return Q(**kwargs) | Q(invoice_number='')


def reverse_backfill(apps, schema_editor):
    SalesInvoice = apps.get_model('invoices', 'SalesInvoice')
    PurchaseInvoice = apps.get_model('invoices', 'PurchaseInvoice')
    InvoiceSequence = apps.get_model('invoices', 'InvoiceSequence')

    SalesInvoice.objects.all().update(invoice_number=None)
    PurchaseInvoice.objects.all().update(invoice_number=None)
    InvoiceSequence.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0010_add_invoice_sequence_and_nullable_number'),
    ]

    operations = [
        migrations.RunPython(backfill_invoice_numbers, reverse_backfill),
    ]
