"""Role matrix uses persisted ordinary users, never superuser-backed managers."""
import pytest
from django.urls import reverse
from apps.accounts.models import User, UserRole

ROUTES = [
    ('user-list', {'MANAGER'}),
    ('customer-list', {'MANAGER', 'TECHNICIAN', 'WAREHOUSE'}),
    ('vehicle-list', {'MANAGER', 'TECHNICIAN', 'WAREHOUSE'}),
    ('brand-list', {'MANAGER', 'TECHNICIAN', 'WAREHOUSE'}),
    ('size-list', {'MANAGER', 'TECHNICIAN', 'WAREHOUSE'}),
    ('tire-list', {'MANAGER', 'TECHNICIAN', 'WAREHOUSE'}),
    ('stock-movement-list', {'MANAGER', 'WAREHOUSE'}),
    ('service-list', {'MANAGER', 'TECHNICIAN', 'WAREHOUSE'}),
    ('supplier-list', {'MANAGER', 'TECHNICIAN', 'WAREHOUSE'}),
    ('sales-invoice-list', {'MANAGER', 'TECHNICIAN', 'WAREHOUSE'}),
    ('purchase-invoice-list', {'MANAGER', 'WAREHOUSE'}),
    ('sales-return-list', {'MANAGER'}),
    ('receipt-voucher-list', {'MANAGER'}),
    ('payment-voucher-list', {'MANAGER'}),
    ('customer-refund-voucher-list', {'MANAGER'}),
    ('dashboard-stats', {'MANAGER'}),
    ('sales-by-brand-report', {'MANAGER'}),
    ('profitability-report', {'MANAGER'}),
    ('inventory-value-report', {'MANAGER'}),
    ('sales-by-date-report', {'MANAGER'}),
]


@pytest.mark.django_db
@pytest.mark.parametrize('route,allowed', ROUTES)
@pytest.mark.parametrize('role', [None, *UserRole.values, 'SUPERUSER'])
def test_read_permission_matrix(api_client, route, allowed, role):
    if role:
        user = User.objects.create(username='matrix', role=role if role != 'SUPERUSER' else UserRole.WAREHOUSE,
                                   is_superuser=role == 'SUPERUSER')
        api_client.force_authenticate(user)
    response = api_client.get(reverse(route))
    expected = 401 if role is None else (200 if role in allowed or role == 'SUPERUSER' else 403)
    assert response.status_code == expected, (route, role, response.data)


@pytest.mark.django_db
@pytest.mark.parametrize('route,allowed', [
    ('user-list', {'MANAGER'}), ('service-list', {'MANAGER'}),
    ('supplier-list', {'MANAGER', 'WAREHOUSE'}),
    ('tire-list', {'MANAGER', 'WAREHOUSE'}),
    ('sales-invoice-list', {'MANAGER', 'TECHNICIAN'}),
    ('purchase-invoice-list', {'MANAGER', 'WAREHOUSE'}),
    ('sales-return-list', {'MANAGER'}), ('receipt-voucher-list', {'MANAGER'}),
    ('payment-voucher-list', {'MANAGER'}), ('customer-refund-voucher-list', {'MANAGER'}),
])
@pytest.mark.parametrize('role', [None, *UserRole.values, 'SUPERUSER'])
def test_write_permission_matrix(api_client, route, allowed, role):
    if role:
        user = User.objects.create(username='writer', role=role if role != 'SUPERUSER' else UserRole.WAREHOUSE,
                                   is_superuser=role == 'SUPERUSER')
        api_client.force_authenticate(user)
    response = api_client.post(reverse(route), {}, format='json')
    expected = 401 if role is None else (400 if role in allowed or role == 'SUPERUSER' else 403)
    assert response.status_code == expected, (route, role, response.data)
