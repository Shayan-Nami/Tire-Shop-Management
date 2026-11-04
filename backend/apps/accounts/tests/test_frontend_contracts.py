"""Real serializer responses must satisfy the SPA's actual TypeScript interfaces."""
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
    tire = Tire.objects.create(tire_name='Contract tire', brand=brand, size=size,
                               stock_quantity=5, sale_price='1000.00', purchase_price='600.00')
    customer = Customer.objects.create(full_name='Contract customer')
    vehicle = Vehicle.objects.create(customer=customer, license_plate='12ب345-ایران11', model='Contract car')
    Service.objects.create(service_name='Contract service', price='100.00')
    Supplier.objects.create(supplier_name='Contract supplier')
    invoice = auth_client_manager.post('/api/v1/invoices/sales/', {
        'customer': customer.pk, 'vehicle': vehicle.pk,
        'tire_items': [{'tire': tire.pk, 'quantity': 1}],
        'status': 'CONFIRMED', 'payment_status': 'PAID', 'payment_method': 'CASH',
    }, format='json')
    assert invoice.status_code == 201, invoice.data
    fixtures = [{'type': 'SalesInvoice', 'data': invoice.json()}]
    endpoints = {
        '/auth/profile/': 'User', '/catalog/tires/': 'PaginatedResponse<Tire>',
        '/catalog/stock-movements/': 'PaginatedResponse<StockMovement>',
        '/crm/customers/': 'PaginatedResponse<Customer>', '/crm/vehicles/': 'PaginatedResponse<Vehicle>',
        '/workshop/services/': 'PaginatedResponse<TechnicalService>',
        '/procurement/suppliers/': 'PaginatedResponse<Supplier>',
        '/treasury/receipts/': 'PaginatedResponse<ReceiptVoucher>',
        '/analytics/dashboard-stats/': 'DashboardStats', '/analytics/sales-by-brand/': 'BrandSalesStat[]',
        '/analytics/profitability/': 'ProfitabilityStat[]', '/analytics/inventory-value/': 'InventoryValueResponse',
        '/analytics/sales-by-date/': 'SalesByDateRangeResponse',
    }
    for endpoint, contract in endpoints.items():
        response = auth_client_manager.get('/api/v1' + endpoint)
        assert response.status_code == 200, (endpoint, response.data)
        fixtures.append({'type': contract, 'data': response.json()})
    result = subprocess.run([node, 'tests/checkBackendContracts.mjs'], cwd=frontend,
                            input=json.dumps(fixtures), text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
