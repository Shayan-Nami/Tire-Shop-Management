from __future__ import annotations

from typing import Any

from rest_framework import serializers

from utils.persian import normalize_digits


class PersianNormalizedCharField(serializers.CharField):
    """CharField that strips whitespace and normalizes Persian/Arabic numerals."""

    def to_internal_value(self, data: Any) -> Any:
        if data is None:
            return None
        val = super().to_internal_value(data)
        if isinstance(val, str):
            norm = normalize_digits(val.strip())
            if not norm:
                return None if self.allow_null else ''
            return norm
        return str(val)
