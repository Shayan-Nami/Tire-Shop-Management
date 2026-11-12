from __future__ import annotations

import datetime

from django.utils import timezone as dj_timezone

from utils.persian import normalize_digits


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    if not (1 <= gm <= 12 and 1 <= gd <= 31):
        raise ValueError(f"ماه ({gm}) یا روز ({gd}) میلادی نامعتبر است.")
    g_d_m_max = [
        0,
        31,
        29 if ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
    ]
    if gd > g_d_m_max[gm]:
        raise ValueError(f"روز ({gd}) برای ماه ({gm}) سال ({gy}) میلادی نامعتبر است.")
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gm > 2:
        gy2 = gy + 1
    else:
        gy2 = gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    if not (1 <= jm <= 12 and 1 <= jd <= 31):
        raise ValueError(f"ماه ({jm}) یا روز ({jd}) هجری شمسی نامعتبر است.")
    if jm > 6 and jd == 31:
        raise ValueError(f"ماه‌های نیمه دوم سال هجری شمسی (ماه {jm}) نمی‌توانند ۳۱ روز داشته باشند.")
    if jm == 12 and jd > 30:
        raise ValueError("ماه اسفند نمی‌تواند بیش از ۳۰ روز باشد.")
    orig_jy, orig_jm, orig_jd = jy, jm, jd
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    sal_a = [
        0,
        31,
        29 if ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
    ]
    gm = 0
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    if gregorian_to_jalali(gy, gm, gd) != (orig_jy, orig_jm, orig_jd):
        raise ValueError(f"تاریخ هجری شمسی نامعتبر است: {orig_jy:04d}/{orig_jm:02d}/{orig_jd:02d}")
    return gy, gm, gd


def parse_jalali_or_gregorian_date(date_str: object) -> str | None:
    if not date_str:
        return None
    normalized = normalize_digits(str(date_str).strip())
    normalized = normalized.replace('/', '-')
    parts = normalized.split('-')
    if len(parts) != 3:
        return None
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None

    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None

    if 1300 <= y <= 1500:
        try:
            gy, gm, gd = jalali_to_gregorian(y, m, d)
            return f"{gy:04d}-{gm:02d}-{gd:02d}"
        except ValueError:
            return None
    if 1900 < y <= 9999:
        try:
            datetime.date(y, m, d)
        except ValueError:
            return None
        return f"{y:04d}-{m:02d}-{d:02d}"
    return None


def _coerce_date(dt: object) -> datetime.date | None:
    if isinstance(dt, datetime.datetime):
        if dj_timezone.is_aware(dt):
            return dj_timezone.localtime(dt).date()
        return dt.date()
    if isinstance(dt, datetime.date):
        return dt
    return None


def format_jalali_date(dt: object) -> str:
    if not dt:
        return ""
    target_date = _coerce_date(dt)
    if target_date is None:
        return ""
    try:
        jy, jm, jd = gregorian_to_jalali(target_date.year, target_date.month, target_date.day)
        return f"{jy:04d}/{jm:02d}/{jd:02d}"
    except ValueError:
        return ""


def get_jalali_year(dt: object | None = None) -> int:
    source: object = dj_timezone.now() if dt is None else dt
    target_date = _coerce_date(source)
    if target_date is None:
        target_date = dj_timezone.localtime(dj_timezone.now()).date()

    try:
        jy, _, _ = gregorian_to_jalali(target_date.year, target_date.month, target_date.day)
    except ValueError:
        now_dt: datetime.date = dj_timezone.localtime(dj_timezone.now()).date()
        jy, _, _ = gregorian_to_jalali(now_dt.year, now_dt.month, now_dt.day)
    return jy
