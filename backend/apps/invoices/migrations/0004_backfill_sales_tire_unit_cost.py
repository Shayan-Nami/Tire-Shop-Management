from decimal import Decimal
from django.db import migrations

def backfill_sales_tire_unit_cost(apps, schema_editor):
    """
    پر کردن فیلد unit_cost برای اقلام فروش قبلی بر اساس بهای خرید جاری تایر در کاتالوگ
    """
    SalesInvoiceTireItem = apps.get_model('invoices', 'SalesInvoiceTireItem')
    
    items_to_update = []
    for item in SalesInvoiceTireItem.objects.all():
        # دریافت قیمت خرید تایر مربوطه
        if item.tire_id:
            Tire = apps.get_model('catalog', 'Tire')
            try:
                tire = Tire.objects.get(pk=item.tire_id)
                if tire.purchase_price:
                    item.unit_cost = tire.purchase_price
                    items_to_update.append(item)
            except Tire.DoesNotExist:
                pass

    if items_to_update:
        SalesInvoiceTireItem.objects.bulk_update(items_to_update, ['unit_cost'])

def reverse_backfill(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0003_salesinvoicetireitem_unit_cost_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_sales_tire_unit_cost, reverse_backfill),
    ]
