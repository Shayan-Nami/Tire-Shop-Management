from __future__ import annotations

from typing import overload

from django.core.validators import RegexValidator

PERSIAN_ARABIC_DIGIT_MAP = str.maketrans({
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
})

phone_validator = RegexValidator(
    regex=r'^09\d{9}$',
    message='شماره موبایل باید با 09 شروع شده و ۱۱ رقم باشد.',
)

supplier_phone_validator = RegexValidator(
    regex=r'^0\d{9,10}$',
    message='شماره تلفن باید با 0 شروع شده و ۱۰ یا ۱۱ رقم عددی باشد.',
)

national_code_validator = RegexValidator(
    regex=r'^\d{10}$',
    message='کد ملی باید ۱۰ رقم عددی باشد.',
)


@overload
def normalize_digits(value: None) -> None: ...


@overload
def normalize_digits(value: object) -> str: ...


def normalize_digits(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value).translate(PERSIAN_ARABIC_DIGIT_MAP)


def normalize_optional_digits(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_digits(str(value).strip())
    return normalized if normalized else None
