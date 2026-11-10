import pytest
from decimal import Decimal
from django.urls import reverse
from django.core.management import call_command, CommandError
from rest_framework import status
from rest_framework.test import APIClient

from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
from apps.customers.models import Customer, Vehicle
from apps.finance.models import ReceiptVoucher, CustomerRefundVoucher
from apps.invoices.models import (
    SalesInvoice, InvoiceStatus, PaymentStatus
)
from apps.invoices.services import create_sales_invoice_service


@pytest.fixture
def e2e_catalog(db, manager_user):
    brand, _ = Brand.objects.get_or_create(brand_name='کویر تایر E2E')
    size, _ = Size.objects.get_or_create(size_name='195/65R15-E2E')
    tire, created = Tire.objects.get_or_create(
        tire_name='کوir تایر رادیال E2E',
        defaults={
            'brand': brand,
            'size': size,
            'stock_quantity': 40,
            'purchase_price': Decimal('1500000.00'),
            'sale_price': Decimal('2500000.00'),
            'min_stock_alert': 4,
        }
    )
    if not created:
        tire.stock_quantity = 40
        tire.purchase_price = Decimal('1500000.00')
        tire.sale_price = Decimal('2500000.00')
        tire.save()

    StockMovement.objects.get_or_create(
        tire=tire,
        movement_type=StockMovementType.INITIAL_STOCK,
        defaults={
            'quantity': 40,
            'balance_after': 40,
            'unit_cost': Decimal('1500000.00'),
            'user': manager_user,
            'description': 'موجودی اولیه E2E'
        }
    )

    customer, _ = Customer.objects.get_or_create(
        phone_number='09129990001',
        defaults={
            'full_name': 'رضا حسینی E2E',
            'national_code': '0019998881',
            'address': 'تهران، خیابان آزادی'
        }
    )

    vehicle, _ = Vehicle.objects.get_or_create(
        license_plate='12B345-77',
        defaults={
            'customer': customer,
            'model': 'پژو 206',
            'year': '1400',
            'tire_size_recommended': '195/65R15'
        }
    )

    return {
        'brand': brand,
        'size': size,
        'tire': tire,
        'customer': customer,
        'vehicle': vehicle,
    }


@pytest.mark.django_db
class TestFeatureContracts:

    def test_login_and_role_identity_payload(self, api_client, manager_user, technician_user, warehouse_user):
        login_url = reverse('token_obtain_pair')
        profile_url = reverse('user_profile')

        roles_to_test = [
            (manager_user, 'MANAGER'),
            (technician_user, 'TECHNICIAN'),
            (warehouse_user, 'WAREHOUSE'),
        ]

        for user, expected_role in roles_to_test:
            login_res = api_client.post(login_url, {'username': user.username, 'password': 'pass123'})
            assert login_res.status_code == status.HTTP_200_OK, f"Login failed for {expected_role}"
            assert 'access' in login_res.data
            assert 'refresh' in login_res.data

            token = login_res.data['access']
            auth_client = APIClient()
            auth_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

            profile_res = auth_client.get(profile_url)
            assert profile_res.status_code == status.HTTP_200_OK
            assert profile_res.data['username'] == user.username
            assert profile_res.data['role'] == expected_role

    def test_sales_return_input_serializer_contract(self, auth_client_manager, e2e_catalog, manager_user):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_price': Decimal('2500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        sales_item = invoice.tire_items.first()
        url = reverse('sales-return-list')

        invalid_payload = {
            'sales_invoice': invoice.pk,
            'reason': 'نارضایتی از کیفیت',
            'items': [
                {'tire': tire.pk, 'quantity': 1}
            ]
        }
        res_invalid = auth_client_manager.post(url, invalid_payload, format='json')
        assert res_invalid.status_code == status.HTTP_400_BAD_REQUEST
        error_str = str(res_invalid.data)
        assert 'sales_invoice_tire_item_id' in error_str or 'شناسه قلم فاکتور' in error_str

        valid_payload = {
            'sales_invoice': invoice.pk,
            'reason': 'عدم تطابق سایز',
            'items': [
                {'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}
            ]
        }
        res_valid = auth_client_manager.post(url, valid_payload, format='json')
        assert res_valid.status_code == status.HTTP_201_CREATED
        assert 'sales_return_id' in res_valid.data
        assert res_valid.data['total_refund_amount'] == '2500000.00'

    def test_treasury_voucher_endpoints_and_primary_keys(self, auth_client_manager, e2e_catalog, manager_user):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']
        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('2500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )

        receipt_url = reverse('receipt-voucher-list')
        receipt_res = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '3000000.00',
            'payment_method': 'کارتخوان'
        }, format='json')
        assert receipt_res.status_code == status.HTTP_201_CREATED
        assert 'receipt_id' in receipt_res.data
        receipt_id = receipt_res.data['receipt_id']

        cancel_url = reverse('receipt-voucher-cancel', kwargs={'pk': receipt_id})
        cancel_res = auth_client_manager.post(cancel_url, {'reason': 'ابطال سند به دلیل اشتباه بانکی'}, format='json')
        assert cancel_res.status_code == status.HTTP_200_OK
        assert cancel_res.data['is_cancelled'] is True
        assert cancel_res.data['receipt_id'] == receipt_id

    def test_customer_specific_vehicle_filtering(self, auth_client_manager):
        cust1 = Customer.objects.create(full_name='مشتری الف', phone_number='09121110011')
        cust2 = Customer.objects.create(full_name='مشتری ب', phone_number='09121110022')

        Vehicle.objects.create(customer=cust1, license_plate='11A111-11', model='پراید')
        Vehicle.objects.create(customer=cust1, license_plate='22A222-22', model='سمند')
        Vehicle.objects.create(customer=cust2, license_plate='33A333-33', model='تارا')

        url = reverse('vehicle-list')
        res = auth_client_manager.get(f"{url}?customer={cust1.pk}")
        assert res.status_code == status.HTTP_200_OK

        returned_plates = [v['license_plate'] for v in res.data['results']]
        assert '11A111-11' in returned_plates
        assert '22A222-22' in returned_plates
        assert '33A333-33' not in returned_plates
        assert res.data['count'] == 2

    def test_enum_partial_payment_status_filtering(self, auth_client_manager, e2e_catalog, manager_user):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']

        inv_unpaid = create_sales_invoice_service(
            customer=customer, vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('2500000.00')}],
            service_items_data=[], created_by=manager_user
        )
        inv_partial = create_sales_invoice_service(
            customer=customer, vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('2500000.00')}],
            service_items_data=[], created_by=manager_user
        )
        ReceiptVoucher.objects.create(
            sales_invoice=inv_partial,
            amount=Decimal('2000000.00'),
            created_by=manager_user
        )
        inv_partial.payment_status = PaymentStatus.PARTIAL
        inv_partial.save(update_fields=['payment_status'])

        url = reverse('sales-invoice-list')
        res = auth_client_manager.get(f"{url}?payment_status=PARTIAL")
        assert res.status_code == status.HTTP_200_OK

        returned_ids = [inv['sales_invoice_id'] for inv in res.data['results']]
        assert inv_partial.pk in returned_ids
        assert inv_unpaid.pk not in returned_ids

    def test_voucher_reference_number_persistence(self, auth_client_manager, e2e_catalog, manager_user):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']
        invoice = create_sales_invoice_service(
            customer=customer, vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('2500000.00')}],
            service_items_data=[], created_by=manager_user
        )

        receipt_url = reverse('receipt-voucher-list')
        payload = {
            'sales_invoice': invoice.pk,
            'amount': '2500000.00',
            'payment_method': 'کارتخوان سامان',
            'reference_number': 'POS-REF-884920'
        }
        res = auth_client_manager.post(receipt_url, payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        assert 'reference_number' in res.data
        assert res.data['reference_number'] == 'POS-REF-884920'

        voucher = ReceiptVoucher.objects.get(receipt_id=res.data['receipt_id'])
        assert getattr(voucher, 'reference_number', None) == 'POS-REF-884920'

    def test_auto_receipt_creation_on_paid_sales_invoice(self, auth_client_manager, e2e_catalog):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']

        invoice_url = reverse('sales-invoice-list')
        payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.CONFIRMED,
            'payment_status': PaymentStatus.PAID,
            'payment_method': 'کارتخوان ملت',
            'reference_number': 'AUTO-POS-999888',
            'discount_amount': '0.00',
            'discount_percent': '0.00',
            'tire_items': [
                {'tire': tire.pk, 'quantity': 2, 'unit_price': '2500000.00'}
            ]
        }
        res = auth_client_manager.post(invoice_url, payload, format='json')
        assert res.status_code == status.HTTP_201_CREATED
        invoice_id = res.data['sales_invoice_id']

        invoice = SalesInvoice.objects.get(pk=invoice_id)
        assert invoice.payment_status == PaymentStatus.PAID

        receipts = invoice.receipts.filter(is_cancelled=False)
        assert receipts.count() == 1, "Expected 1 auto-created ReceiptVoucher for PAID sales invoice"
        receipt = receipts.first()
        assert receipt.amount == Decimal('5000000.00')
        if hasattr(receipt, 'reference_number'):
            assert receipt.reference_number == 'AUTO-POS-999888'

    def test_remaining_amount_and_paid_amount_in_sales_invoice_serializer(
        self, auth_client_manager, e2e_catalog, manager_user
    ):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']
        invoice = create_sales_invoice_service(
            customer=customer, vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 4, 'unit_price': Decimal('2500000.00')}],
            service_items_data=[], created_by=manager_user
        )
        ReceiptVoucher.objects.create(
            sales_invoice=invoice,
            amount=Decimal('3000000.00'),
            created_by=manager_user
        )

        detail_url = reverse('sales-invoice-detail', kwargs={'pk': invoice.pk})
        res = auth_client_manager.get(detail_url)
        assert res.status_code == status.HTTP_200_OK

        assert 'paid_amount' in res.data, "Expected 'paid_amount' in SalesInvoiceSerializer"
        assert 'remaining_amount' in res.data, "Expected 'remaining_amount' in SalesInvoiceSerializer"
        assert Decimal(str(res.data['paid_amount'])) == Decimal('3000000.00')
        assert Decimal(str(res.data['remaining_amount'])) == Decimal('7000000.00')

    def test_error_response_formatting_envelope(self, auth_client_manager):
        cust_url = reverse('customer-list')
        res = auth_client_manager.post(cust_url, {'full_name': ''}, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert 'success' in res.data
        assert res.data['success'] is False
        assert res.data['status_code'] == 400
        assert 'errors' in res.data

    def test_action_button_role_guarding_permissions(self, auth_client_warehouse, e2e_catalog, manager_user):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']
        draft_invoice = SalesInvoice.objects.create(
            customer=customer,
            status=InvoiceStatus.DRAFT,
            total_amount=Decimal('2500000.00'),
            created_by=manager_user
        )
        draft_invoice.tire_items.create(tire=tire, quantity=1, unit_price=Decimal('2500000.00'))

        confirm_url = reverse('sales-invoice-confirm', kwargs={'pk': draft_invoice.pk})
        res = auth_client_warehouse.post(confirm_url)
        assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestBoundaryAndValidationLimits:

    def test_zero_total_invoice_and_discount_handling(self, auth_client_manager, e2e_catalog):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']
        url = reverse('sales-invoice-list')

        res_over = auth_client_manager.post(url, {
            'customer': customer.pk,
            'discount_amount': '6000000.00',
            'tire_items': [{'tire': tire.pk, 'quantity': 2, 'unit_price': '2500000.00'}]
        }, format='json')
        assert res_over.status_code == status.HTTP_400_BAD_REQUEST

        res_neg = auth_client_manager.post(url, {
            'customer': customer.pk,
            'discount_amount': '-1000.00',
            'tire_items': [{'tire': tire.pk, 'quantity': 1, 'unit_price': '2500000.00'}]
        }, format='json')
        assert res_neg.status_code == status.HTTP_400_BAD_REQUEST

        res_zero = auth_client_manager.post(url, {
            'customer': customer.pk,
            'discount_amount': '0.00',
            'discount_percent': '0.00',
            'tire_items': [{'tire': tire.pk, 'quantity': 1, 'unit_price': '2500000.00'}]
        }, format='json')
        assert res_zero.status_code == status.HTTP_201_CREATED
        assert Decimal(str(res_zero.data['total_amount'])) == Decimal('2500000.00')

    def test_maximum_return_quantity_boundary(self, auth_client_manager, e2e_catalog, manager_user):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']
        invoice = create_sales_invoice_service(
            customer=customer, vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('2500000.00')}],
            service_items_data=[], created_by=manager_user
        )
        sales_item = invoice.tire_items.first()
        url = reverse('sales-return-list')

        res = auth_client_manager.post(url, {
            'sales_invoice': invoice.pk,
            'reason': 'مرجوعی بیش از سقف خرید',
            'items': [
                {'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 3}
            ]
        }, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert 'بیشتر از سقف مجاز' in str(res.data) or 'سقف' in str(res.data)

    def test_duplicate_phone_number_error_payload(self, auth_client_manager):
        url = reverse('customer-list')
        Customer.objects.create(full_name='مشتری اول', phone_number='09127778899')

        payload = {
            'full_name': 'مشتری دوم با همان شماره',
            'phone_number': '۰۹۱۲۷۷۷۸۸۹۹'
        }
        res = auth_client_manager.post(url, payload, format='json')
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data['success'] is False
        assert 'phone_number' in res.data['errors']

    def test_overpayment_validation_error(self, auth_client_manager, e2e_catalog, manager_user):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']
        invoice = create_sales_invoice_service(
            customer=customer, vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('2500000.00')}],
            service_items_data=[], created_by=manager_user
        )
        ReceiptVoucher.objects.create(
            sales_invoice=invoice,
            amount=Decimal('3000000.00'),
            created_by=manager_user
        )

        receipt_url = reverse('receipt-voucher-list')
        res = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '2500000.00',
            'payment_method': 'کارتخوان'
        }, format='json')

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert 'مانده بدهی' in str(res.data)


@pytest.mark.django_db
class TestCrossFeatureWorkflows:

    def test_cash_invoice_auto_receipt_dashboard_receivables_and_cancel_lifecycle(
        self, auth_client_manager, e2e_catalog
    ):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']

        invoice_url = reverse('sales-invoice-list')
        invoice_payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.CONFIRMED,
            'payment_status': PaymentStatus.PAID,
            'payment_method': 'کارتخوان پاسارگاد',
            'reference_number': 'POS-TX-554433',
            'tire_items': [
                {'tire': tire.pk, 'quantity': 2, 'unit_price': '2500000.00'}
            ]
        }
        res_inv = auth_client_manager.post(invoice_url, invoice_payload, format='json')
        assert res_inv.status_code == status.HTTP_201_CREATED
        invoice_id = res_inv.data['sales_invoice_id']
        invoice = SalesInvoice.objects.get(pk=invoice_id)

        receipts = invoice.receipts.filter(is_cancelled=False)
        assert receipts.exists(), "ReceiptVoucher must be created automatically for PAID invoice"
        receipt = receipts.first()
        assert receipt.amount == Decimal('5000000.00')

        dashboard_url = reverse('dashboard-stats')
        res_dash = auth_client_manager.get(dashboard_url)
        assert res_dash.status_code == status.HTTP_200_OK
        assert Decimal(str(res_dash.data['total_receivables'])) == Decimal('0.00')
        assert res_dash.data['unpaid_invoices_count'] == 0

        try:
            call_command('reconcile_payments')
        except CommandError as e:
            pytest.fail(f"reconcile_payments failed unexpectedly on auto-settled invoice: {e}")

        cancel_url = reverse('receipt-voucher-cancel', kwargs={'pk': receipt.pk})
        res_cancel = auth_client_manager.post(cancel_url, {'reason': 'مرجوعی رسید به درخواست مشتری'}, format='json')
        assert res_cancel.status_code == status.HTTP_200_OK

        res_dash_after = auth_client_manager.get(dashboard_url)
        assert res_dash_after.status_code == status.HTTP_200_OK
        assert Decimal(str(res_dash_after.data['total_receivables'])) == Decimal('5000000.00')
        assert res_dash_after.data['unpaid_invoices_count'] == 1

    def test_partial_receipt_remaining_amount_and_subsequent_receipt(
        self, auth_client_manager, e2e_catalog, manager_user
    ):
        tire = e2e_catalog['tire']
        customer = e2e_catalog['customer']
        invoice = create_sales_invoice_service(
            customer=customer, vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 3, 'unit_price': Decimal('2500000.00')}],
            service_items_data=[], created_by=manager_user
        )
        receipt_url = reverse('receipt-voucher-list')

        res_r1 = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '3000000.00',
            'payment_method': 'نقدی'
        }, format='json')
        assert res_r1.status_code == status.HTTP_201_CREATED

        inv_detail_url = reverse('sales-invoice-detail', kwargs={'pk': invoice.pk})
        res_inv = auth_client_manager.get(inv_detail_url)
        assert res_inv.status_code == status.HTTP_200_OK
        assert 'paid_amount' in res_inv.data, "Expected 'paid_amount' in sales invoice response"
        assert 'remaining_amount' in res_inv.data, "Expected 'remaining_amount' in sales invoice response"
        assert Decimal(str(res_inv.data['paid_amount'])) == Decimal('3000000.00')
        assert Decimal(str(res_inv.data['remaining_amount'])) == Decimal('4500000.00')
        assert res_inv.data['payment_status'] == PaymentStatus.PARTIAL

        res_over = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '5000000.00',
            'payment_method': 'کارتخوان'
        }, format='json')
        assert res_over.status_code == status.HTTP_400_BAD_REQUEST

        res_r2 = auth_client_manager.post(receipt_url, {
            'sales_invoice': invoice.pk,
            'amount': '4500000.00',
            'payment_method': 'کارتخوان'
        }, format='json')
        assert res_r2.status_code == status.HTTP_201_CREATED

        res_inv_final = auth_client_manager.get(inv_detail_url)
        assert Decimal(str(res_inv_final.data['paid_amount'])) == Decimal('7500000.00')
        assert Decimal(str(res_inv_final.data['remaining_amount'])) == Decimal('0.00')
        assert res_inv_final.data['payment_status'] == PaymentStatus.PAID


@pytest.mark.django_db
class TestEndToEndBusinessWorkflows:

    def test_complete_tire_sales_and_return_lifecycle(self, auth_client_manager, e2e_catalog):
        tire = e2e_catalog['tire']
        initial_stock = tire.stock_quantity

        cust_res = auth_client_manager.post(reverse('customer-list'), {
            'full_name': 'مهندس کامران رستمی',
            'phone_number': '09123334455',
            'national_code': '0012233445',
            'address': 'تهران، میدان ونک'
        }, format='json')
        assert cust_res.status_code == status.HTTP_201_CREATED
        customer_id = cust_res.data['customer_id']

        plate_input = '۱۲ب۳۴۵-۶۸'
        veh_res = auth_client_manager.post(reverse('vehicle-list'), {
            'customer': customer_id,
            'license_plate': plate_input,
            'model': 'دنا پلاس توربو',
            'year': '1401'
        }, format='json')
        assert veh_res.status_code == status.HTTP_201_CREATED
        vehicle_id = veh_res.data['vehicle_id']
        assert veh_res.data['license_plate'] == '12ب345-68'

        v_filter_res = auth_client_manager.get(f"{reverse('vehicle-list')}?customer={customer_id}")
        assert v_filter_res.status_code == status.HTTP_200_OK
        assert v_filter_res.data['count'] == 1
        assert v_filter_res.data['results'][0]['vehicle_id'] == vehicle_id

        invoice_res = auth_client_manager.post(reverse('sales-invoice-list'), {
            'customer': customer_id,
            'vehicle': vehicle_id,
            'status': InvoiceStatus.CONFIRMED,
            'payment_status': PaymentStatus.PAID,
            'payment_method': 'دستگاه کارتخوان پوز',
            'reference_number': 'POS-TX-998877',
            'discount_amount': '0.00',
            'discount_percent': '0.00',
            'tire_items': [
                {'tire': tire.pk, 'quantity': 4, 'unit_price': '2500000.00'}
            ]
        }, format='json')
        assert invoice_res.status_code == status.HTTP_201_CREATED
        invoice_id = invoice_res.data['sales_invoice_id']
        assert invoice_res.data['total_amount'] == '10000000.00'

        tire.refresh_from_db()
        assert tire.stock_quantity == initial_stock - 4

        invoice = SalesInvoice.objects.get(pk=invoice_id)
        receipt = invoice.receipts.filter(is_cancelled=False).first()
        assert receipt is not None
        assert receipt.amount == Decimal('10000000.00')
        if hasattr(receipt, 'reference_number'):
            assert receipt.reference_number == 'POS-TX-998877'

        sales_item = invoice.tire_items.first()
        return_res = auth_client_manager.post(reverse('sales-return-list'), {
            'sales_invoice': invoice_id,
            'reason': 'عدم تطابق آج تایر با درخواست مشتری',
            'items': [
                {'sales_invoice_tire_item_id': sales_item.pk, 'quantity': 1}
            ]
        }, format='json')
        assert return_res.status_code == status.HTTP_201_CREATED
        assert return_res.data['total_refund_amount'] == '2500000.00'

        tire.refresh_from_db()
        assert tire.stock_quantity == initial_stock - 3

        refund_vouchers = CustomerRefundVoucher.objects.filter(sales_invoice=invoice, is_cancelled=False)
        assert refund_vouchers.exists()
        assert refund_vouchers.first().amount == Decimal('2500000.00')
