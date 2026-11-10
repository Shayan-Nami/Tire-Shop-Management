import pytest
from django.urls import reverse

@pytest.mark.django_db
class TestReportsAndAnalytics:

    def test_dashboard_stats_endpoint(self, auth_client_manager):
        url = reverse('dashboard-stats')
        response = auth_client_manager.get(url)
        assert response.status_code == 200
        assert 'today_revenue' in response.data
        assert 'total_inventory_value' in response.data
        assert 'low_stock_count' in response.data
        assert 'total_receivables' in response.data

    def test_technician_blocked_from_financial_reports(self, auth_client_technician):
        endpoints = [
            reverse('dashboard-stats'),
            reverse('profitability-report'),
            reverse('inventory-value-report'),
            reverse('sales-by-brand-report'),
        ]
        for url in endpoints:
            response = auth_client_technician.get(url)
            assert response.status_code == 403

    def test_profitability_report_endpoint(self, auth_client_manager):
        url = reverse('profitability-report')
        response = auth_client_manager.get(url)
        assert response.status_code == 200
        assert isinstance(response.data, list)

    def test_dashboard_receivables_per_invoice_isolation_and_cancelled_exclusion(
        self, auth_client_manager, manager_user
    ):
        from decimal import Decimal
        from apps.catalog.models import Brand, Size, Tire, StockMovement, StockMovementType
        from apps.customers.models import Customer
        from apps.invoices.models import InvoiceStatus
        from apps.invoices.services import create_sales_invoice_service, create_sales_return_service
        from apps.finance.services import create_receipt_voucher_service

        brand = Brand.objects.create(brand_name='بارز تایر تست داشبورد')
        size = Size.objects.create(size_name='185/65R14')
        tire = Tire.objects.create(
            tire_name='تایر تست ۱۸۵',
            brand=brand,
            size=size,
            stock_quantity=50,
            purchase_price=Decimal('500000.00'),
            sale_price=Decimal('1000000.00'),
            min_stock_alert=5
        )
        StockMovement.objects.create(
            tire=tire,
            quantity=50,
            movement_type=StockMovementType.INITIAL_STOCK,
            balance_after=50,
            unit_cost=Decimal('500000.00'),
            user=manager_user,
            description='موجودی اولیه'
        )
        customer1 = Customer.objects.create(full_name='مشتری الف', phone_number='09110000001')
        customer2 = Customer.objects.create(full_name='مشتری ب', phone_number='09110000002')
        customer3 = Customer.objects.create(full_name='مشتری ج', phone_number='09110000003')

        create_sales_invoice_service(
            customer=customer1,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('1000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )

        inv_b = create_sales_invoice_service(
            customer=customer2,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('500000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        create_receipt_voucher_service(inv_b, Decimal('500000.00'), user=manager_user)
        sales_item_b = inv_b.tire_items.first()
        create_sales_return_service(
            invoice=inv_b,
            items_data=[{'sales_invoice_tire_item_id': sales_item_b.pk, 'quantity': 1}],
            reason='مرجوعی فاکتور ب',
            user=manager_user
        )
        inv_b.refresh_from_db()
        assert inv_b.excess_amount == Decimal('500000.00')

        inv_c = create_sales_invoice_service(
            customer=customer3,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('1000000.00')}],
            service_items_data=[],
            created_by=manager_user
        )
        inv_c.status = InvoiceStatus.CANCELLED
        inv_c.save(update_fields=['status'])

        url = reverse('dashboard-stats')
        response = auth_client_manager.get(url)
        assert response.status_code == 200
        assert response.data['total_receivables'] == 1000000.0
        assert response.data['unpaid_invoices_count'] == 1

