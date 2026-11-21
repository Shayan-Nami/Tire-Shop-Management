import pytest
from datetime import datetime, timedelta, timezone as py_timezone
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.utils import aware_utcnow, datetime_from_epoch, datetime_to_epoch
from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer
from apps.invoices.models import SalesInvoice
from utils.jalali import format_jalali_date

@pytest.mark.django_db
class TestSecurityAndValidations:

    def test_jwt_token_blacklist_after_rotation(self, api_client, manager_user):
        login_url = reverse('token_obtain_pair')
        login_res = api_client.post(login_url, {
            'username': 'test_manager',
            'password': 'pass123'
        })
        assert login_res.status_code == 200
        old_refresh = login_res.data['refresh']

        refresh_url = reverse('token_refresh')
        refresh_res = api_client.post(refresh_url, {
            'refresh': old_refresh
        })
        assert refresh_res.status_code == 200
        refresh_res.data.get('refresh')

        reuse_res = api_client.post(refresh_url, {
            'refresh': old_refresh
        })
        assert reuse_res.status_code == 401
        assert "token_not_valid" in str(reuse_res.data) or "لیست سیاه" in str(reuse_res.data)

    def test_receipt_voucher_permissions_restricted_to_manager(self, auth_client_technician, auth_client_manager, manager_user):
        customer = Customer.objects.create(
            full_name='مشتری مالی',
            phone_number='09199999999'
        )
        invoice = SalesInvoice.objects.create(
            customer=customer,
            total_amount=Decimal('500000'),
            created_by=manager_user
        )

        url = reverse('receipt-voucher-list')

        tech_res = auth_client_technician.get(url)
        assert tech_res.status_code == 403

        tech_post = auth_client_technician.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '250000',
            'payment_method': 'نقدی'
        })
        assert tech_post.status_code == 403

        mgr_res = auth_client_manager.get(url)
        assert mgr_res.status_code == 200

        mgr_post = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '250000',
            'payment_method': 'نقدی'
        })
        assert mgr_post.status_code == 201

    def test_catalog_brand_and_size_tires_count(self, auth_client_manager):
        brand = Brand.objects.create(brand_name='کویر تایر تست')
        size = Size.objects.create(size_name='175/70R13')

        Tire.objects.create(
            tire_name='تایر ۱',
            brand=brand,
            size=size,
            stock_quantity=5,
            sale_price=Decimal('1000000'),
            purchase_price=Decimal('800000')
        )
        Tire.objects.create(
            tire_name='تایر ۲',
            brand=brand,
            size=size,
            stock_quantity=8,
            sale_price=Decimal('1200000'),
            purchase_price=Decimal('900000')
        )

        brand_url = reverse('brand-list')
        brand_res = auth_client_manager.get(brand_url)
        assert brand_res.status_code == 200
        brand_item = next(b for b in brand_res.data['results'] if b['brand_name'] == 'کویر تایر تست')
        assert brand_item['tires_count'] == 2

        size_url = reverse('size-list')
        size_res = auth_client_manager.get(size_url)
        assert size_res.status_code == 200
        size_item = next(s for s in size_res.data['results'] if s['size_name'] == '175/70R13')
        assert size_item['tires_count'] == 2

    def test_customer_phone_and_national_code_validators(self):
        invalid_phone_cust = Customer(
            full_name='تست خطا',
            phone_number='123456',
            national_code='0011223344'
        )
        with pytest.raises(DjangoValidationError) as exc:
            invalid_phone_cust.full_clean()
        assert 'phone_number' in exc.value.message_dict

        invalid_nc_cust = Customer(
            full_name='تست کد ملی',
            phone_number='09123456789',
            national_code='12345abc'
        )
        with pytest.raises(DjangoValidationError) as exc:
            invalid_nc_cust.full_clean()
        assert 'national_code' in exc.value.message_dict

        valid_cust = Customer(
            full_name='مشتری معتبر',
            phone_number='09123456789',
            national_code='0123456789'
        )
        valid_cust.full_clean()
        valid_cust.save()
        assert valid_cust.pk is not None

    def test_jalali_date_timezone_aware(self):
        utc_dt = datetime(2026, 3, 20, 22, 30, tzinfo=py_timezone.utc)
        formatted = format_jalali_date(utc_dt)
        assert formatted == "1405/01/01"

    def test_tire_stock_quantity_non_negative(self, db):
        brand = Brand.objects.create(brand_name='برند تست منفی')
        size = Size.objects.create(size_name='195/60R15')

        tire = Tire(
            tire_name='تایر نامعتبر',
            brand=brand,
            size=size,
            stock_quantity=-5,
            sale_price=Decimal('1000000')
        )
        with pytest.raises(DjangoValidationError):
            tire.full_clean()

        with pytest.raises((IntegrityError, DjangoValidationError)):
            Tire.objects.create(
                tire_name='تایر منفی',
                brand=brand,
                size=size,
                stock_quantity=-1,
                sale_price=Decimal('1000000')
            )

    def test_login_stamps_session_exp_claim(self, api_client, manager_user):
        login_res = api_client.post(reverse('token_obtain_pair'), {
            'username': 'test_manager',
            'password': 'pass123',
        })
        assert login_res.status_code == 200

        refresh = RefreshToken(login_res.data['refresh'])
        access = AccessToken(login_res.data['access'])
        max_hours = getattr(settings, 'JWT_MAX_SESSION_HOURS', 12)
        assert max_hours == 12
        assert 'session_exp' in refresh.payload
        assert 'session_exp' in access.payload
        assert refresh['session_exp'] == refresh['iat'] + max_hours * 3600
        assert refresh['exp'] == refresh['session_exp']
        assert access['session_exp'] == refresh['session_exp']

    def test_refresh_preserves_session_exp_and_clamps_refresh_and_outstanding(
        self, api_client, manager_user, monkeypatch
    ):
        login_time = aware_utcnow() - timedelta(hours=6)
        with monkeypatch.context() as mp:
            mp.setattr('rest_framework_simplejwt.tokens.aware_utcnow', lambda: login_time)
            login_res = api_client.post(reverse('token_obtain_pair'), {
                'username': 'test_manager',
                'password': 'pass123',
            })
        assert login_res.status_code == 200

        initial_refresh = RefreshToken(login_res.data['refresh'])
        initial_session_exp = initial_refresh['session_exp']

        refresh_res = api_client.post(reverse('token_refresh'), {
            'refresh': login_res.data['refresh'],
        })
        assert refresh_res.status_code == 200

        rotated_refresh = RefreshToken(refresh_res.data['refresh'])
        assert rotated_refresh['session_exp'] == initial_session_exp
        assert rotated_refresh['exp'] == initial_session_exp
        assert rotated_refresh['exp'] < rotated_refresh['iat'] + 12 * 3600

        outstanding = OutstandingToken.objects.get(jti=rotated_refresh['jti'])
        assert outstanding.expires_at == datetime_from_epoch(initial_session_exp)
        assert BlacklistedToken.objects.filter(token__jti=initial_refresh['jti']).exists()

    def test_refresh_near_session_exp_clamps_access_exp(
        self, api_client, manager_user, monkeypatch
    ):
        login_time = aware_utcnow() - timedelta(hours=11, minutes=50)
        with monkeypatch.context() as mp:
            mp.setattr('rest_framework_simplejwt.tokens.aware_utcnow', lambda: login_time)
            login_res = api_client.post(reverse('token_obtain_pair'), {
                'username': 'test_manager',
                'password': 'pass123',
            })
        assert login_res.status_code == 200
        initial_session_exp = RefreshToken(login_res.data['refresh'])['session_exp']

        refresh_res = api_client.post(reverse('token_refresh'), {
            'refresh': login_res.data['refresh'],
        })
        assert refresh_res.status_code == 200

        access = AccessToken(refresh_res.data['access'])
        rotated_refresh = RefreshToken(refresh_res.data['refresh'])
        assert access['exp'] == initial_session_exp
        assert access['exp'] < access['iat'] + 30 * 60
        assert rotated_refresh['exp'] == initial_session_exp

    def test_refresh_after_session_exp_returns_401(self, api_client, manager_user):
        expired_session_token = RefreshToken.for_user(manager_user)
        expired_session_token['session_exp'] = datetime_to_epoch(aware_utcnow() - timedelta(minutes=1))
        res_claimed = api_client.post(reverse('token_refresh'), {
            'refresh': str(expired_session_token),
        })
        assert res_claimed.status_code == 401
        assert 'منقضی شده است' in str(res_claimed.data)

        legacy_expired_token = RefreshToken.for_user(manager_user)
        legacy_expired_token['iat'] = datetime_to_epoch(aware_utcnow() - timedelta(hours=13))
        res_legacy = api_client.post(reverse('token_refresh'), {
            'refresh': str(legacy_expired_token),
        })
        assert res_legacy.status_code == 401
        assert 'منقضی شده است' in str(res_legacy.data)

    def test_login_clamps_initial_access_and_outstanding_expires_at_without_duplicate_tokens(
        self, api_client, manager_user, settings, monkeypatch
    ):
        settings.JWT_MAX_SESSION_HOURS = 1
        monkeypatch.setattr(AccessToken, 'lifetime', timedelta(hours=2))
        monkeypatch.setattr(RefreshToken, 'lifetime', timedelta(hours=3))

        login_res = api_client.post(reverse('token_obtain_pair'), {
            'username': 'test_manager',
            'password': 'pass123',
        })
        assert login_res.status_code == 200

        refresh = RefreshToken(login_res.data['refresh'])
        access = AccessToken(login_res.data['access'])
        assert OutstandingToken.objects.filter(user=manager_user).count() == 1
        outstanding = OutstandingToken.objects.get(jti=refresh['jti'])
        assert refresh['exp'] == refresh['session_exp']
        assert access['exp'] == refresh['session_exp']
        assert access['exp'] - access['iat'] == 3600
        assert outstanding.expires_at == datetime_from_epoch(refresh['session_exp'])
