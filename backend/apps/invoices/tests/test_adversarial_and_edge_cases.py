import pytest
from decimal import Decimal
from django.urls import reverse
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from apps.accounts.models import User
from apps.customers.models import Customer, Vehicle
from apps.catalog.models import Brand, Size, Tire
from apps.services_app.models import Service
from apps.suppliers.models import Supplier
from apps.invoices.models import SalesInvoice, PurchaseInvoice, InvoiceStatus, PaymentStatus
from apps.finance.models import ReceiptVoucher
from apps.finance.services import create_receipt_voucher_service
from apps.invoices.services import create_sales_invoice_service, create_purchase_invoice_service

@pytest.fixture
def edge_case_setup(db):
    brand = Brand.objects.create(brand_name='بارز سنندج')
    size = Size.objects.create(size_name='185/65R15')
    tire = Tire.objects.create(
        tire_name='تایر رادیال P648',
        brand=brand,
        size=size,
        stock_quantity=20,
        purchase_price=Decimal('1000000'),
        sale_price=Decimal('1500000'),
        min_stock_alert=4
    )
    service = Service.objects.create(
        service_name='تعویض والف استیل',
        price=Decimal('50000'),
        description='تعویض والف چهار چرخ'
    )
    customer = Customer.objects.create(
        full_name='محمد حسینی',
        phone_number='09181112233',
        national_code='3871234567'
    )
    vehicle = Vehicle.objects.create(
        customer=customer,
        license_plate='55س555-55',
        model='تندر ۹۰'
    )
    supplier = Supplier.objects.create(
        supplier_name='پخش تایر غرب',
        phone_number='08733221100'
    )
    return {
        'brand': brand,
        'size': size,
        'tire': tire,
        'service': service,
        'customer': customer,
        'vehicle': vehicle,
        'supplier': supplier,
    }

@pytest.mark.django_db
class TestAdversarialAndEdgeCases:

    def test_multiple_customers_with_empty_or_null_national_code(self):
        """بررسی عدم وقوع خطای UNIQUE constraint هنگام ثبت چند مشتری بدون کد ملی یا با رشته خالی"""
        c1 = Customer.objects.create(
            full_name='مشتری اول بدون کد ملی',
            phone_number='09110000001',
            national_code=''
        )
        c2 = Customer.objects.create(
            full_name='مشتری دوم بدون کد ملی',
            phone_number='09110000002',
            national_code=''
        )
        c3 = Customer.objects.create(
            full_name='مشتری سوم بدون کد ملی',
            phone_number='09110000003',
            national_code=None
        )

        assert c1.national_code is None
        assert c2.national_code is None
        assert c3.national_code is None
        assert Customer.objects.filter(national_code__isnull=True).count() >= 3

    def test_customer_persian_digits_normalization_and_api(self, auth_client_manager):
        """بررسی نرمال‌سازی ارقام فارسی/عربی شماره تلفن و کد ملی در API مشتریان"""
        url = reverse('customer-list')
        payload = {
            'full_name': 'مشتری با کیبورد فارسی',
            'phone_number': '۰۹۱۲۹۸۷۶۵۴۳',
            'national_code': '۰۰۹۸۷۶۵۴۳۲',
            'address': 'تهران، خیابان آزادی'
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 201
        assert res.data['phone_number'] == '09129876543'
        assert res.data['national_code'] == '0098765432'

        # ارسال کد ملی خالی باید بدون خطا پذیرفته شود و None ذخیره گردد
        payload_empty_nc = {
            'full_name': 'مشتری دوم بدون کد ملی API',
            'phone_number': '۰۹۱۸۱۱۱۲۲۴۴',
            'national_code': ''
        }
        res_empty = auth_client_manager.post(url, payload_empty_nc, format='json')
        assert res_empty.status_code == 201
        assert res_empty.data['national_code'] is None

    def test_multiple_users_with_empty_phone_number(self):
        """بررسی عدم وقوع خطای UNIQUE constraint در مدل کاربر برای شماره موبایل خالی"""
        u1 = User.objects.create(
            username='user_empty_phone_1',
            phone_number=''
        )
        u2 = User.objects.create(
            username='user_empty_phone_2',
            phone_number=''
        )
        assert u1.phone_number is None
        assert u2.phone_number is None

    def test_receipt_voucher_negative_or_zero_amount_rejected(self, auth_client_manager, edge_case_setup):
        """سند دریافت وجه با مبلغ منفی یا صفر باید با خطای 400 رد شود"""
        setup = edge_case_setup
        invoice = SalesInvoice.objects.create(
            customer=setup['customer'],
            total_amount=Decimal('1000000'),
            payment_status=PaymentStatus.UNPAID
        )
        url = reverse('receipt-voucher-list')

        # مبلغ صفر
        res_zero = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '0',
            'payment_method': 'نقدی'
        })
        assert res_zero.status_code == 400

        # مبلغ منفی
        res_neg = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '-50000',
            'payment_method': 'نقدی'
        })
        assert res_neg.status_code == 400

    def test_payment_voucher_negative_or_zero_amount_rejected(self, auth_client_manager, edge_case_setup):
        """سند پرداخت وجه با مبلغ منفی یا صفر باید با خطای 400 رد شود"""
        setup = edge_case_setup
        purchase_inv = PurchaseInvoice.objects.create(
            supplier=setup['supplier'],
            total_amount=Decimal('2000000')
        )
        url = reverse('payment-voucher-list')

        # مبلغ صفر
        res_zero = auth_client_manager.post(url, {
            'purchase_invoice': purchase_inv.pk,
            'amount': '0'
        })
        assert res_zero.status_code == 400

        # مبلغ منفی
        res_neg = auth_client_manager.post(url, {
            'purchase_invoice': purchase_inv.pk,
            'amount': '-100000'
        })
        assert res_neg.status_code == 400

    def test_receipt_voucher_exceeding_invoice_total_and_status_sync(self, auth_client_manager, edge_case_setup):
        """بررسی عدم پذیرش مبالغ مازاد بر مانده فاکتور و همگام‌سازی خودکار payment_status"""
        setup = edge_case_setup
        invoice = SalesInvoice.objects.create(
            customer=setup['customer'],
            total_amount=Decimal('500000'),
            payment_status=PaymentStatus.UNPAID
        )
        url = reverse('receipt-voucher-list')

        # ۱. تلاش برای پرداخت مبلغی بیش از کل فاکتور
        res_overflow = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '600000',
            'payment_method': 'کارتخوان'
        })
        assert res_overflow.status_code == 400
        assert "مانده بدهی فاکتور" in str(res_overflow.data)

        # ۲. پرداخت قسط اول (۳۰۰,۰۰۰ تومان) -> وضعیت باید PARTIAL شود
        res_p1 = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '300000',
            'payment_method': 'کارتخوان'
        })
        assert res_p1.status_code == 201
        invoice.refresh_from_db()
        assert invoice.payment_status == PaymentStatus.PARTIAL

        # ۳. تلاش برای پرداخت بیش از مانده (مانده ۲۰۰,۰۰۰ است، درخواست ۲۵۰,۰۰۰)
        res_overflow2 = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '250000',
            'payment_method': 'کارتخوان'
        })
        assert res_overflow2.status_code == 400

        # ۴. تسویه کامل مانده (۲۰۰,۰۰۰ تومان) -> وضعیت باید PAID شود
        res_p2 = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '200000',
            'payment_method': 'کارتخوان'
        })
        assert res_p2.status_code == 201
        invoice.refresh_from_db()
        assert invoice.payment_status == PaymentStatus.PAID

        # ۵. تلاش برای پرداخت پس از تسویه کامل
        res_p3 = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '10000',
            'payment_method': 'کارتخوان'
        })
        assert res_p3.status_code == 400
        assert "سقف مبلغ کل فاکتور رسیده است" in str(res_p3.data)

    def test_receipt_voucher_on_cancelled_invoice_rejected(self, auth_client_manager, edge_case_setup):
        """ثبت سند دریافت وجه برای فاکتور لغو شده باید با خطای 400 رد شود"""
        setup = edge_case_setup
        invoice = SalesInvoice.objects.create(
            customer=setup['customer'],
            total_amount=Decimal('500000'),
            status=InvoiceStatus.CANCELLED
        )
        url = reverse('receipt-voucher-list')
        res = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '100000'
        })
        assert res.status_code == 400
        assert "فاکتور لغو شده" in str(res.data)

    def test_cannot_cancel_invoice_with_existing_receipts(self, auth_client_manager, edge_case_setup):
        """فاکتوری که برای آن سند دریافت وجه ثبت شده نباید قابل لغو باشد"""
        setup = edge_case_setup
        invoice = SalesInvoice.objects.create(
            customer=setup['customer'],
            total_amount=Decimal('800000'),
            status=InvoiceStatus.CONFIRMED
        )
        ReceiptVoucher.objects.create(
            sales_invoice=invoice,
            amount=Decimal('400000')
        )
        cancel_url = reverse('sales-invoice-cancel', kwargs={'pk': invoice.pk})
        res = auth_client_manager.post(cancel_url)
        assert res.status_code == 400
        assert "سند دریافت وجه ثبت شده" in str(res.data)

    def test_sales_invoice_duplicate_tire_items_rejected(self, auth_client_manager, edge_case_setup):
        """ارسال اقلام تایر تکراری در یک فاکتور فروش باید 400 برگرداند نه خطای دیتابیس 500"""
        setup = edge_case_setup
        url = reverse('sales-invoice-list')
        payload = {
            'customer': setup['customer'].pk,
            'tire_items': [
                {'tire': setup['tire'].pk, 'quantity': 1},
                {'tire': setup['tire'].pk, 'quantity': 2}
            ]
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert "تایر تکراری" in str(res.data)

    def test_sales_invoice_duplicate_service_items_rejected(self, auth_client_manager, edge_case_setup):
        """ارسال اقلام خدمت تکراری در یک فاکتور فروش باید با خطای 400 رد شود"""
        setup = edge_case_setup
        url = reverse('sales-invoice-list')
        payload = {
            'customer': setup['customer'].pk,
            'service_items': [
                {'service': setup['service'].pk, 'quantity': 1},
                {'service': setup['service'].pk, 'quantity': 2}
            ]
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert "خدمت تکراری" in str(res.data)

    def test_sales_invoice_empty_items_rejected(self, auth_client_manager, edge_case_setup):
        """صدور فاکتور فروش بدون هیچ قلم تایر و بدون هیچ خدمتی باید 400 بدهد"""
        setup = edge_case_setup
        url = reverse('sales-invoice-list')
        payload = {
            'customer': setup['customer'].pk,
            'tire_items': [],
            'service_items': []
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == 400
        assert "حداقل یک قلم تایر یا یک خدمت" in str(res.data)

    def test_sales_invoice_invalid_discounts_rejected(self, auth_client_manager, edge_case_setup):
        """بررسی اعتبارسنجی مقادیر مرزی و غیرمجاز تخفیف در فاکتور فروش"""
        setup = edge_case_setup
        url = reverse('sales-invoice-list')

        # ۱. درصد تخفیف بالای ۱۰۰
        res1 = auth_client_manager.post(url, {
            'customer': setup['customer'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 1}],
            'discount_percent': 120
        }, format='json')
        assert res1.status_code == 400

        # ۲. درصد تخفیف منفی
        res2 = auth_client_manager.post(url, {
            'customer': setup['customer'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 1}],
            'discount_percent': -10
        }, format='json')
        assert res2.status_code == 400

        # ۳. مبلغ تخفیف منفی
        res3 = auth_client_manager.post(url, {
            'customer': setup['customer'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 1}],
            'discount_amount': -50000
        }, format='json')
        assert res3.status_code == 400

        # ۴. مبلغ تخفیف بیشتر از جمع اقلام (جمع اقلام ۱,۵۰۰,۰۰۰ تومان است)
        res4 = auth_client_manager.post(url, {
            'customer': setup['customer'].pk,
            'tire_items': [{'tire': setup['tire'].pk, 'quantity': 1}],
            'discount_amount': 2000000
        }, format='json')
        assert res4.status_code == 400
        assert "جمع کل اقلام فاکتور" in str(res4.data)

    def test_purchase_invoice_duplicate_tire_items_rejected(self, auth_client_warehouse, edge_case_setup):
        """اقلام تایر تکراری در فاکتور خرید باید 400 برگرداند"""
        setup = edge_case_setup
        url = reverse('purchase-invoice-list')
        payload = {
            'supplier': setup['supplier'].pk,
            'tire_items': [
                {'tire': setup['tire'].pk, 'quantity': 5},
                {'tire': setup['tire'].pk, 'quantity': 3}
            ]
        }
        res = auth_client_warehouse.post(url, payload, format='json')
        assert res.status_code == 400
        assert "تایر تکراری" in str(res.data)

    def test_payment_voucher_exceeding_purchase_total_rejected(self, auth_client_manager, edge_case_setup):
        """عدم امکان ثبت سند پرداخت مازاد بر مبلغ کل فاکتور خرید"""
        setup = edge_case_setup
        purchase_inv = PurchaseInvoice.objects.create(
            supplier=setup['supplier'],
            total_amount=Decimal('1000000')
        )
        url = reverse('payment-voucher-list')

        # مبلغ بیشتر از فاکتور خرید
        res_overflow = auth_client_manager.post(url, {
            'purchase_invoice': purchase_inv.pk,
            'amount': '1200000'
        })
        assert res_overflow.status_code == 400
        assert "مانده بدهی فاکتور خرید" in str(res_overflow.data)

        # پرداخت دقیق
        res_ok = auth_client_manager.post(url, {
            'purchase_invoice': purchase_inv.pk,
            'amount': '1000000'
        })
        assert res_ok.status_code == 201

        # پرداخت بعد از تسویه کامل
        res_over = auth_client_manager.post(url, {
            'purchase_invoice': purchase_inv.pk,
            'amount': '50000'
        })
        assert res_over.status_code == 400

    def test_customer_and_user_full_clean_with_persian_digits(self):
        """بررسی اجرای موفق full_clean روی مدل‌های مشتری و کاربر با ارقام فارسی"""
        cust = Customer(
            full_name='مشتری ارقام فارسی',
            phone_number='۰۹۱۲۱۱۱۲۲۳۳',
            national_code='۰۰۱۱۲۲۳۳۴۴'
        )
        cust.full_clean()
        assert cust.phone_number == '09121112233'
        assert cust.national_code == '0011223344'

        user = User(
            username='user_persian_digits',
            phone_number='۰۹۳۵۱۲۳۴۵۶۷'
        )
        user.set_password('securepass123')
        user.full_clean()
        assert user.phone_number == '09351234567'

    def test_vehicle_plate_persian_digits_normalization(self, auth_client_manager, edge_case_setup):
        """نرمال‌سازی ارقام فارسی در پلاک خودرو در مدل و API"""
        setup = edge_case_setup
        v = Vehicle(
            customer=setup['customer'],
            license_plate='۵۵ب۵۵۵-۵۵',
            model='دنا پلاس'
        )
        v.full_clean()
        v.save()
        assert v.license_plate == '55ب555-55'

        # از طریق API
        url = reverse('vehicle-list')
        res = auth_client_manager.post(url, {
            'customer': setup['customer'].pk,
            'license_plate': '۶۶ج۶۶۶-۶۶',
            'model': 'تارا'
        }, format='json')
        assert res.status_code == 201
        assert res.data['license_plate'] == '66ج666-66'

    def test_dashboard_stats_total_receivables_with_partial_payments(self, auth_client_manager, edge_case_setup):
        """بررسی کسر دقیق اسناد دریافت وجه از فاکتورهای اقساطی در محاسبه total_receivables"""
        setup = edge_case_setup
        # ایجاد فاکتور ۱,۰۰۰,۰۰۰ تومانی با وضعیت UNPAID
        inv = SalesInvoice.objects.create(
            customer=setup['customer'],
            total_amount=Decimal('1000000'),
            payment_status=PaymentStatus.UNPAID,
            status=InvoiceStatus.CONFIRMED
        )

        stats_url = reverse('dashboard-stats')
        res1 = auth_client_manager.get(stats_url)
        assert res1.status_code == 200
        initial_receivables = res1.data['total_receivables']

        # ثبت پرداخت ۴۰۰,۰۰۰ تومان (مانده باید ۶۰۰,۰۰۰ تومان باشد)
        create_receipt_voucher_service(
            sales_invoice=inv,
            amount=Decimal('400000')
        )
        inv.refresh_from_db()
        assert inv.payment_status == PaymentStatus.PARTIAL

        res2 = auth_client_manager.get(stats_url)
        assert res2.status_code == 200
        # بدهی باقی‌مانده باید دقیقاً ۴۰۰,۰۰۰ تومان کمتر از حالت قبل باشد
        assert res2.data['total_receivables'] == initial_receivables - 400000.0

    def test_sales_by_brand_returns_float_numbers(self, auth_client_manager, edge_case_setup):
        """بررسی برگشت مقادیر عددی اعشاری استاندارد (نه رشته) در گزارش فروش بر اساس برند"""
        setup = edge_case_setup
        inv = SalesInvoice.objects.create(
            customer=setup['customer'],
            total_amount=Decimal('3000000'),
            status=InvoiceStatus.CONFIRMED
        )
        from apps.invoices.models import SalesInvoiceTireItem
        SalesInvoiceTireItem.objects.create(
            sales_invoice=inv,
            tire=setup['tire'],
            quantity=2,
            unit_price=Decimal('1500000')
        )

        url = reverse('sales-by-brand-report')
        res = auth_client_manager.get(url)
        assert res.status_code == 200
        assert len(res.data) > 0
        item = next((b for b in res.data if b['brand_name'] == setup['brand'].brand_name), None)
        assert item is not None
        assert isinstance(item['total_revenue'], float)
        assert item['total_revenue'] >= 3000000.0

    def test_sales_by_date_range_with_jalali_dates(self, auth_client_manager, edge_case_setup):
        """پشتیبانی از تاریخ‌های شمسی و ارقام فارسی در فیلتر گزارش بازه زمانی"""
        setup = edge_case_setup
        SalesInvoice.objects.create(
            customer=setup['customer'],
            total_amount=Decimal('1500000'),
            status=InvoiceStatus.CONFIRMED
        )
        url = reverse('sales-by-date-report')

        # فیلتر با تاریخ شمسی جاری (۱۴۰۴ یا ۱۴۰۵)
        res_jalali = auth_client_manager.get(url, {'start_date': '۱۴۰۴/۰۱/۰۱', 'end_date': '۱۴۰۶/۱۲/۲۹'})
        assert res_jalali.status_code == 200
        assert res_jalali.data['total_invoices'] >= 1
        assert res_jalali.data['total_sales_amount'] >= 1500000.0

    def test_technician_blocked_from_cancelling_sales_invoice(self, auth_client_technician, auth_client_manager, edge_case_setup):
        """تکنسین نباید اجازه لغو فاکتور فروش داشته باشد (۴۰۳) و فقط مدیر مجاز است"""
        setup = edge_case_setup
        inv = SalesInvoice.objects.create(
            customer=setup['customer'],
            total_amount=Decimal('1000000'),
            status=InvoiceStatus.CONFIRMED
        )
        cancel_url = reverse('sales-invoice-cancel', kwargs={'pk': inv.pk})

        # درخواست توسط تکنسین
        res_tech = auth_client_technician.post(cancel_url)
        assert res_tech.status_code == 403

        # درخواست توسط مدیر
        res_mgr = auth_client_manager.post(cancel_url)
        assert res_mgr.status_code == 200
        inv.refresh_from_db()
        assert inv.status == InvoiceStatus.CANCELLED

    def test_manager_cannot_delete_own_account(self, auth_client_manager, manager_user):
        """مدیر نباید بتواند حساب کاربری خودش را حذف کند تا از lockout جلوگیری شود"""
        url = reverse('user-detail', kwargs={'pk': manager_user.pk})
        res = auth_client_manager.delete(url)
        assert res.status_code == 400
        assert "امکان حذف حساب کاربری جاری" in str(res.data)

    def test_tire_negative_price_rejected(self, edge_case_setup, auth_client_warehouse):
        """رد قیمت‌های منفی در مدل و سریالایزر تایر"""
        setup = edge_case_setup
        tire_invalid = Tire(
            tire_name='تایر قیمت منفی',
            brand=setup['brand'],
            size=setup['size'],
            sale_price=Decimal('-1000'),
            purchase_price=Decimal('-500')
        )
        with pytest.raises(DjangoValidationError):
            tire_invalid.full_clean()

        # در سطح API
        url = reverse('tire-list')
        res = auth_client_warehouse.post(url, {
            'tire_name': 'تایر تست منفی API',
            'brand': setup['brand'].pk,
            'size': setup['size'].pk,
            'sale_price': '-100000'
        }, format='json')
        assert res.status_code == 400

    def test_service_negative_price_rejected(self, auth_client_manager):
        """رد تعرفه منفی در مدل و سریالایزر خدمات فنی"""
        srv = Service(
            service_name='خدمت منفی',
            price=Decimal('-20000')
        )
        with pytest.raises(DjangoValidationError):
            srv.full_clean()

        url = reverse('service-list')
        res = auth_client_manager.post(url, {
            'service_name': 'خدمت تست منفی API',
            'price': '-50000'
        }, format='json')
        assert res.status_code == 400

    def test_service_layer_defenses_for_sales_and_purchase_invoices(self, edge_case_setup, manager_user, warehouse_user):
        """بررسی اعتبارسنجی‌های لایه سرویس در صورت فراخوانی مستقیم"""
        setup = edge_case_setup
        # ۱. فاکتور فروش بدون قلم
        with pytest.raises(DRFValidationError) as exc1:
            create_sales_invoice_service(
                customer=setup['customer'],
                vehicle=setup['vehicle'],
                tire_items_data=[],
                service_items_data=[],
                created_by=manager_user
            )
        assert "ثبت حداقل یک قلم" in str(exc1.value)

        # ۲. فاکتور فروش با تخفیف بیش از جمع کل اقلام
        with pytest.raises(DRFValidationError) as exc2:
            create_sales_invoice_service(
                customer=setup['customer'],
                vehicle=setup['vehicle'],
                tire_items_data=[{'tire': setup['tire'], 'quantity': 1, 'unit_price': Decimal('1500000')}],
                service_items_data=[],
                discount_amount=Decimal('2000000'),
                created_by=manager_user
            )
        assert "مبلغ تخفیف" in str(exc2.value)

        # ۳. فاکتور خرید بدون قلم
        with pytest.raises(DRFValidationError) as exc3:
            create_purchase_invoice_service(
                supplier=setup['supplier'],
                tire_items_data=[],
                created_by=warehouse_user
            )
        assert "ثبت حداقل یک قلم تایر" in str(exc3.value)

