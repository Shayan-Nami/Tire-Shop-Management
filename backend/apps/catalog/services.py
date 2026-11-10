from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.invoices.models import SalesInvoice, PurchaseInvoice, SalesReturn

from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, F
from utils.domain import DomainValidationError as ValidationError, StockConflict, validate_money, validate_quantity
from .models import Tire, StockMovement, StockMovementType, StockProjectionRepair

@transaction.atomic
def record_stock_movements(movements_data: list[dict], user: User | None=None) -> list[StockMovement]:
    if not movements_data:
        return []

    try:
        tire_ids = sorted(list({int(item['tire_id']) for item in movements_data}))
    except (TypeError, ValueError, KeyError):
        raise ValidationError("شناسه تایر در اطلاعات گردش انبار نامعتبر است.")

    locked_tires = {
        tire.pk: tire
        for tire in Tire.objects.select_for_update().filter(pk__in=tire_ids).order_by('pk')
    }

    for tid in tire_ids:
        if tid not in locked_tires:
            raise ValidationError(f"تایر با شناسه {tid} یافت نشد.")

    projected_balances = {tid: locked_tires[tid].stock_quantity for tid in tire_ids}
    for item in movements_data:
        try:
            tid = int(item['tire_id'])
            delta = validate_quantity(item['quantity_delta'])
        except (TypeError, ValueError, KeyError):
            raise ValidationError("مقادیر گردش انبار نامعتبر است.")
        projected_balances[tid] += delta
        if projected_balances[tid] < 0:
            tire_name = locked_tires[tid].tire_name
            current_qty = locked_tires[tid].stock_quantity
            raise ValidationError(
                f"موجودی تایر '{tire_name}' کافی نیست. موجودی فعلی: {current_qty}، درخواست: {abs(delta)}"
            )

    created_movements = []
    for item in movements_data:
        tid = int(item['tire_id'])
        delta = validate_quantity(item['quantity_delta'])
        if delta == 0:
            continue

        tire = locked_tires[tid]
        previous_stock = tire.stock_quantity
        updates = {'stock_quantity': F('stock_quantity') + delta}

        new_purchase_price = item.get('new_purchase_price')
        if new_purchase_price is not None:
            tire.purchase_price = validate_money(new_purchase_price)
            updates['purchase_price'] = tire.purchase_price

        updated = Tire.objects.filter(pk=tid, stock_quantity=previous_stock).update(**updates)
        if updated != 1:
            raise StockConflict('موجودی تغییر کرده است؛ عملیات را دوباره انجام دهید.')
        tire.stock_quantity = previous_stock + delta

        raw_unit_cost = item.get('unit_cost')
        unit_cost = validate_money(raw_unit_cost if raw_unit_cost is not None else tire.purchase_price)

        movement = StockMovement.objects.create(
            tire=tire,
            quantity=delta,
            movement_type=item['movement_type'],
            balance_after=tire.stock_quantity,
            sales_invoice=item.get('sales_invoice'),
            purchase_invoice=item.get('purchase_invoice'),
            sales_return=item.get('sales_return'),
            unit_cost=unit_cost,
            user=user or item.get('user'),
            description=item.get('description', '')
        )
        created_movements.append(movement)

    return created_movements

@transaction.atomic
def record_stock_movement(
    tire_id: int,
    quantity_delta: int,
    movement_type: str,
    user: User | None=None,
    sales_invoice: SalesInvoice | None=None,
    purchase_invoice: PurchaseInvoice | None=None,
    sales_return: SalesReturn | None=None,
    unit_cost: Decimal | None=None,
    description: str = '',
    new_purchase_price: Decimal | None=None
) -> StockMovement | None:
    movements = record_stock_movements(
        movements_data=[{
            'tire_id': tire_id,
            'quantity_delta': quantity_delta,
            'movement_type': movement_type,
            'sales_invoice': sales_invoice,
            'purchase_invoice': purchase_invoice,
            'sales_return': sales_return,
            'unit_cost': unit_cost,
            'description': description,
            'new_purchase_price': new_purchase_price
        }],
        user=user
    )
    return movements[0] if movements else None


@transaction.atomic
def adjust_tire_stock_service(tire: Tire, counted_quantity: int, reason: str, user: User | None=None) -> StockMovement:
    counted_quantity = validate_quantity(counted_quantity)
    if counted_quantity < 0:
        raise ValidationError("موجودی شمارش‌شده نمی‌تواند منفی باشد.")
    if not reason or not reason.strip():
        raise ValidationError("ثبت علت / توضیحات اصلاح موجودی الزامی است.")

    locked_tire = Tire.objects.select_for_update().get(pk=tire.pk)
    delta = counted_quantity - locked_tire.stock_quantity

    if delta == 0:
        raise ValidationError("موجودی شمارش‌شده دقیقاً برابر با موجودی فعلی سیستم است و نیازی به تعدیل ندارد.")

    updated = Tire.objects.filter(pk=locked_tire.pk, stock_quantity=locked_tire.stock_quantity).update(
        stock_quantity=counted_quantity
    )
    if updated != 1:
        raise StockConflict('موجودی تغییر کرده است؛ عملیات را دوباره انجام دهید.')
    locked_tire.stock_quantity = counted_quantity

    unit_cost = Decimal(str(locked_tire.purchase_price if locked_tire.purchase_price is not None else '0.00'))

    return StockMovement.objects.create(
        tire=locked_tire,
        quantity=delta,
        movement_type=StockMovementType.MANUAL_ADJUSTMENT,
        balance_after=locked_tire.stock_quantity,
        unit_cost=unit_cost,
        user=user,
        description=reason.strip()
    )


@transaction.atomic
def repair_stock_projection_service(tire_id: int, reason: str, user: User | None) -> StockProjectionRepair | None:
    if not reason or not reason.strip():
        raise ValidationError('A repair reason is required.')
    if not user or not user.is_active or not (user.is_superuser or user.role == 'MANAGER'):
        raise ValidationError('An active manager must authorize projection recovery.')

    tire = Tire.objects.select_for_update().get(pk=tire_id)
    movements = StockMovement.objects.filter(tire=tire)
    ledger_stock = movements.aggregate(total=Sum('quantity'))['total'] or 0
    if ledger_stock < 0:
        raise ValidationError('Ledger balance is negative; investigate ledger integrity before recovery.')
    if tire.stock_quantity == ledger_stock:
        return None

    repair = StockProjectionRepair.objects.create(
        tire=tire,
        stock_before=tire.stock_quantity,
        stock_after=ledger_stock,
        last_movement=movements.order_by('-movement_id').first(),
        user=user,
        reason=reason.strip(),
    )
    updated = Tire.objects.filter(pk=tire.pk, stock_quantity=tire.stock_quantity).update(stock_quantity=ledger_stock)
    if updated != 1:
        raise StockConflict('موجودی تغییر کرده است؛ عملیات را دوباره انجام دهید.')
    tire.stock_quantity = ledger_stock
    return repair
