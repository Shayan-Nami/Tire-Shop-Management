from decimal import Decimal
from io import StringIO
from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from apps.catalog.admin import StockMovementInline, TireAdmin
from apps.catalog.models import Brand, Size, StockMovement, StockMovementType, StockProjectionRepair, Tire
from apps.catalog.serializers import TireSerializer
from apps.catalog.services import (
    adjust_tire_stock_service, record_stock_movement, repair_stock_projection_service,
)


@pytest.fixture
def catalog_tire(db):
    tire = Tire.objects.create(
        tire_name='Original', brand=Brand.objects.create(brand_name='Audit'),
        size=Size.objects.create(size_name='205/55R16'), sale_price=Decimal('200.00'),
        purchase_price=Decimal('100.00'),
    )
    record_stock_movement(tire.pk, 10, StockMovementType.INITIAL_STOCK)
    tire.refresh_from_db()
    return tire


def ledger_balance(tire):
    return StockMovement.objects.filter(tire=tire).aggregate(total=Sum('quantity'))['total'] or 0


@pytest.mark.django_db
@pytest.mark.parametrize('admin_edit', [False, True])
def test_stale_metadata_save_preserves_stock_and_purchase_cost(catalog_tire, admin_edit):
    stale = Tire.objects.get(pk=catalog_tire.pk)
    record_stock_movement(
        stale.pk, 2, StockMovementType.PURCHASE,
        unit_cost=Decimal('150.00'), new_purchase_price=Decimal('150.00'),
    )
    if admin_edit:
        stale.tire_name = 'Renamed'
        TireAdmin(Tire, admin.site).save_model(
            None, stale, SimpleNamespace(changed_data=['tire_name']), change=True,
        )
    else:
        serializer = TireSerializer(stale, data={'tire_name': 'Renamed'}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    catalog_tire.refresh_from_db()
    assert catalog_tire.tire_name == 'Renamed'
    assert catalog_tire.stock_quantity == ledger_balance(catalog_tire) == 12
    assert catalog_tire.purchase_price == Decimal('150.00')
    assert stale.stock_quantity == 12


@pytest.mark.django_db
@pytest.mark.parametrize('payload', [
    {'stock_quantity': 999}, {'purchase_price': '1.00'}, {},
    {'tire_name': 'Renamed', 'purchase_price': '1.00', 'stock_quantity': 999},
])
def test_catalog_edits_cannot_write_stock_or_purchase_cost(catalog_tire, payload):
    serializer = TireSerializer(catalog_tire, data=payload, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    catalog_tire.refresh_from_db()
    assert catalog_tire.stock_quantity == 10
    assert catalog_tire.purchase_price == Decimal('100.00')
    assert StockMovement.objects.filter(tire=catalog_tire).count() == 1


@pytest.mark.django_db
def test_catalog_creation_accepts_initial_cost(catalog_tire):
    serializer = TireSerializer(data={
        'tire_name': 'New', 'brand': catalog_tire.brand_id, 'size': catalog_tire.size_id,
        'sale_price': '200.00', 'purchase_price': '75.00',
    })
    serializer.is_valid(raise_exception=True)
    tire = serializer.save()
    assert tire.purchase_price == Decimal('75.00')
    assert tire.stock_quantity == 0


@pytest.mark.django_db
def test_admin_ledger_and_repair_audit_are_immutable(catalog_tire):
    inline = StockMovementInline(Tire, admin.site)
    assert set(inline.readonly_fields) == {field.name for field in StockMovement._meta.fields}
    assert not inline.has_add_permission(None)
    assert not inline.has_change_permission(None)
    assert not inline.can_delete
    for model in (StockMovement, StockProjectionRepair):
        model_admin = admin.site._registry[model]
        assert not model_admin.has_add_permission(None)
        assert not model_admin.has_change_permission(None)
        assert not model_admin.has_delete_permission(None)
    tire_admin = TireAdmin(Tire, admin.site)
    assert 'purchase_price' in tire_admin.get_readonly_fields(None, catalog_tire)
    assert 'purchase_price' not in tire_admin.get_readonly_fields(None)


@pytest.mark.django_db
def test_recovery_rebuilds_only_projection_with_durable_audit(catalog_tire, manager_user):
    Tire.objects.filter(pk=catalog_tire.pk).update(stock_quantity=999)
    movements_before = list(StockMovement.objects.values())
    audit = repair_stock_projection_service(catalog_tire.pk, '  Investigation INC-42  ', manager_user)
    catalog_tire.refresh_from_db()
    assert catalog_tire.stock_quantity == ledger_balance(catalog_tire) == 10
    assert list(StockMovement.objects.values()) == movements_before
    assert audit.stock_before == 999 and audit.stock_after == 10
    assert audit.user == manager_user
    assert audit.reason == 'Investigation INC-42'
    assert audit.last_movement == catalog_tire.stock_movements.latest('movement_id')
    assert repair_stock_projection_service(catalog_tire.pk, 'Retry INC-42', manager_user) is None
    assert StockProjectionRepair.objects.count() == 1
    adjust_tire_stock_service(catalog_tire, 8, 'Physical count after recovery', manager_user)
    catalog_tire.refresh_from_db()
    assert catalog_tire.stock_quantity == ledger_balance(catalog_tire) == 8


@pytest.mark.django_db
@pytest.mark.parametrize('reason', ['', '   '])
def test_recovery_requires_reason(catalog_tire, manager_user, reason):
    with pytest.raises(ValidationError):
        repair_stock_projection_service(catalog_tire.pk, reason, manager_user)
    assert not StockProjectionRepair.objects.exists()


@pytest.mark.django_db
def test_recovery_requires_active_manager(catalog_tire, technician_user, manager_user):
    for actor in (None, technician_user):
        with pytest.raises(ValidationError):
            repair_stock_projection_service(catalog_tire.pk, 'INC-42', actor)
    manager_user.is_active = False
    manager_user.save(update_fields=['is_active'])
    with pytest.raises(ValidationError):
        repair_stock_projection_service(catalog_tire.pk, 'INC-42', manager_user)


@pytest.mark.django_db
def test_default_reconcile_is_read_only(catalog_tire):
    Tire.objects.filter(pk=catalog_tire.pk).update(stock_quantity=999)
    with pytest.raises(CommandError, match='مغایرت موجودی یافت شد'):
        call_command('reconcile_stock', stdout=StringIO())
    catalog_tire.refresh_from_db()
    assert catalog_tire.stock_quantity == 999
    assert not StockProjectionRepair.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('options', [
    {'repair': True}, {'repair': True, 'reason': 'INC-42'},
    {'repair': True, 'user': 'test_manager'}, {'reason': 'INC-42'},
    {'repair': True, 'reason': 'INC-42', 'user': 'test_tech'},
])
def test_reconcile_rejects_incomplete_or_unauthorized_options(catalog_tire, manager_user, technician_user, options):
    with pytest.raises(CommandError):
        call_command('reconcile_stock', stdout=StringIO(), **options)
    assert not StockProjectionRepair.objects.exists()


@pytest.mark.django_db
def test_reconcile_repairs_selected_tire_and_is_idempotent(catalog_tire, manager_user):
    Tire.objects.filter(pk=catalog_tire.pk).update(stock_quantity=999)
    options = dict(repair=True, reason='INC-42', user=manager_user.username, tire_ids=[catalog_tire.pk])
    call_command('reconcile_stock', stdout=StringIO(), **options)
    call_command('reconcile_stock', stdout=StringIO(), **options)
    call_command('reconcile_stock', stdout=StringIO())
    assert StockProjectionRepair.objects.count() == 1
    with pytest.raises(CommandError, match='Unknown tire IDs'):
        call_command('reconcile_stock', tire_ids=[999999], stdout=StringIO())


@pytest.mark.django_db
def test_batch_recovery_rolls_back_if_any_ledger_is_invalid(catalog_tire, manager_user):
    Tire.objects.filter(pk=catalog_tire.pk).update(stock_quantity=999)
    invalid_tire = Tire.objects.create(
        tire_name='Invalid ledger', brand=catalog_tire.brand, size=catalog_tire.size,
        sale_price=200, purchase_price=100,
    )
    StockMovement.objects.create(
        tire=invalid_tire, quantity=-1, movement_type=StockMovementType.SALE, balance_after=0,
    )
    with pytest.raises(CommandError, match='all repairs rolled back'):
        call_command('reconcile_stock', repair=True, reason='INC-42', user=manager_user.username, stdout=StringIO())
    catalog_tire.refresh_from_db()
    assert catalog_tire.stock_quantity == 999
    assert not StockProjectionRepair.objects.exists()
