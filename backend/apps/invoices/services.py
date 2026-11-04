from __future__ import annotations
from typing import Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.customers.models import Customer, Vehicle
    from apps.suppliers.models import Supplier
    from apps.invoices.models import SalesInvoice, PurchaseInvoice, SalesReturn

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.db import transaction, models, IntegrityError
from django.utils import timezone
from utils.domain import DomainValidationError as ValidationError, validate_money, validate_quantity
from .models import (
    SalesInvoice, SalesInvoiceTireItem, SalesInvoiceServiceItem,
    PurchaseInvoice, PurchaseInvoiceTireItem, SalesReturn, SalesReturnItem,
    InvoiceStatus, PaymentStatus, InvoiceSequence
)
from apps.catalog.models import Tire, StockMovement, StockMovementType
from apps.catalog.services import record_stock_movements
from apps.finance.services import create_receipt_voucher_service
from utils.jalali import get_jalali_year


def _validate_invoice_total(invoice: SalesInvoice | PurchaseInvoice) -> None:
    field = invoice._meta.get_field('total_amount')
    maximum = Decimal(10) ** (field.max_digits - field.decimal_places) - Decimal(1).scaleb(-field.decimal_places)
    amount = invoice.total_amount
    if not amount.is_finite() or not Decimal('0.00') <= amount <= maximum:
        raise ValidationError({
            'total_amount': f'مبلغ کل فاکتور باید بین صفر و {maximum:,.2f} باشد.'
        })


@transaction.atomic
def generate_next_invoice_number(doc_type: str, dt: datetime | None=None) -> str:
    """
    تولید اتمیک و بدون تکرار شماره فاکتور پیوسته (Gapless Sequential Numbering)
    بر اساس (doc_type, سال شمسی) با قفل select_for_update روی ردیف شمارنده
    فرمت: S-1405-00001 (فروش) و P-1405-00001 (خرید)
    """
    prefix = 'S' if doc_type == 'SALES' else 'P'
    year = get_jalali_year(dt)

    seq = InvoiceSequence.objects.filter(doc_type=doc_type, year=year).select_for_update().first()
    if seq is None:
        try:
            with transaction.atomic():
                InvoiceSequence.objects.create(doc_type=doc_type, year=year, last_number=0)
        except IntegrityError:
            pass
        seq = InvoiceSequence.objects.select_for_update().get(doc_type=doc_type, year=year)

    seq.last_number += 1
    seq.save(update_fields=['last_number'])

    return f"{prefix}-{year}-{seq.last_number:05d}"


@transaction.atomic
def create_sales_invoice_service(customer: Customer, vehicle: Vehicle | None,
                                 tire_items_data: list[dict[str, Any]], service_items_data: list[dict[str, Any]],
                                 discount_amount: Decimal | int = 0, discount_percent: Decimal | int = 0,
                                 status: str = InvoiceStatus.CONFIRMED, payment_status: str | None = None,
                                 payment_method: str = 'کارتخوان / نقدی', reference_number: str = '',
                                 notes: str = '', created_by: User | None = None) -> SalesInvoice:
    """
    سرویس ایجاد فاکتور فروش همراه با کسر امن و قفل ردیفی موجودی انبار در تراکنش اتمیک
    """
    if vehicle is not None and vehicle.customer_id != customer.pk:
        raise ValidationError({'vehicle': 'خودروی انتخاب‌شده متعلق به این مشتری نیست.'})
    if status not in (InvoiceStatus.DRAFT, InvoiceStatus.CONFIRMED, InvoiceStatus.CANCELLED):
        raise ValidationError({'status': 'وضعیت فاکتور نامعتبر است.'})
    if payment_status is not None and payment_status not in PaymentStatus.values:
        raise ValidationError({'payment_status': 'وضعیت پرداخت نامعتبر است.'})
    if not tire_items_data and not service_items_data:
        raise ValidationError("ثبت حداقل یک قلم تایر یا یک خدمت برای صدور فاکتور فروش الزامی است.")

    tire_ids = [item['tire'].pk for item in tire_items_data if 'tire' in item]
    if len(tire_ids) != len(set(tire_ids)):
        raise ValidationError("تایر تکراری در اقلام فاکتور یافت شد. لطفاً تعداد را تجمیع نمایید.")

    service_ids = [item['service'].pk for item in service_items_data if 'service' in item]
    if len(service_ids) != len(set(service_ids)):
        raise ValidationError("خدمت تکراری در اقلام فاکتور یافت شد. لطفاً تعداد را تجمیع نمایید.")

    try:
        discount_amount = validate_money(discount_amount if discount_amount is not None else 0)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("مبلغ تخفیف وارد شده نامعتبر است.")

    try:
        discount_percent = validate_money(discount_percent if discount_percent is not None else 0)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("درصد تخفیف وارد شده نامعتبر است.")

    if discount_percent < Decimal('0.00') or discount_percent > Decimal('100.00'):
        raise ValidationError("درصد تخفیف باید عددی بین ۰ تا ۱۰۰ باشد.")

    if discount_amount < Decimal('0.00'):
        raise ValidationError("مبلغ تخفیف نمی‌تواند منفی باشد.")

    if discount_amount > 0 and discount_percent > 0:
        raise ValidationError("امکان اعمال هم‌زمان تخفیف مبلغی و درصدی وجود ندارد.")

    if payment_status == PaymentStatus.PARTIAL:
        raise ValidationError("امکان ثبت مستقیم فاکتور در وضعیت نیمه‌پرداخت در بدو صدور وجود ندارد. فاکتور باید ابتدا پرداخت‌نشده یا تسویه‌شده ثبت شود.")

    if status == InvoiceStatus.CANCELLED:
        raise ValidationError("امکان صدور فاکتور در وضعیت لغو شده وجود ندارد.")

    init_payment_status = payment_status or PaymentStatus.UNPAID
    inv_number = generate_next_invoice_number('SALES')
    invoice = SalesInvoice.objects.create(
        invoice_number=inv_number,
        customer=customer,
        vehicle=vehicle,
        status=status,
        payment_status=init_payment_status,
        discount_amount=discount_amount,
        discount_percent=discount_percent,
        notes=notes,
        created_by=created_by
    )

    # Read prices only after all tire locks are held, in the stock ledger's lock order.
    locked_tires = {
        tire.pk: tire
        for tire in Tire.objects.select_for_update().filter(pk__in=tire_ids).order_by('pk')
    }
    if len(locked_tires) != len(tire_ids):
        raise ValidationError("یک یا چند تایر یافت نشد.")

    subtotal = Decimal('0.00')
    movements_data = []

    # ۱. پردازش اقلام تایر و ایجاد رکوردهای فاکتور
    for item in tire_items_data:
        tire_obj = locked_tires[item['tire'].pk]
        try:
            qty = validate_quantity(item['quantity'])
        except (TypeError, ValueError):
            raise ValidationError("تعداد تایر وارد شده نامعتبر است.")
        if qty <= 0:
            raise ValidationError("تعداد تایر باید بزرگتر از صفر باشد.")

        unit_p_val = item.get('unit_price')
        try:
            unit_price = validate_money(unit_p_val) if unit_p_val is not None else tire_obj.sale_price
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("قیمت واحد تایر نامعتبر است.")
        if unit_price < Decimal('0.00'):
            raise ValidationError("قیمت واحد تایر نمی‌تواند منفی باشد.")

        try:
            unit_cost = Decimal(str(tire_obj.purchase_price))
        except (InvalidOperation, TypeError, ValueError):
            unit_cost = Decimal('0.00')
        if unit_cost < Decimal('0.00'):
            raise ValidationError("بهای تمام‌شده واحد نمی‌تواند منفی باشد.")

        SalesInvoiceTireItem.objects.create(
            sales_invoice=invoice,
            tire=tire_obj,
            quantity=qty,
            unit_price=unit_price,
            unit_cost=unit_cost
        )
        subtotal += qty * unit_price

        if invoice.status == InvoiceStatus.CONFIRMED:
            movements_data.append({
                'tire_id': tire_obj.pk,
                'quantity_delta': -qty,
                'movement_type': StockMovementType.SALE,
                'sales_invoice': invoice,
                'unit_cost': unit_cost,
                'description': f"فروش کالا طی فاکتور فروش #{invoice.sales_invoice_id}"
            })

    # کسر موجودی و ثبت گردش انبار به ترتیب صعودی شناسه‌ها
    if movements_data:
        record_stock_movements(movements_data, user=created_by)

    # ۲. پردازش اقلام خدمات
    for s_item in service_items_data:
        service_obj = s_item['service']
        try:
            qty = validate_quantity(s_item.get('quantity', 1))
        except (TypeError, ValueError):
            raise ValidationError("تعداد خدمت وارد شده نامعتبر است.")
        if qty <= 0:
            raise ValidationError("تعداد خدمت باید بزرگتر از صفر باشد.")

        unit_p_val = s_item.get('unit_price')
        try:
            unit_price = validate_money(unit_p_val) if unit_p_val is not None else service_obj.price
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("قیمت واحد خدمت نامعتبر است.")
        if unit_price < Decimal('0.00'):
            raise ValidationError("قیمت واحد خدمت نمی‌تواند منفی باشد.")

        SalesInvoiceServiceItem.objects.create(
            sales_invoice=invoice,
            service=service_obj,
            quantity=qty,
            unit_price=unit_price
        )
        subtotal += qty * unit_price

    # ۳. اعمال تخفیف و محاسبه مبلغ کل نهایی
    if discount_amount > subtotal:
        raise ValidationError(f"مبلغ تخفیف ({discount_amount:,.0f}) نمی‌تواند از جمع کل اقلام فاکتور ({subtotal:,.0f}) بیشتر باشد.")

    total = subtotal
    if discount_percent > 0:
        discount_val = (subtotal * discount_percent) / Decimal('100.0')
        total -= discount_val
    elif discount_amount > 0:
        total -= discount_amount

    invoice.total_amount = max(total, Decimal('0.00'))
    _validate_invoice_total(invoice)
    if payment_status is not None:
        invoice.payment_status = payment_status
    elif invoice.total_amount == Decimal('0.00'):
        invoice.payment_status = PaymentStatus.PAID
    else:
        invoice.payment_status = PaymentStatus.UNPAID
    invoice.save(update_fields=['total_amount', 'payment_status'])

    # صدور خودکار سند دریافت وجه برای فاکتورهای نقدی / تسویه‌شده هم‌زمان با صدور فاکتور
    if init_payment_status == PaymentStatus.PAID and invoice.total_amount > Decimal('0.00'):
        invoice.refresh_from_db(fields=['total_amount'])
        create_receipt_voucher_service(
            sales_invoice=invoice,
            amount=invoice.total_amount,
            payment_method=payment_method or 'کارتخوان / نقدی',
            notes=notes or 'تسویه نقدی/پوز هم‌زمان با صدور فاکتور',
            user=created_by,
            reference_number=reference_number or ''
        )
        invoice.refresh_from_db()

    return invoice

@transaction.atomic
def cancel_sales_invoice_service(invoice: SalesInvoice | int, user: User | None=None) -> SalesInvoice:
    """
    سرویس لغو فاکتور فروش و بازگرداندن اقلام کسر شده به موجودی انبار از طریق دفتر گردش انبار
    """
    invoice_id = invoice.pk if hasattr(invoice, 'pk') else int(invoice)
    locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice_id)

    if locked_invoice.status == InvoiceStatus.CANCELLED:
        raise ValidationError("این فاکتور قبلاً لغو شده است.")

    if locked_invoice.returns.exists():
        raise ValidationError("امکان لغو فاکتوری که برای آن سند مرجوعی ثبت شده وجود ندارد. ابتدا وضعیت مرجوعی‌ها را بررسی نمایید.")

    if locked_invoice.receipts.filter(is_cancelled=False).exists():
        raise ValidationError("امکان لغو فاکتوری که برای آن سند دریافت وجه ثبت شده وجود ندارد. ابتدا اسناد دریافت وجه را بررسی یا حذف نمایید.")

    # اگر فاکتور تایید شده بود، تایرها به انبار بازگردانده شده و سند گردش SALE_CANCEL ثبت می‌شود
    if locked_invoice.status == InvoiceStatus.CONFIRMED and locked_invoice.tire_items.exists():
        movements_data = [
            {
                'tire_id': item.tire_id,
                'quantity_delta': item.quantity,
                'movement_type': StockMovementType.SALE_CANCEL,
                'sales_invoice': locked_invoice,
                'unit_cost': item.unit_cost,
                'description': f"لغو فاکتور فروش #{locked_invoice.sales_invoice_id}"
            }
            for item in locked_invoice.tire_items.all()
        ]
        record_stock_movements(movements_data, user=user)

    locked_invoice.status = InvoiceStatus.CANCELLED
    locked_invoice.save(update_fields=['status'])
    return locked_invoice

@transaction.atomic
def confirm_sales_invoice_service(invoice: SalesInvoice | int, user: User | None=None) -> SalesInvoice:
    """
    سرویس تایید فاکتور فروش در وضعیت پیش‌نویس (DRAFT)، کسر اتمیک اقلام از انبار
    و تغییر وضعیت به CONFIRMED
    """
    invoice_id = invoice.pk if hasattr(invoice, 'pk') else int(invoice)
    locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice_id)

    if locked_invoice.status != InvoiceStatus.DRAFT:
        raise ValidationError("تنها فاکتورهای در وضعیت پیشنویس (DRAFT) قابلیت تایید و نهاییسازی دارند.")

    items = list(locked_invoice.tire_items.all())
    locked_tires = {
        tire.pk: tire
        for tire in Tire.objects.select_for_update().filter(
            pk__in=[item.tire_id for item in items]
        ).order_by('pk')
    }
    # A draft does not consume stock; finalize cost at the actual stock-out time.
    for item in items:
        item.unit_cost = locked_tires[item.tire_id].purchase_price
    if items:
        SalesInvoiceTireItem.objects.bulk_update(items, ['unit_cost'])

    movements_data = [
        {
            'tire_id': item.tire_id,
            'quantity_delta': -item.quantity,
            'movement_type': StockMovementType.SALE,
            'sales_invoice': locked_invoice,
            'unit_cost': item.unit_cost,
            'description': f"تایید و خروج کالای فاکتور فروش #{locked_invoice.sales_invoice_id}"
        }
        for item in items
    ]
    if movements_data:
        record_stock_movements(movements_data, user=user)

    locked_invoice.status = InvoiceStatus.CONFIRMED
    locked_invoice.save(update_fields=['status', 'updated_at'])
    return locked_invoice

@transaction.atomic
def create_purchase_invoice_service(supplier: Supplier, tire_items_data: list[dict[str, Any]], created_by: User | None=None) -> PurchaseInvoice:
    """
    سرویس ثبت فاکتور خرید از تأمین‌کننده، افزایش موجودی انبار و به‌روزرسانی قیمت خرید تایرها
    از طریق دفتر گردش انبار
    """
    if not tire_items_data:
        raise ValidationError("ثبت حداقل یک قلم تایر برای فاکتور خرید الزامی است.")

    tire_ids = [item['tire'].pk for item in tire_items_data if 'tire' in item]
    if len(tire_ids) != len(set(tire_ids)):
        raise ValidationError("تایر تکراری در اقلام فاکتور خرید یافت شد. لطفاً تعداد را در یک ردیف تجمیع نمایید.")

    inv_number = generate_next_invoice_number('PURCHASE')
    invoice = PurchaseInvoice.objects.create(
        invoice_number=inv_number,
        supplier=supplier,
        created_by=created_by
    )

    locked_tires = {
        tire.pk: tire
        for tire in Tire.objects.select_for_update().filter(pk__in=tire_ids).order_by('pk')
    }
    if len(locked_tires) != len(tire_ids):
        raise ValidationError("یک یا چند تایر یافت نشد.")

    total = Decimal('0.00')
    movements_data = []

    for item in tire_items_data:
        tire_obj = locked_tires[item['tire'].pk]
        try:
            qty = validate_quantity(item['quantity'])
        except (TypeError, ValueError):
            raise ValidationError("تعداد قلم خرید نامعتبر است.")
        if qty <= 0:
            raise ValidationError("تعداد قلم خرید باید مثبت باشد.")

        unit_c_val = item.get('unit_cost')
        try:
            unit_cost = validate_money(unit_c_val) if unit_c_val is not None else tire_obj.purchase_price
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("بهای خرید واحد نامعتبر است.")
        if unit_cost < Decimal('0.00'):
            raise ValidationError("بهای خرید واحد نمی‌تواند منفی باشد.")

        PurchaseInvoiceTireItem.objects.create(
            purchase_invoice=invoice,
            tire=tire_obj,
            quantity=qty,
            unit_cost=unit_cost,
            previous_purchase_price=tire_obj.purchase_price,
        )
        total += qty * unit_cost

        movements_data.append({
            'tire_id': tire_obj.pk,
            'quantity_delta': qty,
            'movement_type': StockMovementType.PURCHASE,
            'purchase_invoice': invoice,
            'unit_cost': unit_cost,
            'new_purchase_price': unit_cost,  # به‌روزرسانی قیمت خرید تایر به آخرین نرخ خرید
            'description': f"ورود خرید طی فاکتور #{invoice.purchase_invoice_id}"
        })

    record_stock_movements(movements_data, user=created_by)

    invoice.total_amount = total
    _validate_invoice_total(invoice)
    if total == Decimal('0.00'):
        invoice.payment_status = PaymentStatus.PAID
        invoice.save(update_fields=['total_amount', 'payment_status'])
    else:
        invoice.save(update_fields=['total_amount'])
    return invoice

@transaction.atomic
def cancel_purchase_invoice_service(invoice: PurchaseInvoice | int, user: User | None=None) -> PurchaseInvoice:
    """
    سرویس لغو فاکتور خرید، کسر موجودی انبار از طریق گردش PURCHASE_CANCEL
    و بازگرداندن هوشمند نرخ خرید تایر (purchase_price) به آخرین نرخ خرید قبلی
    """
    invoice_id = invoice.pk if hasattr(invoice, 'pk') else int(invoice)
    locked_invoice = PurchaseInvoice.objects.select_for_update().get(pk=invoice_id)

    if locked_invoice.status == InvoiceStatus.CANCELLED:
        raise ValidationError("این فاکتور خرید قبلاً لغو شده است.")

    if locked_invoice.payments.filter(is_cancelled=False).exists():
        raise ValidationError("امکان لغو فاکتوری که برای آن سند پرداخت وجه ثبت شده وجود ندارد. ابتدا اسناد پرداخت را بررسی یا باطل نمایید.")

    items = list(locked_invoice.tire_items.all())
    locked_tires = {
        tire.pk: tire
        for tire in Tire.objects.select_for_update().filter(
            pk__in=[item.tire_id for item in items]
        ).order_by('pk')
    }
    if items:
        movements_data = [
            {
                'tire_id': item.tire_id,
                'quantity_delta': -item.quantity,  # کسر از انبار
                'movement_type': StockMovementType.PURCHASE_CANCEL,
                'purchase_invoice': locked_invoice,
                'unit_cost': item.unit_cost,
                'description': f"لغو فاکتور خرید #{locked_invoice.purchase_invoice_id}"
            }
            for item in items
        ]
        # در صورت ناکافی بودن موجودی انبار، record_stock_movements خطای فارسی صادر می‌کند
        record_stock_movements(movements_data, user=user)

        # بازگرداندن purchase_price در صورتی که این فاکتور آخرین خرید تایر بوده باشد
        for item in items:
            tire = locked_tires[item.tire_id]
            purchase_movement = StockMovement.objects.get(
                tire=tire, movement_type=StockMovementType.PURCHASE,
                purchase_invoice=locked_invoice,
            )
            has_later_purchase = StockMovement.objects.filter(
                tire=tire,
                movement_type=StockMovementType.PURCHASE,
                movement_id__gt=purchase_movement.pk
            ).exclude(
                purchase_invoice=locked_invoice
            ).exclude(
                purchase_invoice__status=InvoiceStatus.CANCELLED
            ).exists()
            if not has_later_purchase:
                prev_purchase = StockMovement.objects.filter(
                    tire=tire,
                    movement_type__in=[StockMovementType.PURCHASE, StockMovementType.INITIAL_STOCK],
                ).exclude(
                    purchase_invoice=locked_invoice
                ).exclude(
                    purchase_invoice__status=InvoiceStatus.CANCELLED
                ).order_by('-movement_id').first()
                if prev_purchase and prev_purchase.unit_cost is not None:
                    restored_price = prev_purchase.unit_cost
                else:
                    # Include cancelled purchases: the first snapshot is the catalog
                    # baseline, even when intermediate purchases were cancelled first.
                    first_purchase = StockMovement.objects.filter(
                        tire=tire, movement_type=StockMovementType.PURCHASE,
                    ).order_by('movement_id').first()
                    first_item = PurchaseInvoiceTireItem.objects.get(
                        tire=tire, purchase_invoice_id=first_purchase.purchase_invoice_id,
                    )
                    restored_price = first_item.previous_purchase_price
                    if restored_price is None:
                        raise ValidationError(
                            "قیمت خرید پیش از اولین خرید در سوابق قدیمی موجود نیست؛ ابتدا سابقه قیمت را تکمیل نمایید."
                        )
                tire.purchase_price = restored_price
                tire.save(update_fields=['purchase_price'])


    locked_invoice.status = InvoiceStatus.CANCELLED
    locked_invoice.save(update_fields=['status'])
    return locked_invoice

@transaction.atomic
def create_sales_return_service(invoice: SalesInvoice | int, items_data: list[dict], reason: str, return_date: datetime | None=None, user: User | None=None, auto_refund: bool = False) -> SalesReturn:
    """
    سرویس ثبت سند مرجوعی فروش (SalesReturn)، افزایش موجودی انبار و ثبت دقیق گردش SALE_RETURN.
    
    قواعد مالی و انبارداری:
    ۱. فاکتور قفل شده (select_for_update) و وضعیت آن نباید لغو شده باشد.
    ۲. سهم تخفیف فاکتور (ریالی یا درصدی) بر اساس نسبت تخفیف کل فاکتور به نسبت اقلام اعمال و تا ۲ رقم اعشار با ROUND_HALF_UP گرد می‌شود.
    ۳. کنترل سقف مجاز مرجوعی بر اساس مانده مرجوع‌نشده هر قلم تایر.
    ۴. جلوگیری از انباشت خطای رند: اگر مرجوعی شامل کل مانده قلم باشد، تفاضل سهم کل از استردادهای قبلی درج می‌شود.
    ۵. درج گردش انبار با unit_cost واقعی اسنپ‌شات‌شده همان قلم در زمان فروش.
    """
    invoice_id = invoice.pk if hasattr(invoice, 'pk') else int(invoice)
    locked_invoice = SalesInvoice.objects.select_for_update().get(pk=invoice_id)

    if locked_invoice.status == InvoiceStatus.CANCELLED:
        raise ValidationError("امکان ثبت مرجوعی برای فاکتور لغو شده وجود ندارد.")

    if locked_invoice.status == InvoiceStatus.DRAFT:
        raise ValidationError("امکان ثبت مرجوعی برای فاکتور در وضعیت پیش‌نویس وجود ندارد. ابتدا فاکتور را تایید نمایید.")

    if locked_invoice.status != InvoiceStatus.CONFIRMED:
        raise ValidationError("امکان ثبت مرجوعی فقط برای فاکتورهای تایید شده (CONFIRMED) وجود دارد.")

    if not reason or not reason.strip():
        raise ValidationError("ثبت علت / شرح مرجوعی الزامی است.")

    if not items_data:
        raise ValidationError("ثبت حداقل یک قلم تایر جهت مرجوعی الزامی است.")

    item_ids = [item.get('sales_invoice_tire_item_id') or item.get('tire_item_id') for item in items_data]
    if len(item_ids) != len(set(item_ids)):
        raise ValidationError("قلم تایر تکراری در اقلام مرجوعی یافت شد. لطفاً تعداد را تجمیع نمایید.")

    if return_date:
        if return_date > timezone.now():
            raise ValidationError("تاریخ مرجوعی نمی‌تواند در آینده باشد.")
    else:
        return_date = timezone.now()

    # محاسبه ضریب تخفیف برای لحاظ کردن سهم تخفیف در مبلغ استرداد
    invoice_items = {item.pk: item for item in locked_invoice.tire_items.select_related('tire')}
    subtotal = sum((item.quantity * item.unit_price for item in invoice_items.values()), Decimal('0.00'))
    subtotal += locked_invoice.service_items.aggregate(
        total=models.Sum(models.F('quantity') * models.F('unit_price'))
    )['total'] or Decimal('0.00')
    past_returns = {row['sales_invoice_tire_item_id']: row for row in
        SalesReturnItem.objects.filter(sales_invoice_tire_item_id__in=invoice_items).values(
            'sales_invoice_tire_item_id'
        ).annotate(total_qty=models.Sum('quantity'), total_refund=models.Sum('refund_amount'))}

    if locked_invoice.discount_percent > 0:
        discount_factor = Decimal('1.00') - (locked_invoice.discount_percent / Decimal('100.00'))
    elif locked_invoice.discount_amount > 0 and subtotal > Decimal('0.00'):
        discount_factor = Decimal('1.00') - (locked_invoice.discount_amount / subtotal)
    else:
        discount_factor = Decimal('1.00')

    discount_factor = max(Decimal('0.00'), discount_factor)

    sales_return = SalesReturn.objects.create(
        sales_invoice=locked_invoice,
        return_date=return_date,
        reason=reason.strip(),
        created_by=user,
        total_refund_amount=Decimal('0.00')
    )

    total_refund = Decimal('0.00')
    movements_data = []

    for item_data in items_data:
        tire_item_id = item_data.get('sales_invoice_tire_item_id') or item_data.get('tire_item_id')
        if not tire_item_id:
            raise ValidationError("شناسه قلم فاکتور تایر (sales_invoice_tire_item_id) الزامی است.")

        tire_item = invoice_items.get(tire_item_id)
        if not tire_item:
            raise ValidationError(f"قلم تایر با شناسه {tire_item_id} در فاکتور فروش #{locked_invoice.sales_invoice_id} یافت نشد.")

        try:
            qty = validate_quantity(item_data.get('quantity', 0))
        except (TypeError, ValueError):
            raise ValidationError("تعداد قلم مرجوعی نامعتبر است.")
        if qty <= 0:
            raise ValidationError("تعداد قلم مرجوعی باید بزرگتر از صفر باشد.")

        # واکشی مجموع تعداد و مبالغ استرداد قبلی این قلم درون همین تراکنش
        past_returns_aggr = past_returns.get(tire_item.pk, {})
        already_returned_qty = past_returns_aggr.get('total_qty') or 0
        already_refunded_amount = past_returns_aggr.get('total_refund') or Decimal('0.00')

        remaining_qty = tire_item.quantity - already_returned_qty
        if qty > remaining_qty:
            raise ValidationError(
                f"تعداد مرجوعی تایر '{tire_item.tire.tire_name}' ({qty} حلقه) بیشتر از سقف مجاز قابل مرجوعی ({remaining_qty} حلقه) است."
            )

        # سهم کل خالص این قلم از فاکتور پس از اعمال ضریب تخفیف
        item_total_gross = Decimal(str(tire_item.quantity)) * tire_item.unit_price
        item_total_net = (item_total_gross * discount_factor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # اگر تعداد مرجوعی برابر تمام مانده این قلم باشد، جهت جلوگیری از انباشت خطای رند،
        # مبلغ استرداد برابر مانده سهم خالص قلم قرار می‌گیرد.
        if qty == remaining_qty:
            item_refund = max(item_total_net - already_refunded_amount, Decimal('0.00'))
        else:
            raw_refund = Decimal(str(qty)) * tire_item.unit_price * discount_factor
            item_refund = max(raw_refund.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), Decimal('0.00'))

        total_refund += item_refund

        SalesReturnItem.objects.create(
            sales_return=sales_return,
            sales_invoice_tire_item=tire_item,
            tire=tire_item.tire,
            quantity=qty,
            unit_price=tire_item.unit_price,
            unit_cost=tire_item.unit_cost,
            refund_amount=item_refund
        )


        movements_data.append({
            'tire_id': tire_item.tire_id,
            'quantity_delta': qty,  # ورود به انبار (مثبت)
            'movement_type': StockMovementType.SALE_RETURN,
            'sales_invoice': locked_invoice,
            'sales_return': sales_return,
            'unit_cost': tire_item.unit_cost,  # بهای تمام‌شده اسنپ‌شات‌شده قلم اصلی
            'description': f"مرجوعی از فاکتور فروش #{locked_invoice.sales_invoice_id} - {reason.strip()}"
        })

    # ثبت گردش‌های انبار به صورت اتمیک با قفل صعودی
    record_stock_movements(movements_data, user=user)

    sales_return.total_refund_amount = total_refund
    sales_return.save(update_fields=['total_refund_amount'])

    from apps.finance.services import sync_sales_invoice_payment_status
    sync_sales_invoice_payment_status(locked_invoice)

    if auto_refund and locked_invoice.excess_amount > Decimal('0.00'):
        from apps.finance.services import create_customer_refund_voucher_service
        create_customer_refund_voucher_service(
            sales_invoice=locked_invoice,
            amount=locked_invoice.excess_amount,
            sales_return=sales_return,
            payment_method='کارتخوان / نقدی',
            notes=f'استرداد وجه بابت مرجوعی شماره {sales_return.sales_return_id}',
            user=user
        )

    return sales_return

