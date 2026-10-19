import pytest
from decimal import Decimal
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User, UserRole
from apps.customers.models import Customer, Vehicle
from apps.catalog.models import Tire, Brand, Size
from apps.invoices.models import (
    SalesInvoice, InvoiceStatus, PaymentStatus
)
from apps.invoices.services import (
    create_sales_invoice_service,
    cancel_sales_invoice_service,
    create_sales_return_service
)
from apps.finance.models import ReceiptVoucher, CustomerRefundVoucher
from apps.finance.services import create_receipt_voucher_service


@pytest.fixture
def settlement_setup(db):
    brand, _ = Brand.objects.get_or_create(brand_name='میشلن فرانسه')
    size, _ = Size.objects.get_or_create(size_name='205/55R16-PILOT')
    tire, _ = Tire.objects.get_or_create(
        tire_name='میشلن پایلوت اسپورت ۴',
        defaults={
            'brand': brand,
            'size': size,
            'stock_quantity': 50,
            'purchase_price': Decimal('2000000.00'),
            'sale_price': Decimal('3000000.00'),
            'min_stock_alert': 5
        }
    )
    customer, _ = Customer.objects.get_or_create(
        phone_number='09129998877',
        defaults={
            'full_name': 'مشتری آزمون تسویه فاکتور',
            'national_code': '0019998877'
        }
    )
    vehicle, _ = Vehicle.objects.get_or_create(
        license_plate='12B34577',
        defaults={
            'customer': customer,
            'model': 'پژو ۲۰۶'
        }
    )
    manager, _ = User.objects.get_or_create(
        username='manager_settlement',
        defaults={
            'role': UserRole.MANAGER,
            'full_name': 'مدیر سیستم و حسابداری',
            'is_staff': True
        }
    )
    return {
        'brand': brand,
        'size': size,
        'tire': tire,
        'customer': customer,
        'vehicle': vehicle,
        'manager': manager
    }


@pytest.mark.django_db
class TestInvoiceSettlement:
    """
    مجموعه آزمون‌های تجربی و تنش‌زا برای راستی‌آزمایی جامع فاکتورهای نقدی،
    تخفیف‌های مرزی (۱۰۰٪، جزئی)، کاراکترهای یونیکد، آمارهای داشبورد و ابزار تطبیق پرداخت‌ها
    """

    def test_cash_sale_100_percent_discount_boundary(
        self, settlement_setup, auth_client_manager
    ):
        """
        سناریو ۱: فاکتور فروش نقدی با ۱۰۰٪ تخفیف درصدی (مبلغ نهایی صفر)
        - نباید خطا بدهد
        - نباید سند دریافت صفر ریالی ایجاد شود (چون مبالغ <= 0 در سند مالی ممنوع است)
        - وضعیت پرداخت باید PAID باشد
        - مانده بدهی در داشبورد باید دقیقاً 0.00 باشد
        - دستور تطبیق پرداخت‌ها باید بدون مغایرت تایید کند
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': tire.sale_price}],
            service_items_data=[],
            discount_percent=Decimal('100.00'),
            payment_status=PaymentStatus.PAID,
            payment_method='کارتخوان / نقدی',
            reference_number='FREE-100-DISCOUNT',
            created_by=manager
        )

        assert invoice.total_amount == Decimal('0.00')
        assert invoice.payment_status == PaymentStatus.PAID
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.paid_amount == Decimal('0.00')

        # نباید سند دریافت ایجاد شده باشد چون مبلغ صفر است
        assert invoice.receipts.count() == 0

        # استعلام از داشبورد
        dash_res = auth_client_manager.get(reverse('dashboard-stats'))
        assert dash_res.status_code == status.HTTP_200_OK
        assert Decimal(str(dash_res.data['total_receivables'])) == Decimal('0.00')
        assert dash_res.data['unpaid_invoices_count'] == 0

        # تطبیق پرداخت‌ها
        call_command('reconcile_payments')

    def test_cash_sale_100_percent_amount_discount_boundary(
        self, settlement_setup, auth_client_manager
    ):
        """
        سناریو ۲: فاکتور فروش نقدی با تخفیف مبلغی دقیقاً معادل جمع کل فاکتور
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        # ۲ حلقه با قیمت ۳,۰۰۰,۰۰۰ = ۶,۰۰۰,۰۰۰ جمع کل
        subtotal = Decimal('6000000.00')
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': tire.sale_price}],
            service_items_data=[],
            discount_amount=subtotal,
            payment_status=PaymentStatus.PAID,
            payment_method='کارتخوان',
            reference_number='FULL-AMT-DISCOUNT',
            created_by=manager
        )

        assert invoice.total_amount == Decimal('0.00')
        assert invoice.payment_status == PaymentStatus.PAID
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.receipts.count() == 0

        dash_res = auth_client_manager.get(reverse('dashboard-stats'))
        assert dash_res.status_code == status.HTTP_200_OK
        assert Decimal(str(dash_res.data['total_receivables'])) == Decimal('0.00')
        assert dash_res.data['unpaid_invoices_count'] == 0

        call_command('reconcile_payments')

    def test_cash_sale_discount_exceeding_subtotal_rejected(
        self, settlement_setup
    ):
        """
        سناریو ۳: تخفیف بیش از جمع کل فاکتور باید صریحاً با ValidationError رد شود
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        subtotal = Decimal('6000000.00')
        with pytest.raises(ValidationError) as exc:
            create_sales_invoice_service(
                customer=customer,
                vehicle=vehicle,
                tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': tire.sale_price}],
                service_items_data=[],
                discount_amount=subtotal + Decimal('0.01'),
                payment_status=PaymentStatus.PAID,
                created_by=manager
            )
        assert "از جمع کل اقلام فاکتور" in str(exc.value.detail[0])

    def test_cash_sale_partial_discounts_exact_auto_receipt(
        self, settlement_setup, auth_client_manager
    ):
        """
        سناریو ۴: فاکتورهای فروش نقدی با تخفیف‌های درصدی و مبلغی متنوع
        بررسی تطابق دقیق ریالی سند دریافت با مبلغ نهایی فاکتور
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        # الف) تخفیف ۲۵٪ روی ۶,۰۰۰,۰۰۰ تومان -> مبلغ کل = ۴,۵۰۰,۰۰۰ تومان
        inv1 = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': tire.sale_price}],
            service_items_data=[],
            discount_percent=Decimal('25.00'),
            payment_status=PaymentStatus.PAID,
            payment_method='کارتخوان سامان',
            reference_number='POS-SEP-998877',
            created_by=manager
        )
        assert inv1.total_amount == Decimal('4500000.00')
        assert inv1.receipts.count() == 1
        rcpt1 = inv1.receipts.first()
        assert rcpt1.amount == Decimal('4500000.00')
        assert rcpt1.reference_number == 'POS-SEP-998877'
        assert inv1.remaining_amount == Decimal('0.00')
        assert inv1.paid_amount == Decimal('4500000.00')

        # ب) تخفیف مبلغی ۱,۲۰۰,۰۰۰ تومان روی ۶,۰۰۰,۰۰۰ تومان -> مبلغ کل = ۴,۸۰۰,۰۰۰ تومان
        inv2 = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': tire.sale_price}],
            service_items_data=[],
            discount_amount=Decimal('1200000.00'),
            payment_status=PaymentStatus.PAID,
            payment_method='نقدی',
            reference_number='CASH-RCV-001',
            created_by=manager
        )
        assert inv2.total_amount == Decimal('4800000.00')
        assert inv2.receipts.count() == 1
        rcpt2 = inv2.receipts.first()
        assert rcpt2.amount == Decimal('4800000.00')
        assert inv2.remaining_amount == Decimal('0.00')

        # ج) تخفیف ۳۳.۳۳٪
        inv3 = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': tire.sale_price}],
            service_items_data=[],
            discount_percent=Decimal('33.33'),
            payment_status=PaymentStatus.PAID,
            payment_method='دستگاه کارتخوان ملت',
            reference_number='MELLAT-3333',
            created_by=manager
        )
        expected_total = Decimal('6000000.00') - (Decimal('6000000.00') * Decimal('33.33') / Decimal('100.0'))
        assert inv3.total_amount == expected_total
        assert inv3.receipts.first().amount == expected_total
        assert inv3.remaining_amount == Decimal('0.00')

        # استعلام داشبورد پس از هر ۳ فاکتور نقدی
        dash_res = auth_client_manager.get(reverse('dashboard-stats'))
        assert dash_res.status_code == status.HTTP_200_OK
        assert Decimal(str(dash_res.data['total_receivables'])) == Decimal('0.00')
        assert dash_res.data['unpaid_invoices_count'] == 0

        call_command('reconcile_payments')

    def test_extreme_unicode_reference_numbers(
        self, settlement_setup, auth_client_manager
    ):
        """
        سناریو ۵: ذخیره و بازیابی کاراکترهای یونیکد پیچیده، کاراکترهای کنترلی نیم‌فاصله،
        ایموجی، نشانه‌های خاص و مرز ۱۰۰ کاراکتر در reference_number
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']

        # دقیقا ۱۰۰ کاراکتر با حروف فارسی، نیم‌فاصله، نمادها و اعداد
        complex_ref = "پیگیری‌کارتخوان-مرکزی-۱۲۳۴۵۶-!@#$%^&*()_+{}[]:;<>?,./~-شعبه‌اصلی-تست-نهایی-مرحله۱-۹۹۸۸۷۷"
        # برش یا تطبیق با طول دقیق ۱۰۰ کاراکتر
        exact_100_ref = (complex_ref + ("X" * 100))[:100]
        assert len(exact_100_ref) == 100

        # ارسال از طریق API فاکتور فروش
        url = reverse('sales-invoice-list')
        payload = {
            'customer': customer.pk,
            'vehicle': vehicle.pk,
            'status': InvoiceStatus.CONFIRMED,
            'payment_status': PaymentStatus.PAID,
            'payment_method': 'دستگاه کارتخوان به پرداخت',
            'reference_number': exact_100_ref,
            'tire_items': [
                {'tire': tire.pk, 'quantity': 1, 'unit_price': str(tire.sale_price)}
            ]
        }

        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED, res.data
        inv_id = res.data['sales_invoice_id']
        assert Decimal(str(res.data['remaining_amount'])) == Decimal('0.00')
        assert Decimal(str(res.data['paid_amount'])) == tire.sale_price

        # بررسی در پایگاه داده
        inv = SalesInvoice.objects.get(pk=inv_id)
        rcpt = inv.receipts.first()
        assert rcpt is not None
        assert rcpt.reference_number == exact_100_ref

        # استعلام از طریق جستجوی رسیدها در API مالی
        receipts_url = reverse('receipt-voucher-list')
        search_res = auth_client_manager.get(f"{receipts_url}?search={exact_100_ref[:20]}")
        assert search_res.status_code == status.HTTP_200_OK
        results = search_res.data.get('results', search_res.data)
        assert len(results) >= 1
        found_ref = results[0]['reference_number']
        assert found_ref == exact_100_ref

    def test_oversized_reference_number_rejected(
        self, settlement_setup, auth_client_manager
    ):
        """
        سناریو ۶: شماره مرجع با طول بیش از ۱۰۰ کاراکتر باید رد شود
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']

        over_100_ref = "A" * 101
        url = reverse('sales-invoice-list')
        payload = {
            'customer': customer.pk,
            'vehicle': vehicle.pk,
            'status': InvoiceStatus.CONFIRMED,
            'payment_status': PaymentStatus.PAID,
            'reference_number': over_100_ref,
            'tire_items': [
                {'tire': tire.pk, 'quantity': 1, 'unit_price': str(tire.sale_price)}
            ]
        }

        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_cash_sale_prevents_manual_overpayment(
        self, settlement_setup
    ):
        """
        سناریو ۷: تلاش برای ثبت رسید دستی مازاد بر فاکتور نقدی تسویه‌شده باید رد شود
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': tire.sale_price}],
            service_items_data=[],
            payment_status=PaymentStatus.PAID,
            created_by=manager
        )

        with pytest.raises(ValidationError) as exc:
            create_receipt_voucher_service(
                sales_invoice=inv,
                amount=Decimal('1000.00'),
                user=manager
            )
        assert "سقف مبلغ کل فاکتور رسیده است" in str(exc.value)

    def test_cash_sale_prevents_invoice_cancellation_with_active_receipt(
        self, settlement_setup
    ):
        """
        سناریو ۸: فاکتور نقدی دارای رسید خودکار نمی‌تواند پیش از ابطال رسید لغو گردد
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': tire.sale_price}],
            service_items_data=[],
            payment_status=PaymentStatus.PAID,
            created_by=manager
        )

        with pytest.raises(ValidationError) as exc:
            cancel_sales_invoice_service(inv, user=manager)
        assert "اسناد دریافت وجه" in str(exc.value.detail[0])

    def test_cash_sale_partial_return_and_dashboard_balance(
        self, settlement_setup, auth_client_manager
    ):
        """
        سناریو ۹: مرجوعی یک قلم از فاکتور نقدی تسویه‌شده
        - مرجوعی ثبت می‌شود
        - سند استرداد به مشتری صادر می‌شود
        - مانده مطالبات داشبورد همچنان 0.00 باقی می‌ماند
        - دستور تطبیق پرداخت‌ها صفر مغایرت گزارش می‌دهد
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        # خرید ۲ حلقه نقدی به قیمت ۳,۰۰۰,۰۰۰ = ۶,۰۰۰,۰۰۰ تومان
        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': tire.sale_price}],
            service_items_data=[],
            payment_status=PaymentStatus.PAID,
            reference_number='POS-RETURN-TEST',
            created_by=manager
        )
        tire_item = inv.tire_items.first()

        # ثبت مرجوعی ۱ حلقه
        return_url = reverse('sales-return-list')
        payload = {
            'sales_invoice': inv.sales_invoice_id,
            'reason': 'معیوب بودن والف تایر',
            'items': [
                {
                    'sales_invoice_tire_item_id': tire_item.id,
                    'quantity': 1
                }
            ]
        }
        res = auth_client_manager.post(return_url, payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED, res.data

        inv.refresh_from_db()
        assert inv.net_amount == Decimal('3000000.00')
        assert inv.remaining_amount == Decimal('0.00')

        # بررسی داشبورد
        dash_res = auth_client_manager.get(reverse('dashboard-stats'))
        assert dash_res.status_code == status.HTTP_200_OK
        assert Decimal(str(dash_res.data['total_receivables'])) == Decimal('0.00')
        assert dash_res.data['unpaid_invoices_count'] == 0

        # تطبیق پرداخت‌ها
        call_command('reconcile_payments')

    def test_multi_invoice_stress_suite_dashboard_and_reconciliation(
        self, settlement_setup, auth_client_manager
    ):
        """
        سناریو ۱۰: استرس تست با ترکیبی از ۱۰ فاکتور نقدی با تخفیف‌های مختلف و پرداخت‌های گوناگون
        تایید عملکرد دقیق و بدون مغایرت DashboardStatsView و reconcile_payments
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        discount_scenarios = [
            (Decimal('0.00'), Decimal('0.00'), 'نقدی', 'REF-01'),
            (Decimal('5.00'), Decimal('0.00'), 'دستگاه کارتخوان سامان', 'REF-02-SEP'),
            (Decimal('10.00'), Decimal('0.00'), 'دستگاه کارتخوان ملت', 'REF-03-MEL'),
            (Decimal('0.00'), Decimal('50000.00'), 'کارتخوان پارسیان', 'REF-04-PAR'),
            (Decimal('20.00'), Decimal('0.00'), 'پایا / ساتنا', 'REF-05-IBAN'),
            (Decimal('0.00'), Decimal('200000.00'), 'نقدی', 'REF-06-CASH'),
            (Decimal('50.00'), Decimal('0.00'), 'کارتخوان', 'REF-07-POS'),
            (Decimal('75.00'), Decimal('0.00'), 'کارتخوان', 'REF-08-POS'),
            (Decimal('100.00'), Decimal('0.00'), 'کارتخوان', 'REF-09-FREE'),
            (Decimal('0.00'), tire.sale_price, 'کارتخوان', 'REF-10-AMT-FREE'),
        ]

        for pct, amt, method, ref in discount_scenarios:
            create_sales_invoice_service(
                customer=customer,
                vehicle=vehicle,
                tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': tire.sale_price}],
                service_items_data=[],
                discount_percent=pct,
                discount_amount=amt,
                payment_status=PaymentStatus.PAID,
                payment_method=method,
                reference_number=ref,
                created_by=manager
            )

        # بررسی نهایی داشبورد
        dash_res = auth_client_manager.get(reverse('dashboard-stats'))
        assert dash_res.status_code == status.HTTP_200_OK
        assert Decimal(str(dash_res.data['total_receivables'])) == Decimal('0.00')
        assert dash_res.data['unpaid_invoices_count'] == 0

        # اجرای دستور تطبیق پرداخت‌ها روی کل پایگاه داده
        call_command('reconcile_payments')

    def test_mixed_cash_and_credit_sales_receivables_isolation(
        self, settlement_setup, auth_client_manager
    ):
        """
        سناریو ۱۱: تفکیک دقیق مطالبات نسیه از نقدی در داشبورد
        - یک فاکتور نسیه (UNPAID) به مبلغ ۳,۰۰۰,۰۰۰ تومان صادر می‌شود
        - پنج فاکتور نقدی (PAID) به مجموع ۱۵,۰۰۰,۰۰۰ تومان صادر می‌شود
        - داشبورد باید دقیقاً ۳,۰۰۰,۰۰۰ تومان مطالبات معوق و دقیقاً ۱ فاکتور پرداخت‌نشده نشان دهد
        - فاکتورهای نقدی به هیچ وجه نباید در مانده مطالبات اثر بگذارند یا مبلغی اضافه کنند
        """
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        # فاکتور نسیه (UNPAID)
        credit_inv = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': tire.sale_price}],
            service_items_data=[],
            payment_status=PaymentStatus.UNPAID,
            created_by=manager
        )
        assert credit_inv.remaining_amount == tire.sale_price

        # ۵ فاکتور نقدی (PAID)
        for i in range(5):
            create_sales_invoice_service(
                customer=customer,
                vehicle=vehicle,
                tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': tire.sale_price}],
                service_items_data=[],
                payment_status=PaymentStatus.PAID,
                payment_method='کارتخوان',
                reference_number=f'MIXED-CASH-{i+1}',
                created_by=manager
            )

        dash_res = auth_client_manager.get(reverse('dashboard-stats'))
        assert dash_res.status_code == status.HTTP_200_OK
        # مطالبات باید دقیقاً معادل تنها فاکتور نسیه باشد (۳,۰۰۰,۰۰۰ تومان)
        assert Decimal(str(dash_res.data['total_receivables'])) == tire.sale_price
        assert dash_res.data['unpaid_invoices_count'] == 1

        call_command('reconcile_payments')

    def test_reconcile_payments_command_output_and_zero_discrepancies(
        self, settlement_setup
    ):
        """
        سناریو ۱۲: اجرای مستقیم دستور reconcile_payments در محیط با تراکنش‌های مختلف
        و اعتبارسنجی خروجی متنی موفقیت‌آمیز
        """
        from io import StringIO
        tire = settlement_setup['tire']
        customer = settlement_setup['customer']
        vehicle = settlement_setup['vehicle']
        manager = settlement_setup['manager']

        # صدور فاکتور نقدی با رسید خودکار
        create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': tire.sale_price}],
            service_items_data=[],
            payment_status=PaymentStatus.PAID,
            reference_number='VERIFY-RECONCILE-001',
            created_by=manager
        )

        out = StringIO()
        call_command('reconcile_payments', stdout=out)
        output_str = out.getvalue()

        assert "۰ مغایرت" in output_str or "0 مغایرت" in output_str
        assert "تطبیق پرداخت‌ها با موفقیت انجام شد" in output_str

