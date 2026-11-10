from decimal import Decimal
import pytest
from apps.accounts.models import User, UserRole
from apps.invoices.permissions import SalesInvoicePermission
from apps.customers.models import Customer
from apps.invoices.services import create_sales_invoice_service
from apps.finance.services import create_receipt_voucher_service
from apps.services_app.models import Service
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.django_db


def test_superuser_with_warehouse_role_can_issue_sales():
    user = User(username='root', role=UserRole.WAREHOUSE, is_superuser=True)
    request = APIRequestFactory().post('/')
    request.user = user
    assert SalesInvoicePermission().has_permission(request, None)


def test_logout_cannot_revoke_another_users_refresh(api_client, technician_user, manager_user):
    refresh = RefreshToken.for_user(manager_user)
    api_client.force_authenticate(technician_user)
    response = api_client.post('/api/v1/auth/logout/', {'refresh': str(refresh)})
    assert response.status_code == 400
    RefreshToken(str(refresh))


@pytest.mark.parametrize('amount', ['NaN', 'Infinity', '-Infinity', '0.001'])
def test_receipt_service_rejects_unrepresentable_amount(amount):
    customer = Customer.objects.create(full_name='validation')
    service = Service.objects.create(service_name='mounting', price=Decimal('100'))
    invoice = create_sales_invoice_service(customer, None, [], [{'service': service}])
    with pytest.raises(ValidationError):
        create_receipt_voucher_service(invoice, Decimal(amount))
    assert not invoice.receipts.exists()
