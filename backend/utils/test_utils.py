import hashlib
import logging
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import DecimalField, ProtectedError, Value
from django.http import QueryDict
from rest_framework import status
from rest_framework.exceptions import MethodNotAllowed, Throttled
from rest_framework.test import APIRequestFactory

from apps.catalog.models import Brand, Size, Tire
from utils.domain import DomainValidationError, validate_money, validate_quantity
from utils.exceptions import custom_exception_handler
from utils.expressions import DecimalDivision
from utils.jalali import (
    format_jalali_date,
    get_jalali_year,
    gregorian_to_jalali,
    jalali_to_gregorian,
    parse_jalali_or_gregorian_date,
)
from utils.mixins import ImmutableDocumentViewSetMixin
from utils.persian import normalize_digits, normalize_optional_digits
from utils.throttling import LoginIPRateThrottle, LoginUsernameRateThrottle, TokenRefreshRateThrottle


@pytest.mark.django_db
def test_decimal_division_sqlite_precision_and_zero_safety():
    brand = Brand.objects.create(brand_name='Division Brand')
    size = Size.objects.create(size_name='205/55R16')
    tire_non_zero = Tire.objects.create(
        tire_name='NonZero Tire',
        brand=brand,
        size=size,
        stock_quantity=1,
        min_stock_alert=3,
        sale_price=Decimal('1000.00'),
        purchase_price=Decimal('800.00'),
    )
    tire_zero = Tire.objects.create(
        tire_name='Zero Alert Tire',
        brand=brand,
        size=size,
        stock_quantity=1,
        min_stock_alert=0,
        sale_price=Decimal('1000.00'),
        purchase_price=Decimal('800.00'),
    )

    qs = Tire.objects.annotate(
        ratio_literal=DecimalDivision(Value(1), Value(3)),
        ratio_cols=DecimalDivision('stock_quantity', 'min_stock_alert'),
        ratio_zero_lit=DecimalDivision(Value(1), Value(0)),
        ratio_zero_dec=DecimalDivision(Value(Decimal('10.00')), Value(Decimal('0.00'))),
    )
    row_nz = qs.get(pk=tire_non_zero.pk)
    assert Decimal('0.33') < row_nz.ratio_literal < Decimal('0.34')
    assert Decimal('0.33') < row_nz.ratio_cols < Decimal('0.34')
    assert row_nz.ratio_zero_lit is None
    assert row_nz.ratio_zero_dec is None

    row_z = qs.get(pk=tire_zero.pk)
    assert row_z.ratio_cols is None


@pytest.mark.django_db
def test_decimal_division_non_sqlite_sql_compilation():
    class FakeCompiler:
        def compile(self, node):
            if hasattr(node, 'as_sql'):
                return node.as_sql(self, FakeConnection())
            return str(node), []

    class FakeConnection:
        vendor = 'postgresql'

        class ops:
            @staticmethod
            def quote_name(name):
                return f'"{name}"'

            @staticmethod
            def conditional_expression_supported_in_where_clause():
                return True

            @staticmethod
            def lookup_cast(lookup_type, internal_type=None):
                return '%s'

            @staticmethod
            def prep_for_iexact_query(x):
                return x

            @staticmethod
            def check_expression_support(expression):
                pass

    from django.db import connections

    compiler = Tire.objects.all().query.get_compiler(using='default')
    int_div = DecimalDivision(Value(1), Value(3))
    sql_int, _ = int_div.as_sql(compiler, FakeConnection())
    assert 'NULLIF' in sql_int
    assert 'CAST(' in sql_int or '::' in sql_int

    dec_num = Value(Decimal('100.00'), output_field=DecimalField(max_digits=20, decimal_places=2))
    dec_div = DecimalDivision(dec_num, Value(Decimal('3.00'), output_field=DecimalField(max_digits=14, decimal_places=2)))
    sql_dec, _ = dec_div.as_sql(compiler, FakeConnection())
    assert 'NULLIF' in sql_dec
    assert 'DECIMAL(28, 12)' not in sql_dec
    assert connections['default'] is not None


def test_validate_money_quantizes_and_rejects_invalid_values():
    assert validate_money(100) == Decimal('100.00')
    assert validate_money('12.3') == Decimal('12.30')
    assert validate_money('12.3400') == Decimal('12.34')
    negative_zero = validate_money('-0.00')
    assert negative_zero == Decimal('0.00')
    assert not negative_zero.is_signed()

    for bad in [None, True, False, 'abc', 'NaN', 'Infinity', '-Infinity', '12.345', Decimal('1e15')]:
        with pytest.raises(DomainValidationError):
            validate_money(bad)


def test_validate_quantity_bounds():
    assert validate_quantity('5') == 5
    assert validate_quantity(Decimal('12.00')) == 12
    for bad in [True, False, '1.5', 'NaN', 'abc', None]:
        with pytest.raises(DomainValidationError):
            validate_quantity(bad)


def test_jalali_round_trip_and_gregorian_calendar_validation():
    assert parse_jalali_or_gregorian_date('') is None
    assert parse_jalali_or_gregorian_date('invalid') is None
    assert parse_jalali_or_gregorian_date('1404/12/31') is None
    assert parse_jalali_or_gregorian_date('1404/12/30') is None
    assert parse_jalali_or_gregorian_date('۱۴۰۳/۱۲/۳۰') == '2025-03-20'

    with pytest.raises(ValueError):
        jalali_to_gregorian(1404, 12, 30)
    with pytest.raises(ValueError):
        jalali_to_gregorian(1403, 7, 31)
    with pytest.raises(ValueError):
        gregorian_to_jalali(2025, 2, 29)

    assert parse_jalali_or_gregorian_date('2026-02-31') is None
    assert parse_jalali_or_gregorian_date('2026-02-29') is None
    assert parse_jalali_or_gregorian_date('2024-02-29') == '2024-02-29'
    assert parse_jalali_or_gregorian_date('10000-01-01') is None

    aware_dt = datetime(2025, 3, 21, 10, 0, tzinfo=dt_timezone.utc)
    assert format_jalali_date(aware_dt) == '1404/01/01'
    assert format_jalali_date(date(2025, 3, 20)) == '1403/12/30'
    assert format_jalali_date('not-a-date') == ''
    assert get_jalali_year(aware_dt) == 1404
    assert isinstance(get_jalali_year(), int)


def test_persian_digit_normalization():
    assert normalize_digits(None) is None
    assert normalize_digits('۰۹۱۲٣٤٥') == '0912345'
    assert normalize_optional_digits(None) is None
    assert normalize_optional_digits('   ') is None
    assert normalize_optional_digits(' ۰۹۱۲ ') == '0912'


def test_login_username_rate_throttle_keys_by_sha256_across_ips():
    factory = APIRequestFactory()
    throttle = LoginUsernameRateThrottle()

    req_ip1 = factory.post('/api/v1/auth/login/', {}, REMOTE_ADDR='10.0.0.1')
    req_ip1.data = {'username': ' AliReza '}

    req_ip1_upper = factory.post('/api/v1/auth/login/', {}, REMOTE_ADDR='10.0.0.1')
    qd = QueryDict('', mutable=True)
    qd['phone_number'] = 'alireza'
    req_ip1_upper.data = qd

    req_ip2 = factory.post('/api/v1/auth/login/', {}, REMOTE_ADDR='10.0.0.2')
    req_ip2.data = {'username': 'alireza'}

    k1 = throttle.get_cache_key(req_ip1, None)
    k1_q = throttle.get_cache_key(req_ip1_upper, None)
    k2 = throttle.get_cache_key(req_ip2, None)

    expected_hash = hashlib.sha256(b'alireza').hexdigest()
    assert k1 == k1_q == k2
    assert expected_hash in k1
    assert 'alireza' not in k1

    req_blank = factory.post('/api/v1/auth/login/', {}, REMOTE_ADDR='10.0.0.1')
    req_blank.data = {'username': '   '}
    assert throttle.get_cache_key(req_blank, None) is None

    req_list = factory.post('/api/v1/auth/login/', {}, REMOTE_ADDR='10.0.0.1')
    req_list.data = ['not', 'a', 'mapping']
    assert throttle.get_cache_key(req_list, None) is None

    ip_key = LoginIPRateThrottle().get_cache_key(req_ip1, None)
    assert '10.0.0.1' in ip_key

    req_ip1.user = type('Anon', (), {'is_authenticated': False})()
    refresh_key = TokenRefreshRateThrottle().get_cache_key(req_ip1, None)
    assert '10.0.0.1' in refresh_key
    req_ip1.user = type('Authed', (), {'is_authenticated': True, 'pk': 42})()
    assert '42' in TokenRefreshRateThrottle().get_cache_key(req_ip1, None)


def test_custom_exception_handler_logs_integrity_and_unhandled_errors(caplog, settings):
    caplog.set_level(logging.INFO, logger='apps')

    res_integrity = custom_exception_handler(IntegrityError('duplicate key'), {})
    assert res_integrity is not None
    assert res_integrity.status_code == status.HTTP_400_BAD_REQUEST
    assert res_integrity.data['success'] is False
    assert any(r.levelno == logging.WARNING and 'duplicate key' in r.getMessage() for r in caplog.records)

    settings.DEBUG = False
    caplog.clear()
    res_unhandled = custom_exception_handler(RuntimeError('boom'), {})
    assert res_unhandled is not None
    assert res_unhandled.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert any(r.levelno == logging.ERROR and 'boom' in r.getMessage() for r in caplog.records)

    settings.DEBUG = True
    assert custom_exception_handler(RuntimeError('debug-boom'), {}) is None

    res_dict_val = custom_exception_handler(DjangoValidationError({'field': ['err']}), {})
    assert res_dict_val.status_code == 400

    res_list_val = custom_exception_handler(DjangoValidationError(['err1']), {})
    assert res_list_val.status_code == 400

    res_protected = custom_exception_handler(ProtectedError('protected', set()), {})
    assert res_protected.status_code == 400

    res_throttled = custom_exception_handler(Throttled(wait=12.2), {})
    assert res_throttled.status_code == 429
    assert res_throttled.data['errors']['available_in_seconds'] == 13


def test_immutable_document_mixin_blocks_mutations():
    mixin = ImmutableDocumentViewSetMixin()
    for method in (mixin.update, mixin.partial_update, mixin.destroy):
        with pytest.raises(MethodNotAllowed):
            method(None)


def test_dummy_patch_unused_import_guard():
    with patch('utils.exceptions.logger') as mock_logger:
        custom_exception_handler(IntegrityError('x'), {})
        assert mock_logger.warning.called


def test_standard_pagination_respects_configured_page_size(settings):
    from rest_framework.request import Request
    from utils.pagination import StandardResultsSetPagination

    paginator = StandardResultsSetPagination()
    req_default = Request(APIRequestFactory().get('/'))
    assert paginator.get_page_size(req_default) == 20

    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'PAGE_SIZE': 35}
    assert paginator.get_page_size(req_default) == 35

    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'PAGE_SIZE': 500}
    assert paginator.get_page_size(req_default) == 100

    req_override = Request(APIRequestFactory().get('/?page_size=12'))
    assert paginator.get_page_size(req_override) == 12
