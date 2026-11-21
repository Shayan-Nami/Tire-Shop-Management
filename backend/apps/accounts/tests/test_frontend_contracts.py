import json
from pathlib import Path
import shutil
import subprocess

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.catalog.models import Brand, Size, StockMovement, Tire
from apps.customers.models import Customer, Vehicle
from apps.finance.models import CustomerRefundVoucher, PaymentVoucher, ReceiptVoucher
from apps.invoices.models import PurchaseInvoice, SalesInvoice, SalesReturn
from apps.services_app.models import Service
from apps.suppliers.models import Supplier


@pytest.mark.django_db
def test_api_responses_match_frontend_types(
    auth_client_manager,
    auth_client_technician,
    auth_client_warehouse,
):
    frontend = Path(__file__).resolve().parents[4] / 'frontend'
    node = shutil.which('node')
    if not node or not (frontend / 'node_modules/typescript').exists():
        pytest.skip('Install Node and run npm ci in frontend for the cross-stack contract check')

    fixtures: list[dict[str, object]] = []

    brand = Brand.objects.create(brand_name='Contract brand')
    size = Size.objects.create(size_name='195/65R15')
    tire = Tire.objects.create(
        tire_name='Contract tire',
        brand=brand,
        size=size,
        stock_quantity=10,
        sale_price='1000.00',
        purchase_price='600.00',
        min_stock_alert=15,
    )
    customer = Customer.objects.create(full_name='Contract customer', phone_number='09120009988')
    nullable_customer = Customer.objects.create(full_name='No phone customer', phone_number=None)
    vehicle = Vehicle.objects.create(customer=customer, license_plate='12ب345-ایران11', model='Contract car')
    service = Service.objects.create(service_name='Contract service', price='100.00')
    supplier = Supplier.objects.create(supplier_name='Contract supplier', phone_number='02188776655')

    contract_user = User.objects.create_user(
        username='contract_auth_user',
        password='StrongContractPass123!',
        role=UserRole.TECHNICIAN,
        full_name='کاربر تست قرارداد',
        phone_number='09123334455',
    )
    anon_client = APIClient()
    login_resp = anon_client.post('/api/v1/auth/login/', {
        'username': 'contract_auth_user',
        'password': 'StrongContractPass123!',
    }, format='json')
    assert login_resp.status_code == 200, login_resp.data
    login_data = login_resp.json()
    assert isinstance(login_data.get('access'), str) and login_data['access']
    assert isinstance(login_data.get('refresh'), str) and login_data['refresh']
    fixtures.append({'type': 'AuthResponse', 'data': login_data})

    refresh_resp = anon_client.post('/api/v1/auth/token/refresh/', {
        'refresh': login_data['refresh'],
    }, format='json')
    assert refresh_resp.status_code == 200, refresh_resp.data
    refresh_data = refresh_resp.json()
    assert isinstance(refresh_data.get('access'), str) and refresh_data['access']
    assert isinstance(refresh_data.get('refresh'), str) and refresh_data['refresh']

    user_client = APIClient()
    user_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_data['access']}")
    profile_patch = user_client.patch('/api/v1/auth/profile/', {
        'full_name': 'کاربر قرارداد بروزرسانی‌شده',
    }, format='json')
    assert profile_patch.status_code == 200, profile_patch.data
    fixtures.append({'type': 'User', 'data': profile_patch.json()})

    logout_invalid = user_client.post('/api/v1/auth/logout/', {
        'refresh': 'invalid-refresh-token',
    }, format='json')
    assert logout_invalid.status_code == 400, logout_invalid.data
    logout_invalid_data = logout_invalid.json()
    assert logout_invalid_data['success'] is False
    assert logout_invalid_data['status_code'] == 400
    assert isinstance(logout_invalid_data['errors'].get('detail'), str)

    logout_valid = user_client.post('/api/v1/auth/logout/', {
        'refresh': refresh_data['refresh'],
    }, format='json')
    assert logout_valid.status_code == 200, logout_valid.data
    assert isinstance(logout_valid.json().get('detail'), str)

    change_pw_client = APIClient()
    change_pw_client.force_authenticate(user=contract_user)
    change_pw_resp = change_pw_client.post('/api/v1/auth/change-password/', {
        'old_password': 'StrongContractPass123!',
        'new_password': 'NewStrongContractPass456!',
    }, format='json')
    assert change_pw_resp.status_code == 200, change_pw_resp.data
    assert isinstance(change_pw_resp.json().get('detail'), str)

    created_user_resp = auth_client_manager.post('/api/v1/auth/users/', {
        'username': 'contract_managed_user',
        'password': 'ManagedUserPass123!',
        'full_name': 'کاربر ایجاد شده',
        'role': UserRole.WAREHOUSE,
        'phone_number': '09123334466',
    }, format='json')
    assert created_user_resp.status_code == 201, created_user_resp.data
    created_user_data = created_user_resp.json()
    fixtures.append({'type': 'User', 'data': created_user_data})

    patched_user_resp = auth_client_manager.patch(
        f"/api/v1/auth/users/{created_user_data['id']}/",
        {'full_name': 'کاربر ویرایش شده'},
        format='json',
    )
    assert patched_user_resp.status_code == 200, patched_user_resp.data
    fixtures.append({'type': 'User', 'data': patched_user_resp.json()})

    adjust_resp = auth_client_manager.post(f'/api/v1/catalog/tires/{tire.pk}/adjust-stock/', {
        'counted_quantity': 11,
        'reason': 'انبارگردانی قرارداد',
    }, format='json')
    assert adjust_resp.status_code == 200, adjust_resp.data
    adjust_data = adjust_resp.json()
    assert set(adjust_data.keys()) == {'message', 'movement_id', 'difference', 'current_stock'}
    assert isinstance(adjust_data['message'], str)
    assert adjust_data['difference'] == 1
    assert adjust_data['current_stock'] == 11

    dup_vehicle = auth_client_manager.post('/api/v1/crm/vehicles/', {
        'customer': customer.pk,
        'license_plate': vehicle.license_plate,
        'model': 'Duplicate car',
    }, format='json')
    assert dup_vehicle.status_code == 400, dup_vehicle.data
    dup_vehicle_data = dup_vehicle.json()
    assert dup_vehicle_data['success'] is False
    assert dup_vehicle_data['status_code'] == 400
    assert 'license_plate' in dup_vehicle_data['errors']

    invoice = auth_client_manager.post('/api/v1/invoices/sales/', {
        'customer': customer.pk,
        'vehicle': vehicle.pk,
        'tire_items': [{'tire': tire.pk, 'quantity': 2}],
        'service_items': [{'service': service.pk, 'quantity': 1}],
        'status': 'CONFIRMED',
        'payment_status': 'PAID',
        'payment_method': 'CASH',
    }, format='json')
    assert invoice.status_code == 201, invoice.data
    invoice_data = invoice.json()
    fixtures.append({'type': 'SalesInvoice', 'data': invoice_data})

    draft_invoice_resp = auth_client_manager.post('/api/v1/invoices/sales/', {
        'customer': nullable_customer.pk,
        'vehicle': None,
        'tire_items': [{'tire': tire.pk, 'quantity': 1}],
        'service_items': [],
        'status': 'DRAFT',
        'payment_status': 'UNPAID',
    }, format='json')
    assert draft_invoice_resp.status_code == 201, draft_invoice_resp.data
    draft_data = draft_invoice_resp.json()
    assert draft_data['vehicle'] is None
    assert draft_data.get('vehicle_plate') is None
    assert draft_data.get('vehicle_model') is None
    assert draft_data['customer_phone'] is None
    fixtures.append({'type': 'SalesInvoice', 'data': draft_data})

    confirm_resp = auth_client_manager.post(
        f"/api/v1/invoices/sales/{draft_data['sales_invoice_id']}/confirm/",
        {},
        format='json',
    )
    assert confirm_resp.status_code == 200, confirm_resp.data
    confirm_data = confirm_resp.json()
    assert isinstance(confirm_data.get('message'), str)
    assert confirm_data['invoice']['status'] == 'CONFIRMED'
    assert confirm_data['sales_invoice_id'] == draft_data['sales_invoice_id']
    fixtures.append({'type': 'SalesInvoice', 'data': confirm_data['invoice']})

    cancel_sales_resp = auth_client_manager.post(
        f"/api/v1/invoices/sales/{draft_data['sales_invoice_id']}/cancel/",
        {},
        format='json',
    )
    assert cancel_sales_resp.status_code == 200, cancel_sales_resp.data
    cancel_sales_data = cancel_sales_resp.json()
    assert isinstance(cancel_sales_data.get('message'), str)
    assert cancel_sales_data['invoice']['status'] == 'CANCELLED'
    fixtures.append({'type': 'SalesInvoice', 'data': cancel_sales_data['invoice']})

    unpaid_sales_resp = auth_client_manager.post('/api/v1/invoices/sales/', {
        'customer': customer.pk,
        'vehicle': None,
        'tire_items': [{'tire': tire.pk, 'quantity': 1}],
        'service_items': [],
        'status': 'CONFIRMED',
        'payment_status': 'UNPAID',
    }, format='json')
    assert unpaid_sales_resp.status_code == 201, unpaid_sales_resp.data
    unpaid_sales_data = unpaid_sales_resp.json()

    receipt_resp = auth_client_manager.post('/api/v1/treasury/receipts/', {
        'sales_invoice': unpaid_sales_data['sales_invoice_id'],
        'amount': '500.00',
        'payment_method': 'POS',
    }, format='json')
    assert receipt_resp.status_code == 201, receipt_resp.data
    receipt_data = receipt_resp.json()
    fixtures.append({'type': 'ReceiptVoucher', 'data': receipt_data})

    receipt_cancel_resp = auth_client_manager.post(
        f"/api/v1/treasury/receipts/{receipt_data['receipt_id']}/cancel/",
        {'reason': 'لغو سند دریافت تست قرارداد'},
        format='json',
    )
    assert receipt_cancel_resp.status_code == 200, receipt_cancel_resp.data
    cancelled_receipt_data = receipt_cancel_resp.json()
    assert cancelled_receipt_data['is_cancelled'] is True
    fixtures.append({'type': 'ReceiptVoucher', 'data': cancelled_receipt_data})

    purchase = auth_client_manager.post('/api/v1/invoices/purchases/', {
        'supplier': supplier.pk,
        'tire_items': [{'tire': tire.pk, 'quantity': 2, 'unit_cost': '600.00'}],
    }, format='json')
    assert purchase.status_code == 201, purchase.data
    purchase_data = purchase.json()
    fixtures.append({'type': 'PurchaseInvoice', 'data': purchase_data})

    payment = auth_client_manager.post('/api/v1/treasury/payments/', {
        'purchase_invoice': purchase_data['purchase_invoice_id'],
        'amount': '500.00',
        'payment_method': 'CASH',
    }, format='json')
    assert payment.status_code == 201, payment.data
    payment_data = payment.json()
    fixtures.append({'type': 'PaymentVoucher', 'data': payment_data})

    payment_cancel_resp = auth_client_manager.post(
        f"/api/v1/treasury/payments/{payment_data['payment_id']}/cancel/",
        {'reason': 'لغو سند پرداخت تست قرارداد'},
        format='json',
    )
    assert payment_cancel_resp.status_code == 200, payment_cancel_resp.data
    cancelled_payment_data = payment_cancel_resp.json()
    assert cancelled_payment_data['is_cancelled'] is True
    fixtures.append({'type': 'PaymentVoucher', 'data': cancelled_payment_data})

    purchase_for_cancel = auth_client_manager.post('/api/v1/invoices/purchases/', {
        'supplier': supplier.pk,
        'tire_items': [{'tire': tire.pk, 'quantity': 2, 'unit_cost': '600.00'}],
    }, format='json')
    assert purchase_for_cancel.status_code == 201, purchase_for_cancel.data
    p_cancel_id = purchase_for_cancel.json()['purchase_invoice_id']

    purchase_cancel_resp = auth_client_manager.post(
        f'/api/v1/invoices/purchases/{p_cancel_id}/cancel/',
        {},
        format='json',
    )
    assert purchase_cancel_resp.status_code == 200, purchase_cancel_resp.data
    purchase_cancel_data = purchase_cancel_resp.json()
    assert isinstance(purchase_cancel_data.get('message'), str)
    assert purchase_cancel_data['invoice']['status'] == 'CANCELLED'
    fixtures.append({'type': 'PurchaseInvoice', 'data': purchase_cancel_data['invoice']})

    sales_return = auth_client_manager.post('/api/v1/invoices/returns/', {
        'sales_invoice': invoice_data['sales_invoice_id'],
        'reason': 'Contract return',
        'items': [{
            'sales_invoice_tire_item_id': invoice_data['tire_items'][0]['id'],
            'quantity': 1,
        }],
    }, format='json')
    assert sales_return.status_code == 201, sales_return.data
    return_data = sales_return.json()
    fixtures.append({'type': 'SalesReturn', 'data': return_data})

    auto_refunds_resp = auth_client_manager.get(
        f"/api/v1/treasury/customer-refunds/?sales_invoice={invoice_data['sales_invoice_id']}"
    )
    assert auto_refunds_resp.status_code == 200, auto_refunds_resp.data
    auto_refund_id = auto_refunds_resp.json()['results'][0]['refund_id']

    refund_cancel_resp = auth_client_manager.post(
        f'/api/v1/treasury/customer-refunds/{auto_refund_id}/cancel/',
        {'reason': 'لغو استرداد خودکار تست قرارداد'},
        format='json',
    )
    assert refund_cancel_resp.status_code == 200, refund_cancel_resp.data
    fixtures.append({'type': 'CustomerRefundVoucher', 'data': refund_cancel_resp.json()})

    manual_refund_resp = auth_client_manager.post('/api/v1/treasury/customer-refunds/', {
        'sales_invoice': invoice_data['sales_invoice_id'],
        'sales_return': return_data['sales_return_id'],
        'amount': '1000.00',
        'payment_method': 'BANK_TRANSFER',
    }, format='json')
    assert manual_refund_resp.status_code == 201, manual_refund_resp.data
    manual_refund_data = manual_refund_resp.json()
    fixtures.append({'type': 'CustomerRefundVoucher', 'data': manual_refund_data})

    SalesInvoice.objects.filter(pk=draft_data['sales_invoice_id']).update(created_by=None)
    PurchaseInvoice.objects.filter(pk=p_cancel_id).update(created_by=None)
    SalesReturn.objects.filter(pk=return_data['sales_return_id']).update(created_by=None)
    ReceiptVoucher.objects.filter(pk=receipt_data['receipt_id']).update(created_by=None)
    PaymentVoucher.objects.filter(pk=payment_data['payment_id']).update(created_by=None)
    CustomerRefundVoucher.objects.filter(pk=manual_refund_data['refund_id']).update(created_by=None)
    StockMovement.objects.filter(pk=adjust_data['movement_id']).update(user=None)

    nullable_checks = [
        (f"/api/v1/invoices/sales/{draft_data['sales_invoice_id']}/", 'SalesInvoice', 'created_by_name'),
        (f'/api/v1/invoices/purchases/{p_cancel_id}/', 'PurchaseInvoice', 'created_by_name'),
        (f"/api/v1/invoices/returns/{return_data['sales_return_id']}/", 'SalesReturn', 'created_by_name'),
        (f"/api/v1/treasury/receipts/{receipt_data['receipt_id']}/", 'ReceiptVoucher', 'created_by_name'),
        (f"/api/v1/treasury/payments/{payment_data['payment_id']}/", 'PaymentVoucher', 'created_by_name'),
        (
            f"/api/v1/treasury/customer-refunds/{manual_refund_data['refund_id']}/",
            'CustomerRefundVoucher',
            'created_by_name',
        ),
    ]
    for url, contract, nullable_field in nullable_checks:
        detail_resp = auth_client_manager.get(url)
        assert detail_resp.status_code == 200, (url, detail_resp.data)
        detail_payload = detail_resp.json()
        assert detail_payload.get(nullable_field) is None, (url, detail_payload)
        fixtures.append({'type': contract, 'data': detail_payload})

    tech_invoice_resp = auth_client_technician.post('/api/v1/invoices/sales/', {
        'customer': customer.pk,
        'vehicle': None,
        'tire_items': [{'tire': tire.pk, 'quantity': 1}],
        'service_items': [{'service': service.pk, 'quantity': 1}],
        'status': 'CONFIRMED',
        'payment_status': 'PAID',
        'payment_method': 'CASH',
    }, format='json')
    assert tech_invoice_resp.status_code == 201, tech_invoice_resp.data
    tech_invoice_data = tech_invoice_resp.json()
    assert 'unit_cost' not in tech_invoice_data['tire_items'][0]
    fixtures.append({'type': 'SalesInvoice', 'data': tech_invoice_data})

    tech_sales_list = auth_client_technician.get('/api/v1/invoices/sales/')
    assert tech_sales_list.status_code == 200, tech_sales_list.data
    tech_sales_payload = tech_sales_list.json()
    assert len(tech_sales_payload['results']) > 0
    for inv in tech_sales_payload['results']:
        for tire_item in inv['tire_items']:
            assert 'unit_cost' not in tire_item
    fixtures.append({'type': 'PaginatedResponse<SalesInvoice>', 'data': tech_sales_payload})

    tech_tires_list = auth_client_technician.get('/api/v1/catalog/tires/')
    assert tech_tires_list.status_code == 200, tech_tires_list.data
    tech_tires_payload = tech_tires_list.json()
    assert len(tech_tires_payload['results']) > 0
    for tire_row in tech_tires_payload['results']:
        assert 'purchase_price' not in tire_row
    fixtures.append({'type': 'PaginatedResponse<Tire>', 'data': tech_tires_payload})

    wh_movements_list = auth_client_warehouse.get('/api/v1/catalog/stock-movements/')
    assert wh_movements_list.status_code == 200, wh_movements_list.data
    wh_movements_payload = wh_movements_list.json()
    assert len(wh_movements_payload['results']) > 0
    for mov in wh_movements_payload['results']:
        assert 'unit_cost' not in mov
    fixtures.append({'type': 'PaginatedResponse<StockMovement>', 'data': wh_movements_payload})

    wh_sales_list = auth_client_warehouse.get('/api/v1/invoices/sales/')
    assert wh_sales_list.status_code == 200, wh_sales_list.data
    wh_sales_payload = wh_sales_list.json()
    assert len(wh_sales_payload['results']) > 0
    for inv in wh_sales_payload['results']:
        for tire_item in inv['tire_items']:
            assert 'unit_cost' not in tire_item
    fixtures.append({'type': 'PaginatedResponse<SalesInvoice>', 'data': wh_sales_payload})

    endpoints = {
        '/auth/profile/': 'User',
        '/auth/users/': 'PaginatedResponse<User>',
        '/catalog/brands/': 'PaginatedResponse<Brand>',
        '/catalog/sizes/': 'PaginatedResponse<Size>',
        '/catalog/tires/': 'PaginatedResponse<Tire>',
        '/catalog/tires/low-stock/': 'PaginatedResponse<Tire>',
        '/catalog/stock-movements/': 'PaginatedResponse<StockMovement>',
        '/crm/customers/': 'PaginatedResponse<Customer>',
        '/crm/vehicles/': 'PaginatedResponse<Vehicle>',
        '/workshop/services/': 'PaginatedResponse<TechnicalService>',
        '/procurement/suppliers/': 'PaginatedResponse<Supplier>',
        '/invoices/sales/': 'PaginatedResponse<SalesInvoice>',
        '/invoices/purchases/': 'PaginatedResponse<PurchaseInvoice>',
        '/invoices/returns/': 'PaginatedResponse<SalesReturn>',
        '/treasury/receipts/': 'PaginatedResponse<ReceiptVoucher>',
        '/treasury/payments/': 'PaginatedResponse<PaymentVoucher>',
        '/treasury/customer-refunds/': 'PaginatedResponse<CustomerRefundVoucher>',
        '/analytics/dashboard-stats/': 'DashboardStats',
        '/analytics/sales-by-brand/': 'BrandSalesStat[]',
        '/analytics/profitability/': 'ProfitabilityStat[]',
        '/analytics/inventory-value/': 'InventoryValueResponse',
        '/analytics/sales-by-date/': 'SalesByDateRangeResponse',
    }
    for endpoint, contract in endpoints.items():
        response = auth_client_manager.get('/api/v1' + endpoint)
        assert response.status_code == 200, (endpoint, response.data)
        payload = response.json()
        if contract.startswith('PaginatedResponse<'):
            assert len(payload['results']) > 0, (endpoint, payload)
        fixtures.append({'type': contract, 'data': payload})

    result = subprocess.run(
        [node, 'tests/checkBackendContracts.mjs'],
        cwd=frontend,
        input=json.dumps(fixtures),
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
