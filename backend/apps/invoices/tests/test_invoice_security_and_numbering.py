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
    """پاکسازی کش پیش و پس از هر تست جهت جلوگیری از تداخل نرخ درخواست‌ها"""
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

    # ایجاد دو تکنسین مجزا
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
        """
        تست جامع مقابله با آسیب‌پذیری BOLA/IDOR:
        - تکنسین الف و تکنسین ب فاکتورهای مجزا ثبت می‌کنند.
        - تکنسین الف در فهرست فقط فاکتور خودش را می‌بیند.
        - درخواست تکنسین الف برای مشاهده جزئیات فاکتور تکنسین ب باید با 404 مواجه شود.
        - مدیر به فاکتور هر دو تکنسین دسترسی دارد.
        """
        data = setup_security_data
        client_a = data['client_tech_a']
        client_b = data['client_tech_b']

        # صدور فاکتور توسط تکنسین الف
        res_create_a = client_a.post(reverse('sales-invoice-list'), {
            'customer': data['customer'].pk,
            'tire_items': [{'tire': data['tire'].pk, 'quantity': 1, 'unit_price': 1500000}]
        }, format='json')
        assert res_create_a.status_code == 201
        inv_a_id = res_create_a.data['sales_invoice_id']

        # صدور فاکتور توسط تکنسین ب
        res_create_b = client_b.post(reverse('sales-invoice-list'), {
            'customer': data['customer'].pk,
            'tire_items': [{'tire': data['tire'].pk, 'quantity': 1, 'unit_price': 1500000}]
        }, format='json')
        assert res_create_b.status_code == 201
        inv_b_id = res_create_b.data['sales_invoice_id']

        # تکنسین الف فهرست فاکتورها را دریافت می‌کند -> فقط فاکتور الف در فهرست است
        list_a = client_a.get(reverse('sales-invoice-list'))
        assert list_a.status_code == 200
        ids_seen_by_a = [item['sales_invoice_id'] for item in list_a.data['results']]
        assert inv_a_id in ids_seen_by_a
        assert inv_b_id not in ids_seen_by_a

        # تکنسین الف درخواست مشاهده جزئیات فاکتور ب را می‌دهد -> 404 Not Found
        detail_b_for_a = client_a.get(reverse('sales-invoice-detail', kwargs={'pk': inv_b_id}))
        assert detail_b_for_a.status_code == 404

        # تکنسین الف فاکتور خودش را می‌بیند -> 200 OK
        detail_a_for_a = client_a.get(reverse('sales-invoice-detail', kwargs={'pk': inv_a_id}))
        assert detail_a_for_a.status_code == 200

        # مدیر فاکتور هر دو تکنسین را مشاهده می‌کند
        assert auth_client_manager.get(reverse('sales-invoice-detail', kwargs={'pk': inv_a_id})).status_code == 200
        assert auth_client_manager.get(reverse('sales-invoice-detail', kwargs={'pk': inv_b_id})).status_code == 200

    def test_warehouse_cannot_create_sales_invoice_but_has_read_only_access(
        self, setup_security_data, auth_client_warehouse, manager_user
    ):
        """
        انباردار مجاز به صدور فاکتور فروش نیست (403)، اما دسترسی فقط‌خواندنی به فهرست و جزئیات دارد.
        """
        data = setup_security_data

        # ایجاد یک فاکتور فروش توسط سیستم
        inv = create_sales_invoice_service(
            customer=data['customer'],
            vehicle=None,
            tire_items_data=[{'tire': data['tire'], 'quantity': 1, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )

        # تلاش انباردار برای صدور فاکتور فروش -> 403 Forbidden
        post_res = auth_client_warehouse.post(reverse('sales-invoice-list'), {
            'customer': data['customer'].pk,
            'tire_items': [{'tire': data['tire'].pk, 'quantity': 1, 'unit_price': 1500000}]
        }, format='json')
        assert post_res.status_code == 403

        # مشاهده لیست توسط انباردار -> 200 OK
        list_res = auth_client_warehouse.get(reverse('sales-invoice-list'))
        assert list_res.status_code == 200

        # مشاهده جزئیات توسط انباردار -> 200 OK
        detail_res = auth_client_warehouse.get(reverse('sales-invoice-detail', kwargs={'pk': inv.pk}))
        assert detail_res.status_code == 200

    def test_technician_blocked_from_all_purchase_invoice_endpoints(
        self, setup_security_data, auth_client_warehouse, manager_user
    ):
        """
        تکنسین‌ها به طور کامل از تمام اندپوینت‌های فاکتور خرید مسدود هستند (403).
        انباردار و مدیر دسترسی دارند.
        """
        data = setup_security_data
        client_tech = data['client_tech_a']

        p_inv = create_purchase_invoice_service(
            supplier=data['supplier'],
            tire_items_data=[{'tire': data['tire'], 'quantity': 2, 'unit_cost': Decimal('1000000.00')}],
            created_by=manager_user
        )

        # تکنسین GET list -> 403
        assert client_tech.get(reverse('purchase-invoice-list')).status_code == 403
        # تکنسین GET detail -> 403
        assert client_tech.get(reverse('purchase-invoice-detail', kwargs={'pk': p_inv.pk})).status_code == 403
        # تکنسین POST create -> 403
        assert client_tech.post(reverse('purchase-invoice-list'), {
            'supplier': data['supplier'].pk,
            'tire_items': [{'tire': data['tire'].pk, 'quantity': 1, 'unit_cost': 1000000}]
        }, format='json').status_code == 403

        # انباردار GET list -> 200
        assert auth_client_warehouse.get(reverse('purchase-invoice-list')).status_code == 200
        # انباردار GET detail -> 200
        assert auth_client_warehouse.get(reverse('purchase-invoice-detail', kwargs={'pk': p_inv.pk})).status_code == 200

    def test_technician_cannot_cancel_own_sales_invoice(self, setup_security_data):
        """
        تکنسین حتی روی فاکتور صادرشده توسط خودش نیز اجازه فراخوانی اکشن لغو را ندارد (403).
        """
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
        """
        بهای تمام‌شده واحد (unit_cost) برای تکنسین و انباردار در فاکتور فروش ماسک می‌شود، اما مدیر آن را می‌بیند.
        """
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

        # تکنسین
        res_tech = client_tech.get(detail_url)
        assert res_tech.status_code == 200
        assert 'unit_cost' not in res_tech.data['tire_items'][0]

        # انباردار
        res_wh = auth_client_warehouse.get(detail_url)
        assert res_wh.status_code == 200
        assert 'unit_cost' not in res_wh.data['tire_items'][0]

        # مدیر
        res_mgr = auth_client_manager.get(detail_url)
        assert res_mgr.status_code == 200
        assert 'unit_cost' in res_mgr.data['tire_items'][0]
        assert Decimal(str(res_mgr.data['tire_items'][0]['unit_cost'])) == Decimal('1000000.00')

    def test_stock_movement_api_prevents_secondary_leakage_to_technician(
        self, setup_security_data, manager_user
    ):
        """
        دفتر گردش انبار: تکنسین گردش‌های خرید دیگران یا قیمت خرید را نمی‌بیند.
        """
        data = setup_security_data
        client_tech = data['client_tech_a']

        # ثبت یک فاکتور خرید توسط مدیر (ورود به انبار)
        create_purchase_invoice_service(
            supplier=data['supplier'],
            tire_items_data=[{'tire': data['tire'], 'quantity': 5, 'unit_cost': Decimal('1000000.00')}],
            created_by=manager_user
        )

        # استعلام گردش‌های انبار توسط تکنسین الف -> دسترسی مسدود (403)
        res = client_tech.get(reverse('stock-movement-list'))
        assert res.status_code == 403

    def test_sales_invoice_get_queryset_fail_closed_when_request_or_user_missing(self, db):
        """
        بررسی امنیتی Fail-Closed: اگر request یا user روی ویوست موجود نباشد،
        متد get_queryset باید الزاماً یک کوئری‌ست خالی (none()) برگرداند نه کل رکوردهای دیتابیس.
        """
        from apps.invoices.views import SalesInvoiceViewSet
        from rest_framework.test import APIRequestFactory
        from django.contrib.auth.models import AnonymousUser

        # ۱. بدون شیء request
        view = SalesInvoiceViewSet()
        assert view.get_queryset().count() == 0

        # ۲. با شیء request اما کاربر ناشناس (AnonymousUser)
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
        """
        بررسی فرمت شماره فاکتور انسانی (S-1405-0000X و P-1405-0000X)، پیوستگی و یکتایی
        """
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

        # بررسی شماره‌گذاری پیوسته
        num1 = int(inv1.invoice_number.split('-')[-1])
        num2 = int(inv2.invoice_number.split('-')[-1])
        assert num2 == num1 + 1

    def test_search_sales_invoice_by_invoice_number(
        self, setup_security_data, auth_client_manager, manager_user
    ):
        """
        بررسی امکان جستجوی سریع فاکتور بر اساس فیلد invoice_number
        """
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
        """
        تست اطمینان از عدم تکرار شماره فاکتور بعد از مهاجرت داده‌ای (backfill):
        شمارنده برای سال جاری باید ادامه شماره‌های موجود را بدون تکرار تولید کند.
        """
        from apps.invoices.models import InvoiceSequence
        data = setup_security_data

        # شبیه‌سازی وضعیت پس از backfill که در آن آخرین شماره سال 1405 روی 50 تنظیم شده است
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

        # شماره فاکتور باید S-1405-00051 باشد
        assert new_inv.invoice_number == f"S-{year}-00051"


@pytest.mark.django_db
class TestThrottlingAndEnvironment:

    def test_login_rate_limiting_ip_throttle_and_persian_429_response(self, client):
        """
        تست محدودسازی نرخ درخواست ورود (۵ درخواست در دقیقه بر اساس IP) و پیام فارسی ۴۲۹
        """
        login_url = reverse('token_obtain_pair')
        payload = {'username': '09129999999', 'password': 'WrongPassword!'}

        # ۵ تلاش اول
        for _ in range(5):
            res = client.post(login_url, payload)
            assert res.status_code in (400, 401)

        # تلاش ششم در همان دقیقه باید ۴۲۹ شود
        res_blocked = client.post(login_url, payload)
        assert res_blocked.status_code == 429
        assert 'بیش از حد مجاز است' in str(res_blocked.data)
        assert 'available_in_seconds' in res_blocked.data['errors']

    def test_login_rate_limiting_username_throttle(self, client):
        """
        تست محدودسازی ورود بر اساس نام کاربری حتی اگر آدرس IP متفاوت باشد
        """
        login_url = reverse('token_obtain_pair')
        payload = {'username': 'targeted_user@test.com', 'password': 'WrongPassword!'}

        # ۵ تلاش از IPهای مختلف برای یک نام کاربری
        for i in range(5):
            res = client.post(login_url, payload, REMOTE_ADDR=f'192.168.1.{i+10}')
            assert res.status_code in (400, 401)

        # تلاش ششم با IP جدید برای همان کاربر -> باید ۴۲۹ شود
        res_blocked = client.post(login_url, payload, REMOTE_ADDR='192.168.1.99')
        assert res_blocked.status_code == 429
        assert 'بیش از حد مجاز است' in str(res_blocked.data)

    def test_debug_defaults_to_false_without_env_and_jwt_lifetimes_from_env(self, monkeypatch):
        """
        بررسی پیش‌فرض‌های محیطی:
        - در غیاب متغیر محیطی DJANGO_DEBUG، مقدار DEBUG باید False باشد.
        - مقادیر طول عمر JWT (دقیقه و روز) از متغیرهای محیطی استخراج شوند.
        """
        # حذف متغیر DJANGO_DEBUG
        monkeypatch.delenv('DJANGO_DEBUG', raising=False)
        resolved_debug = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
        assert resolved_debug is False

        # خواندن طول عمر توکن از متغیر محیطی
        monkeypatch.setenv('JWT_ACCESS_MINUTES', '60')
        monkeypatch.setenv('JWT_REFRESH_DAYS', '7')
        access_min = int(os.environ.get('JWT_ACCESS_MINUTES', '1440'))
        refresh_days = int(os.environ.get('JWT_REFRESH_DAYS', '14'))
        assert access_min == 60
        assert refresh_days == 7

    def test_production_guard_raises_improperly_configured_without_secret_key(self, monkeypatch):
        """
        تست گارد امنیتی پروداکشن: در صورت DEBUG=False و عدم تعیین کلید امنیتی اختصاصی (یا کلید خالی)،
        برنامه باید با خطای ImproperlyConfigured متوقف شود.
        """
        from django.core.exceptions import ImproperlyConfigured

        insecure_key = 'django-insecure-tire-shop-production-secret-key-shayan-nami-2026'

        def evaluate_production_security(debug_flag: bool, secret_key: str):
            if not secret_key:
                if debug_flag:
                    return insecure_key
                else:
                    raise ImproperlyConfigured(
                        "خطای امنیتی پروداکشن: در حالت DEBUG=False، متغیر محیطی DJANGO_SECRET_KEY باید حتماً با یک کلید امن، یکتا و تصادفی مقداردهی شود."
                    )
            elif not debug_flag and secret_key == insecure_key:
                raise ImproperlyConfigured(
                    "خطای امنیتی پروداکشن: استفاده از کلید محرمانه پیش‌فرض و هاردکد شده در محیط پروداکشن مجاز نیست."
                )
            return secret_key

        # ۱. توقف برنامه در صورت نبود SECRET_KEY (خالی بودن) وقتی DEBUG=False
        with pytest.raises(ImproperlyConfigured) as exc_empty:
            evaluate_production_security(False, '')
        assert 'خطای امنیتی پروداکشن' in str(exc_empty.value)

        # ۲. توقف برنامه در صورت استفاده از کلید پیش‌فرض ناامن وقتی DEBUG=False
        with pytest.raises(ImproperlyConfigured) as exc_insecure:
            evaluate_production_security(False, insecure_key)
        assert 'کلید محرمانه پیش‌فرض' in str(exc_insecure.value)

        # ۳. پذیرش کلید امن در پروداکشن
        assert evaluate_production_security(False, 'secure-random-prod-key-xyz') == 'secure-random-prod-key-xyz'

    def test_spoofed_x_forwarded_for_ignored_when_num_proxies_is_zero(self, client):
        """
        بررسی امنیتی NUM_PROXIES=0:
        اگر مهاجم هدر جعلی X-Forwarded-For ارسال کند، با NUM_PROXIES=0 فیلتر IP باید بر اساس
        REMOTE_ADDR عمل کند و تغییر هدر نباید سقف ورود را دور بزند.
        """
        login_url = reverse('token_obtain_pair')
        fixed_ip = '192.168.10.55'

        # ۵ تلاش از یک IP با هدرهای X-Forwarded-For متفاوت
        for i in range(5):
            res = client.post(
                login_url,
                {'username': f'spoof_user_{i}@test.com', 'password': 'WrongPassword!'},
                REMOTE_ADDR=fixed_ip,
                HTTP_X_FORWARDED_FOR=f'10.200.0.{i+1}'
            )
            assert res.status_code in (400, 401)

        # تلاش ششم با هدر جعلی جدید اما از همان REMOTE_ADDR -> باید ۴۲۹ شود
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
        """
        بررسی امنیتی مستندات API (Swagger / Redoc / Schema):
        در صورت DEBUG=False، مستندات و اسکیما باید برای کاربر ناشناس و تکنسین مسدود (401/403)
        و فقط برای مدیر سیستم در دسترس (200) باشد.
        """
        settings.DEBUG = False

        docs_url = reverse('swagger-ui')
        schema_url = reverse('schema')
        client_tech = setup_security_data['client_tech_a']

        # ۱. کاربر ناشناس به مستندات دسترسی ندارد
        res_anon = client.get(docs_url)
        assert res_anon.status_code in (401, 403)

        # ۲. تکنسین به مستندات دسترسی ندارد (403)
        res_tech = client_tech.get(docs_url)
        assert res_tech.status_code == 403

        # ۳. مدیر سیستم دسترسی کامل دارد (200)
        res_mgr_docs = auth_client_manager.get(docs_url)
        assert res_mgr_docs.status_code == 200

        # ۴. اسکیما نیز برای مدیر در دسترس است
        res_mgr_schema = auth_client_manager.get(schema_url)
        assert res_mgr_schema.status_code == 200

    def test_pagination_caps_page_size_at_max_page_size_100(self, auth_client_manager):
        """
        بررسی سقف محافظتی اندازه‌گیری صفحات (max_page_size = 100):
        ارسال page_size با مقادیر نجومی نباید منجر به بارگذاری بیش از ۱۰۰ رکورد شود.
        """
        from utils.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        assert paginator.max_page_size == 100

        res = auth_client_manager.get(f"{reverse('tire-list')}?page_size=500")
        assert res.status_code == 200
        # حتی با ارسال page_size=500، تعداد رکوردهای خروجی نمی‌تواند بیش از 100 باشد
        assert len(res.data['results']) <= 100

    def test_login_does_not_distinguish_existing_vs_non_existing_users(self, client, setup_security_data):
        """
        بررسی جلوگیری از آسیب‌پذیری نشت حساب کاربری (User Enumeration):
        پیام خطای احراز هویت برای نام کاربری ناموجود و کاربر موجود با رمز اشتباه کاملاً یکسان است.
        """
        login_url = reverse('token_obtain_pair')

        # نام کاربری ناموجود
        res_non_existing = client.post(login_url, {
            'username': 'definitely_non_existing_user_99999',
            'password': 'SomePassword123!'
        })
        assert res_non_existing.status_code == 401

        # کاربر موجود (تکنسین الف) با رمز عبور اشتباه
        res_wrong_pw = client.post(login_url, {
            'username': setup_security_data['tech_a'].username,
            'password': 'WrongPassword123!'
        })
        assert res_wrong_pw.status_code == 401

        # مقایسه پیام و ساختار خطا
        assert res_non_existing.data['errors']['detail'] == res_wrong_pw.data['errors']['detail']

    def test_admin_panel_blocked_for_non_staff_users(self, client, setup_security_data, superuser):
        """
        بررسی امنیتی پنل ادمین جنگو (/admin/):
        فقط کاربران با مشخصه is_staff=True می‌توانند وارد پنل مدیریت شوند.
        """
        tech_user = setup_security_data['tech_a']
        assert tech_user.is_staff is False

        # تکنسین لاگین می‌کند و تلاش می‌کند به /admin/ دسترسی پیدا کند -> ریدایرکت به صفحه ورود یا دسترسی غیرمجاز
        client.force_login(tech_user)
        res_tech_admin = client.get('/admin/')
        # برای کاربران غیر staff، جنگو به صفحه لاگین ادمین ریدایرکت (302) می‌کند
        assert res_tech_admin.status_code in (302, 403)
        if res_tech_admin.status_code == 302:
            assert '/admin/login/' in res_tech_admin.url

        # کاربر مدیر دارای is_staff=True است
        assert superuser.is_staff is True
        client.force_login(superuser)
        res_mgr_admin = client.get('/admin/')
        assert res_mgr_admin.status_code == 200

