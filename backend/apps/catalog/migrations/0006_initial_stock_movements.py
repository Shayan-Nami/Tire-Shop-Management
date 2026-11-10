from decimal import Decimal
from django.db import migrations

def create_initial_stock_movements(apps, schema_editor):
    Tire = apps.get_model('catalog', 'Tire')
    StockMovement = apps.get_model('catalog', 'StockMovement')

    movements_to_create = []
    for tire in Tire.objects.filter(stock_quantity__gt=0):
        movements_to_create.append(
            StockMovement(
                tire=tire,
                quantity=tire.stock_quantity,
                movement_type='INITIAL_STOCK',
                balance_after=tire.stock_quantity,
                unit_cost=tire.purchase_price,
                description='موجودی اولیه هنگام راه‌اندازی دفتر گردش انبار'
            )
        )

    if movements_to_create:
        StockMovement.objects.bulk_create(movements_to_create)

def reverse_initial_stock_movements(apps, schema_editor):
    StockMovement = apps.get_model('catalog', 'StockMovement')
    StockMovement.objects.filter(movement_type='INITIAL_STOCK').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_stockmovement'),
    ]

    operations = [
        migrations.RunPython(create_initial_stock_movements, reverse_initial_stock_movements),
    ]
