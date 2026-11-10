from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer
from apps.invoices.models import InvoiceStatus
from apps.invoices.services import create_sales_invoice_service, create_sales_return_service
from apps.services_app.models import Service


@pytest.fixture
def brand_sale_data(db):
    size = Size.objects.create(size_name='195/65R15')
    tires = []
    for name in ('Brand A', 'Brand B'):
        brand = Brand.objects.create(brand_name=name)
        tires.append(Tire.objects.create(
            tire_name=f'{name} tire', brand=brand, size=size,
            stock_quantity=50, purchase_price=Decimal('40.00'),
            sale_price=Decimal('100.00'),
        ))
    customer = Customer.objects.create(full_name='Discount customer', phone_number='09112223344')
    service = Service.objects.create(service_name='Balancing', price=Decimal('200.00'))
    return customer, tires, service


def create_mixed_invoice(brand_sale_data, manager_user, **discount):
    customer, tires, service = brand_sale_data
    return create_sales_invoice_service(
        customer=customer, vehicle=None,
        tire_items_data=[
            {'tire': tires[0], 'quantity': 2, 'unit_price': Decimal('100.00')},
            {'tire': tires[1], 'quantity': 1, 'unit_price': Decimal('100.00')},
        ],
        service_items_data=[{'service': service, 'quantity': 1, 'unit_price': Decimal('200.00')}],
        created_by=manager_user, **discount,
    )


def get_brand_rows(client, **params):
    response = client.get(reverse('sales-by-brand-report'), params)
    assert response.status_code == 200
    assert isinstance(response.data, list)
    for row in response.data:
        assert set(row) == {'brand_name', 'total_quantity', 'total_revenue'}
        assert isinstance(row['total_revenue'], float)
    return response.data


@pytest.mark.django_db
@pytest.mark.parametrize('discount', [
    {'discount_amount': Decimal('100.00')},
    {'discount_percent': Decimal('20.00')},
])
def test_mixed_service_and_tires_allocate_discount_and_discounted_partial_return(
    auth_client_manager, manager_user, brand_sale_data, discount,
):
    invoice = create_mixed_invoice(brand_sale_data, manager_user, **discount)
    assert invoice.total_amount == Decimal('400.00')
    assert get_brand_rows(auth_client_manager) == [
        {'brand_name': 'Brand A', 'total_quantity': 2, 'total_revenue': 160.0},
        {'brand_name': 'Brand B', 'total_quantity': 1, 'total_revenue': 80.0},
    ]

    item = invoice.tire_items.get(tire=brand_sale_data[1][0])
    returned = create_sales_return_service(
        invoice=invoice,
        items_data=[{'sales_invoice_tire_item_id': item.pk, 'quantity': 1}],
        reason='Partial discounted return', user=manager_user,
    )
    assert returned.total_refund_amount == Decimal('80.00')
    assert get_brand_rows(auth_client_manager) == [
        {'brand_name': 'Brand A', 'total_quantity': 1, 'total_revenue': 80.0},
        {'brand_name': 'Brand B', 'total_quantity': 1, 'total_revenue': 80.0},
    ]
    assert get_brand_rows(auth_client_manager, brand_id=brand_sale_data[1][0].brand_id) == [
        {'brand_name': 'Brand A', 'total_quantity': 1, 'total_revenue': 80.0},
    ]
    profitability = auth_client_manager.get(reverse('profitability-report'))
    assert profitability.status_code == 200
    assert sum(row['total_revenue'] for row in profitability.data) == 160.0


@pytest.mark.django_db
@pytest.mark.parametrize('discount', [
    {'discount_amount': Decimal('100.00')},
    {'discount_percent': Decimal('20.00')},
])
def test_full_discounted_tire_return_leaves_no_phantom_brand_revenue(
    auth_client_manager, manager_user, brand_sale_data, discount,
):
    invoice = create_mixed_invoice(brand_sale_data, manager_user, **discount)
    returned = create_sales_return_service(
        invoice=invoice,
        items_data=[
            {'sales_invoice_tire_item_id': item.pk, 'quantity': item.quantity}
            for item in invoice.tire_items.all()
        ],
        reason='All tires returned', user=manager_user,
    )
    assert returned.total_refund_amount == Decimal('240.00')
    assert get_brand_rows(auth_client_manager) == [
        {'brand_name': 'Brand A', 'total_quantity': 0, 'total_revenue': 0.0},
        {'brand_name': 'Brand B', 'total_quantity': 0, 'total_revenue': 0.0},
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(('discount', 'expected_revenue'), [
    ({}, 200.0),
    ({'discount_amount': Decimal('500.00')}, 0.0),
    ({'discount_percent': Decimal('100.00')}, 0.0),
])
def test_no_discount_and_fully_discounted_invoices_preserve_brand_contract(
    auth_client_manager, manager_user, brand_sale_data, discount, expected_revenue,
):
    create_mixed_invoice(brand_sale_data, manager_user, **discount)
    rows = get_brand_rows(auth_client_manager)
    assert rows == [
        {'brand_name': 'Brand A', 'total_quantity': 2, 'total_revenue': expected_revenue},
        {'brand_name': 'Brand B', 'total_quantity': 1, 'total_revenue': expected_revenue / 2},
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(('discount', 'revenues'), [
    ({'discount_percent': Decimal('20.00')}, [Decimal('160.00'), Decimal('80.00')]),
    ({'discount_percent': Decimal('33.33')}, [Decimal('133.34'), Decimal('66.67')]),
    ({'discount_amount': Decimal('1.00')}, [Decimal('199.60'), Decimal('99.80')]),
])
def test_discount_division_preserves_fractional_revenue_and_full_return(
    auth_client_manager, manager_user, brand_sale_data, discount, revenues,
):
    invoice = create_mixed_invoice(brand_sale_data, manager_user, **discount)
    assert get_brand_rows(auth_client_manager) == [
        {'brand_name': tire.brand.brand_name, 'total_quantity': quantity, 'total_revenue': float(revenue)}
        for tire, quantity, revenue in zip(brand_sale_data[1], [2, 1], revenues)
    ]
    profitability = auth_client_manager.get(reverse('profitability-report'))
    assert profitability.status_code == 200
    by_tire = {row['tire_id']: row for row in profitability.data}
    for tire, quantity, revenue in zip(brand_sale_data[1], [2, 1], revenues):
        assert by_tire[tire.pk]['total_revenue'] == float(revenue)
        assert by_tire[tire.pk]['total_profit'] == float(revenue - quantity * Decimal('40.00'))

    returned = create_sales_return_service(
        invoice=invoice,
        items_data=[
            {'sales_invoice_tire_item_id': item.pk, 'quantity': item.quantity}
            for item in invoice.tire_items.all()
        ],
        reason='Fractional discount full return', user=manager_user,
    )
    assert returned.total_refund_amount == sum(revenues)
    assert all(row['total_revenue'] == 0.0 for row in get_brand_rows(auth_client_manager))
    profitability = auth_client_manager.get(reverse('profitability-report'))
    assert profitability.status_code == 200
    assert all(row['total_revenue'] == 0.0 and row['total_profit'] == 0.0 for row in profitability.data)


@pytest.mark.django_db
@pytest.mark.parametrize('status', [InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED])
def test_nonconfirmed_discounted_sales_and_returns_are_excluded(
    auth_client_manager, manager_user, brand_sale_data, status,
):
    invoice = create_mixed_invoice(brand_sale_data, manager_user, discount_amount=Decimal('100.00'))
    item = invoice.tire_items.first()
    create_sales_return_service(
        invoice=invoice,
        items_data=[{'sales_invoice_tire_item_id': item.pk, 'quantity': 1}],
        reason='Excluded invoice return', user=manager_user,
    )
    invoice.status = status
    invoice.save(update_fields=['status'])
    assert get_brand_rows(auth_client_manager) == []
