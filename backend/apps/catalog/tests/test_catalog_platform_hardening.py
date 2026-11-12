from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.catalog.models import Brand, Size, StockMovement, StockMovementType, Tire
from apps.catalog.services import repair_stock_projection_service
from apps.customers.models import Customer
from apps.invoices.services import create_sales_invoice_service, create_sales_return_service
from utils.domain import DomainValidationError

User = get_user_model()


@pytest.mark.django_db
def test_superuser_with_technician_role_sees_cost_fields_and_can_order_by_purchase_price():
    superuser = User.objects.create_user(
        username='super_tech',
        password='StrongPassword123!',
        role=UserRole.TECHNICIAN,
        is_superuser=True,
        is_staff=True,
    )
    client = APIClient()
    client.force_authenticate(user=superuser)

    brand = Brand.objects.create(brand_name='SuperBrand')
    size = Size.objects.create(size_name='215/55R17')
    tire1 = Tire.objects.create(
        tire_name='Tire A',
        brand=brand,
        size=size,
        stock_quantity=5,
        sale_price=Decimal('2000.00'),
        purchase_price=Decimal('1500.00'),
        min_stock_alert=10,
    )
    Tire.objects.create(
        tire_name='Tire B',
        brand=brand,
        size=size,
        stock_quantity=5,
        sale_price=Decimal('1800.00'),
        purchase_price=Decimal('1000.00'),
        min_stock_alert=10,
    )
    StockMovement.objects.create(
        tire=tire1,
        quantity=5,
        movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=5,
        unit_cost=Decimal('1500.00'),
        user=superuser,
    )

    res_tires = client.get(f"{reverse('tire-list')}?ordering=purchase_price")
    assert res_tires.status_code == 200
    assert res_tires.data['results'][0]['tire_name'] == 'Tire B'
    assert 'purchase_price' in res_tires.data['results'][0]

    res_moves = client.get(reverse('stock-movement-list'))
    assert res_moves.status_code == 200
    assert 'unit_cost' in res_moves.data['results'][0]
    assert 'purchase_invoice' in res_moves.data['results'][0]


@pytest.mark.django_db
def test_low_stock_endpoint_supports_filtering_search_and_ordering(auth_client_manager):
    b1 = Brand.objects.create(brand_name='LowBrandOne')
    b2 = Brand.objects.create(brand_name='LowBrandTwo')
    s1 = Size.objects.create(size_name='185/65R15')
    Tire.objects.create(
        tire_name='Low Alpha',
        brand=b1,
        size=s1,
        stock_quantity=1,
        sale_price=Decimal('1000.00'),
        purchase_price=Decimal('700.00'),
        min_stock_alert=5,
    )
    Tire.objects.create(
        tire_name='Low Beta',
        brand=b2,
        size=s1,
        stock_quantity=2,
        sale_price=Decimal('1200.00'),
        purchase_price=Decimal('800.00'),
        min_stock_alert=5,
    )

    url = reverse('tire-low-stock')
    res_brand = auth_client_manager.get(f'{url}?brand={b1.pk}')
    assert res_brand.status_code == 200
    assert len(res_brand.data['results']) == 1
    assert res_brand.data['results'][0]['tire_name'] == 'Low Alpha'

    res_search = auth_client_manager.get(f'{url}?search=Beta')
    assert res_search.status_code == 200
    assert len(res_search.data['results']) == 1
    assert res_search.data['results'][0]['tire_name'] == 'Low Beta'

    res_ord = auth_client_manager.get(f'{url}?ordering=-sale_price')
    assert res_ord.status_code == 200
    assert [r['tire_name'] for r in res_ord.data['results']] == ['Low Beta', 'Low Alpha']


@pytest.mark.django_db
def test_stock_movement_filters_sales_return_and_falls_back_user_name(auth_client_warehouse, manager_user):
    no_fullname_user = User.objects.create_user(
        username='plain_wh',
        password='StrongPassword123!',
        role=UserRole.WAREHOUSE,
        full_name='',
    )
    brand = Brand.objects.create(brand_name='ReturnMoveBrand')
    size = Size.objects.create(size_name='195/65R15')
    tire = Tire.objects.create(
        tire_name='ReturnMoveTire',
        brand=brand,
        size=size,
        stock_quantity=10,
        sale_price=Decimal('1000.00'),
        purchase_price=Decimal('600.00'),
    )
    StockMovement.objects.create(
        tire=tire,
        quantity=10,
        movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=10,
        unit_cost=Decimal('600.00'),
        user=no_fullname_user,
    )
    StockMovement.objects.create(
        tire=tire,
        quantity=1,
        movement_type=StockMovementType.MANUAL_ADJUSTMENT,
        balance_after=11,
        unit_cost=Decimal('600.00'),
        user=None,
    )
    tire.stock_quantity = 11
    tire.save(update_fields=['stock_quantity'])

    customer = Customer.objects.create(full_name='Return Customer', phone_number='09128887766')
    invoice = create_sales_invoice_service(
        customer=customer,
        vehicle=None,
        tire_items_data=[{'tire': tire, 'quantity': 2}],
        service_items_data=[],
        status='CONFIRMED',
        payment_status='UNPAID',
        created_by=manager_user,
    )
    sales_item = invoice.tire_items.first()
    sales_return = create_sales_return_service(
        invoice=invoice,
        items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
        reason='Defective tread',
        user=no_fullname_user,
    )

    res = auth_client_warehouse.get(f"{reverse('stock-movement-list')}?sales_return={sales_return.pk}")
    assert res.status_code == 200
    assert len(res.data['results']) == 1
    row = res.data['results'][0]
    assert row['sales_return'] == sales_return.pk
    assert row['user_name'] == 'plain_wh'

    res_all = auth_client_warehouse.get(reverse('stock-movement-list'))
    null_user_row = next(r for r in res_all.data['results'] if r['user'] is None)
    assert null_user_row['user_name'] == ''


@pytest.mark.django_db
def test_repair_stock_projection_missing_tire_raises_domain_validation(manager_user):
    with pytest.raises(DomainValidationError, match='999999'):
        repair_stock_projection_service(tire_id=999999, reason='repair missing', user=manager_user)
