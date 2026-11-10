import datetime

import pytest
from django.urls import reverse

from utils.jalali import (
    gregorian_to_jalali,
    is_jalali_leap_year,
    jalali_to_gregorian,
    parse_jalali_or_gregorian_date,
)


@pytest.mark.parametrize('year', [1399, 1403, 1408])
def test_known_leap_years(year):
    assert is_jalali_leap_year(year) is True


@pytest.mark.parametrize('year', [1400, 1401, 1402, 1404, 1405])
def test_known_common_years(year):
    assert is_jalali_leap_year(year) is False


def test_esfand_30_accepted_only_in_leap_years():
    assert jalali_to_gregorian(1403, 12, 30) == (2025, 3, 20)
    assert jalali_to_gregorian(1399, 12, 30) == (2021, 3, 20)

    for year in (1404, 1402):
        with pytest.raises(ValueError, match='کبیسه نیست'):
            jalali_to_gregorian(year, 12, 30)
    assert jalali_to_gregorian(1404, 12, 29) == (2026, 3, 20)


def test_leap_rule_matches_conversion_round_trip():
    for year in range(1300, 1501):
        next_new_year = datetime.date(*jalali_to_gregorian(year + 1, 1, 1))
        last_day = next_new_year - datetime.timedelta(days=1)
        _, month, day = gregorian_to_jalali(last_day.year, last_day.month, last_day.day)
        assert (month, day) == (12, 30 if is_jalali_leap_year(year) else 29), year


def test_parse_rejects_esfand_30_in_common_year():
    assert parse_jalali_or_gregorian_date('1404/12/30') is None
    assert parse_jalali_or_gregorian_date('۱۴۰۴/۱۲/۳۰') is None
    assert parse_jalali_or_gregorian_date('1403/12/30') == '2025-03-20'


@pytest.mark.django_db
def test_report_endpoint_returns_400_for_invalid_esfand_30(auth_client_manager):
    url = reverse('sales-by-date-report')

    response = auth_client_manager.get(url, {'start_date': '1404/12/30'})
    assert response.status_code == 400
    assert 'start_date' in response.data['errors']

    response = auth_client_manager.get(url, {'end_date': '1404-12-30'})
    assert response.status_code == 400
    assert 'end_date' in response.data['errors']

    assert auth_client_manager.get(url, {'start_date': '1403/12/30'}).status_code == 200
