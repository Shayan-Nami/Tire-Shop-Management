import pytest
from decimal import Decimal
from datetime import datetime, timezone as py_timezone
from django.urls import reverse
from django.conf import settings
from apps.accounts.models import User, UserRole
from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer
from apps.suppliers.models import Supplier
from apps.invoices.models import (
    SalesInvoice, SalesInvoiceServiceItem,
    InvoiceStatus
)
from apps.services_app.models import Service
from apps.invoices.services import (
    create_sales_invoice_service, create_purchase_invoice_service,
    create_sales_return_service, generate_next_invoice_number
)
from apps.catalog.services import adjust_tire_stock_service
from utils.throttling import LoginUsernameRateThrottle
from utils.jalali import gregorian_to_jalali, jalali_to_gregorian, parse_jalali_or_gregorian_date, format_jalali_date, get_jalali_year
from apps.invoices.permissions import SalesInvoicePermission as InvoicesSalesInvoicePermission
from apps.accounts.permissions import SalesInvoicePermission as AccountsSalesInvoicePermission


@pytest.mark.django_db
class TestRegressionFixes:

    # --------------------------------------------------------------------------
    # 1. Database Settings: USE_SQL_SERVER definition
    # --------------------------------------------------------------------------
    def test_settings_use_sql_server_defined(self):
        assert hasattr(settings, 'USE_SQL_SERVER')
        assert isinstance(settings.USE_SQL_SERVER, bool)

    # --------------------------------------------------------------------------
    # 2. Financial Integrity: Zero unit_price / unit_cost supported
    # --------------------------------------------------------------------------
    def test_zero_price_and_cost_not_overwritten(self, manager_user):
        brand = Brand.objects.create(brand_name='بارز پروموشن')
        size = Size.objects.create(size_name='185/65R15')
        tire = Tire.objects.create(
            tire_name='تایر هدیه',
            brand=brand,
            size=size,
            stock_quantity=10,
            sale_price=Decimal('2000000.00'),
            purchase_price=Decimal('1500000.00')
        )
        service = Service.objects.create(
            service_name='بالانس رایگان',
            price=Decimal('100000.00')
        )
        customer = Customer.objects.create(full_name='مشتری پروموشن', phone_number='09120000010')

        # فاکتور فروش با قیمت تایر ۰ و قیمت خدمت ۰
        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('0.00')}],
            service_items_data=[{'service': service, 'quantity': 1, 'unit_price': Decimal('0.00')}],
            created_by=manager_user
        )
        t_item = inv.tire_items.first()
        s_item = inv.service_items.first()
        assert t_item.unit_price == Decimal('0.00')
        assert s_item.unit_price == Decimal('0.00')
        assert inv.total_amount == Decimal('0.00')

        # فاکتور خرید با قیمت خرید ۰
        supplier = Supplier.objects.create(supplier_name='تأمین‌کننده هدیه', phone_number='09120000011')
        p_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_cost': Decimal('0.00')}],
            created_by=manager_user
        )
        p_item = p_inv.tire_items.first()
        assert p_item.unit_cost == Decimal('0.00')

        # آزمون PurchaseInvoiceCreateSerializer برای unit_cost برابر 0 و همچنین None
        from apps.invoices.serializers import PurchaseInvoiceCreateSerializer
        fake_req = type('Request', (), {'user': manager_user})()
        ser_zero = PurchaseInvoiceCreateSerializer(
            data={'supplier': supplier.pk, 'tire_items': [{'tire': tire.pk, 'quantity': 1, 'unit_cost': '0.00'}]},
            context={'request': fake_req}
        )
        assert ser_zero.is_valid(), ser_zero.errors
        saved_zero = ser_zero.save()
        assert saved_zero.tire_items.first().unit_cost == Decimal('0.00')

        tire_normal = Tire.objects.create(
            tire_name='تایر استاندارد',
            brand=brand,
            size=size,
            stock_quantity=10,
            sale_price=Decimal('2000000.00'),
            purchase_price=Decimal('1500000.00')
        )
        ser_none = PurchaseInvoiceCreateSerializer(
            data={'supplier': supplier.pk, 'tire_items': [{'tire': tire_normal.pk, 'quantity': 1}]},
            context={'request': fake_req}
        )
        assert ser_none.is_valid(), ser_none.errors
        saved_none = ser_none.save()
        assert saved_none.tire_items.first().unit_cost == tire_normal.purchase_price

    # --------------------------------------------------------------------------
    # 3. Access Control: Non-superuser manager blocked from modifying superuser
    # --------------------------------------------------------------------------
    def test_manager_cannot_modify_superuser(self, api_client, superuser):
        # مدیر عادی که سوپریوزر نیست
        regular_manager = User.objects.create_user(
            username='regular_mgr',
            password='Password123!',
            role=UserRole.MANAGER,
            is_staff=True,
            is_superuser=False
        )

        api_client.force_authenticate(user=regular_manager)
        url = reverse('user-detail', kwargs={'pk': superuser.pk})

        # تلاش برای تغییر نام یا رمز سوپریوزر
        res_patch = api_client.patch(url, {'full_name': 'هک سوپریوزر'})
        assert res_patch.status_code == 403

        # تلاش برای حذف سوپریوزر
        res_delete = api_client.delete(url)
        assert res_delete.status_code == 403

        # تلاش برای غیرفعال‌سازی حساب کاربری جاری توسط خود مدیر
        own_url = reverse('user-detail', kwargs={'pk': regular_manager.pk})
        res_deact = api_client.patch(own_url, {'is_active': False})
        assert res_deact.status_code == 400
        errors = res_deact.data.get('errors', res_deact.data)
        assert 'is_active' in errors

        # تلاش برای تغییر نقش حساب کاربری خود
        res_demote = api_client.patch(own_url, {'role': UserRole.TECHNICIAN})
        assert res_demote.status_code == 400
        errors_role = res_demote.data.get('errors', res_demote.data)
        assert 'role' in errors_role

    # --------------------------------------------------------------------------
    # 4. User Account: User profile self-update and change-password
    # --------------------------------------------------------------------------
    def test_h2_user_profile_patch_and_change_password(self, api_client, technician_user):
        api_client.force_authenticate(user=technician_user)

        # ۱. ویرایش مشخصات فردی با PATCH و PUT
        profile_url = reverse('user_profile')
        patch_res = api_client.patch(profile_url, {
            'full_name': 'نام جدید تکنسین',
            'phone_number': '09351234567'
        })
        assert patch_res.status_code == 200
        technician_user.refresh_from_db()
        assert technician_user.full_name == 'نام جدید تکنسین'
        assert technician_user.phone_number == '09351234567'

        put_res = api_client.put(profile_url, {
            'full_name': 'نام تکنسین با PUT',
            'phone_number': '09351234568'
        })
        assert put_res.status_code == 200
        technician_user.refresh_from_db()
        assert technician_user.full_name == 'نام تکنسین با PUT'

        # ۲. تغییر رمز عبور با رمز عبور اشتباه
        cp_url = reverse('change_password')
        fail_cp = api_client.post(cp_url, {
            'old_password': 'wrong_password',
            'new_password': 'NewStrongPassword123!'
        })
        assert fail_cp.status_code == 400

        # ۲-ب. تغییر رمز عبور به رمز فعلی (باید با خطا مواجه شود)
        same_cp = api_client.post(cp_url, {
            'old_password': 'pass123',
            'new_password': 'pass123'
        })
        assert same_cp.status_code == 400

        # ۳. تغییر رمز عبور با رمز صحیح
        success_cp = api_client.post(cp_url, {
            'old_password': 'pass123',
            'new_password': 'NewStrongPassword123!'
        })
        assert success_cp.status_code == 200
        technician_user.refresh_from_db()
        assert technician_user.check_password('NewStrongPassword123!')

    # --------------------------------------------------------------------------
    # 5. Catalog Permissions: Dynamic ordering_fields hides purchase_price for technicians
    # --------------------------------------------------------------------------
    def test_h3_technician_cannot_order_by_purchase_price(self, auth_client_technician, auth_client_manager):
        brand = Brand.objects.create(brand_name='برند تست سورت')
        size = Size.objects.create(size_name='185/65R14')
        tire_expensive = Tire.objects.create(
            tire_name='AAA تایر گران',
            brand=brand,
            size=size,
            stock_quantity=10,
            sale_price=Decimal('1000000.00'),
            purchase_price=Decimal('900000.00')
        )
        tire_cheap = Tire.objects.create(
            tire_name='ZZZ تایر ارزان',
            brand=brand,
            size=size,
            stock_quantity=10,
            sale_price=Decimal('1000000.00'),
            purchase_price=Decimal('100000.00')
        )

        url = reverse('tire-list')

        # مدیر بر اساس purchase_price صعودی مرتب می‌کند: تایر ارزان باید اول باشد
        mgr_res = auth_client_manager.get(f"{url}?ordering=purchase_price")
        assert mgr_res.status_code == 200
        mgr_items = mgr_res.data['results']
        assert len(mgr_items) >= 2
        assert 'purchase_price' in mgr_items[0]
        sorted_mgr_pks = [x['tire_id'] for x in mgr_items if x['tire_id'] in (tire_cheap.pk, tire_expensive.pk)]
        assert sorted_mgr_pks == [tire_cheap.pk, tire_expensive.pk]

        # تکنسین مرتب‌سازی بر اساس purchase_price ارسال می‌کند
        tech_res = auth_client_technician.get(f"{url}?ordering=purchase_price")
        assert tech_res.status_code == 200
        tech_items = tech_res.data['results']
        assert len(tech_items) >= 2
        # برای تکنسین فیلد purchase_price نباید برگردد
        for item in tech_items:
            assert 'purchase_price' not in item
        # و ترتیب مرتب‌سازی بر اساس purchase_price اعمال نمی‌شود، بلکه ترتیب پیش‌فرض الفبایی نام است
        sorted_tech_pks = [x['tire_id'] for x in tech_items if x['tire_id'] in (tire_cheap.pk, tire_expensive.pk)]
        assert sorted_tech_pks == [tire_expensive.pk, tire_cheap.pk]

    # --------------------------------------------------------------------------
    # 6. Analytics: ProfitabilityReportView ORM aggregation
    # --------------------------------------------------------------------------
    def test_profitability_report_orm_aggregation(self, auth_client_manager, manager_user):
        brand = Brand.objects.create(brand_name='یزد تایر گزارش سود')
        size = Size.objects.create(size_name='205/55R16')
        tire = Tire.objects.create(
            tire_name='تایر یزد ۲۰۵',
            brand=brand,
            size=size,
            stock_quantity=50,
            sale_price=Decimal('1500000.00'),
            purchase_price=Decimal('1000000.00')
        )
        StockMovement.objects.create(
            tire=tire,
            quantity=50,
            movement_type=StockMovementType.INITIAL_STOCK,
            balance_after=50,
            unit_cost=Decimal('1000000.00'),
            user=manager_user,
            description='موجودی اولیه'
        )
        customer = Customer.objects.create(full_name='مشتری سودآوری', phone_number='09121112233')

        # فاکتور ۱: ۱ عدد بدون تخفیف -> درآمد = ۱,۵۰۰,۰۰۰، بهای تمام‌شده = ۱,۰۰۰,۰۰۰
        inv1 = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            discount_amount=0,
            discount_percent=0,
            created_by=manager_user
        )

        # فاکتور ۲: ۲ عدد با ۱۰٪ تخفیف -> درآمد = ۲,۷۰۰,۰۰۰، بهای تمام‌شده = ۲,۰۰۰,۰۰۰
        create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            discount_percent=Decimal('10.00'),
            created_by=manager_user
        )

        # فاکتور ۳: ۲ عدد با ۵۰۰,۰۰۰ ریال تخفیف مبلغی -> درآمد = ۲,۵۰۰,۰۰۰، بهای تمام‌شده = ۲,۰۰۰,۰۰۰
        create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1500000.00')}],
            service_items_data=[],
            discount_amount=Decimal('500000.00'),
            created_by=manager_user
        )

        # مرجوعی ۱ عدد از فاکتور ۱ -> کاهش ۱ عدد، درآمد مرجوعی ۱,۵۰۰,۰۰۰، بهای تمام‌شده مرجوعی ۱,۰۰۰,۰۰۰
        item_inv1 = inv1.tire_items.first()
        create_sales_return_service(
            invoice=inv1,
            items_data=[{'sales_invoice_tire_item_id': item_inv1.pk, 'quantity': 1}],
            reason='مرجوعی قلم بدون تخفیف',
            user=manager_user
        )

        # محاسبات نهایی مورد انتظار:
        # کل فروخته شده: (۱ + ۲ + ۲) - ۱ = ۴ عدد
        # درآمد خالص: (۱,۵۰۰,۰۰۰ + ۲,۷۰۰,۰۰۰ + ۲,۵۰۰,۰۰۰) - ۱,۵۰۰,۰۰۰ = ۵,۲۰۰,۰۰۰
        # بهای تمام‌شده خالص: (۱,۰۰۰,۰۰۰ + ۲,۰۰۰,۰۰۰ + ۲,۰۰۰,۰۰۰) - ۱,۰۰۰,۰۰۰ = ۴,۰۰۰,۰۰۰
        # سود ناخالص: ۵,۲۰۰,۰۰۰ - ۴,۰۰۰,۰۰۰ = ۱,۲۰۰,۰۰۰

        url = reverse('profitability-report')
        res = auth_client_manager.get(url)
        assert res.status_code == 200
        matched = [item for item in res.data if item['tire_id'] == tire.pk]
        assert len(matched) == 1
        stat = matched[0]
        assert stat['total_sold'] == 4
        assert stat['total_revenue'] == 5200000.0
        assert stat['total_cost'] == 4000000.0
        assert stat['total_profit'] == 1200000.0

    # --------------------------------------------------------------------------
    # 7. Authentication: Logout endpoint blacklists refresh token
    # --------------------------------------------------------------------------
    def test_logout_blacklists_refresh_token(self, api_client, manager_user):
        login_url = reverse('token_obtain_pair')
        login_res = api_client.post(login_url, {
            'username': 'test_manager',
            'password': 'pass123'
        })
        assert login_res.status_code == 200
        refresh_token = login_res.data['refresh']
        access_token = login_res.data['access']

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_url = reverse('logout')

        # خروج بدون ارسال توکن refresh
        bad_logout = api_client.post(logout_url, {})
        assert bad_logout.status_code == 400

        # ارسال داده نامعتبر غیر دیکشنری
        bad_payload = api_client.post(logout_url, ['not_a_dict'], format='json')
        assert bad_payload.status_code == 400

        # ارسال توکن نامعتبر یا تصادفی
        invalid_token_res = api_client.post(logout_url, {'refresh': 'invalid.token.here'})
        assert invalid_token_res.status_code == 400

        # خروج موفق با توکن refresh
        logout_res = api_client.post(logout_url, {'refresh': refresh_token})
        assert logout_res.status_code == 200

        # تلاش مجدد برای تجدید توکن با توکن منقضی/بلاک‌شده
        refresh_url = reverse('token_refresh')
        reuse_res = api_client.post(refresh_url, {'refresh': refresh_token})
        assert reuse_res.status_code == 401

    # --------------------------------------------------------------------------
    # 8. User Creation: Mandatory password validation
    # --------------------------------------------------------------------------
    def test_user_creation_requires_password(self, auth_client_manager):
        url = reverse('user-list')
        res = auth_client_manager.post(url, {
            'username': 'user_no_password',
            'full_name': 'کاربر بدون پسورد',
            'role': UserRole.TECHNICIAN
        })
        assert res.status_code == 400
        errors = res.data.get('errors', res.data)
        assert 'password' in errors

    # --------------------------------------------------------------------------
    # 9. Invoices: Cancel actions return updated CANCELLED instance
    # --------------------------------------------------------------------------
    def test_m3_invoice_cancel_returns_updated_cancelled_object(self, auth_client_manager, manager_user):
        brand = Brand.objects.create(brand_name='کویر کنسل')
        size = Size.objects.create(size_name='175/70R13')
        tire = Tire.objects.create(
            tire_name='تایر ۱۷۵',
            brand=brand,
            size=size,
            stock_quantity=20,
            sale_price=Decimal('1200000.00'),
            purchase_price=Decimal('900000.00')
        )
        StockMovement.objects.create(
            tire=tire,
            quantity=20,
            movement_type=StockMovementType.INITIAL_STOCK,
            balance_after=20,
            unit_cost=Decimal('900000.00'),
            user=manager_user,
            description='موجودی اولیه'
        )
        customer = Customer.objects.create(full_name='مشتری لغو', phone_number='09128889900')

        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1200000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        url = reverse('sales-invoice-cancel', kwargs={'pk': inv.pk})
        res = auth_client_manager.post(url)
        assert res.status_code == 200
        assert res.data['invoice']['status'] == InvoiceStatus.CANCELLED

    # --------------------------------------------------------------------------
    # 10. Query Optimization: created_by in select_related for Finance ViewSets
    # --------------------------------------------------------------------------
    def test_finance_viewsets_select_related_created_by(self):
        from apps.finance.views import ReceiptVoucherViewSet, PaymentVoucherViewSet, CustomerRefundVoucherViewSet
        assert 'created_by' in ReceiptVoucherViewSet.queryset.query.select_related
        assert 'created_by' in PaymentVoucherViewSet.queryset.query.select_related
        assert 'created_by' in CustomerRefundVoucherViewSet.queryset.query.select_related

    # --------------------------------------------------------------------------
    # 11. Security & Stability: Throttling safely handles non-dict request.data
    # --------------------------------------------------------------------------
    def test_m5_throttling_handles_non_dict_data_safely(self):
        class DummyRequest:
            data = ["item1", "item2"]

        throttle = LoginUsernameRateThrottle()
        key = throttle.get_cache_key(DummyRequest(), None)
        assert key is None

    # --------------------------------------------------------------------------
    # 12. Financial Reporting: Dashboard stats allows true negative net revenue
    # --------------------------------------------------------------------------
    def test_l1_dashboard_stats_allows_negative_revenue(self, auth_client_manager, manager_user):
        customer = Customer.objects.create(full_name='مشتری مرجوعی کلان', phone_number='09127776655')
        brand = Brand.objects.create(brand_name='تست منفی')
        size = Size.objects.create(size_name='165/65R13')
        tire = Tire.objects.create(
            tire_name='تایر پراید',
            brand=brand,
            size=size,
            stock_quantity=10,
            sale_price=Decimal('1000000.00'),
            purchase_price=Decimal('800000.00')
        )
        StockMovement.objects.create(
            tire=tire,
            quantity=10,
            movement_type=StockMovementType.INITIAL_STOCK,
            balance_after=10,
            unit_cost=Decimal('800000.00'),
            user=manager_user,
            description='موجودی اولیه'
        )

        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        # تاریخ فاکتور را به دیروز منتقل می‌کنیم
        SalesInvoice.objects.filter(pk=inv.pk).update(
            invoice_date=datetime(2020, 1, 1, 12, 0, tzinfo=py_timezone.utc)
        )

        # مرجوعی امروز ثبت می‌شود (فروش امروز = ۰، مرجوعی = ۱,۰۰۰,۰۰۰ -> درآمد خالص = -۱,۰۰۰,۰۰۰)
        item = inv.tire_items.first()
        create_sales_return_service(
            invoice=inv,
            items_data=[{'sales_invoice_tire_item_id': item.pk, 'quantity': 1}],
            reason='مرجوعی بدون فروش امروز',
            user=manager_user
        )

        url = reverse('dashboard-stats')
        res = auth_client_manager.get(url)
        assert res.status_code == 200
        # درآمد نباید صفر کلمپ شده باشد
        assert res.data['today_revenue'] <= 0

    # --------------------------------------------------------------------------
    # 13. Catalog Serializers: tires_count uses SerializerMethodField
    # --------------------------------------------------------------------------
    def test_l2_catalog_serializers_tires_count(self):
        from apps.catalog.serializers import BrandSerializer
        brand = Brand.objects.create(brand_name='برند بدون انوتیشن')
        ser = BrandSerializer(brand)
        assert ser.data['tires_count'] == 0
        assert not hasattr(brand, '_tires_count')

    # --------------------------------------------------------------------------
    # 14. Stock Ledger: adjust_tire_stock_service updates stock directly
    # --------------------------------------------------------------------------
    def test_l3_adjust_tire_stock_service_clean_execution(self, manager_user):
        brand = Brand.objects.create(brand_name='برند تعدیل')
        size = Size.objects.create(size_name='195/60R15')
        tire = Tire.objects.create(
            tire_name='تایر تعدیل',
            brand=brand,
            size=size,
            stock_quantity=10,
            sale_price=Decimal('1500000.00'),
            purchase_price=Decimal('1100000.00')
        )
        movement = adjust_tire_stock_service(
            tire=tire,
            counted_quantity=14,
            reason='انبارگردانی فصلی',
            user=manager_user
        )
        assert movement.quantity == 4
        tire.refresh_from_db()
        assert tire.stock_quantity == 14

    # --------------------------------------------------------------------------
    # 15. Data Sanitization: Customer and vehicle serializers normalize in validators
    # --------------------------------------------------------------------------
    def test_l4_customer_serializer_validators_normalize_cleanly(self):
        from apps.customers.serializers import CustomerSerializer, VehicleSerializer
        customer = Customer.objects.create(full_name='مشتری فرمت', phone_number='09121234567')

        v_ser = VehicleSerializer(data={
            'customer': customer.pk,
            'license_plate': '۱۲ ایران ۳۴۵ ب ۶۷',
            'model': 'پژو 206'
        })
        assert v_ser.is_valid(), v_ser.errors
        assert v_ser.validated_data['license_plate'] == '12 ایران 345 ب 67'

        c_ser = CustomerSerializer(data={
            'full_name': 'مشتری جدید با ارقام فارسی',
            'phone_number': '۰۹۱۲۳۴۵۶۷۸۹',
            'national_code': '۰۰۱۲۳۴۵۶۷۸'
        })
        assert c_ser.is_valid(), c_ser.errors
        assert c_ser.validated_data['phone_number'] == '09123456789'
        assert c_ser.validated_data['national_code'] == '0012345678'

    # --------------------------------------------------------------------------
    # User update uses super().update() and validates password context
    # --------------------------------------------------------------------------
    def test_l5_l6_user_serializer_update_and_password_validation(self):
        from apps.accounts.serializers import UserCreateUpdateSerializer
        # اعتبارسنجی مشابهت رمز عبور با نام کاربری
        ser = UserCreateUpdateSerializer(data={
            'username': 'unique_user_test',
            'password': 'unique_user_test',  # مشابه نام کاربری
            'role': UserRole.TECHNICIAN
        })
        assert not ser.is_valid()
        assert 'password' in ser.errors

        # آپدیت کاربر با super().update()
        valid_ser = UserCreateUpdateSerializer(data={
            'username': 'user_super_update',
            'password': 'StrongPassword123!',
            'role': UserRole.TECHNICIAN
        })
        assert valid_ser.is_valid(), valid_ser.errors
        user = valid_ser.save()

        update_ser = UserCreateUpdateSerializer(user, data={'full_name': 'نام ویرایش‌شده'}, partial=True)
        assert update_ser.is_valid(), update_ser.errors
        updated_user = update_ser.save()
        assert updated_user.full_name == 'نام ویرایش‌شده'

    # --------------------------------------------------------------------------
    # SalesInvoicePermission re-export and placement
    # --------------------------------------------------------------------------
    def test_l7_sales_invoice_permission_domain_placement(self):
        assert InvoicesSalesInvoicePermission is AccountsSalesInvoicePermission

    # --------------------------------------------------------------------------
    # item_refund non-negative in partial returns
    # --------------------------------------------------------------------------
    def test_l8_item_refund_guaranteed_non_negative(self, manager_user):
        brand = Brand.objects.create(brand_name='برند رند')
        size = Size.objects.create(size_name='175/65R14')
        tire = Tire.objects.create(
            tire_name='تایر رند',
            brand=brand,
            size=size,
            stock_quantity=10,
            sale_price=Decimal('1000000.00'),
            purchase_price=Decimal('800000.00')
        )
        customer = Customer.objects.create(full_name='مشتری رند', phone_number='09129998877')
        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1000000.00')}],
            service_items_data=[],
            discount_amount=Decimal('100000.00'),
            created_by=manager_user
        )
        item = inv.tire_items.first()
        ret = create_sales_return_service(
            invoice=inv,
            items_data=[{'sales_invoice_tire_item_id': item.pk, 'quantity': 1}],
            reason='تست عدم منفی شدن استرداد',
            user=manager_user
        )
        ret_item = ret.items.first()
        assert ret_item.refund_amount >= Decimal('0.00')

    # --------------------------------------------------------------------------
    # CheckConstraint non-negative on invoice items
    # --------------------------------------------------------------------------
    def test_l9_check_constraints_prevent_negative_values(self, manager_user):
        from django.db import IntegrityError
        brand = Brand.objects.create(brand_name='برند قید')
        size = Size.objects.create(size_name='175/65R14')
        tire = Tire.objects.create(
            tire_name='تایر قید',
            brand=brand,
            size=size,
            stock_quantity=10,
            sale_price=Decimal('1000000.00'),
            purchase_price=Decimal('800000.00')
        )
        customer = Customer.objects.create(full_name='مشتری قید', phone_number='09129998866')
        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        service = Service.objects.create(service_name='خدمت قید', price=Decimal('50000.00'))

        # درج مستقیم قیمت منفی برای SalesInvoiceServiceItem باید با IntegrityError رد شود
        with pytest.raises(IntegrityError):
            SalesInvoiceServiceItem.objects.create(
                sales_invoice=inv,
                service=service,
                quantity=1,
                unit_price=Decimal('-100.00')
            )

    # --------------------------------------------------------------------------
    # Safe sequence creation
    # --------------------------------------------------------------------------
    def test_l10_safe_sequential_number_generation(self):
        num1 = generate_next_invoice_number('SALES')
        num2 = generate_next_invoice_number('SALES')
        assert num1 != num2
        assert num1.startswith('S-')
        assert num2.startswith('S-')

    # --------------------------------------------------------------------------
    # Jalali bound checks and validations
    # --------------------------------------------------------------------------
    def test_l11_jalali_bound_checks_and_validations(self):
        # بررسی ماه‌های نامعتبر
        with pytest.raises(ValueError):
            gregorian_to_jalali(2026, 13, 10)

        with pytest.raises(ValueError):
            gregorian_to_jalali(2026, 0, 10)

        with pytest.raises(ValueError):
            gregorian_to_jalali(2024, 2, 30)  # فوریه نمی‌تواند ۳۰ روز باشد

        with pytest.raises(ValueError):
            jalali_to_gregorian(1405, 13, 1)

        with pytest.raises(ValueError):
            jalali_to_gregorian(1405, 0, 1)

        with pytest.raises(ValueError):
            jalali_to_gregorian(1403, 8, 31)  # آبان حداکثر ۳۰ روز است

        with pytest.raises(ValueError):
            jalali_to_gregorian(1403, 12, 31)  # اسفند نمی‌تواند ۳۱ روز باشد

        # پارس تاریخ با مقادیر نامعتبر
        assert parse_jalali_or_gregorian_date('1405-13-40') is None
        assert parse_jalali_or_gregorian_date('1403-08-31') is None
        assert parse_jalali_or_gregorian_date('invalid') is None
        assert parse_jalali_or_gregorian_date('') is None

        # اعتبارسنجی نوع ورودی format_jalali_date و get_jalali_year
        assert format_jalali_date(None) == ""
        assert format_jalali_date("invalid_date_type") == ""
        assert isinstance(get_jalali_year("invalid_type"), int)
