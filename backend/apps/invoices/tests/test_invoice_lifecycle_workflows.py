from decimal import Decimal
from unittest.mock import patch
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from apps.catalog.models import Brand, Size, Tire, StockMovement
from apps.customers.models import Customer
from apps.services_app.models import Service
from apps.invoices.models import InvoiceStatus, PaymentStatus, SalesInvoice
from apps.invoices.services import create_sales_invoice_service, confirm_sales_invoice_service, create_sales_return_service
from apps.finance.services import create_receipt_voucher_service, create_customer_refund_voucher_service

pytestmark = pytest.mark.django_db


@pytest.fixture
def shop():
    brand = Brand.objects.create(brand_name='Barez')
    size = Size.objects.create(size_name='195/65R15')
    customer = Customer.objects.create(full_name='Sample customer')
    service = Service.objects.create(service_name='Mount and balance', price=Decimal('20'))
    def tire(number):
        return Tire.objects.create(tire_name=f'Sample tire {number}', brand=brand, size=size,
                                   stock_quantity=10, sale_price=Decimal('100'), purchase_price=Decimal('50'))
    return customer, service, tire


def test_mixed_draft_payment_return_and_refund_lifecycle(shop, manager_user):
    customer, service, make_tire = shop
    tire = make_tire(1)
    invoice = create_sales_invoice_service(customer, None, [{'tire': tire, 'quantity': 2}],
        [{'service': service}], status=InvoiceStatus.DRAFT, created_by=manager_user)
    tire.refresh_from_db()
    assert tire.stock_quantity == 10
    assert not StockMovement.objects.filter(sales_invoice=invoice).exists()
    invoice = confirm_sales_invoice_service(invoice, manager_user)
    tire.refresh_from_db()
    assert tire.stock_quantity == 8
    create_receipt_voucher_service(invoice, Decimal('100'))
    invoice.refresh_from_db()
    assert invoice.payment_status == PaymentStatus.PARTIAL
    assert invoice.remaining_amount == Decimal('120')
    create_receipt_voucher_service(invoice, Decimal('120'))
    invoice.refresh_from_db()
    assert invoice.payment_status == PaymentStatus.PAID
    returned = create_sales_return_service(invoice, [{'tire_item_id': invoice.tire_items.get().pk, 'quantity': 1}], 'return')
    assert returned.total_refund_amount == Decimal('100')
    create_customer_refund_voucher_service(invoice, Decimal('100'), sales_return=returned)
    tire.refresh_from_db()
    assert tire.stock_quantity == 9
    assert invoice.net_amount == invoice.paid_amount == Decimal('120')
    assert invoice.remaining_amount == invoice.excess_amount == 0


@pytest.mark.parametrize('quantity', [True, 1.5, '1.5', float('nan')])
def test_fractional_quantity_rejected_without_side_effects(shop, quantity):
    customer, service, make_tire = shop
    tire = make_tire(1)
    with pytest.raises(ValidationError):
        create_sales_invoice_service(customer, None, [{'tire': tire, 'quantity': quantity}], [])
    tire.refresh_from_db()
    assert tire.stock_quantity == 10
    assert not SalesInvoice.objects.exists()
    assert not StockMovement.objects.exists()


def test_stock_and_sequence_rollback_when_line_write_fails(shop):
    customer, service, make_tire = shop
    tire = make_tire(1)
    with patch('apps.invoices.services.SalesInvoiceServiceItem.objects.create', side_effect=RuntimeError('write failed')):
        with pytest.raises(RuntimeError):
            create_sales_invoice_service(customer, None, [{'tire': tire, 'quantity': 1}], [{'service': service}])
    tire.refresh_from_db()
    assert tire.stock_quantity == 10
    assert not SalesInvoice.objects.exists()
    assert not StockMovement.objects.exists()
    invoice = create_sales_invoice_service(customer, None, [], [{'service': service, 'unit_price': Decimal('0')}])
    assert invoice.invoice_number.endswith('00001')
    assert invoice.payment_status == PaymentStatus.PAID


def test_return_read_queries_do_not_grow_per_line(shop):
    customer, service, make_tire = shop
    counts = []
    for count in (1, 6):
        invoice = create_sales_invoice_service(customer, None,
            [{'tire': make_tire(f'{count}-{i}'), 'quantity': 1} for i in range(count)], [])
        items = [{'tire_item_id': item.pk, 'quantity': 1} for item in invoice.tire_items.all()]
        with CaptureQueriesContext(connection) as queries:
            returned = create_sales_return_service(invoice, items, 'query regression')
        assert returned.total_refund_amount == Decimal(100 * count)
        counts.append(sum(q['sql'].lstrip().upper().startswith('SELECT') for q in queries))
    assert counts[0] == counts[1], counts


@pytest.mark.parametrize('route', ['sales-invoice-list', 'dashboard-stats', 'sales-by-brand-report', 'profitability-report'])
def test_read_query_count_is_bounded(shop, auth_client_manager, manager_user, route):
    customer, service, make_tire = shop
    counts = []
    for count in (1, 5):
        for i in range(count):
            create_sales_invoice_service(customer, None, [{'tire': make_tire(f'{count}-{i}'), 'quantity': 1}],
                                         [{'service': service}], created_by=manager_user)
        with CaptureQueriesContext(connection) as queries:
            response = auth_client_manager.get(reverse(route))
            assert response.status_code == 200
        counts.append(len(queries))
    assert counts[0] == counts[1], counts
