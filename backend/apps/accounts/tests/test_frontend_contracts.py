import json
from pathlib import Path
import shutil
import subprocess

import pytest

from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer, Vehicle
from apps.services_app.models import Service
from apps.suppliers.models import Supplier


@pytest.mark.django_db
def test_api_responses_match_frontend_types(auth_client_manager):
    frontend = Path(__file__).resolve().parents[4] / 'frontend'
    node = shutil.which('node')
    if not node or not (frontend / 'node_modules/typescript').exists():
        pytest.skip('Install Node and run npm ci in frontend for the cross-stack contract check')

    brand = Brand.objects.create(brand_name='Contract brand')
    size = Size.objects.create(size_name='195/65R15')
    tire = Tire.objects.create(
        tire_name='Contract tire',
        brand=brand,
        size=size,
        stock_quantity=10,
        sale_price='1000.00',
        purchase_price='600.00',
        min_stock_alert=12,
    )
    customer = Customer.objects.create(full_name='Contract customer', phone_number='09120009988')
    vehicle = Vehicle.objects.create(customer=customer, license_plate='12ب345-ایران11', model='Contract car')
    service = Service.objects.create(service_name='Contract service', price='100.00')
    supplier = Supplier.objects.create(supplier_name='Contract supplier', phone_number='02188776655')

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

    purchase = auth_client_manager.post('/api/v1/invoices/purchases/', {
        'supplier': supplier.pk,
        'tire_items': [{'tire': tire.pk, 'quantity': 2, 'unit_cost': '600.00'}],
    }, format='json')
    assert purchase.status_code == 201, purchase.data
    purchase_data = purchase.json()

    payment = auth_client_manager.post('/api/v1/treasury/payments/', {
        'purchase_invoice': purchase_data['purchase_invoice_id'],
        'amount': '500.00',
        'payment_method': 'CASH',
    }, format='json')
    assert payment.status_code == 201, payment.data

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

    fixtures = [
        {'type': 'SalesInvoice', 'data': invoice_data},
        {'type': 'PurchaseInvoice', 'data': purchase_data},
        {'type': 'SalesReturn', 'data': return_data},
        {'type': 'PaymentVoucher', 'data': payment.json()},
    ]
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
