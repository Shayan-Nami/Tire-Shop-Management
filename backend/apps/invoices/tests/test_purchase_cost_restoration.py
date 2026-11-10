from decimal import Decimal

import pytest

from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.invoices.services import create_purchase_invoice_service, cancel_purchase_invoice_service
from apps.suppliers.models import Supplier


@pytest.mark.django_db
@pytest.mark.parametrize('baseline', ['0.00', '50.00'])
def test_cancel_purchase_restores_zero_or_positive_initial_cost(baseline, manager_user):
    tire = Tire.objects.create(
        tire_name='آزمون بازیابی قیمت',
        brand=Brand.objects.create(brand_name='برند آزمون قیمت'),
        size=Size.objects.create(size_name='195/65R15'),
        purchase_price=Decimal(baseline), sale_price=Decimal('200.00'),
        stock_quantity=5,
    )
    StockMovement.objects.create(
        tire=tire, movement_type=StockMovementType.INITIAL_STOCK,
        quantity=5, balance_after=5, unit_cost=Decimal(baseline),
    )
    invoice = create_purchase_invoice_service(
        supplier=Supplier.objects.create(supplier_name='تأمین‌کننده آزمون'),
        tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_cost': Decimal('100.00')}],
        created_by=manager_user,
    )
    tire.refresh_from_db()
    assert tire.purchase_price == Decimal('100.00')
    cancel_purchase_invoice_service(invoice, user=manager_user)
    tire.refresh_from_db()
    assert tire.purchase_price == Decimal(baseline)
    assert tire.stock_quantity == 5
