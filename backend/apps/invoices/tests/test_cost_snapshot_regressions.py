from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Brand, Size, StockMovement, StockMovementType, Tire
from apps.customers.models import Customer
from apps.invoices.models import InvoiceStatus, PurchaseInvoiceTireItem
from apps.invoices.services import (
    cancel_purchase_invoice_service,
    confirm_sales_invoice_service,
    create_purchase_invoice_service,
    create_sales_invoice_service,
)
from apps.suppliers.models import Supplier


@pytest.fixture
def cost_data(db):
    tire = Tire.objects.create(
        tire_name='Cost snapshot tire',
        brand=Brand.objects.create(brand_name='Cost snapshot brand'),
        size=Size.objects.create(size_name='195/65R15'),
        stock_quantity=10, purchase_price=Decimal('50.00'),
        sale_price=Decimal('200.00'),
    )
    customer = Customer.objects.create(full_name='Cost customer', phone_number='09112223344')
    supplier = Supplier.objects.create(supplier_name='Cost supplier')
    return tire, customer, supplier


def purchase(tire, supplier, cost):
    return create_purchase_invoice_service(
        supplier=supplier,
        tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_cost': Decimal(cost)}],
    )


def sale(tire, customer, **kwargs):
    return create_sales_invoice_service(
        customer=customer, vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 1}],
        service_items_data=[], **kwargs,
    )


@pytest.mark.django_db
@pytest.mark.parametrize('cost', ['0.00', '90.00'])
def test_sale_uses_current_database_cost_not_stale_caller(cost_data, cost):
    tire, customer, supplier = cost_data
    purchase(tire, supplier, cost)
    assert tire.purchase_price == Decimal('50.00')  # Deliberately stale caller object.
    invoice = sale(tire, customer)
    item = invoice.tire_items.get()
    movement = StockMovement.objects.get(sales_invoice=invoice, movement_type=StockMovementType.SALE)
    assert item.unit_cost == movement.unit_cost == Decimal(cost)
    tire.refresh_from_db()
    assert tire.stock_quantity == 11


@pytest.mark.django_db
@pytest.mark.parametrize('cost', ['0.00', '90.00'])
def test_draft_confirmation_finalizes_cost_at_stock_out(cost_data, cost):
    tire, customer, supplier = cost_data
    invoice = sale(tire, customer, status=InvoiceStatus.DRAFT)
    assert invoice.tire_items.get().unit_cost == Decimal('50.00')
    assert not StockMovement.objects.filter(sales_invoice=invoice).exists()
    purchase(tire, supplier, cost)
    confirmed = confirm_sales_invoice_service(invoice)
    assert confirmed.status == InvoiceStatus.CONFIRMED
    assert confirmed.total_amount == Decimal('200.00')
    assert confirmed.tire_items.get().unit_cost == Decimal(cost)
    assert StockMovement.objects.get(sales_invoice=invoice).unit_cost == Decimal(cost)
    Tire.objects.filter(pk=tire.pk).update(purchase_price=Decimal('120.00'))
    assert confirmed.tire_items.get().unit_cost == Decimal(cost)


@pytest.mark.django_db
def test_failed_draft_confirmation_rolls_back_cost_and_status(cost_data):
    tire, customer, _ = cost_data
    invoice = sale(tire, customer, status=InvoiceStatus.DRAFT)
    Tire.objects.filter(pk=tire.pk).update(stock_quantity=0, purchase_price=Decimal('90.00'))
    with pytest.raises(ValidationError):
        confirm_sales_invoice_service(invoice)
    invoice.refresh_from_db()
    assert invoice.status == InvoiceStatus.DRAFT
    assert invoice.tire_items.get().unit_cost == Decimal('50.00')
    assert not StockMovement.objects.filter(sales_invoice=invoice).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('baseline', ['0.00', '50.00'])
@pytest.mark.parametrize('order', [(0, 1, 2), (2, 1, 0), (1, 0, 2)])
def test_no_stock_history_restores_catalog_baseline_after_sequential_cancels(cost_data, baseline, order):
    tire, _, supplier = cost_data
    Tire.objects.filter(pk=tire.pk).update(purchase_price=Decimal(baseline))
    assert not StockMovement.objects.filter(tire=tire).exists()
    invoices = [purchase(tire, supplier, cost) for cost in ['100.00', '150.00', '200.00']]
    assert invoices[0].tire_items.get().previous_purchase_price == Decimal(baseline)
    active = [True, True, True]
    for index in order:
        cancel_purchase_invoice_service(invoices[index])
        active[index] = False
        expected = next((Decimal(['100.00', '150.00', '200.00'][i])
                         for i in reversed(range(3)) if active[i]), Decimal(baseline))
        tire.refresh_from_db()
        assert tire.purchase_price == expected
        assert tire.stock_quantity == 10 + 2 * sum(active)
    assert StockMovement.objects.filter(tire=tire, movement_type=StockMovementType.PURCHASE_CANCEL).count() == 3


@pytest.mark.django_db
def test_unknown_legacy_baseline_rejects_cancellation_atomically(cost_data):
    tire, _, supplier = cost_data
    invoice = purchase(tire, supplier, '100.00')
    PurchaseInvoiceTireItem.objects.filter(purchase_invoice=invoice).update(previous_purchase_price=None)
    with pytest.raises(ValidationError, match='قیمت خرید'):
        cancel_purchase_invoice_service(invoice)
    tire.refresh_from_db()
    invoice.refresh_from_db()
    assert tire.purchase_price == Decimal('100.00')
    assert tire.stock_quantity == 12
    assert invoice.status == InvoiceStatus.CONFIRMED
    assert not StockMovement.objects.filter(movement_type=StockMovementType.PURCHASE_CANCEL).exists()


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row-lock SQL')
@pytest.mark.parametrize('draft', [False, True])
def test_ordered_tire_locks_precede_item_cost_writes(cost_data, draft):
    tire, customer, _ = cost_data
    other = Tire.objects.create(
        tire_name='Other cost tire', brand=tire.brand, size=tire.size,
        stock_quantity=10, purchase_price=Decimal('75.00'), sale_price=Decimal('200.00'),
    )
    kwargs = dict(
        customer=customer, vehicle=None,
        tire_items_data=[{'tire': other, 'quantity': 1}, {'tire': tire, 'quantity': 1}],
        service_items_data=[],
    )
    if draft:
        invoice = create_sales_invoice_service(**kwargs, status=InvoiceStatus.DRAFT)
    with CaptureQueriesContext(connection) as captured:
        if draft:
            confirm_sales_invoice_service(invoice)
        else:
            create_sales_invoice_service(**kwargs)
    sql = [query['sql'] for query in captured]
    locks = [i for i, query in enumerate(sql) if 'FROM "Tier"' in query and 'FOR UPDATE' in query]
    writes = [i for i, query in enumerate(sql)
              if query.startswith(('INSERT INTO "SalesInvoice_TireItems"', 'UPDATE "SalesInvoice_TireItems"'))]
    assert locks and writes
    assert locks[0] < min(writes)
    assert 'ORDER BY "Tier"."tire_id" ASC' in sql[locks[0]]
