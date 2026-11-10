from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer
from apps.invoices.models import InvoiceStatus, SalesInvoice, SalesReturn


@pytest.mark.django_db
def test_dashboard_counts_only_today_confirmed_activity(auth_client_manager):
    start = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    customer = Customer.objects.create(full_name='مشتری گزارش روزانه')

    def invoice(number, date, status=InvoiceStatus.CONFIRMED):
        return SalesInvoice.objects.create(
            invoice_number=number, customer=customer, invoice_date=date,
            status=status, total_amount=Decimal('1000.00'),
        )

    current = invoice('S-1405-00001', start)
    invoice('S-1405-00002', start - timedelta(microseconds=1))
    invoice('S-1405-00003', start + timedelta(days=1))
    cancelled = invoice('S-1405-00004', start, InvoiceStatus.CANCELLED)
    for date, source, amount in [
        (start, current, '100.00'),
        (start - timedelta(microseconds=1), current, '200.00'),
        (start + timedelta(days=1), current, '300.00'),
        (start, cancelled, '400.00'),
    ]:
        SalesReturn.objects.create(
            sales_invoice=source, return_date=date, reason='آزمون بازه روزانه',
            total_refund_amount=Decimal(amount),
        )

    response = auth_client_manager.get(reverse('dashboard-stats'))
    assert response.status_code == 200
    assert response.data['today_invoices_count'] == 1
    assert Decimal(str(response.data['today_revenue'])) == Decimal('900.00')
