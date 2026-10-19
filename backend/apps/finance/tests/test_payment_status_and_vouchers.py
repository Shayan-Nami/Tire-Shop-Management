import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer
from apps.suppliers.models import Supplier
from apps.invoices.models import (
    SalesInvoice, PurchaseInvoice, InvoiceStatus, PaymentStatus
)
from apps.finance.models import ReceiptVoucher, PaymentVoucher, CustomerRefundVoucher
from apps.finance.services import (
    create_receipt_voucher_service,
    cancel_receipt_voucher_service,
    create_payment_voucher_service,
    cancel_payment_voucher_service,
    create_customer_refund_voucher_service,
    cancel_customer_refund_voucher_service,
    sync_sales_invoice_payment_status,
    sync_purchase_invoice_payment_status
)
from apps.invoices.services import (
    create_sales_invoice_service,
    create_purchase_invoice_service,
    cancel_purchase_invoice_service,
    create_sales_return_service
)


@pytest.fixture
def setup_finance_data(db, manager_user):
    brand = Brand.objects.create(brand_name='کویر تایر')
    size = Size.objects.create(size_name='205/55R16')
    tire = Tire.objects.create(
        tire_name='کوir تایر رادیال',
        brand=brand,
        size=size,
        stock_quantity=30,
        purchase_price=Decimal('1000000.00'),
        sale_price=Decimal('1500000.00'),
        min_stock_alert=5
    )
    StockMovement.objects.create(
        tire=tire,
        quantity=30,
        movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=30,
        unit_cost=Decimal('1000000.00'),
        user=manager_user,
        description='موجودی اولیه'
    )
    customer = Customer.objects.create(
        full_name='محمد حسینی',
        phone_number='09129876543'
    )
    supplier = Supplier.objects.create(
        supplier_name='پخش تایر مرکزی',
        phone_number='02188889999'
    )
    return {
        'brand': brand,
        'size': size,
        'tire': tire,
        'customer': customer,
        'supplier': supplier
    }


@pytest.mark.django_db
class TestPaymentStatusAndVouchers:

    def test_sales_invoice_payment_status_transitions_and_voucher_cancellation(
        self, setup_finance_data, manager_user
    ):
        """
        تست گذار وضعیت پرداخت فاکتور فروش:
        UNPAID -> PARTIAL -> PAID
        سپس با ابطال اسناد دریافت:
        PAID -> PARTIAL -> UNPAID
        """
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.total_amount == Decimal('1000000.00')
        assert invoice.payment_status == PaymentStatus.UNPAID

        # ۱. پرداخت جزئی ۳۰۰,۰۰۰ -> وضعیت PARTIAL
        r1 = create_receipt_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('300000.00'),
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.payment_status == PaymentStatus.PARTIAL

        # ۲. پرداخت مانده ۷۰۰,۰۰۰ -> وضعیت PAID
        r2 = create_receipt_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('700000.00'),
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.payment_status == PaymentStatus.PAID

        # ۳. ابطال سند دوم (۷۰۰,۰۰۰) -> بازگشت وضعیت به PARTIAL
        cancel_receipt_voucher_service(r2, reason='اشتباه در درج کارتخوان', user=manager_user)
        invoice.refresh_from_db()
        assert invoice.payment_status == PaymentStatus.PARTIAL

        # ۴. ابطال سند اول (۳۰۰,۰۰۰) -> بازگشت وضعیت به UNPAID
        cancel_receipt_voucher_service(r1, reason='برگشت تراکنش بانکی', user=manager_user)
        invoice.refresh_from_db()
        assert invoice.payment_status == PaymentStatus.UNPAID

    def test_payment_exceeding_remaining_rejected_in_service_and_api(
        self, setup_finance_data, manager_user, auth_client_manager
    ):
        """پرداخت بیشتر از مانده بدهی فاکتور در سطح سرویس و API رد می‌شود"""
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        create_receipt_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('600000.00'),
            user=manager_user
        )
        # مانده بدهی: ۴۰۰,۰۰۰

        # تلاش برای ثبت ۵۰۰,۰۰۰ در لایه سرویس -> ValidationError
        with pytest.raises(ValidationError) as exc:
            create_receipt_voucher_service(
                sales_invoice=invoice,
                amount=Decimal('500000.00'),
                user=manager_user
            )
        assert 'بیشتر باشد' in str(exc.value)

        # تلاش برای ثبت ۵۰۰,۰۰۰ از طریق API -> 400 Bad Request
        url = reverse('receipt-voucher-list')
        res = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'amount': '500000.00'
        })
        assert res.status_code == 400
        assert 'amount' in res.data['errors']

    def test_sales_return_after_full_payment_creates_excess_amount(
        self, setup_finance_data, manager_user, auth_client_manager
    ):
        """مرجوعی پس از تسویه کامل فاکتور، فیلد محاسباتی excess_amount ایجاد می‌کند"""
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()

        # تسویه کامل
        create_receipt_voucher_service(invoice, Decimal('1000000.00'), user=manager_user)
        invoice.refresh_from_db()
        assert invoice.payment_status == PaymentStatus.PAID
        assert invoice.excess_amount == Decimal('0.00')

        # مرجوعی ۱ حلقه (۵۰۰,۰۰۰ تومان)
        create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='نارضایتی مشتری',
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.net_amount == Decimal('500000.00')
        assert invoice.excess_amount == Decimal('500000.00')
        assert invoice.payment_status == PaymentStatus.PAID

        # تأیید وجود excess_amount در خروجی سریالایزر فاکتور
        detail_url = reverse('sales-invoice-detail', kwargs={'pk': invoice.pk})
        res = auth_client_manager.get(detail_url)
        assert res.status_code == 200
        assert Decimal(str(res.data['excess_amount'])) == Decimal('500000.00')

    def test_customer_refund_voucher_and_over_refund_rejected(
        self, setup_finance_data, manager_user, auth_client_manager
    ):
        """
        ثبت سند استرداد وجه به مشتری:
        ۱. استرداد بیشتر از مازاد پرداخت رد می‌شود
        ۲. استرداد معتبر excess_amount را صفر می‌کند
        """
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()
        create_receipt_voucher_service(invoice, Decimal('1000000.00'), user=manager_user)
        ret = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی',
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.excess_amount == Decimal('500000.00')

        # ۱. تلاش برای استرداد ۶۰۰,۰۰۰ تومان (بیشتر از ۵۰۰,۰۰۰) -> رد
        with pytest.raises(ValidationError) as exc:
            create_customer_refund_voucher_service(
                sales_invoice=invoice,
                amount=Decimal('600000.00'),
                user=manager_user
            )
        assert 'بیشتر باشد' in str(exc.value)

        # ۲. استرداد معتبر ۳۰۰,۰۰۰ تومان از طریق API
        refund_url = reverse('customer-refund-voucher-list')
        res1 = auth_client_manager.post(refund_url, {
            'sales_invoice': invoice.pk,
            'sales_return': ret.pk,
            'amount': '300000.00',
            'notes': 'استرداد نقدی قسط اول'
        })
        assert res1.status_code == 201
        invoice.refresh_from_db()
        assert invoice.excess_amount == Decimal('200000.00')

        # ۳. استرداد ۲۰۰,۰۰۰ مانده از طریق سرویس
        create_customer_refund_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('200000.00'),
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.excess_amount == Decimal('0.00')

        # ۴. تلاش برای استرداد مجدد زمانی که مازاد ۰ است -> رد
        with pytest.raises(ValidationError) as exc2:
            create_customer_refund_voucher_service(
                sales_invoice=invoice,
                amount=Decimal('50000.00'),
                user=manager_user
            )
        assert 'مازاد پرداختی قابل استرداد ندارد' in str(exc2.value)

    def test_cancel_customer_refund_restores_excess_amount(
        self, setup_finance_data, manager_user
    ):
        """ابطال سند استرداد وجه، مبلغ مازاد فاکتور را دوباره احیا می‌کند"""
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('800000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()
        create_receipt_voucher_service(invoice, Decimal('800000.00'), user=manager_user)
        create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی کامل',
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.excess_amount == Decimal('800000.00')

        refund = create_customer_refund_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('800000.00'),
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.excess_amount == Decimal('0.00')

        # ابطال سند استرداد
        cancel_customer_refund_voucher_service(
            voucher=refund,
            reason='خطا در عودت وجه',
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.excess_amount == Decimal('800000.00')

    def test_purchase_invoice_payment_status_transitions_and_cancel(
        self, setup_finance_data, manager_user
    ):
        """
        تست گذار وضعیت پرداخت فاکتور خرید (UNPAID -> PARTIAL -> PAID)،
        ابطال اسناد پرداخت و امکان لغو فاکتور خرید پس از ابطال پرداخت‌ها
        """
        tire = setup_finance_data['tire']
        supplier = setup_finance_data['supplier']

        p_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_cost': Decimal('1000000.00')}],
            created_by=manager_user
        )
        p_inv.refresh_from_db()
        assert p_inv.total_amount == Decimal('2000000.00')
        assert p_inv.payment_status == PaymentStatus.UNPAID

        # ۱. پرداخت جزئی ۱,۰۰۰,۰۰۰ -> PARTIAL
        pv1 = create_payment_voucher_service(p_inv, Decimal('1000000.00'), user=manager_user)
        p_inv.refresh_from_db()
        assert p_inv.payment_status == PaymentStatus.PARTIAL

        # ۲. پرداخت مابقی ۱,۰۰۰,۰۰۰ -> PAID
        pv2 = create_payment_voucher_service(p_inv, Decimal('1000000.00'), user=manager_user)
        p_inv.refresh_from_db()
        assert p_inv.payment_status == PaymentStatus.PAID

        # تلاش برای لغو فاکتور در حضور پرداخت فعال -> رد با خطا
        with pytest.raises(ValidationError) as exc_cancel:
            cancel_purchase_invoice_service(p_inv, user=manager_user)
        assert 'سند پرداخت وجه' in str(exc_cancel.value)

        # ۳. ابطال پرداخت دوم -> وضعیت PARTIAL
        cancel_payment_voucher_service(pv2, reason='ابطال چک صیادی', user=manager_user)
        p_inv.refresh_from_db()
        assert p_inv.payment_status == PaymentStatus.PARTIAL

        # ۴. ابطال پرداخت اول -> وضعیت UNPAID
        cancel_payment_voucher_service(pv1, reason='ابطال حواله بانکی', user=manager_user)
        p_inv.refresh_from_db()
        assert p_inv.payment_status == PaymentStatus.UNPAID

        # حالا که تمام اسناد پرداخت ابطال شده‌اند، لغو فاکتور خرید باید با موفقیت انجام شود
        cancel_purchase_invoice_service(p_inv, user=manager_user)
        p_inv.refresh_from_db()
        assert p_inv.status == InvoiceStatus.CANCELLED

    def test_vouchers_api_blocks_put_patch_delete_with_405(
        self, setup_finance_data, manager_user, auth_client_manager
    ):
        """متدهای PUT, PATCH و DELETE روی تمام اسناد مالی باید 405 MethodNotAllowed باشند"""
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']
        supplier = setup_finance_data['supplier']

        sales_inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        receipt = create_receipt_voucher_service(sales_inv, Decimal('200000.00'), user=manager_user)

        r_url = reverse('receipt-voucher-detail', kwargs={'pk': receipt.pk})
        assert auth_client_manager.delete(r_url).status_code == 405
        assert auth_client_manager.put(r_url, {'amount': '300000.00'}).status_code == 405
        assert auth_client_manager.patch(r_url, {'amount': '300000.00'}).status_code == 405

        purch_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_cost': Decimal('400000.00')}],
            created_by=manager_user
        )
        payment = create_payment_voucher_service(purch_inv, Decimal('200000.00'), user=manager_user)

        p_url = reverse('payment-voucher-detail', kwargs={'pk': payment.pk})
        assert auth_client_manager.delete(p_url).status_code == 405
        assert auth_client_manager.put(p_url, {'amount': '300000.00'}).status_code == 405
        assert auth_client_manager.patch(p_url, {'amount': '300000.00'}).status_code == 405

    def test_saved_payment_status_matches_recalculated_status_at_every_step(
        self, setup_finance_data, manager_user
    ):
        """
        بررسی یکپارچگی داده: در تمام مراحل فاکتور فروش، وضعیت ذخیره‌شده با محاسبه مجدد از روی اسناد دقیقاً برابر است
        """
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('600000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()

        def assert_in_sync():
            invoice.refresh_from_db()
            recalc = sync_sales_invoice_payment_status(invoice)
            assert invoice.payment_status == recalc
            return recalc

        # گام ۱: صدور فاکتور -> UNPAID
        assert assert_in_sync() == PaymentStatus.UNPAID

        # گام ۲: پرداخت جزئی ۵۰۰,۰۰۰ -> PARTIAL
        r1 = create_receipt_voucher_service(invoice, Decimal('500000.00'), user=manager_user)
        assert assert_in_sync() == PaymentStatus.PARTIAL

        # گام ۳: پرداخت مابقی ۷۰۰,۰۰۰ -> PAID
        r2 = create_receipt_voucher_service(invoice, Decimal('700000.00'), user=manager_user)
        assert assert_in_sync() == PaymentStatus.PAID

        # گام ۴: مرجوعی ۱ حلقه (۶۰۰,۰۰۰) -> همچنان PAID (با مازاد ۶۰۰,۰۰۰)
        create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='تست انطباق',
            user=manager_user
        )
        assert assert_in_sync() == PaymentStatus.PAID
        assert invoice.excess_amount == Decimal('600000.00')

        # گام ۵: استرداد ۶۰۰,۰۰۰ مازاد -> همچنان PAID
        refund = create_customer_refund_voucher_service(invoice, Decimal('600000.00'), user=manager_user)
        assert assert_in_sync() == PaymentStatus.PAID
        assert invoice.excess_amount == Decimal('0.00')

        # گام ۶: تلاش برای ابطال سند دریافت ۷۰۰,۰۰۰ در حالی که استرداد فعال ۶۰۰,۰۰۰ است -> باید مسدود شود (Fix 1)
        with pytest.raises(ValidationError) as exc_info:
            cancel_receipt_voucher_service(r2, reason='تست ابطال مستقیم', user=manager_user)
        assert 'کمتر خواهد شد' in str(exc_info.value)
        assert 'ابتدا اسناد استرداد وجه مربوطه را ابطال نمایید' in str(exc_info.value)

        # گام ۷: ابتدا ابطال سند استرداد ۶۰۰,۰۰۰
        cancel_customer_refund_voucher_service(refund, reason='ابطال استرداد برای اصلاح اسناد', user=manager_user)
        assert assert_in_sync() == PaymentStatus.PAID
        assert invoice.excess_amount == Decimal('600000.00')

        # گام ۸: اکنون ابطال سند دریافت ۷۰۰,۰۰۰ موفقیت‌آمیز است -> دریافتی ۵۰۰,۰۰۰ در برابر خالص ۶۰۰,۰۰۰ -> PARTIAL
        cancel_receipt_voucher_service(r2, reason='تست ابطال سند دریافت', user=manager_user)
        assert assert_in_sync() == PaymentStatus.PARTIAL
        assert invoice.excess_amount == Decimal('0.00')

    def test_cancel_receipt_voucher_blocked_when_receipts_less_than_refunds(
        self, setup_finance_data, manager_user
    ):
        """
        بررسی دقیق عدم امکان ابطال ReceiptVoucher در صورتی که دریافتی‌های معتبر باقی‌مانده
        کمتر از استردادهای معتبر شود (با قفل ردیف فاکتور و خطای مشخص فارسی).
        """
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()

        # ثبت دریافتی ۱,۰۰۰,۰۰۰
        r1 = create_receipt_voucher_service(invoice, Decimal('1000000.00'), user=manager_user)
        # مرجوعی کامل
        create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی جهت تست ابطال',
            user=manager_user
        )
        # استرداد ۶۰۰,۰۰۰ به مشتری
        create_customer_refund_voucher_service(invoice, Decimal('600000.00'), user=manager_user)

        # تلاش برای ابطال سند دریافت وجه: بعد از ابطال دریافتی 0 می‌شود در حالی که استرداد معتبر 600,000 است -> باید رد شود
        with pytest.raises(ValidationError) as exc:
            cancel_receipt_voucher_service(r1, reason='ابطال غیرمجاز', user=manager_user)
        assert 'کمتر خواهد شد' in str(exc.value)
        assert 'ابتدا اسناد استرداد وجه مربوطه را ابطال نمایید' in str(exc.value)

    def test_voucher_cancellation_validation_and_permissions(
        self, setup_finance_data, manager_user, auth_client_manager, auth_client_warehouse, auth_client_technician
    ):
        """
        اعتبارسنجی ابطال سند:
        - نیاز به دلیل غیرخالی
        - رد ابطال مجدد
        - مجوز دسترسی فقط برای مدیر (تکنسین و انباردار 403)
        """
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        receipt = create_receipt_voucher_service(invoice, Decimal('300000.00'), user=manager_user)

        cancel_url = reverse('receipt-voucher-cancel', kwargs={'pk': receipt.pk})

        # تکنسین 403
        assert auth_client_technician.post(cancel_url, {'reason': 'تست'}).status_code == 403
        # انباردار 403
        assert auth_client_warehouse.post(cancel_url, {'reason': 'تست'}).status_code == 403

        # مدیر بدون ذکر دلیل -> 400
        res_no_reason = auth_client_manager.post(cancel_url, {'reason': ''})
        assert res_no_reason.status_code == 400
        assert 'reason' in res_no_reason.data['errors']

        # مدیر با دلیل معتبر -> 200
        res_ok = auth_client_manager.post(cancel_url, {'reason': 'دلیل معتبر ابطال'})
        assert res_ok.status_code == 200
        assert res_ok.data['is_cancelled'] is True
        assert res_ok.data['cancellation_reason'] == 'دلیل معتبر ابطال'

        # تلاش مجدد برای ابطال سند باطل‌شده -> 400
        res_double = auth_client_manager.post(cancel_url, {'reason': 'ابطال دوباره'})
        assert res_double.status_code == 400
        assert 'قبلاً ابطال شده' in str(res_double.data)

    def test_reference_number_persisted_and_returned_across_vouchers_and_api(
        self, setup_finance_data, manager_user, auth_client_manager
    ):
        """
        تست جامع ذخیره و بازخوانی reference_number (شماره پیگیری / مرجع بانکی)
        در اسناد دریافت، پرداخت و استرداد وجه در لایه سرویس و اندپوینت‌های API
        """
        tire = setup_finance_data['tire']
        customer = setup_finance_data['customer']
        supplier = setup_finance_data['supplier']

        # ۱. تست سند دریافت وجه (ReceiptVoucher)
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )

        receipt = create_receipt_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('400000.00'),
            payment_method='دستگاه پوز سامان',
            reference_number='POS-REF-100200',
            notes='تست شماره پیگیری دریافتی',
            user=manager_user
        )
        assert receipt.reference_number == 'POS-REF-100200'

        # واکشی از طریق API
        r_url = reverse('receipt-voucher-detail', kwargs={'pk': receipt.pk})
        res_r = auth_client_manager.get(r_url)
        assert res_r.status_code == 200
        assert res_r.data['reference_number'] == 'POS-REF-100200'

        # ثبت دریافت وجه از طریق API با شماره پیگیری
        res_post_r = auth_client_manager.post(reverse('receipt-voucher-list'), {
            'sales_invoice': invoice.pk,
            'amount': '300000.00',
            'payment_method': 'کارتخوان بانک ملت',
            'reference_number': 'POS-REF-MEL-300400',
            'notes': 'ثبت از طریق API'
        }, format='json')
        assert res_post_r.status_code == 201
        assert res_post_r.data['reference_number'] == 'POS-REF-MEL-300400'

        # جستجو بر اساس reference_number
        res_search_r = auth_client_manager.get(f"{reverse('receipt-voucher-list')}?search=MEL-300400")
        assert res_search_r.status_code == 200
        assert res_search_r.data['count'] == 1
        assert res_search_r.data['results'][0]['reference_number'] == 'POS-REF-MEL-300400'

        # ۲. تست سند پرداخت وجه (PaymentVoucher)
        p_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_cost': Decimal('400000.00')}],
            created_by=manager_user
        )

        payment = create_payment_voucher_service(
            purchase_invoice=p_inv,
            amount=Decimal('500000.00'),
            payment_method='حواله پایا',
            reference_number='PAYA-TRX-556677',
            notes='تست شماره پیگیری پرداختی',
            user=manager_user
        )
        assert payment.reference_number == 'PAYA-TRX-556677'

        p_url = reverse('payment-voucher-detail', kwargs={'pk': payment.pk})
        res_p = auth_client_manager.get(p_url)
        assert res_p.status_code == 200
        assert res_p.data['reference_number'] == 'PAYA-TRX-556677'

        res_post_p = auth_client_manager.post(reverse('payment-voucher-list'), {
            'purchase_invoice': p_inv.pk,
            'amount': '200000.00',
            'payment_method': 'ساتنا',
            'reference_number': 'SATNA-TRX-889900'
        }, format='json')
        assert res_post_p.status_code == 201
        assert res_post_p.data['reference_number'] == 'SATNA-TRX-889900'

        res_search_p = auth_client_manager.get(f"{reverse('payment-voucher-list')}?search=SATNA-TRX")
        assert res_search_p.status_code == 200
        assert res_search_p.data['count'] == 1

        # ۳. تست سند استرداد وجه به مشتری (CustomerRefundVoucher)
        # تکمیل تسویه فاکتور فروش اول (۳۰۰,۰۰۰ باقی‌مانده)
        create_receipt_voucher_service(invoice, Decimal('300000.00'), user=manager_user)
        sales_item = invoice.tire_items.first()
        s_return = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='تست استرداد',
            user=manager_user
        )

        refund = create_customer_refund_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('200000.00'),
            sales_return=s_return,
            payment_method='کارتخوان / نقدی',
            reference_number='REF-TRACK-112233',
            notes='استرداد جزئی وجه مرجوعی',
            user=manager_user
        )
        assert refund.reference_number == 'REF-TRACK-112233'

        ref_url = reverse('customer-refund-voucher-detail', kwargs={'pk': refund.pk})
        res_ref = auth_client_manager.get(ref_url)
        assert res_ref.status_code == 200
        assert res_ref.data['reference_number'] == 'REF-TRACK-112233'

        res_post_ref = auth_client_manager.post(reverse('customer-refund-voucher-list'), {
            'sales_invoice': invoice.pk,
            'sales_return': s_return.pk,
            'amount': '100000.00',
            'payment_method': 'کارت‌به‌کارت',
            'reference_number': 'REF-TRACK-445566'
        }, format='json')
        assert res_post_ref.status_code == 201
        assert res_post_ref.data['reference_number'] == 'REF-TRACK-445566'

        res_search_ref = auth_client_manager.get(f"{reverse('customer-refund-voucher-list')}?search=445566")
        assert res_search_ref.status_code == 200
        assert res_search_ref.data['count'] == 1
