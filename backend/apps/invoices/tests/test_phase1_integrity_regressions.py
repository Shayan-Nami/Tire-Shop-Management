from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import UserRole
from apps.catalog.models import Brand, Size, Tire
from apps.customers.models import Customer
from apps.finance.models import CustomerRefundVoucher, ReceiptVoucher
from apps.invoices.models import (
    InvoiceStatus,
    PaymentStatus,
    PurchaseInvoice,
    PurchaseInvoiceTireItem,
    SalesInvoice,
    SalesInvoiceTireItem,
    SalesReturn,
)
from apps.invoices.serializers import SalesReturnItemSerializer
from apps.invoices.services import (
    _validate_invoice_total,
    cancel_purchase_invoice_service,
    create_purchase_invoice_service,
    create_sales_invoice_service,
    create_sales_return_service,
    generate_next_invoice_number,
)
from apps.services_app.models import Service
from apps.suppliers.models import Supplier
from utils.domain import DomainValidationError


@pytest.fixture
def phase1_setup(db):
    brand = Brand.objects.create(brand_name='پیرلی')
    size = Size.objects.create(size_name='205/55R16')
    tire_a = Tire.objects.create(
        tire_name='تایر الف',
        brand=brand,
        size=size,
        stock_quantity=20,
        purchase_price=Decimal('60.00'),
        sale_price=Decimal('100.00'),
    )
    tire_b = Tire.objects.create(
        tire_name='تایر ب',
        brand=brand,
        size=size,
        stock_quantity=20,
        purchase_price=Decimal('60.00'),
        sale_price=Decimal('100.00'),
    )
    tire_c = Tire.objects.create(
        tire_name='تایر ج',
        brand=brand,
        size=size,
        stock_quantity=20,
        purchase_price=Decimal('60.00'),
        sale_price=Decimal('100.00'),
    )
    service = Service.objects.create(service_name='بالانس چرخ', price=Decimal('100.00'))
    customer = Customer.objects.create(full_name='مشتری فاز یک', phone_number='09120001122')
    supplier = Supplier.objects.create(supplier_name='تامین‌کننده فاز یک', phone_number='09120003344')
    return {
        'tire_a': tire_a,
        'tire_b': tire_b,
        'tire_c': tire_c,
        'service': service,
        'customer': customer,
        'supplier': supplier,
    }


@pytest.mark.django_db
class TestPhase1InvoiceIntegrity:
    def test_percentage_discount_total_quantized_and_decimal_scale_validated(self, phase1_setup, manager_user):
        tire = phase1_setup['tire_a']
        invoice = create_sales_invoice_service(
            customer=phase1_setup['customer'],
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('101.00')}],
            service_items_data=[],
            discount_percent=Decimal('33.33'),
            created_by=manager_user,
        )
        assert invoice.total_amount == Decimal('67.34')

        invoice.total_amount = Decimal('100.123')
        with pytest.raises(DomainValidationError) as exc_info:
            _validate_invoice_total(invoice)
        assert 'total_amount' in exc_info.value.detail

    def test_draft_plus_paid_blocked_while_technician_confirmed_paid_allowed(
        self, phase1_setup, auth_client_technician, auth_client_manager, manager_user
    ):
        tire = phase1_setup['tire_a']
        customer = phase1_setup['customer']

        with pytest.raises(DomainValidationError):
            create_sales_invoice_service(
                customer=customer,
                vehicle=None,
                tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('100.00')}],
                service_items_data=[],
                status=InvoiceStatus.DRAFT,
                payment_status=PaymentStatus.PAID,
                created_by=manager_user,
            )

        url = reverse('sales-invoice-list')
        payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.DRAFT,
            'payment_status': PaymentStatus.PAID,
            'tire_items': [{'tire': tire.pk, 'quantity': 1, 'unit_price': '100.00'}],
            'service_items': [],
        }
        assert auth_client_manager.post(url, payload, format='json').status_code == 400
        assert auth_client_technician.post(url, payload, format='json').status_code == 400

        counter_payload = {
            'customer': customer.pk,
            'status': InvoiceStatus.CONFIRMED,
            'payment_status': PaymentStatus.PAID,
            'payment_method': 'POS',
            'tire_items': [{'tire': tire.pk, 'quantity': 1, 'unit_price': '100.00'}],
            'service_items': [],
        }
        res_tech = auth_client_technician.post(url, counter_payload, format='json')
        assert res_tech.status_code == 201
        assert res_tech.data['status'] == InvoiceStatus.CONFIRMED
        assert res_tech.data['payment_status'] == PaymentStatus.PAID
        assert ReceiptVoucher.objects.filter(sales_invoice_id=res_tech.data['sales_invoice_id']).exists()

    def test_zero_total_invoice_forces_paid_even_when_unpaid_passed(
        self, phase1_setup, auth_client_manager, manager_user
    ):
        tire = phase1_setup['tire_a']
        customer = phase1_setup['customer']

        inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('100.00')}],
            service_items_data=[],
            discount_amount=Decimal('100.00'),
            payment_status=PaymentStatus.UNPAID,
            created_by=manager_user,
        )
        assert inv.total_amount == Decimal('0.00')
        assert inv.payment_status == PaymentStatus.PAID
        assert not ReceiptVoucher.objects.filter(sales_invoice=inv).exists()

        res = auth_client_manager.post(
            reverse('sales-invoice-list'),
            {
                'customer': customer.pk,
                'status': InvoiceStatus.CONFIRMED,
                'payment_status': PaymentStatus.UNPAID,
                'discount_percent': '100.00',
                'tire_items': [{'tire': tire.pk, 'quantity': 1, 'unit_price': '100.00'}],
                'service_items': [],
            },
            format='json',
        )
        assert res.status_code == 201
        assert Decimal(str(res.data['total_amount'])) == Decimal('0.00')
        assert res.data['payment_status'] == PaymentStatus.PAID

    def test_invoice_number_and_invoice_date_share_single_now_snapshot(self, phase1_setup, manager_user):
        esfand_end = datetime(2026, 3, 20, 23, 59, 50, tzinfo=ZoneInfo('Asia/Tehran'))
        farvardin_start = datetime(2026, 3, 21, 0, 0, 10, tzinfo=ZoneInfo('Asia/Tehran'))

        with patch('apps.invoices.services.timezone.now', return_value=esfand_end), patch(
            'apps.invoices.services.generate_next_invoice_number', wraps=generate_next_invoice_number
        ) as spy_sales_num:
            sales_inv = create_sales_invoice_service(
                customer=phase1_setup['customer'],
                vehicle=None,
                tire_items_data=[{'tire': phase1_setup['tire_a'], 'quantity': 1, 'unit_price': Decimal('100.00')}],
                service_items_data=[],
                created_by=manager_user,
            )
            spy_sales_num.assert_called_once_with('SALES', dt=esfand_end)

        with patch('apps.invoices.services.timezone.now', return_value=farvardin_start), patch(
            'apps.invoices.services.generate_next_invoice_number', wraps=generate_next_invoice_number
        ) as spy_purch_num:
            purchase_inv = create_purchase_invoice_service(
                supplier=phase1_setup['supplier'],
                tire_items_data=[{'tire': phase1_setup['tire_b'], 'quantity': 1, 'unit_cost': Decimal('60.00')}],
                created_by=manager_user,
            )
            spy_purch_num.assert_called_once_with('PURCHASE', dt=farvardin_start)

        assert sales_inv.invoice_date == esfand_end
        assert sales_inv.invoice_number.startswith('S-1404-')
        assert purchase_inv.invoice_date == farvardin_start
        assert purchase_inv.invoice_number.startswith('P-1405-')

    def test_mixed_and_multi_item_sales_returns_avoid_rounding_overflow_and_underflow(
        self, phase1_setup, manager_user
    ):
        customer = phase1_setup['customer']
        tire_a = phase1_setup['tire_a']
        tire_b = phase1_setup['tire_b']
        tire_c = phase1_setup['tire_c']
        service = phase1_setup['service']

        mixed_inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[
                {'tire': tire_a, 'quantity': 1, 'unit_price': Decimal('100.00')},
                {'tire': tire_b, 'quantity': 1, 'unit_price': Decimal('100.00')},
            ],
            service_items_data=[{'service': service, 'quantity': 1, 'unit_price': Decimal('100.00')}],
            discount_amount=Decimal('1.00'),
            payment_status=PaymentStatus.PAID,
            created_by=manager_user,
        )
        assert mixed_inv.total_amount == Decimal('299.00')
        item_a = mixed_inv.tire_items.get(tire=tire_a)
        item_b = mixed_inv.tire_items.get(tire=tire_b)

        ret_mixed = create_sales_return_service(
            invoice=mixed_inv,
            items_data=[
                {'sales_invoice_tire_item_id': item_a.pk, 'quantity': 1},
                {'sales_invoice_tire_item_id': item_b.pk, 'quantity': 1},
            ],
            reason='مرجوعی کامل تایرهای فاکتور ترکیبی',
            user=manager_user,
            auto_refund=True,
        )
        assert ret_mixed.total_refund_amount == Decimal('199.33')
        mixed_inv.refresh_from_db()
        assert mixed_inv.net_amount == Decimal('99.67')
        refund_voucher = CustomerRefundVoucher.objects.get(sales_return=ret_mixed)
        assert refund_voucher.amount == Decimal('199.33')

        underflow_inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[
                {'tire': tire_a, 'quantity': 1, 'unit_price': Decimal('100.00')},
                {'tire': tire_b, 'quantity': 1, 'unit_price': Decimal('100.00')},
                {'tire': tire_c, 'quantity': 1, 'unit_price': Decimal('100.00')},
            ],
            service_items_data=[],
            discount_amount=Decimal('2.00'),
            created_by=manager_user,
        )
        assert underflow_inv.total_amount == Decimal('298.00')
        u_items = [underflow_inv.tire_items.get(tire=t) for t in (tire_a, tire_b, tire_c)]
        ret_seq = [
            create_sales_return_service(
                invoice=underflow_inv,
                items_data=[{'sales_invoice_tire_item_id': item.pk, 'quantity': 1}],
                reason=f'مرجوعی ترتیبی {idx}',
                user=manager_user,
            )
            for idx, item in enumerate(u_items, start=1)
        ]
        assert sum(r.total_refund_amount for r in ret_seq) == Decimal('298.00')
        assert [r.total_refund_amount for r in ret_seq] == [Decimal('99.33'), Decimal('99.33'), Decimal('99.34')]

        overflow_inv = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[
                {'tire': tire_a, 'quantity': 1, 'unit_price': Decimal('100.00')},
                {'tire': tire_b, 'quantity': 1, 'unit_price': Decimal('100.00')},
                {'tire': tire_c, 'quantity': 1, 'unit_price': Decimal('0.00')},
            ],
            service_items_data=[],
            discount_amount=Decimal('1.00'),
            created_by=manager_user,
        )
        ret_with_free = create_sales_return_service(
            invoice=overflow_inv,
            items_data=[
                {'sales_invoice_tire_item_id': overflow_inv.tire_items.get(tire=tire_a).pk, 'quantity': 1},
                {'sales_invoice_tire_item_id': overflow_inv.tire_items.get(tire=tire_b).pk, 'quantity': 1},
                {'sales_invoice_tire_item_id': overflow_inv.tire_items.get(tire=tire_c).pk, 'quantity': 1},
            ],
            reason='مرجوعی همراه قلم رایگان',
            user=manager_user,
        )
        assert ret_with_free.total_refund_amount == Decimal('199.00')
        assert ret_with_free.items.get(tire=tire_c).refund_amount == Decimal('0.00')

    def test_sales_return_rejects_date_before_invoice_date(
        self, phase1_setup, manager_user, auth_client_manager
    ):
        tire = phase1_setup['tire_a']
        inv = create_sales_invoice_service(
            customer=phase1_setup['customer'],
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_price': Decimal('100.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        tire_item = inv.tire_items.get()
        early_date = inv.invoice_date - timedelta(hours=1)

        with pytest.raises(DomainValidationError, match='پیش از تاریخ صدور'):
            create_sales_return_service(
                invoice=inv,
                items_data=[{'sales_invoice_tire_item_id': tire_item.pk, 'quantity': 1}],
                reason='تاریخ نامعتبر',
                return_date=early_date,
                user=manager_user,
            )

        res = auth_client_manager.post(
            reverse('sales-return-list'),
            {
                'sales_invoice': inv.pk,
                'return_date': early_date.isoformat(),
                'reason': 'تست API تاریخ نامعتبر',
                'items': [{'sales_invoice_tire_item_id': tire_item.pk, 'quantity': 1}],
            },
            format='json',
        )
        assert res.status_code == 400
        assert 'return_date' in res.data.get('errors', res.data)

    def test_cancel_purchase_invoice_skips_prior_cancelled_and_handles_missing_item(
        self, phase1_setup, manager_user
    ):
        tire = phase1_setup['tire_a']
        supplier = phase1_setup['supplier']

        prior_cancelled = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_cost': Decimal('100.00')}],
            created_by=manager_user,
        )
        PurchaseInvoiceTireItem.objects.filter(purchase_invoice=prior_cancelled).update(previous_purchase_price=None)
        PurchaseInvoice.objects.filter(pk=prior_cancelled.pk).update(status=InvoiceStatus.CANCELLED)

        Tire.objects.filter(pk=tire.pk).update(purchase_price=Decimal('75.00'))
        second = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 2, 'unit_cost': Decimal('140.00')}],
            created_by=manager_user,
        )
        cancel_purchase_invoice_service(second, user=manager_user)
        tire.refresh_from_db()
        assert tire.purchase_price == Decimal('75.00')

        broken = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_cost': Decimal('120.00')}],
            created_by=manager_user,
        )
        item = broken.tire_items.get()
        PurchaseInvoiceTireItem.objects.filter(pk=item.pk).update(previous_purchase_price=None)
        with pytest.raises(DomainValidationError):
            cancel_purchase_invoice_service(broken, user=manager_user)

    def test_sales_return_item_unit_cost_masked_for_technician_and_warehouse_not_superuser(
        self, phase1_setup, manager_user, technician_user, warehouse_user, superuser
    ):
        inv = create_sales_invoice_service(
            customer=phase1_setup['customer'],
            vehicle=None,
            tire_items_data=[{'tire': phase1_setup['tire_a'], 'quantity': 2, 'unit_price': Decimal('100.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        sales_return = create_sales_return_service(
            invoice=inv,
            items_data=[{'sales_invoice_tire_item_id': inv.tire_items.get().pk, 'quantity': 1}],
            reason='بررسی دسترسی قیمت تمام‌شده',
            user=manager_user,
        )
        return_item = sales_return.items.get()

        superuser.role = UserRole.TECHNICIAN
        superuser.save(update_fields=['role'])

        factory = RequestFactory()
        for user, expect_visible in [
            (technician_user, False),
            (warehouse_user, False),
            (manager_user, True),
            (superuser, True),
        ]:
            req = factory.get('/')
            req.user = user
            serialized = SalesReturnItemSerializer(return_item, context={'request': req}).data
            assert ('unit_cost' in serialized) is expect_visible

    def test_sales_invoice_tire_item_save_preserves_explicit_zero_cost(self, phase1_setup, manager_user):
        inv = create_sales_invoice_service(
            customer=phase1_setup['customer'],
            vehicle=None,
            tire_items_data=[{'tire': phase1_setup['tire_a'], 'quantity': 1, 'unit_price': Decimal('100.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        zero_cost_item = SalesInvoiceTireItem.objects.create(
            sales_invoice=inv,
            tire=phase1_setup['tire_b'],
            quantity=1,
            unit_price=Decimal('100.00'),
            unit_cost=Decimal('0.00'),
        )
        assert zero_cost_item.unit_cost == Decimal('0.00')

        none_cost_item = SalesInvoiceTireItem(
            sales_invoice=inv,
            tire=phase1_setup['tire_c'],
            quantity=1,
            unit_price=Decimal('100.00'),
            unit_cost=None,
        )
        none_cost_item.save()
        assert none_cost_item.unit_cost == Decimal('60.00')

    def test_sales_return_admin_is_strictly_read_only(self, superuser):
        req = RequestFactory().get('/admin/')
        req.user = superuser
        model_admin = admin.site._registry[SalesReturn]
        assert model_admin.has_view_permission(req)
        assert not model_admin.has_add_permission(req)
        assert not model_admin.has_change_permission(req)
        assert not model_admin.has_delete_permission(req)
        assert set(model_admin.get_readonly_fields(req)) == {
            field.name for field in SalesReturn._meta.fields
        }
        for inline in model_admin.get_inline_instances(req):
            assert not inline.has_add_permission(req)
            assert not inline.has_change_permission(req)
            assert not inline.has_delete_permission(req)

    def test_invoice_filters_tehran_day_bounds_purchase_dates_and_cancel_messages(
        self, phase1_setup, auth_client_manager, manager_user
    ):
        tehran_tz = ZoneInfo('Asia/Tehran')
        tire = phase1_setup['tire_a']
        customer = phase1_setup['customer']
        supplier = phase1_setup['supplier']

        sales_late = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('100.00')}],
            service_items_data=[],
            status=InvoiceStatus.DRAFT,
            created_by=manager_user,
        )
        sales_next_day = create_sales_invoice_service(
            customer=customer,
            vehicle=None,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_price': Decimal('100.00')}],
            service_items_data=[],
            created_by=manager_user,
        )
        SalesInvoice.objects.filter(pk=sales_late.pk).update(
            invoice_date=datetime(2026, 10, 10, 23, 59, 59, tzinfo=tehran_tz)
        )
        SalesInvoice.objects.filter(pk=sales_next_day.pk).update(
            invoice_date=datetime(2026, 10, 11, 0, 0, 0, tzinfo=tehran_tz)
        )

        sales_list_res = auth_client_manager.get(
            reverse('sales-invoice-list'),
            {'start_date': '2026-10-10', 'end_date': '2026-10-10'},
        )
        assert sales_list_res.status_code == 200
        returned_sales_ids = [row['sales_invoice_id'] for row in sales_list_res.data['results']]
        assert sales_late.pk in returned_sales_ids
        assert sales_next_day.pk not in returned_sales_ids

        confirm_res = auth_client_manager.post(reverse('sales-invoice-confirm', args=[sales_late.pk]))
        assert confirm_res.status_code == 200
        assert 'returned_amount' in confirm_res.data['invoice']

        cancel_sales_res = auth_client_manager.post(reverse('sales-invoice-cancel', args=[sales_next_day.pk]))
        assert cancel_sales_res.status_code == 200
        assert sales_next_day.invoice_number in cancel_sales_res.data['message']

        purchase_inv = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_cost': Decimal('60.00')}],
            created_by=manager_user,
        )
        purchase_next = create_purchase_invoice_service(
            supplier=supplier,
            tire_items_data=[{'tire': tire, 'quantity': 1, 'unit_cost': Decimal('60.00')}],
            created_by=manager_user,
        )
        PurchaseInvoice.objects.filter(pk=purchase_inv.pk).update(
            invoice_date=datetime(2026, 10, 10, 23, 45, 0, tzinfo=tehran_tz)
        )
        PurchaseInvoice.objects.filter(pk=purchase_next.pk).update(
            invoice_date=datetime(2026, 10, 11, 0, 5, 0, tzinfo=tehran_tz)
        )

        purchase_list_res = auth_client_manager.get(
            reverse('purchase-invoice-list'),
            {'start_date': '2026-10-10', 'end_date': '2026-10-10'},
        )
        assert purchase_list_res.status_code == 200
        returned_purchase_ids = [row['purchase_invoice_id'] for row in purchase_list_res.data['results']]
        assert purchase_inv.pk in returned_purchase_ids
        assert purchase_next.pk not in returned_purchase_ids

        cancel_purchase_res = auth_client_manager.post(reverse('purchase-invoice-cancel', args=[purchase_next.pk]))
        assert cancel_purchase_res.status_code == 200
        assert purchase_next.invoice_number in cancel_purchase_res.data['message']
