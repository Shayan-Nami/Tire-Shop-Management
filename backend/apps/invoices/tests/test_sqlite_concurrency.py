"""SQLite serializes writers; a lock failure is retryable, never a committed partial sale."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
import pytest
from django.db import connection, connections, OperationalError
from rest_framework.exceptions import ValidationError
from apps.catalog.models import Brand, Size, Tire, StockMovement
from apps.customers.models import Customer
from apps.invoices.models import InvoiceStatus, SalesInvoice
from apps.invoices.services import create_sales_invoice_service, confirm_sales_invoice_service


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(connection.vendor != 'sqlite', reason='SQLite writer-contention behavior')
def test_competing_drafts_never_commit_double_stock_out():
    tire = Tire.objects.create(tire_name='Last tire', brand=Brand.objects.create(brand_name='Race'),
        size=Size.objects.create(size_name='195/65R15'), stock_quantity=1,
        sale_price=Decimal('100'), purchase_price=Decimal('50'))
    customer = Customer.objects.create(full_name='Race customer')
    invoices = [create_sales_invoice_service(customer, None, [{'tire': tire, 'quantity': 1}], [],
                status=InvoiceStatus.DRAFT) for _ in range(2)]
    barrier = Barrier(2, timeout=10)
    def confirm(pk):
        try:
            barrier.wait()
            confirm_sales_invoice_service(pk)
            return 'confirmed'
        except OperationalError as exc:
            assert 'locked' in str(exc).lower()
            return 'locked'
        except ValidationError:
            return 'rejected'
        finally:
            # Django keeps shared-memory SQLite connections open in close(); the worker is done.
            worker_connection = connections['default']
            if worker_connection.connection is not None:
                worker_connection.connection.close()
                worker_connection.connection = None
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(confirm, invoice.pk) for invoice in invoices]
        outcomes = [future.result(timeout=15) for future in futures]
    assert outcomes.count('confirmed') <= 1
    # Retry only after the competing writers have exited, as a client would.
    for invoice in invoices:
        invoice.refresh_from_db()
        if invoice.status == InvoiceStatus.DRAFT:
            try:
                confirm_sales_invoice_service(invoice)
            except ValidationError:
                pass
    tire.refresh_from_db()
    assert tire.stock_quantity == 0
    assert SalesInvoice.objects.filter(status=InvoiceStatus.CONFIRMED).count() == 1
    assert StockMovement.objects.filter(tire=tire).count() == 1
