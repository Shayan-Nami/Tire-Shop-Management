import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from apps.customers.models import Customer
from apps.invoices.models import SalesInvoice, PurchaseInvoice, InvoiceSequence


@pytest.mark.django_db
@pytest.mark.parametrize('model', [SalesInvoice, PurchaseInvoice, InvoiceSequence])
def test_financial_document_admin_disallows_direct_writes(model, superuser):
    request = RequestFactory().get('/admin/')
    request.user = superuser
    model_admin = admin.site._registry[model]
    assert model_admin.has_view_permission(request)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)
    assert set(model_admin.get_readonly_fields(request)) == {
        field.name for field in model._meta.fields
    }
    for inline in model_admin.get_inline_instances(request):
        assert not inline.has_add_permission(request)
        assert not inline.has_change_permission(request)
        assert not inline.has_delete_permission(request)


@pytest.mark.django_db
def test_admin_post_cannot_change_invoice_or_delete_it(client, superuser):
    invoice = SalesInvoice.objects.create(
        invoice_number='AUDIT-ADMIN',
        customer=Customer.objects.create(full_name='آزمون پنل مدیریت'),
        total_amount='1000.00',
    )
    client.force_login(superuser)
    change_url = reverse('admin:invoices_salesinvoice_change', args=[invoice.pk])
    assert client.get(change_url).status_code == 200
    assert client.post(change_url, {'total_amount': '1.00'}).status_code == 403
    delete_url = reverse('admin:invoices_salesinvoice_delete', args=[invoice.pk])
    assert client.post(delete_url, {'post': 'yes'}).status_code == 403
    invoice.refresh_from_db()
    assert invoice.total_amount == 1000
