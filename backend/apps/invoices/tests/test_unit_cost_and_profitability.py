import pytest
from decimal import Decimal
from django.urls import reverse
from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer
from apps.invoices.models import SalesInvoiceTireItem, InvoiceStatus
from apps.invoices.services import create_sales_invoice_service

@pytest.fixture
def catalog_setup(db):
    brand = Brand.objects.create(brand_name='کویر تایر')
    size = Size.objects.create(size_name='185/65R14')
    tire = Tire.objects.create(
        tire_name='کویر تایر KB14',
        brand=brand,
        size=size,
        stock_quantity=20,
        purchase_price=Decimal('2000000.00'),
        sale_price=Decimal('2600000.00'),
        min_stock_alert=5
    )
    customer = Customer.objects.create(
        full_name='رضا احمدی',
        phone_number='09123456789',
        national_code='0011223344'
    )
    return {'brand': brand, 'size': size, 'tire': tire, 'customer': customer}

@pytest.mark.django_db
class TestUnitCostAndProfitability:

    def test_sales_invoice_snapshots_unit_cost_from_tire_purchase_price(self, catalog_setup, manager_user):
        tire = catalog_setup['tire']
        customer = catalog_setup['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[
                {'tire': tire, 'quantity': 4, 'unit_price': tire.sale_price}
            ],
            service_items_data=[],
            created_by=manager_user
        )

        item = invoice.tire_items.first()
        assert item is not None
        assert item.unit_cost == Decimal('2000000.00')
        assert item.unit_price == Decimal('2600000.00')

    def test_tire_purchase_price_change_does_not_affect_past_invoice_item_cost_or_profit(
        self, catalog_setup, auth_client_manager
    ):
        tire = catalog_setup['tire']
        customer = catalog_setup['customer']

        payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.CONFIRMED,
            'payment_status': 'PAID',
            'tire_items': [
                {'tire': tire.pk, 'quantity': 2, 'unit_price': str(tire.sale_price)}
            ],
            'service_items': []
        }
        res_create = auth_client_manager.post(reverse('sales-invoice-list'), payload, format='json')
        assert res_create.status_code == 201
        invoice_id = res_create.data['sales_invoice_id']

        item = SalesInvoiceTireItem.objects.get(sales_invoice_id=invoice_id)
        assert item.unit_cost == Decimal('2000000.00')

        tire.purchase_price = Decimal('3200000.00')
        tire.save(update_fields=['purchase_price'])

        item.refresh_from_db()
        assert item.unit_cost == Decimal('2000000.00')

        report_url = reverse('profitability-report')
        res_report = auth_client_manager.get(report_url)
        assert res_report.status_code == 200

        tire_profit_data = next((r for r in res_report.data if r['tire_id'] == tire.pk), None)
        assert tire_profit_data is not None
        assert tire_profit_data['total_sold'] == 2
        assert tire_profit_data['total_revenue'] == 5200000.0
        assert tire_profit_data['total_cost'] == 4000000.0
        assert tire_profit_data['total_profit'] == 1200000.0

    def test_technician_cannot_view_unit_cost_in_sales_invoice(
        self, catalog_setup, auth_client_manager, auth_client_technician, technician_user
    ):
        tire = catalog_setup['tire']
        customer = catalog_setup['customer']

        invoice = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[
                {'tire': tire, 'quantity': 2, 'unit_price': tire.sale_price}
            ],
            service_items_data=[],
            created_by=technician_user
        )

        detail_url = reverse('sales-invoice-detail', kwargs={'pk': invoice.pk})

        res_tech = auth_client_technician.get(detail_url)
        assert res_tech.status_code == 200
        tire_item_tech = res_tech.data['tire_items'][0]
        assert 'unit_cost' not in tire_item_tech
        assert 'unit_price' in tire_item_tech

        res_mgr = auth_client_manager.get(detail_url)
        assert res_mgr.status_code == 200
        tire_item_mgr = res_mgr.data['tire_items'][0]
        assert 'unit_cost' in tire_item_mgr
        assert tire_item_mgr['unit_cost'] == '2000000.00'

    def test_client_provided_unit_cost_is_strictly_ignored(
        self, catalog_setup, auth_client_manager
    ):
        tire = catalog_setup['tire']
        customer = catalog_setup['customer']

        payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.CONFIRMED,
            'payment_status': 'PAID',
            'tire_items': [
                {
                    'tire': tire.pk,
                    'quantity': 1,
                    'unit_price': '2500000.00',
                    'unit_cost': '99999999.00'
                }
            ],
            'service_items': []
        }
        res = auth_client_manager.post(reverse('sales-invoice-list'), payload, format='json')
        assert res.status_code == 201

        invoice_id = res.data['sales_invoice_id']
        item = SalesInvoiceTireItem.objects.get(sales_invoice_id=invoice_id)
        assert item.unit_cost == Decimal('2000000.00')
        assert item.unit_cost != Decimal('99999999.00')

    def test_sales_invoice_tire_item_negative_unit_cost_rejected_in_model(self, catalog_setup):
        from django.core.exceptions import ValidationError as DjangoValidationError
        item = SalesInvoiceTireItem(
            sales_invoice=None,
            tire=catalog_setup['tire'],
            quantity=1,
            unit_price=Decimal('2500000.00'),
            unit_cost=Decimal('-1000.00')
        )
        with pytest.raises(DjangoValidationError):
            item.full_clean(exclude=['sales_invoice'])
