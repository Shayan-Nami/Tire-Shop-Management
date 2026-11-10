import pytest
from datetime import datetime, timezone as py_timezone
from decimal import Decimal
from django.urls import reverse
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
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
