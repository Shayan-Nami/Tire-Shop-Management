from datetime import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator

from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer
from apps.invoices.models import InvoiceStatus, SalesInvoice, SalesReturn
from apps.invoices.services import create_sales_invoice_service, create_sales_return_service
from apps.reports.serializers import SalesByDateRangeResponseSerializer


def at_day(day):
    return timezone.make_aware(datetime(2026, 10, day, 12))


@pytest.fixture
def period_data(db):
    tire = Tire.objects.create(
        tire_name='Period tire', brand=Brand.objects.create(brand_name='Period brand'),
        size=Size.objects.create(size_name='195/65R15'), stock_quantity=20,
        purchase_price=Decimal('40.00'), sale_price=Decimal('100.00'),
    )
    customer = Customer.objects.create(full_name='Period customer', phone_number='09112223344')
    return tire, customer


def sell(period_data, day, quantity=1, **kwargs):
    tire, customer = period_data
    invoice = create_sales_invoice_service(
        customer=customer, vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': quantity}],
        service_items_data=[], **kwargs,
    )
    SalesInvoice.objects.filter(pk=invoice.pk).update(invoice_date=at_day(day))
    return invoice


def return_sale(invoice, day, quantity=1):
    returned = create_sales_return_service(
        invoice=invoice,
        items_data=[{'sales_invoice_tire_item_id': invoice.tire_items.get().pk, 'quantity': quantity}],
        reason='Period return',
    )
    SalesReturn.objects.filter(pk=returned.pk).update(return_date=at_day(day))
    return returned


def report(client, **params):
    response = client.get(reverse('sales-by-date-report'), params)
    assert response.status_code == 200
    data = response.data
    assert data['total_sales_amount'] == data['gross_sales_amount'] - data['total_refund_amount']
    return data


@pytest.mark.django_db
def test_return_only_period_has_negative_net_sales(auth_client_manager, period_data):
    invoice = sell(period_data, 1, quantity=2)
    return_sale(invoice, 10)
    data = report(auth_client_manager, start_date='2026-10-10', end_date='2026-10-10')
    assert data == {
        'total_invoices': 0, 'total_sales_amount': -100.0,
        'gross_sales_amount': 0.0, 'total_refund_amount': 100.0,
        'start_date': '2026-10-10', 'end_date': '2026-10-10',
    }
    # Returning stock does not require a cash refund voucher to affect this report.
    assert not invoice.refunds.exists()


@pytest.mark.django_db
def test_period_components_use_independent_dates_and_exclude_nonconfirmed(auth_client_manager, period_data):
    old = sell(period_data, 1, quantity=2, discount_percent=Decimal('10.00'))
    return_sale(old, 10)
    return_sale(old, 11)
    sell(period_data, 10, discount_amount=Decimal('20.00'))
    sell(period_data, 10, status=InvoiceStatus.DRAFT)
    excluded = sell(period_data, 10)
    return_sale(excluded, 10)
    SalesInvoice.objects.filter(pk=excluded.pk).update(status=InvoiceStatus.CANCELLED)
    data = report(auth_client_manager, start_date='2026-10-10', end_date='2026-10-10')
    assert data['total_invoices'] == 1
    assert data['gross_sales_amount'] == 80.0
    assert data['total_refund_amount'] == 90.0
    assert data['total_sales_amount'] == -10.0
    all_dates = report(auth_client_manager)
    assert all_dates['gross_sales_amount'] == 260.0
    assert all_dates['total_refund_amount'] == 180.0
    assert all_dates['total_sales_amount'] == 80.0


@pytest.mark.django_db
@pytest.mark.parametrize('params', [
    {}, {'start_date': '2026-10-10'}, {'end_date': '2026-10-10'},
    {'start_date': '2026-10-10', 'end_date': '2026-10-10'},
])
def test_empty_period_components_are_zero(auth_client_manager, params):
    data = report(auth_client_manager, **params)
    assert data['total_invoices'] == 0
    assert data['gross_sales_amount'] == data['total_refund_amount'] == data['total_sales_amount'] == 0.0


@pytest.mark.django_db
def test_date_report_schema_exposes_gross_returns_and_signed_net():
    fields = SalesByDateRangeResponseSerializer().fields
    assert {'gross_sales_amount', 'total_refund_amount', 'total_sales_amount'} <= fields.keys()
    assert fields['total_sales_amount'].min_value is None
    schema = SchemaGenerator().get_schema(public=True)
    properties = schema['components']['schemas']['SalesByDateRangeResponse']['properties']
    assert {'gross_sales_amount', 'total_refund_amount', 'total_sales_amount'} <= properties.keys()
    assert 'minimum' not in properties['total_sales_amount']


@pytest.mark.django_db
@pytest.mark.parametrize('price', ['0.00', '100.00'])
def test_brand_revenue_ties_sort_by_name_not_creation_order(auth_client_manager, period_data, price):
    tire, customer = period_data
    # Insert in reverse alphabetical order so database/insertion order is not the contract.
    for name in ['Zulu tie', 'Alpha tie', 'Middle tie']:
        other = Tire.objects.create(
            tire_name=name, brand=Brand.objects.create(brand_name=name), size=tire.size,
            stock_quantity=5, purchase_price=Decimal('0.00'), sale_price=Decimal(price),
        )
        create_sales_invoice_service(
            customer=customer, vehicle=None,
            tire_items_data=[{'tire': other, 'quantity': 1}], service_items_data=[],
        )
    response = auth_client_manager.get(reverse('sales-by-brand-report'))
    assert response.status_code == 200
    assert [row['brand_name'] for row in response.data] == ['Alpha tie', 'Middle tie', 'Zulu tie']
    assert all(row['total_revenue'] == float(price) for row in response.data)
