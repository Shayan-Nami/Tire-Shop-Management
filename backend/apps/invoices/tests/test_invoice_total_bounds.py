from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.models import Brand, Size, StockMovement, Tire
from apps.customers.models import Customer
from apps.finance.models import ReceiptVoucher
from apps.invoices.models import (
    InvoiceSequence, PurchaseInvoice, PurchaseInvoiceTireItem,
    SalesInvoice, SalesInvoiceServiceItem, SalesInvoiceTireItem,
)
from apps.services_app.models import Service
from apps.suppliers.models import Supplier


MAX_TOTAL = Decimal('999999999999.99')


@pytest.fixture
def total_bounds_data(db):
    brand = Brand.objects.create(brand_name='Total bounds')
    size = Size.objects.create(size_name='Total bounds')
    tires = [
        Tire.objects.create(
            tire_name=f'Bounds tire {index}', brand=brand, size=size,
            stock_quantity=10, sale_price=Decimal('200.00'),
            purchase_price=Decimal('100.00'),
        )
        for index in range(2)
    ]
    return {
        'tires': tires,
        'service': Service.objects.create(service_name='Bounds service', price='100.00'),
        'customer': Customer.objects.create(full_name='Total bounds customer'),
        'supplier': Supplier.objects.create(supplier_name='Total bounds supplier'),
    }


@pytest.mark.django_db
@pytest.mark.parametrize('kind', [
    'purchase', 'purchase_multiple', 'sales_tire', 'sales_service',
    'sales_mixed', 'sales_draft',
])
def test_overflow_total_rejected_without_committing_documents_or_stock(
    auth_client_manager, total_bounds_data, kind,
):
    data = total_bounds_data
    if kind.startswith('purchase'):
        url = reverse('purchase-invoice-list')
        items = [{'tire': data['tires'][0].pk, 'quantity': 2, 'unit_cost': str(MAX_TOTAL)}]
        if kind == 'purchase_multiple':
            items = [
                {'tire': tire.pk, 'quantity': 1, 'unit_cost': '600000000000.00'}
                for tire in data['tires']
            ]
        payload = {'supplier': data['supplier'].pk, 'tire_items': items}
    else:
        url = reverse('sales-invoice-list')
        payload = {'customer': data['customer'].pk}
        if kind == 'sales_service':
            payload['service_items'] = [
                {'service': data['service'].pk, 'quantity': 2, 'unit_price': str(MAX_TOTAL)},
            ]
        elif kind == 'sales_mixed':
            payload['tire_items'] = [
                {'tire': data['tires'][0].pk, 'quantity': 1, 'unit_price': '600000000000.00'},
            ]
            payload['service_items'] = [
                {'service': data['service'].pk, 'quantity': 1, 'unit_price': '600000000000.00'},
            ]
        else:
            payload['tire_items'] = [
                {'tire': data['tires'][0].pk, 'quantity': 2, 'unit_price': str(MAX_TOTAL)},
            ]
            if kind == 'sales_draft':
                payload['status'] = 'DRAFT'

    response = auth_client_manager.post(url, payload, format='json')

    assert response.status_code == 400, response.data
    assert 'total_amount' in response.data['errors']
    for model in (
        SalesInvoice, PurchaseInvoice, SalesInvoiceTireItem, SalesInvoiceServiceItem,
        PurchaseInvoiceTireItem, StockMovement, InvoiceSequence, ReceiptVoucher,
    ):
        assert not model.objects.exists(), model.__name__
    for tire in data['tires']:
        tire.refresh_from_db()
        assert tire.stock_quantity == 10
        assert tire.purchase_price == Decimal('100.00')
    listing = auth_client_manager.get(url)
    assert listing.status_code == 200
    assert listing.data['count'] == 0


@pytest.mark.django_db
@pytest.mark.parametrize('kind', ['sales', 'purchase'])
def test_exact_total_limit_remains_supported(auth_client_manager, total_bounds_data, kind):
    data = total_bounds_data
    if kind == 'sales':
        url = reverse('sales-invoice-list')
        model = SalesInvoice
        payload = {
            'customer': data['customer'].pk,
            'tire_items': [
                {'tire': data['tires'][0].pk, 'quantity': 1, 'unit_price': str(MAX_TOTAL)},
            ],
        }
    else:
        url = reverse('purchase-invoice-list')
        model = PurchaseInvoice
        payload = {
            'supplier': data['supplier'].pk,
            'tire_items': [
                {'tire': data['tires'][0].pk, 'quantity': 1, 'unit_cost': str(MAX_TOTAL)},
            ],
        }

    response = auth_client_manager.post(url, payload, format='json')

    assert response.status_code == 201, response.data
    assert Decimal(response.data['total_amount']) == MAX_TOTAL
    assert model.objects.get().total_amount == MAX_TOTAL
    assert auth_client_manager.get(url).status_code == 200


@pytest.mark.django_db
def test_discounted_total_within_capacity_is_accepted(auth_client_manager, total_bounds_data):
    data = total_bounds_data
    response = auth_client_manager.post(reverse('sales-invoice-list'), {
        'customer': data['customer'].pk,
        'discount_percent': '50.00',
        'tire_items': [
            {'tire': data['tires'][0].pk, 'quantity': 2, 'unit_price': '600000000000.00'},
        ],
    }, format='json')

    assert response.status_code == 201, response.data
    assert SalesInvoice.objects.get().total_amount == Decimal('600000000000.00')
