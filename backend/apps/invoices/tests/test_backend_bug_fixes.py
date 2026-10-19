import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib import admin
from django.core.management import call_command
from rest_framework.exceptions import ValidationError
from apps.invoices.models import (
    SalesInvoice, PurchaseInvoice, SalesReturn, InvoiceSequence,
    InvoiceStatus, PaymentStatus
)
from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer, Vehicle
from apps.suppliers.models import Supplier
from apps.services_app.models import Service
from apps.invoices.services import (
    generate_next_invoice_number, create_sales_invoice_service,
    create_purchase_invoice_service, create_sales_return_service
)
from apps.finance.services import (
    sync_sales_invoice_payment_status, sync_purchase_invoice_payment_status,
    create_receipt_voucher_service
)


@pytest.fixture
def base_catalog(db):
    brand = Brand.objects.create(brand_name='بارز فیکس')
    size = Size.objects.create(size_name='185/65R14 فیکس')
    tire = Tire.objects.create(
        tire_name='بارز پریمیوم 185',
        brand=brand,
        size=size,
        stock_quantity=20,
        sale_price=Decimal('2000000.00'),
        purchase_price=Decimal('1500000.00')
    )
    supplier = Supplier.objects.create(supplier_name='تأمین‌کننده فیکس')
    customer = Customer.objects.create(full_name='مشتری تست باگ', phone_number='09120001122')
    vehicle = Vehicle.objects.create(customer=customer, license_plate='11ب222-33', model='پژو 206')
    return {
        'brand': brand, 'size': size, 'tire': tire,
        'supplier': supplier, 'customer': customer, 'vehicle': vehicle
    }


@pytest.mark.django_db
class TestBackendBugFixes:

    def test_c1_generate_next_invoice_number_standalone_atomic(self):
        """تولید شماره فاکتور باید به صورت مستقل با @transaction.atomic بدون خطا اجرا شود"""
        inv_num_sales = generate_next_invoice_number('SALES')
        assert inv_num_sales.startswith('S-')

        inv_num_purch = generate_next_invoice_number('PURCHASE')
        assert inv_num_purch.startswith('P-')

    def test_c1_sync_payment_status_standalone_atomic(self, base_catalog, manager_user):
        """توابع sync_payment_status باید به صورت مستقل خارج از تراکنش دستی با موفقیت اجرا شوند"""
        inv = SalesInvoice.objects.create(
            customer=base_catalog['customer'],
            total_amount=Decimal('1000000.00'),
            created_by=manager_user
        )
        status = sync_sales_invoice_payment_status(inv)
        assert status == PaymentStatus.UNPAID

        p_inv = PurchaseInvoice.objects.create(
            supplier=base_catalog['supplier'],
            total_amount=Decimal('2000000.00'),
            created_by=manager_user
        )
        p_status = sync_purchase_invoice_payment_status(p_inv)
        assert p_status == PaymentStatus.UNPAID

    def test_c2_and_h3_sales_invoice_serializer_rejects_cancelled_and_partial(self, auth_client_manager, base_catalog):
        """رد ثبت مستقیم فاکتور در وضعیت لغو شده یا وضعیت نیمه‌پرداخت در بدو صدور"""
        url = reverse('sales-invoice-list')

        # تلاش برای ثبت در وضعیت CANCELLED
        res1 = auth_client_manager.post(url, {
            'customer': base_catalog['customer'].pk,
            'status': InvoiceStatus.CANCELLED,
            'tire_items': [{'tire': base_catalog['tire'].pk, 'quantity': 1}]
        }, format='json')
        assert res1.status_code == 400
        assert 'status' in str(res1.data)

        # تلاش برای ثبت در وضعیت PARTIAL
        res2 = auth_client_manager.post(url, {
            'customer': base_catalog['customer'].pk,
            'payment_status': PaymentStatus.PARTIAL,
            'tire_items': [{'tire': base_catalog['tire'].pk, 'quantity': 1}]
        }, format='json')
        assert res2.status_code == 400
        assert 'payment_status' in str(res2.data)

    def test_c3_customer_and_vehicle_permission_technician_cannot_delete(self, auth_client_technician, auth_client_manager, base_catalog):
        """تکنسین می‌تواند مشتری/خودرو ایجاد و مشاهده کند اما نمی‌تواند حذف کند"""
        cust = Customer.objects.create(full_name='مشتری تست حذف', phone_number='09129998877')
        detail_url = reverse('customer-detail', kwargs={'pk': cust.pk})

        # تکنسین مسدود است (403)
        res_tech = auth_client_technician.delete(detail_url)
        assert res_tech.status_code == 403

        # مدیر مجاز است
        res_mgr = auth_client_manager.delete(detail_url)
        assert res_mgr.status_code == 204

    def test_c4_sales_return_rejects_cross_invoice_item(self, auth_client_manager, base_catalog, manager_user):
        """رد مرجوعی آیتم فاکتور الف به اسم فاکتور ب"""
        inv_a = create_sales_invoice_service(
            customer=base_catalog['customer'],
            vehicle=base_catalog['vehicle'],
            tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 2}],
            service_items_data=[],
            created_by=manager_user
        )
        inv_b = create_sales_invoice_service(
            customer=base_catalog['customer'],
            vehicle=base_catalog['vehicle'],
            tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 1}],
            service_items_data=[],
            created_by=manager_user
        )
        item_a = inv_a.tire_items.first()

        # ارسال آیتم فاکتور الف برای مرجوعی از فاکتور ب
        url = reverse('sales-return-list')
        payload = {
            'sales_invoice': inv_b.pk,
            'reason': 'تست مرجوعی نامعتبر',
            'items': [{'sales_invoice_tire_item_id': item_a.pk, 'quantity': 1}]
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert 'متعلق به فاکتور' in str(res.data)

    def test_m12_sales_return_rejects_duplicate_item_in_same_payload(self, auth_client_manager, base_catalog, manager_user):
        """رد تکرار یک آیتم تایر درون یک پی‌لود مرجوعی"""
        inv = create_sales_invoice_service(
            customer=base_catalog['customer'],
            vehicle=base_catalog['vehicle'],
            tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 4}],
            service_items_data=[],
            created_by=manager_user
        )
        item = inv.tire_items.first()

        url = reverse('sales-return-list')
        payload = {
            'sales_invoice': inv.pk,
            'reason': 'تست اقلام تکراری',
            'items': [
                {'sales_invoice_tire_item_id': item.pk, 'quantity': 1},
                {'sales_invoice_tire_item_id': item.pk, 'quantity': 1}
            ]
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert 'تکراری' in str(res.data)

    def test_m6_health_check_endpoint(self, api_client):
        """بررسی سلامت سرور و پایگاه داده از اندپوینت /api/health/"""
        url = reverse('health-check')
        res = api_client.get(url)
        assert res.status_code == 200
        assert res.json()['status'] == 'healthy'
        assert res.json()['database'] == 'connected'

    def test_h10_user_self_deletion_standard_error(self, auth_client_manager, manager_user):
        """حذف اکانت جاری توسط خود کاربر باید خطای استاندارد اعتبارسنجی بدهد"""
        url = reverse('user-detail', kwargs={'pk': manager_user.pk})
        res = auth_client_manager.delete(url)
        assert res.status_code == 400
        assert res.data['success'] is False
        assert res.data['status_code'] == 400

    def test_h4_safe_type_conversion_in_sales_invoice(self, manager_user, base_catalog):
        """ورودی‌های نامعتبر عددی باید خطای اعتبارسنجی فارسی ۴۰۰ بدهند نه ۵۰۰ کرش"""
        with pytest.raises(ValidationError):
            create_sales_invoice_service(
                customer=base_catalog['customer'],
                vehicle=base_catalog['vehicle'],
                tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 'invalid'}],
                service_items_data=[],
                created_by=manager_user
            )

        with pytest.raises(ValidationError):
            create_sales_invoice_service(
                customer=base_catalog['customer'],
                vehicle=base_catalog['vehicle'],
                tire_items_data=[{'tire': base_catalog['tire'], 'quantity': 1}],
                service_items_data=[],
                discount_percent='not-a-number',
                created_by=manager_user
            )

    def test_m10_invoice_sequence_registered_in_admin(self):
        """مدل InvoiceSequence باید در پنل ادمین جنگو ثبت شده باشد"""
        assert InvoiceSequence in admin.site._registry

    def test_h6_reconcile_commands_run_cleanly(self):
        """دستورات تطبیق انبار و حسابداری باید بدون خطا و در بلاک اتمیک اجرا شوند"""
        call_command('reconcile_stock')
        call_command('reconcile_payments')

    def test_h2_discount_percent_model_validation(self, base_catalog, manager_user):
        """اعتبارسنجی مدل برای درصد تخفیف منفی یا بیش از ۱۰۰"""
        inv = SalesInvoice(
            customer=base_catalog['customer'],
            discount_percent=Decimal('150.00'),
            created_by=manager_user
        )
        with pytest.raises(Exception):
            inv.full_clean()
