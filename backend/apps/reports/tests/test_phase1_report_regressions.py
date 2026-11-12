from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse

from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer
from apps.invoices.models import SalesInvoice, SalesReturn, SalesReturnItem
from apps.invoices.services import create_sales_invoice_service, create_sales_return_service
from apps.reports.services import (
    dashboard_stats,
    inventory_value,
    profitability,
    sales_by_brand,
    sales_by_date,
)
from apps.services_app.models import Service


@pytest.fixture
def reports_phase1_data(db):
    brand_a = Brand.objects.create(brand_name='هانکوک')
    brand_b = Brand.objects.create(brand_name='یوکوهاما')
    size = Size.objects.create(size_name='225/50R17')
    tire_a = Tire.objects.create(
        tire_name='تایر ای',
        brand=brand_a,
        size=size,
        stock_quantity=15,
        purchase_price=Decimal('40.00'),
        sale_price=Decimal('101.00'),
    )
    tire_b = Tire.objects.create(
        tire_name='تایر بی',
        brand=brand_b,
        size=size,
        stock_quantity=15,
        purchase_price=Decimal('40.00'),
        sale_price=Decimal('100.00'),
    )
    service = Service.objects.create(service_name='تنظیم فرمان', price=Decimal('100.00'))
    customer = Customer.objects.create(full_name='مشتری گزارش', phone_number='09127778899')
    return {
        'brand_a': brand_a,
        'brand_b': brand_b,
        'tire_a': tire_a,
        'tire_b': tire_b,
        'service': service,
        'customer': customer,
    }


@pytest.mark.django_db
class TestPhase1ReportsRegressions:
    def test_zero_net_qty_zeroes_out_brand_revenue_and_profitability(self, reports_phase1_data, manager_user):
        tire_a = reports_phase1_data['tire_a']
        tire_b = reports_phase1_data['tire_b']
        customer = reports_phase1_data['customer']

        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[
                {'tire': tire_a, 'quantity': 1, 'unit_price': Decimal('100.00')},
                {'tire': tire_b, 'quantity': 1, 'unit_price': Decimal('100.00')},
            ],
            service_items_data=[],
            discount_amount=Decimal('1.00'),
            created_by=manager_user,
        )
        ret = create_sales_return_service(
            invoice=inv,
            items_data=[
                {'sales_invoice_tire_item_id': inv.tire_items.get(tire=tire_a).pk, 'quantity': 1},
                {'sales_invoice_tire_item_id': inv.tire_items.get(tire=tire_b).pk, 'quantity': 1},
            ],
            reason='مرجوعی کامل هر دو تایر',
            user=manager_user,
        )
        SalesReturnItem.objects.filter(sales_return=ret, tire=tire_a).update(refund_amount=Decimal('99.65'))

        brand_rows = {row['brand_name']: row for row in sales_by_brand()}
        assert brand_rows['هانکوک']['total_quantity'] == 0
        assert brand_rows['هانکوک']['total_revenue'] == 0.0
        assert brand_rows['یوکوهاما']['total_quantity'] == 0
        assert brand_rows['یوکوهاما']['total_revenue'] == 0.0

        prof_rows = {row['tire_id']: row for row in profitability()}
        assert prof_rows[tire_a.pk]['total_sold'] == 0
        assert prof_rows[tire_a.pk]['total_revenue'] == 0.0
        assert prof_rows[tire_a.pk]['total_cost'] == 0.0
        assert prof_rows[tire_a.pk]['total_profit'] == 0.0

    def test_sales_by_date_respects_asia_tehran_day_bounds(
        self, reports_phase1_data, manager_user, auth_client_manager
    ):
        tehran_tz = ZoneInfo('Asia/Tehran')
        tire = reports_phase1_data['tire_a']
        customer = reports_phase1_data['customer']

        inv_prev_night = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('100.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        inv_early_tehran = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('200.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        inv_late_tehran = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('300.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        inv_next_day = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('400.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        ret_early_tehran = create_sales_return_service(
            invoice=inv_early_tehran,
            items_data=[{'sales_invoice_tire_item_id': inv_early_tehran.tire_items.get().pk, 'quantity': 1}],
            reason='مرجوعی نیمه‌شب تهران',
            user=manager_user,
        )

        SalesInvoice.objects.filter(pk=inv_prev_night.pk).update(
            invoice_date=datetime(2026, 10, 9, 23, 59, 59, tzinfo=tehran_tz)
        )
        SalesInvoice.objects.filter(pk=inv_early_tehran.pk).update(
            invoice_date=datetime(2026, 10, 10, 0, 30, 0, tzinfo=tehran_tz)
        )
        SalesInvoice.objects.filter(pk=inv_late_tehran.pk).update(
            invoice_date=datetime(2026, 10, 10, 23, 30, 0, tzinfo=tehran_tz)
        )
        SalesInvoice.objects.filter(pk=inv_next_day.pk).update(
            invoice_date=datetime(2026, 10, 11, 0, 0, 0, tzinfo=tehran_tz)
        )
        SalesReturn.objects.filter(pk=ret_early_tehran.pk).update(
            return_date=datetime(2026, 10, 10, 1, 0, 0, tzinfo=tehran_tz)
        )

        result = sales_by_date(start_date='2026-10-10', end_date='2026-10-10')
        assert result['total_invoices'] == 2
        assert result['gross_sales_amount'] == 500.0
        assert result['total_refund_amount'] == 200.0
        assert result['total_sales_amount'] == 300.0

        api_res = auth_client_manager.get(
            reverse('sales-by-date-report'),
            {'start_date': '2026-10-10', 'end_date': '2026-10-10'},
        )
        assert api_res.status_code == 200
        assert api_res.data['total_invoices'] == 2
        assert api_res.data['total_sales_amount'] == 300.0

    def test_report_decimal_outputs_quantized_to_two_decimal_places(self, reports_phase1_data, manager_user):
        tire_a = reports_phase1_data['tire_a']
        inv = create_sales_invoice_service(
            customer=reports_phase1_data['customer'],
            vehicle=None,
            tire_items_data=[{'tire': tire_a, 'quantity': 1, 'unit_price': Decimal('101.00')}],
            service_items_data=[],
            discount_percent=Decimal('33.33'),
            created_by=manager_user,
        )
        assert inv.total_amount == Decimal('67.34')

        dash = dashboard_stats()
        brands = sales_by_brand()
        prof = profitability()
        inv_val = inventory_value()
        by_date = sales_by_date()

        for val in [
            dash['today_revenue'],
            dash['total_receivables'],
            dash['total_inventory_value'],
            brands[0]['total_revenue'],
            prof[0]['total_revenue'],
            prof[0]['total_cost'],
            prof[0]['total_profit'],
            inv_val['total_inventory_value'],
            by_date['total_sales_amount'],
            by_date['gross_sales_amount'],
        ]:
            dec = Decimal(str(val))
            assert dec == dec.quantize(Decimal('0.01'))
