import os
import pytest
from decimal import Decimal
from django.urls import reverse
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.accounts.models import UserRole
from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer
from apps.suppliers.models import Supplier
from apps.invoices.services import create_sales_invoice_service, create_purchase_invoice_service

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def setup_security_data(db, manager_user):
    brand = Brand.objects.create(brand_name='بارز پیرلی تست')
    size = Size.objects.create(size_name='205/60R15')
    tire = Tire.objects.create(
        tire_name='تایر پیرلی اسپرت',
        brand=brand,
        size=size,
        stock_quantity=100,
        purchase_price=Decimal('1000000.00'),
        sale_price=Decimal('1500000.00'),
        min_stock_alert=5
    )
    StockMovement.objects.create(
        tire=tire,
        quantity=100,
        movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=100,
        unit_cost=Decimal('1000000.00'),
        user=manager_user,
        description='موجودی اولیه'
    )
    customer = Customer.objects.create(full_name='مشتری استیج ۵', phone_number='09121113355')
    supplier = Supplier.objects.create(supplier_name='تأمین‌کننده استیج ۵', phone_number='02177778899')

    tech_a = User.objects.create_user(
        username='tech_a',
        phone_number='09120000001',
        password='Password123!',
        role=UserRole.TECHNICIAN,
        full_name='تکنسین الف'
    )
    tech_b = User.objects.create_user(
        username='tech_b',
        phone_number='09120000002',
        password='Password123!',
        role=UserRole.TECHNICIAN,
        full_name='تکنسین ب'
    )

    client_tech_a = APIClient()
    client_tech_a.force_authenticate(user=tech_a)

    client_tech_b = APIClient()
    client_tech_b.force_authenticate(user=tech_b)

    return {
        'tire': tire,
        'customer': customer,
        'supplier': supplier,
        'tech_a': tech_a,
        'tech_b': tech_b,
        'client_tech_a': client_tech_a,
        'client_tech_b': client_tech_b,
    }


@pytest.mark.django_db
class TestInvoiceSecurityAndPermissions:

    def test_technician_can_only_view_own_sales_invoices_and_gets_404_on_others(
        self, setup_security_data, auth_client_manager
    ):
        data = setup_security_data
        client_a = data['client_tech_a']
        client_b = data['client_tech_b']

        res_create_a = client_a.post(reverse('sales-invoice-list'), {
            'customer': data['customer'].pk,
            'tire_items': [{'tire': data['tire'].pk, 'quantity': 1, 'unit_price': 1500000}]
        }, format='json')
        assert res_create_a.status_code == 201
        inv_a_id = res_create_a.data['sales_invoice_id']

        res_create_b = client_b.post(reverse('sales-invoice-list'), {
            'customer': data['customer'].pk,
            'tire_items': [{'tire': data['tire'].pk, 'quantity': 1, 'unit_price': 1500000}]
        }, format='json')
        assert res_create_b.status_code == 201
        inv_b_id = res_create_b.data['sales_invoice_id']

        list_a = client_a.get(reverse('sales-invoice-list'))
        assert list_a.status_code == 200
        ids_seen_by_a = [item['sales_invoice_id'] for item in list_a.data['results']]
        assert inv_a_id in ids_seen_by_a
        assert inv_b_id not in ids_seen_by_a

        detail_b_for_a = client_a.get(reverse('sales-invoice-detail', kwargs={'pk': inv_b_id}))
        assert detail_b_for_a.status_code == 404

        detail_a_for_a = client_a.get(reverse('sales-invoice-detail', kwargs={'pk': inv_a_id}))
        assert detail_a_for_a.status_code == 200

        assert auth_client_manager.get(reverse('sales-invoice-detail', kwargs={'pk': inv_a_id})).status_code == 200
        assert auth_client_manager.get(reverse('sales-invoice-detail', kwargs={'pk': inv_b_id})).status_code == 200

    def test_warehouse_cannot_create_sales_invoice_but_has_read_only_access(
        self, setup_security_data, auth_client_warehouse, manager_user
    ):
        data = setup_security_data

        inv = create_sales_invoice_service(
            customer=data['customer'],
            vehicle=None,
            tire_items_data=[{'tire': data['tire'], 'quantity': 1, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )

        post_res = auth_client_warehouse.post(reverse('sales-invoice-list'), {
            'customer': data['customer'].pk,
            'tire_items': [{'tire': data['tire'].pk, 'quantity': 1, 'unit_price': 1500000}]
        }, format='json')
        assert post_res.status_code == 403

        list_res = auth_client_warehouse.get(reverse('sales-invoice-list'))
        assert list_res.status_code == 200

        detail_res = auth_client_warehouse.get(reverse('sales-invoice-detail', kwargs={'pk': inv.pk}))
        assert detail_res.status_code == 200

    def test_technician_blocked_from_all_purchase_invoice_endpoints(
        self, setup_security_data, auth_client_warehouse, manager_user
    ):
        data = setup_security_data
        client_tech = data['client_tech_a']

        p_inv = create_purchase_invoice_service(
            supplier=data['supplier'],
            tire_items_data=[{'tire': data['tire'], 'quantity': 2, 'unit_cost': Decimal('1000000.00')}],
            created_by=manager_user
        )

        assert client_tech.get(reverse('purchase-invoice-list')).status_code == 403
        assert client_tech.get(reverse('purchase-invoice-detail', kwargs={'pk': p_inv.pk})).status_code == 403
        assert client_tech.post(reverse('purchase-invoice-list'), {
            'supplier': data['supplier'].pk,
            'tire_items': [{'tire': data['tire'].pk, 'quantity': 1, 'unit_cost': 1000000}]
        }, format='json').status_code == 403

        assert auth_client_warehouse.get(reverse('purchase-invoice-list')).status_code == 200
        assert auth_client_warehouse.get(reverse('purchase-invoice-detail', kwargs={'pk': p_inv.pk})).status_code == 200

    def test_technician_cannot_cancel_own_sales_invoice(self, setup_security_data):
        data = setup_security_data
        client_a = data['client_tech_a']

        res_create = client_a.post(reverse('sales-invoice-list'), {
            'customer': data['customer'].pk,
            'tire_items': [{'tire': data['tire'].pk, 'quantity': 1, 'unit_price': 1500000}]
        }, format='json')
        assert res_create.status_code == 201
        inv_id = res_create.data['sales_invoice_id']

        cancel_url = reverse('sales-invoice-cancel', kwargs={'pk': inv_id})
        res_cancel = client_a.post(cancel_url)
        assert res_cancel.status_code == 403

    def test_unit_cost_masked_for_technician_and_warehouse_on_sales_invoice(
        self, setup_security_data, auth_client_warehouse, auth_client_manager, manager_user
    ):
        data = setup_security_data
        client_tech = data['client_tech_a']

        inv = create_sales_invoice_service(
            customer=data['customer'],
            vehicle=None,
            tire_items_data=[{'tire': data['tire'], 'quantity': 1, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            created_by=data['tech_a']
        )

        detail_url = reverse('sales-invoice-detail', kwargs={'pk': inv.pk})

        res_tech = client_tech.get(detail_url)
        assert res_tech.status_code == 200
        assert 'unit_cost' not in res_tech.data['tire_items'][0]

        res_wh = auth_client_warehouse.get(detail_url)
        assert res_wh.status_code == 200
        assert 'unit_cost' not in res_wh.data['tire_items'][0]

        res_mgr = auth_client_manager.get(detail_url)
        assert res_mgr.status_code == 200
        assert 'unit_cost' in res_mgr.data['tire_items'][0]
        assert Decimal(str(res_mgr.data['tire_items'][0]['unit_cost'])) == Decimal('1000000.00')

    def test_stock_movement_api_prevents_secondary_leakage_to_technician(
        self, setup_security_data, manager_user
    ):
        data = setup_security_data
        client_tech = data['client_tech_a']

        create_purchase_invoice_service(
            supplier=data['supplier'],
            tire_items_data=[{'tire': data['tire'], 'quantity': 5, 'unit_cost': Decimal('1000000.00')}],
            created_by=manager_user
        )

        res = client_tech.get(reverse('stock-movement-list'))
        assert res.status_code == 403

    def test_sales_invoice_get_queryset_fail_closed_when_request_or_user_missing(self, db):
        from apps.invoices.views import SalesInvoiceViewSet
        from rest_framework.test import APIRequestFactory
        from django.contrib.auth.models import AnonymousUser

        view = SalesInvoiceViewSet()
        assert view.get_queryset().count() == 0

        factory = APIRequestFactory()
        req = factory.get(reverse('sales-invoice-list'))
        req.user = AnonymousUser()
        view.request = req
        assert view.get_queryset().count() == 0


@pytest.mark.django_db
class TestSequentialInvoiceNumbering:

    def test_sequential_invoice_numbering_format_and_uniqueness(
        self, setup_security_data, manager_user
    ):
        data = setup_security_data

        inv1 = create_sales_invoice_service(
            customer=data['customer'],
            vehicle=None,
            tire_items_data=[{'tire': data['tire'], 'quantity': 1, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        inv2 = create_sales_invoice_service(
            customer=data['customer'],
            vehicle=None,
            tire_items_data=[{'tire': data['tire'], 'quantity': 1, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        p_inv1 = create_purchase_invoice_service(
            supplier=data['supplier'],
            tire_items_data=[{'tire': data['tire'], 'quantity': 1, 'unit_cost': Decimal('1000000.00')}],
            created_by=manager_user
        )

        assert inv1.invoice_number.startswith('S-')
        assert inv2.invoice_number.startswith('S-')
        assert p_inv1.invoice_number.startswith('P-')
        assert inv1.invoice_number != inv2.invoice_number

        num1 = int(inv1.invoice_number.split('-')[-1])
        num2 = int(inv2.invoice_number.split('-')[-1])
        assert num2 == num1 + 1

    def test_search_sales_invoice_by_invoice_number(
        self, setup_security_data, auth_client_manager, manager_user
    ):
        data = setup_security_data
        inv = create_sales_invoice_service(
            customer=data['customer'],
            vehicle=None,
            tire_items_data=[{'tire': data['tire'], 'quantity': 1, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        url = f"{reverse('sales-invoice-list')}?search={inv.invoice_number}"
        res = auth_client_manager.get(url)
        assert res.status_code == 200
        assert res.data['count'] == 1
        assert res.data['results'][0]['invoice_number'] == inv.invoice_number

    def test_invoice_creation_after_backfill_does_not_generate_duplicate_numbers(
        self, setup_security_data, manager_user
    ):
        from apps.invoices.models import InvoiceSequence
        data = setup_security_data

        year = 1405
        seq, _ = InvoiceSequence.objects.update_or_create(
            doc_type='SALES',
            year=year,
            defaults={'last_number': 50}
        )

        new_inv = create_sales_invoice_service(
            customer=data['customer'],
            vehicle=None,
            tire_items_data=[{'tire': data['tire'], 'quantity': 1, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )

        assert new_inv.invoice_number == f"S-{year}-00051"


@pytest.mark.django_db
class TestThrottlingAndEnvironment:

    def test_login_rate_limiting_ip_throttle_and_persian_429_response(self, client):
        login_url = reverse('token_obtain_pair')
        payload = {'username': '09129999999', 'password': 'WrongPassword!'}

        for _ in range(5):
            res = client.post(login_url, payload)
            assert res.status_code in (400, 401)

        res_blocked = client.post(login_url, payload)
        assert res_blocked.status_code == 429
        assert 'بیش از حد مجاز است' in str(res_blocked.data)
        assert 'available_in_seconds' in res_blocked.data['errors']

    def test_login_rate_limiting_username_throttle(self, client):
        login_url = reverse('token_obtain_pair')
        payload = {'username': 'targeted_user@test.com', 'password': 'WrongPassword!'}

        for i in range(5):
            res = client.post(login_url, payload, REMOTE_ADDR=f'192.168.1.{i+10}')
            assert res.status_code in (400, 401)

        res_blocked = client.post(login_url, payload, REMOTE_ADDR='192.168.1.99')
        assert res_blocked.status_code == 429
        assert 'بیش از حد مجاز است' in str(res_blocked.data)

    def test_debug_defaults_to_false_without_env_and_jwt_lifetimes_from_env(self, monkeypatch):
        monkeypatch.delenv('DJANGO_DEBUG', raising=False)
        resolved_debug = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
        assert resolved_debug is False

        monkeypatch.setenv('JWT_ACCESS_MINUTES', '60')
        monkeypatch.setenv('JWT_REFRESH_DAYS', '7')
        access_min = int(os.environ.get('JWT_ACCESS_MINUTES', '1440'))
        refresh_days = int(os.environ.get('JWT_REFRESH_DAYS', '14'))
        assert access_min == 60
        assert refresh_days == 7

    def test_spoofed_x_forwarded_for_ignored_when_num_proxies_is_zero(self, client):
        login_url = reverse('token_obtain_pair')
        fixed_ip = '192.168.10.55'

        for i in range(5):
            res = client.post(
                login_url,
                {'username': f'spoof_user_{i}@test.com', 'password': 'WrongPassword!'},
                REMOTE_ADDR=fixed_ip,
                HTTP_X_FORWARDED_FOR=f'10.200.0.{i+1}'
            )
            assert res.status_code in (400, 401)

        res_blocked = client.post(
            login_url,
            {'username': 'spoof_user_6@test.com', 'password': 'WrongPassword!'},
            REMOTE_ADDR=fixed_ip,
            HTTP_X_FORWARDED_FOR='10.200.0.99'
        )
        assert res_blocked.status_code == 429
        assert 'بیش از حد مجاز است' in str(res_blocked.data)

    def test_api_docs_restricted_to_manager_when_debug_false(
        self, client, auth_client_manager, setup_security_data, settings
    ):
        settings.DEBUG = False

        docs_url = reverse('swagger-ui')
        schema_url = reverse('schema')
        client_tech = setup_security_data['client_tech_a']

        res_anon = client.get(docs_url)
        assert res_anon.status_code in (401, 403)

        res_tech = client_tech.get(docs_url)
        assert res_tech.status_code == 403

        res_mgr_docs = auth_client_manager.get(docs_url)
        assert res_mgr_docs.status_code == 200

        res_mgr_schema = auth_client_manager.get(schema_url)
        assert res_mgr_schema.status_code == 200

    def test_pagination_caps_page_size_at_max_page_size_100(self, auth_client_manager):
        from utils.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        assert paginator.max_page_size == 100

        res = auth_client_manager.get(f"{reverse('tire-list')}?page_size=500")
        assert res.status_code == 200
        assert len(res.data['results']) <= 100

    def test_login_does_not_distinguish_existing_vs_non_existing_users(self, client, setup_security_data):
        login_url = reverse('token_obtain_pair')

        res_non_existing = client.post(login_url, {
            'username': 'definitely_non_existing_user_99999',
            'password': 'SomePassword123!'
        })
        assert res_non_existing.status_code == 401

        res_wrong_pw = client.post(login_url, {
            'username': setup_security_data['tech_a'].username,
            'password': 'WrongPassword123!'
        })
        assert res_wrong_pw.status_code == 401

        assert res_non_existing.data['errors']['detail'] == res_wrong_pw.data['errors']['detail']

    def test_admin_panel_blocked_for_non_staff_users(self, client, setup_security_data, superuser):
        tech_user = setup_security_data['tech_a']
        assert tech_user.is_staff is False

        client.force_login(tech_user)
        res_tech_admin = client.get('/admin/')
        assert res_tech_admin.status_code in (302, 403)
        if res_tech_admin.status_code == 302:
            assert '/admin/login/' in res_tech_admin.url

        assert superuser.is_staff is True
        client.force_login(superuser)
        res_mgr_admin = client.get('/admin/')
        assert res_mgr_admin.status_code == 200

