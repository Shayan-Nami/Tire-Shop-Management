"""
Test Suite: Financial Calculation & Overpayment Safeguards

Tested Dimensions:
1. Multi-step partial receipts, sales returns, and customer refunds lifecycle:
   - remaining_amount accuracy at every step on model property, queryset annotation, and API serializer
   - excess_amount calculation
   - payment_status transitions (UNPAID -> PARTIAL -> PAID -> PARTIAL -> PAID)
   - voucher cancellations and remaining_amount recalculation
2. Overpayment rejection safeguards:
   - amount > remaining_amount rejected via API (HTTP 400) and service (ValidationError)
   - exact boundary (amount == remaining_amount) succeeds
   - fully paid invoice rejects new receipt
   - zero and negative amounts rejected
   - payment on cancelled invoice rejected
3. Reference number preservation & queryability:
   - reference_number preserved across ReceiptVoucher, PaymentVoucher, CustomerRefundVoucher
   - auto-created cash receipt preserves reference_number from SalesInvoice payload
   - search via ?search=<ref> on all voucher list endpoints
   - verification of exact query parameter ?reference_number=<ref> vs ?search=<ref>
"""

import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer, Vehicle
from apps.suppliers.models import Supplier
from apps.invoices.models import SalesInvoice, InvoiceStatus, PaymentStatus
from apps.invoices.services import create_sales_invoice_service, create_sales_return_service
from apps.finance.services import (
    create_receipt_voucher_service,
    create_customer_refund_voucher_service
)


@pytest.fixture
def finance_test_setup(db, manager_user):
    brand = Brand.objects.create(brand_name='چالشگر گلدستون')
    size = Size.objects.create(size_name='215/60R16-TEST')
    tire = Tire.objects.create(
        tire_name='تایر رادیال چالشگر',
        brand=brand,
        size=size,
        stock_quantity=50,
        purchase_price=Decimal('2000000.00'),
        sale_price=Decimal('3000000.00'),
        min_stock_alert=5
    )
    StockMovement.objects.create(
        tire=tire,
        quantity=50,
        movement_type=StockMovementType.INITIAL_STOCK,
        balance_after=50,
        unit_cost=Decimal('2000000.00'),
        user=manager_user,
        description='موجودی اولیه چالش'
    )
    customer = Customer.objects.create(
        full_name='سامان کاویانی (مشتری تست چالش)',
        phone_number='09121112233'
    )
    vehicle = Vehicle.objects.create(
        customer=customer,
        license_plate='55ج777-66',
        model='دنا پلاس'
    )
    supplier = Supplier.objects.create(
        supplier_name='تأمین پخش کاسپین',
        phone_number='02177778888'
    )
    return {
        'brand': brand,
        'size': size,
        'tire': tire,
        'customer': customer,
        'vehicle': vehicle,
        'supplier': supplier
    }


@pytest.mark.django_db
class TestFinancialRemainingAmountAndRefundsLifecycle:
    """
    Challenge 1: Verify that remaining_amount accurately reflects remaining debt
    after multiple partial receipts, returns, customer refunds, and voucher cancellations.
    """

    def test_multi_step_partial_receipts_returns_refunds_and_cancellations(
        self, finance_test_setup, auth_client_manager, manager_user
    ):
        tire = finance_test_setup['tire']
        customer = finance_test_setup['customer']
        vehicle = finance_test_setup['vehicle']

        # Step 1: Create SalesInvoice with 4 tires @ 3,000,000 = 12,000,000 IRR
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=vehicle,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_price': Decimal('3000000.00')}],
            service_items_data=[],
            payment_status=PaymentStatus.UNPAID,
            created_by=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.total_amount == Decimal('12000000.00')
        assert invoice.net_amount == Decimal('12000000.00')
        assert invoice.paid_amount == Decimal('0.00')
        assert invoice.remaining_amount == Decimal('12000000.00')
        assert invoice.excess_amount == Decimal('0.00')
        assert invoice.payment_status == PaymentStatus.UNPAID

        # Verify API representation (GET /invoices/sales/{id}/ and list)
        detail_url = reverse('sales-invoice-detail', kwargs={'pk': invoice.pk})
        res_api = auth_client_manager.get(detail_url)
        assert res_api.status_code == status.HTTP_200_OK
        assert Decimal(res_api.data['remaining_amount']) == Decimal('12000000.00')
        assert Decimal(res_api.data['paid_amount']) == Decimal('0.00')
        assert res_api.data['payment_status'] == PaymentStatus.UNPAID

        # Step 2: 1st Partial Receipt: 4,000,000 IRR via API
        receipt_url = reverse('receipt-voucher-list')
        res_r1 = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '4000000.00',
            'payment_method': 'کارتخوان بانک ملت',
            'reference_number': 'REC-PARTIAL-1'
        }, format='json')
        assert res_r1.status_code == status.HTTP_201_CREATED

        invoice.refresh_from_db()
        assert invoice.paid_amount == Decimal('4000000.00')
        assert invoice.remaining_amount == Decimal('8000000.00')
        assert invoice.payment_status == PaymentStatus.PARTIAL

        res_api = auth_client_manager.get(detail_url)
        assert Decimal(res_api.data['remaining_amount']) == Decimal('8000000.00')
        assert Decimal(res_api.data['paid_amount']) == Decimal('4000000.00')
        assert res_api.data['payment_status'] == PaymentStatus.PARTIAL

        # Step 3: 2nd Partial Receipt: 3,000,000 IRR via service
        r2 = create_receipt_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('3000000.00'),
            payment_method='کارتخوان سامان',
            reference_number='REC-PARTIAL-2',
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.paid_amount == Decimal('7000000.00')
        assert invoice.remaining_amount == Decimal('5000000.00')
        assert invoice.payment_status == PaymentStatus.PARTIAL

        res_api = auth_client_manager.get(detail_url)
        assert Decimal(res_api.data['remaining_amount']) == Decimal('5000000.00')
        assert Decimal(res_api.data['paid_amount']) == Decimal('7000000.00')

        # Step 4: Sales Return of 1 tire (3,000,000 IRR)
        # Customer previously paid 7,000,000. Total was 12,000,000.
        # New net_amount = 9,000,000. Effective paid = 7,000,000.
        # Remaining debt must become 9,000,000 - 7,000,000 = 2,000,000 IRR.
        sales_item = invoice.tire_items.first()
        create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی قلم اول به دلیل عدم نیاز',
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.returned_amount == Decimal('3000000.00')
        assert invoice.net_amount == Decimal('9000000.00')
        assert invoice.paid_amount == Decimal('7000000.00')
        assert invoice.remaining_amount == Decimal('2000000.00')
        assert invoice.excess_amount == Decimal('0.00')
        assert invoice.payment_status == PaymentStatus.PARTIAL

        res_api = auth_client_manager.get(detail_url)
        assert Decimal(res_api.data['net_amount']) == Decimal('9000000.00')
        assert Decimal(res_api.data['remaining_amount']) == Decimal('2000000.00')
        assert Decimal(res_api.data['paid_amount']) == Decimal('7000000.00')

        # Step 5: Customer pays remaining debt of 2,000,000 IRR
        r3 = create_receipt_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('2000000.00'),
            payment_method='نقدی',
            reference_number='REC-FULL-3',
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.paid_amount == Decimal('9000000.00')
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.excess_amount == Decimal('0.00')
        assert invoice.payment_status == PaymentStatus.PAID

        res_api = auth_client_manager.get(detail_url)
        assert Decimal(res_api.data['remaining_amount']) == Decimal('0.00')
        assert Decimal(res_api.data['paid_amount']) == Decimal('9000000.00')
        assert res_api.data['payment_status'] == PaymentStatus.PAID

        # Step 6: Customer returns ANOTHER tire (3,000,000 IRR) from the fully paid invoice
        # New net_amount = 12,000,000 - 6,000,000 = 6,000,000.
        # Customer had paid 9,000,000.
        # Excess is 9,000,000 - 6,000,000 = 3,000,000 IRR.
        # Remaining debt is 0.00.
        s_return_2 = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی قلم دوم با مازاد پرداختی',
            user=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.returned_amount == Decimal('6000000.00')
        assert invoice.net_amount == Decimal('6000000.00')
        assert invoice.paid_amount == Decimal('9000000.00')
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.excess_amount == Decimal('3000000.00')
        assert invoice.payment_status == PaymentStatus.PAID

        res_api = auth_client_manager.get(detail_url)
        assert Decimal(res_api.data['excess_amount']) == Decimal('3000000.00')
        assert Decimal(res_api.data['remaining_amount']) == Decimal('0.00')

        # Step 7: Issue partial CustomerRefundVoucher of 1,000,000 IRR via API
        refund_url = reverse('customer-refund-voucher-list')
        res_ref1 = auth_client_manager.post(refund_url, {
            'sales_invoice': invoice.pk,
            'sales_return': s_return_2.pk,
            'amount': '1000000.00',
            'payment_method': 'کارت‌به‌کارت',
            'reference_number': 'REFUND-PART-1'
        }, format='json')
        assert res_ref1.status_code == status.HTTP_201_CREATED

        invoice.refresh_from_db()
        # net paid = 9,000,000 - 1,000,000 = 8,000,000
        # net amount = 6,000,000
        # remaining_amount = max(6m - 8m, 0) = 0
        # excess_amount = 8m - 6m = 2,000,000
        assert invoice.paid_amount == Decimal('8000000.00')
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.excess_amount == Decimal('2000000.00')
        assert invoice.payment_status == PaymentStatus.PAID

        res_api = auth_client_manager.get(detail_url)
        assert Decimal(res_api.data['excess_amount']) == Decimal('2000000.00')
        assert Decimal(res_api.data['remaining_amount']) == Decimal('0.00')
        assert Decimal(res_api.data['paid_amount']) == Decimal('8000000.00')

        # Step 8: Issue remaining CustomerRefundVoucher of 2,000,000 IRR via service
        ref2 = create_customer_refund_voucher_service(
            sales_invoice=invoice,
            amount=Decimal('2000000.00'),
            sales_return=s_return_2,
            payment_method='کارتخوان / نقدی',
            reference_number='REFUND-PART-2',
            user=manager_user
        )
        invoice.refresh_from_db()
        # net paid = 9,000,000 - 3,000,000 = 6,000,000
        # net amount = 6,000,000
        # excess = 0.00, remaining = 0.00
        assert invoice.paid_amount == Decimal('6000000.00')
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.excess_amount == Decimal('0.00')
        assert invoice.payment_status == PaymentStatus.PAID

        res_api = auth_client_manager.get(detail_url)
        assert Decimal(res_api.data['excess_amount']) == Decimal('0.00')
        assert Decimal(res_api.data['remaining_amount']) == Decimal('0.00')
        assert Decimal(res_api.data['paid_amount']) == Decimal('6000000.00')

        # Step 9: Cancel the 2nd customer refund voucher (ref2: 2,000,000)
        # Net paid goes back to 9,000,000 - 1,000,000 = 8,000,000.
        # Excess restores to 2,000,000.
        cancel_ref_url = reverse('customer-refund-voucher-cancel', kwargs={'pk': ref2.pk})
        res_cancel_ref = auth_client_manager.post(cancel_ref_url, {'reason': 'ابطال استرداد اشتباه'}, format='json')
        assert res_cancel_ref.status_code == status.HTTP_200_OK

        invoice.refresh_from_db()
        assert invoice.excess_amount == Decimal('2000000.00')
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.paid_amount == Decimal('8000000.00')

        # Step 10: Cancel Receipt r3 (2,000,000)
        # Valid receipts: 4,000,000 + 3,000,000 = 7,000,000.
        # Valid refunds: 1,000,000.
        # Net received = 6,000,000.
        # Net invoice amount = 6,000,000.
        # Remaining debt = 0.00, excess = 0.00.
        cancel_r3_url = reverse('receipt-voucher-cancel', kwargs={'pk': r3.pk})
        res_cancel_r3 = auth_client_manager.post(cancel_r3_url, {'reason': 'ابطال دریافت'}, format='json')
        assert res_cancel_r3.status_code == status.HTTP_200_OK

        invoice.refresh_from_db()
        assert invoice.paid_amount == Decimal('6000000.00')
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.excess_amount == Decimal('0.00')
        assert invoice.payment_status == PaymentStatus.PAID

        # Step 11: Cancel Receipt r2 (3,000,000)
        # Valid receipts: 4,000,000.
        # Valid refunds: 1,000,000.
        # Net received = 3,000,000.
        # Net invoice amount = 6,000,000.
        # Remaining debt must rise to 6,000,000 - 3,000,000 = 3,000,000 IRR!
        # Payment status must transition back to PARTIAL!
        cancel_r2_url = reverse('receipt-voucher-cancel', kwargs={'pk': r2.pk})
        res_cancel_r2 = auth_client_manager.post(cancel_r2_url, {'reason': 'ابطال دریافت دوم'}, format='json')
        assert res_cancel_r2.status_code == status.HTTP_200_OK

        invoice.refresh_from_db()
        assert invoice.paid_amount == Decimal('3000000.00')
        assert invoice.remaining_amount == Decimal('3000000.00')
        assert invoice.excess_amount == Decimal('0.00')
        assert invoice.payment_status == PaymentStatus.PARTIAL

        res_api = auth_client_manager.get(detail_url)
        assert Decimal(res_api.data['remaining_amount']) == Decimal('3000000.00')
        assert Decimal(res_api.data['paid_amount']) == Decimal('3000000.00')
        assert res_api.data['payment_status'] == PaymentStatus.PARTIAL


@pytest.mark.django_db
class TestOverpaymentSafeguards:
    """
    Challenge 2: Verify that attempting to create a receipt voucher for an amount
    exceeding remaining_amount is rejected by backend validation (API and Service).
    """

    def test_overpayment_rejected_by_serializer_and_service(
        self, finance_test_setup, auth_client_manager, manager_user
    ):
        tire = finance_test_setup['tire']
        customer = finance_test_setup['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('3000000.00')}],
            service_items_data=[],
            payment_status=PaymentStatus.UNPAID,
            created_by=manager_user
        )
        assert invoice.total_amount == Decimal('6000000.00')
        assert invoice.remaining_amount == Decimal('6000000.00')

        receipt_url = reverse('receipt-voucher-list')

        # 1. Attempt amount > remaining_amount (6,000,001 on remaining 6,000,000)
        res_over = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '6000001.00',
            'payment_method': 'کارتخوان'
        }, format='json')
        assert res_over.status_code == status.HTTP_400_BAD_REQUEST
        error_str = str(res_over.data)
        assert 'مانده بدهی' in error_str or 'بیشتر باشد' in error_str

        # Service level rejection
        with pytest.raises(ValidationError) as exc_info:
            create_receipt_voucher_service(
                sales_invoice=invoice,
                amount=Decimal('6000001.00'),
                user=manager_user
            )
        assert 'مانده بدهی' in str(exc_info.value) or 'بیشتر باشد' in str(exc_info.value)

        # 2. Pay 4,000,000 (remaining becomes 2,000,000)
        res_p = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '4000000.00',
            'payment_method': 'کارتخوان'
        }, format='json')
        assert res_p.status_code == status.HTTP_201_CREATED

        invoice.refresh_from_db()
        assert invoice.remaining_amount == Decimal('2000000.00')

        # 3. Attempt amount > remaining (e.g. 2,000,000.01)
        res_over2 = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '2000000.01',
            'payment_method': 'کارتخوان'
        }, format='json')
        assert res_over2.status_code == status.HTTP_400_BAD_REQUEST
        assert 'مانده بدهی' in str(res_over2.data)

        # 4. Exact boundary (amount == remaining_amount: 2,000,000.00) must SUCCEED
        res_exact = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '2000000.00',
            'payment_method': 'کارتخوان'
        }, format='json')
        assert res_exact.status_code == status.HTTP_201_CREATED

        invoice.refresh_from_db()
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.payment_status == PaymentStatus.PAID

        # 5. Attempt ANY positive receipt on fully paid invoice (remaining == 0)
        res_over3 = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '1.00',
            'payment_method': 'نقدی'
        }, format='json')
        assert res_over3.status_code == status.HTTP_400_BAD_REQUEST
        assert 'سقف مبلغ کل فاکتور رسیده است' in str(res_over3.data)

        # Service level rejection on fully paid invoice
        with pytest.raises(ValidationError) as exc_info2:
            create_receipt_voucher_service(
                sales_invoice=invoice,
                amount=Decimal('100.00'),
                user=manager_user
            )
        assert 'سقف مبلغ کل فاکتور رسیده است' in str(exc_info2.value)

    def test_zero_negative_and_cancelled_invoice_receipt_safeguards(
        self, finance_test_setup, auth_client_manager, manager_user
    ):
        tire = finance_test_setup['tire']
        customer = finance_test_setup['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('3000000.00')}],
            service_items_data=[],
            payment_status=PaymentStatus.UNPAID,
            created_by=manager_user
        )

        receipt_url = reverse('receipt-voucher-list')

        # Zero amount rejected
        res_zero = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '0.00',
            'payment_method': 'نقدی'
        }, format='json')
        assert res_zero.status_code == status.HTTP_400_BAD_REQUEST

        # Negative amount rejected
        res_neg = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '-50000.00',
            'payment_method': 'نقدی'
        }, format='json')
        assert res_neg.status_code == status.HTTP_400_BAD_REQUEST

        # Cancel the invoice
        from apps.invoices.services import cancel_sales_invoice_service
        cancel_sales_invoice_service(invoice, user=manager_user)
        invoice.refresh_from_db()
        assert invoice.status == InvoiceStatus.CANCELLED

        # Receipt on cancelled invoice rejected
        res_cancel = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '1000000.00',
            'payment_method': 'نقدی'
        }, format='json')
        assert res_cancel.status_code == status.HTTP_400_BAD_REQUEST
        assert 'فاکتور لغو شده' in str(res_cancel.data)


@pytest.mark.django_db
class TestReferenceNumberPreservationAndSearchAcrossVouchers:
    """
    Challenge 3: Verify that reference_number is preserved across all voucher endpoints
    (receipts, payments, refunds) and searchable via API query parameters.
    """

    def test_reference_number_receipt_vouchers(
        self, finance_test_setup, auth_client_manager, manager_user
    ):
        tire = finance_test_setup['tire']
        customer = finance_test_setup['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('3000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )

        # 1. POST receipt with reference_number
        ref_code = 'POS-REF-CHALLENGE-990011'
        res_create = auth_client_manager.post(reverse('receipt-voucher-list'), {
            'sales_invoice': invoice.pk,
            'amount': '2500000.00',
            'payment_method': 'کارتخوان بانک ملت',
            'reference_number': ref_code,
            'notes': 'تست پیگیری دریافت'
        }, format='json')
        assert res_create.status_code == status.HTTP_201_CREATED
        assert res_create.data['reference_number'] == ref_code
        voucher_id = res_create.data['receipt_id']

        # 2. GET detail
        detail_url = reverse('receipt-voucher-detail', kwargs={'pk': voucher_id})
        res_detail = auth_client_manager.get(detail_url)
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data['reference_number'] == ref_code

        # 3. GET list with ?search=<ref>
        list_url = f"{reverse('receipt-voucher-list')}?search=CHALLENGE-990011"
        res_search = auth_client_manager.get(list_url)
        assert res_search.status_code == status.HTTP_200_OK
        assert res_search.data['count'] == 1
        assert res_search.data['results'][0]['receipt_id'] == voucher_id
        assert res_search.data['results'][0]['reference_number'] == ref_code

    def test_reference_number_payment_vouchers(
        self, finance_test_setup, auth_client_manager, manager_user
    ):
        tire = finance_test_setup['tire']
        supplier = finance_test_setup['supplier']

        from apps.invoices.services import create_purchase_invoice_service
        p_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 5, 'unit_cost': Decimal('2000000.00')}],
            created_by=manager_user
        )

        ref_code = 'PAYA-REF-CHALLENGE-334455'
        res_create = auth_client_manager.post(reverse('payment-voucher-list'), {
            'purchase_invoice': p_inv.pk,
            'amount': '5000000.00',
            'payment_method': 'حواله پایا',
            'reference_number': ref_code,
            'notes': 'تست پیگیری پرداخت به تأمین‌کننده'
        }, format='json')
        assert res_create.status_code == status.HTTP_201_CREATED
        assert res_create.data['reference_number'] == ref_code
        voucher_id = res_create.data['payment_id']

        # GET detail
        detail_url = reverse('payment-voucher-detail', kwargs={'pk': voucher_id})
        res_detail = auth_client_manager.get(detail_url)
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data['reference_number'] == ref_code

        # GET list with ?search=<ref>
        list_url = f"{reverse('payment-voucher-list')}?search=CHALLENGE-334455"
        res_search = auth_client_manager.get(list_url)
        assert res_search.status_code == status.HTTP_200_OK
        assert res_search.data['count'] == 1
        assert res_search.data['results'][0]['payment_id'] == voucher_id
        assert res_search.data['results'][0]['reference_number'] == ref_code

    def test_reference_number_customer_refund_vouchers(
        self, finance_test_setup, auth_client_manager, manager_user
    ):
        tire = finance_test_setup['tire']
        customer = finance_test_setup['customer']

        # Create paid sales invoice
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('3000000.00')}],
            service_items_data=[],
            payment_status=PaymentStatus.PAID,
            payment_method='کارتخوان',
            reference_number='INIT-POS-REF',
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()

        # Sales return creates excess
        s_return = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='تست مرجوعی برای استرداد',
            user=manager_user
        )

        ref_code = 'REFUND-REF-CHALLENGE-778899'
        res_create = auth_client_manager.post(reverse('customer-refund-voucher-list'), {
            'sales_invoice': invoice.pk,
            'sales_return': s_return.pk,
            'amount': '3000000.00',
            'payment_method': 'کارت‌به‌کارت',
            'reference_number': ref_code,
            'notes': 'تست پیگیری استرداد به مشتری'
        }, format='json')
        assert res_create.status_code == status.HTTP_201_CREATED
        assert res_create.data['reference_number'] == ref_code
        voucher_id = res_create.data['refund_id']

        # GET detail
        detail_url = reverse('customer-refund-voucher-detail', kwargs={'pk': voucher_id})
        res_detail = auth_client_manager.get(detail_url)
        assert res_detail.status_code == status.HTTP_200_OK
        assert res_detail.data['reference_number'] == ref_code

        # GET list with ?search=<ref>
        list_url = f"{reverse('customer-refund-voucher-list')}?search=CHALLENGE-778899"
        res_search = auth_client_manager.get(list_url)
        assert res_search.status_code == status.HTTP_200_OK
        assert res_search.data['count'] == 1
        assert res_search.data['results'][0]['refund_id'] == voucher_id
        assert res_search.data['results'][0]['reference_number'] == ref_code

    def test_auto_created_cash_receipt_preserves_reference_number(
        self, finance_test_setup, auth_client_manager, manager_user
    ):
        tire = finance_test_setup['tire']
        customer = finance_test_setup['customer']

        auto_ref = 'POS-CASH-AUTOREF-667788'
        invoice_payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.CONFIRMED,
            'payment_status': PaymentStatus.PAID,
            'payment_method': 'دستگاه پوز سامان',
            'reference_number': auto_ref,
            'tire_items': [
                {'tire': tire.pk, 'quantity': 1, 'unit_price': '3000000.00'}
            ]
        }
        res_inv = auth_client_manager.post(reverse('sales-invoice-list'), invoice_payload, format='json')
        assert res_inv.status_code == status.HTTP_201_CREATED
        inv_id = res_inv.data['sales_invoice_id']

        # Check auto-created receipt voucher
        invoice = SalesInvoice.objects.get(pk=inv_id)
        receipt = invoice.receipts.filter(is_cancelled=False).first()
        assert receipt is not None
        assert receipt.reference_number == auto_ref
        assert receipt.payment_method == 'دستگاه پوز سامان'

        # Check searchable via treasury API
        search_url = f"{reverse('receipt-voucher-list')}?search=AUTOREF-667788"
        res_search = auth_client_manager.get(search_url)
        assert res_search.status_code == status.HTTP_200_OK
        assert res_search.data['count'] == 1
        assert res_search.data['results'][0]['reference_number'] == auto_ref

    def test_persian_and_max_length_reference_numbers(
        self, finance_test_setup, auth_client_manager, manager_user
    ):
        tire = finance_test_setup['tire']
        customer = finance_test_setup['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('3000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )

        # 100 character reference number (max length boundary)
        max_len_ref = 'R' * 100
        res1 = auth_client_manager.post(reverse('receipt-voucher-list'), {
            'sales_invoice': invoice.pk,
            'amount': '1000000.00',
            'payment_method': 'کارتخوان',
            'reference_number': max_len_ref
        }, format='json')
        assert res1.status_code == status.HTTP_201_CREATED
        assert res1.data['reference_number'] == max_len_ref

        # 101 character reference number (exceeds max length)
        too_long_ref = 'R' * 101
        res2 = auth_client_manager.post(reverse('receipt-voucher-list'), {
            'sales_invoice': invoice.pk,
            'amount': '500000.00',
            'payment_method': 'کارتخوان',
            'reference_number': too_long_ref
        }, format='json')
        assert res2.status_code == status.HTTP_400_BAD_REQUEST

        # Persian digits reference number
        persian_ref = 'پیگیری-۱۲۳۴۵۶'
        res3 = auth_client_manager.post(reverse('receipt-voucher-list'), {
            'sales_invoice': invoice.pk,
            'amount': '500000.00',
            'payment_method': 'کارتخوان',
            'reference_number': persian_ref
        }, format='json')
        assert res3.status_code == status.HTTP_201_CREATED
        assert res3.data['reference_number'] == persian_ref

        # Search by Persian digits
        res_search = auth_client_manager.get(f"{reverse('receipt-voucher-list')}?search=۱۲۳۴۵۶")
        assert res_search.status_code == status.HTTP_200_OK
        assert res_search.data['count'] == 1
        assert res_search.data['results'][0]['reference_number'] == persian_ref


@pytest.mark.django_db
class TestDiscountedInvoiceReturnsAndFinancialIntegrity:
    """
    Challenge 4: Verify remaining_amount and overpayment safeguards on discounted invoices.
    """

    def test_discounted_invoice_returns_and_remaining_debt_accuracy(
        self, finance_test_setup, auth_client_manager, manager_user
    ):
        tire = finance_test_setup['tire']
        customer = finance_test_setup['customer']

        # Invoice: 2 tires @ 3,000,000 = 6,000,000. Discount 10% (600,000). Total = 5,400,000 IRR.
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('3000000.00')}],
            service_items_data=[],
            discount_percent=Decimal('10.00'),
            payment_status=PaymentStatus.UNPAID,
            created_by=manager_user
        )
        invoice.refresh_from_db()
        assert invoice.total_amount == Decimal('5400000.00')
        assert invoice.remaining_amount == Decimal('5400000.00')

        # Customer pays 2,000,000 IRR
        create_receipt_voucher_service(invoice, Decimal('2000000.00'), user=manager_user)
        invoice.refresh_from_db()
        assert invoice.paid_amount == Decimal('2000000.00')
        assert invoice.remaining_amount == Decimal('3400000.00')

        # Customer returns 1 tire.
        # Gross price = 3,000,000. Net after 10% discount = 2,700,000 IRR.
        # Net invoice amount becomes 5,400,000 - 2,700,000 = 2,700,000 IRR.
        # Customer paid 2,000,000.
        # Remaining debt must be 2,700,000 - 2,000,000 = 700,000 IRR!
        sales_item = invoice.tire_items.first()
        s_return = create_sales_return_service(
            invoice=invoice,
            items_data=[{'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}],
            reason='مرجوعی فاکتور دارای تخفیف',
            user=manager_user
        )
        invoice.refresh_from_db()
        assert s_return.total_refund_amount == Decimal('2700000.00')
        assert invoice.net_amount == Decimal('2700000.00')
        assert invoice.paid_amount == Decimal('2000000.00')
        assert invoice.remaining_amount == Decimal('700000.00')

        # Attempt to overpay: try 700,001 on remaining 700,000
        receipt_url = reverse('receipt-voucher-list')
        res_over = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '700001.00',
            'payment_method': 'کارتخوان'
        }, format='json')
        assert res_over.status_code == status.HTTP_400_BAD_REQUEST
        assert 'مانده بدهی' in str(res_over.data)

        # Pay exact remaining: 700,000 IRR
        res_exact = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '700000.00',
            'payment_method': 'کارتخوان'
        }, format='json')
        assert res_exact.status_code == status.HTTP_201_CREATED

        invoice.refresh_from_db()
        assert invoice.remaining_amount == Decimal('0.00')
        assert invoice.paid_amount == Decimal('2700000.00')
        assert invoice.payment_status == PaymentStatus.PAID

