from io import StringIO
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import UserRole
from apps.catalog.management.commands import seed_tire_shop


User = get_user_model()
DEMO_PASSWORDS = {
    'admin': 'admin123',
    'technician': 'tech123',
    'warehouse': 'warehouse123',
}


@pytest.mark.parametrize('debug,opt_in', [(False, False), (False, True), (True, False)])
def test_seed_refuses_before_any_database_access(settings, monkeypatch, debug, opt_in):
    settings.DEBUG = debug
    settings.ALLOW_DEMO_SEED = opt_in
    create_user = Mock(side_effect=AssertionError('Seed must not access the database'))
    monkeypatch.setattr(User.objects, 'get_or_create', create_user)
    with pytest.raises(CommandError, match='DEBUG=True and ALLOW_DEMO_SEED=True'):
        call_command('seed_tire_shop', stdout=StringIO())
    create_user.assert_not_called()


@pytest.fixture
def mock_business_seed(monkeypatch):
    # Exercise the entire command while isolating account safety from business fixtures.
    record = Mock(stock_quantity=0)
    record.sales_invoices.exists.return_value = True
    for model in [
        seed_tire_shop.Brand, seed_tire_shop.Size, seed_tire_shop.Tire,
        seed_tire_shop.Service, seed_tire_shop.Supplier,
        seed_tire_shop.Customer, seed_tire_shop.Vehicle,
    ]:
        monkeypatch.setattr(model.objects, 'get_or_create', Mock(return_value=(record, False)))
    invoice = Mock()
    monkeypatch.setattr(seed_tire_shop, 'create_sales_invoice_service', invoice)
    stock = Mock()
    monkeypatch.setattr(seed_tire_shop.StockMovement.objects, 'create', stock)
    return invoice, stock


@pytest.mark.django_db
@pytest.mark.parametrize('preexisting', [False, True])
def test_seed_twice_preserves_passwords(settings, monkeypatch, mock_business_seed, preexisting):
    settings.DEBUG = True
    settings.ALLOW_DEMO_SEED = True
    if preexisting:
        for username in DEMO_PASSWORDS:
            User.objects.create_user(
                username=username, password=f'Existing-{username}!8274',
                role=UserRole.WAREHOUSE, is_staff=False, is_superuser=False,
            )
    initial_hashes = dict(User.objects.filter(username__in=DEMO_PASSWORDS).values_list('username', 'password'))
    original_set_password = User.set_password
    hashed_users = []

    def track_password_hashing(user, password):
        hashed_users.append(user.username)
        original_set_password(user, password)

    monkeypatch.setattr(User, 'set_password', track_password_hashing)
    output = StringIO()
    call_command('seed_tire_shop', stdout=output)
    assert sorted(hashed_users) == ([] if preexisting else sorted(DEMO_PASSWORDS))
    assert User.objects.filter(username__in=DEMO_PASSWORDS).count() == 3
    for user in User.objects.filter(username__in=DEMO_PASSWORDS):
        if preexisting:
            assert user.password == initial_hashes[user.username]
            assert user.role == UserRole.WAREHOUSE
            assert not user.is_staff
            assert not user.is_superuser
        else:
            assert user.check_password(DEMO_PASSWORDS[user.username])
            # A real password change between runs must not be overwritten by the seed.
            original_set_password(user, f'Changed-{user.username}!8274')
            user.save(update_fields=['password'])
    retained_hashes = dict(User.objects.filter(username__in=DEMO_PASSWORDS).values_list('username', 'password'))
    hashed_users.clear()

    call_command('seed_tire_shop', stdout=output)
    assert hashed_users == []
    assert dict(User.objects.filter(username__in=DEMO_PASSWORDS).values_list('username', 'password')) == retained_hashes
    for user in User.objects.filter(username__in=DEMO_PASSWORDS):
        prefix = 'Existing' if preexisting else 'Changed'
        assert user.check_password(f'{prefix}-{user.username}!8274')
    for password in DEMO_PASSWORDS.values():
        assert password not in output.getvalue()
    invoice, stock = mock_business_seed
    invoice.assert_not_called()
    stock.assert_not_called()
