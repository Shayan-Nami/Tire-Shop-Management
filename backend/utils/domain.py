from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import DecimalValidator
from rest_framework.exceptions import ValidationError


class DomainValidationError(ValidationError):
    pass


class StockConflict(DomainValidationError):
    pass


MONEY_QUANTIZER = Decimal('0.01')


def validate_money(value: object) -> Decimal:
    try:
        if value is None or isinstance(value, bool):
            raise ValueError('invalid money value')
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise ValueError('non-finite decimal')
        DecimalValidator(max_digits=14, decimal_places=2)(amount.normalize())
        quantized = amount.quantize(MONEY_QUANTIZER)
    except (InvalidOperation, TypeError, ValueError, DjangoValidationError) as exc:
        raise DomainValidationError('مبلغ وارد شده نامعتبر است؛ حداکثر دو رقم اعشار مجاز است.') from exc
    return Decimal('0.00') if quantized == 0 else quantized


def validate_quantity(value: object) -> int:
    try:
        number = Decimal(str(value))
        if isinstance(value, bool) or not number.is_finite() or number != number.to_integral_value():
            raise ValueError('not an integer')
        return int(number)
    except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
        raise DomainValidationError('تعداد باید یک عدد صحیح باشد.') from exc
