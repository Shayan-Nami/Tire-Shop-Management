from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError
from .models import Tire, StockMovement, StockMovementType, StockProjectionRepair

@transaction.atomic
def record_stock_movements(movements_data: list[dict], user=None) -> list[StockMovement]:
    """
    سرویس مرکزی و جامع ثبت گروهی گردش‌های انبار.
    
    ویژگی‌های کلیدی:
    ۱. جلوگیری قطعی از Deadlock: شناسه‌ها استخراج شده و به ترتیب صعودی (order_by('pk')) قفل می‌شوند.
    ۲. ایمنی در همروندی (Concurrency Safety): با select_for_update ردیف‌های مربوطه قفل می‌شوند.
    ۳. کنترل موجودی منفی: پیش‌بینی مانده برای هر تایر انجام و در صورت کسری موجودی خطا صادر می‌شود.
    ۴. اتمیک بودن: تمام عملیات تغییر موجودی و درج در دفتر گردش در یک تراکنش انجام می‌شود.
    """
    if not movements_data:
        return []

    # ۱. استخراج و مرتب‌سازی صعودی شناسه‌های تایر جهت پیشگیری از بن‌بست همروندی (Deadlock)
    try:
        tire_ids = sorted(list({int(item['tire_id']) for item in movements_data}))
    except (TypeError, ValueError, KeyError):
        raise ValidationError("شناسه تایر در اطلاعات گردش انبار نامعتبر است.")

    # ۲. قفل ردیفی تایرها در تراکنش جاری به ترتیب صعودی PK
    locked_tires = {
        tire.pk: tire
        for tire in Tire.objects.select_for_update().filter(pk__in=tire_ids).order_by('pk')
    }

    # اعتبارسنجی وجود همه تایرها
    for tid in tire_ids:
        if tid not in locked_tires:
            raise ValidationError(f"تایر با شناسه {tid} یافت نشد.")

    # ۳. بررسی پیش‌بینی مانده برای جلوگیری از منفی شدن موجودی انبار
    projected_balances = {tid: locked_tires[tid].stock_quantity for tid in tire_ids}
    for item in movements_data:
        try:
            tid = int(item['tire_id'])
            delta = int(item['quantity_delta'])
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
    # ۴. اعمال تغییرات موجودی و درج رکوردهای گردش انبار
    for item in movements_data:
        tid = int(item['tire_id'])
        delta = int(item['quantity_delta'])
        if delta == 0:
            continue

        tire = locked_tires[tid]
        tire.stock_quantity += delta
        update_fields = ['stock_quantity']

        # به‌روزرسانی قیمت خرید در صورت ثبت فاکتور خرید (آخرین نرخ خرید)
        new_purchase_price = item.get('new_purchase_price')
        if new_purchase_price is not None:
            tire.purchase_price = Decimal(str(new_purchase_price))
            update_fields.append('purchase_price')

        tire.save(update_fields=update_fields)

        raw_unit_cost = item.get('unit_cost')
        unit_cost = Decimal(str(raw_unit_cost if raw_unit_cost is not None else tire.purchase_price))

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
    user=None,
    sales_invoice=None,
    purchase_invoice=None,
    sales_return=None,
    unit_cost=None,
    description: str = '',
    new_purchase_price=None
) -> StockMovement:
    """
    ثبت تکی گردش انبار برای یک تایر (فراخوانی سرویس مرکزی record_stock_movements در لایه زیرین)
    """
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
def adjust_tire_stock_service(tire: Tire, counted_quantity: int, reason: str, user=None) -> StockMovement:
    """
    سرویس اصلاح دستی و انبارگردانی تایر.
    ورودی: مقدار جدید شمارش‌شده توسط انباردار (counted_quantity).
    سیستم اختلاف را نسبت به موجودی جاری محاسبه و در قالب سند MANUAL_ADJUSTMENT ثبت می‌کند.
    """
    if counted_quantity < 0:
        raise ValidationError("موجودی شمارش‌شده نمی‌تواند منفی باشد.")
    if not reason or not reason.strip():
        raise ValidationError("ثبت علت / توضیحات اصلاح موجودی الزامی است.")

    # قفل کردن تایر جهت واکشی دقیق‌ترین موجودی در لحظه تراکنش
    locked_tire = Tire.objects.select_for_update().get(pk=tire.pk)
    delta = counted_quantity - locked_tire.stock_quantity

    if delta == 0:
        raise ValidationError("موجودی شمارش‌شده دقیقاً برابر با موجودی فعلی سیستم است و نیازی به تعدیل ندارد.")

    locked_tire.stock_quantity = counted_quantity
    locked_tire.save(update_fields=['stock_quantity'])

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
def repair_stock_projection_service(tire_id: int, reason: str, user):
    """Rebuild from verified ledger truth; this is not a physical stock adjustment."""
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
    tire.stock_quantity = ledger_stock
    tire.save(update_fields=['stock_quantity'])
    return repair
