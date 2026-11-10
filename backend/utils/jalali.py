import datetime

def gregorian_to_jalali(gy, gm, gd):
    if not (1 <= gm <= 12 and 1 <= gd <= 31):
        raise ValueError(f"ماه ({gm}) یا روز ({gd}) میلادی نامعتبر است.")
    g_d_m_max = [0, 31, 29 if ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if gd > g_d_m_max[gm]:
        raise ValueError(f"روز ({gd}) برای ماه ({gm}) سال ({gy}) میلادی نامعتبر است.")
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if (gm > 2):
        gy2 = gy + 1
    else:
        gy2 = gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if (days > 365):
        jy += ((days - 1) // 365)
        days = (days - 1) % 365
    if (days < 186):
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

from django.utils import timezone as dj_timezone
from utils.persian import normalize_digits

def jalali_to_gregorian(jy, jm, jd):
    if not (1 <= jm <= 12 and 1 <= jd <= 31):
        raise ValueError(f"ماه ({jm}) یا روز ({jd}) هجری شمسی نامعتبر است.")
    if jm > 6 and jd == 31:
        raise ValueError(f"ماه‌های نیمه دوم سال هجری شمسی (ماه {jm}) نمی‌توانند ۳۱ روز داشته باشند.")
    if jm == 12 and jd > 30:
        raise ValueError("ماه اسفند نمی‌تواند بیش از ۳۰ روز باشد.")
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
        gy += ((days - 1) // 365)
        days = (days - 1) % 365
    gd = days + 1
    sal_a = [0, 31, 29 if ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm, gd

def parse_jalali_or_gregorian_date(date_str):
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
    elif y > 1900:
        return f"{y:04d}-{m:02d}-{d:02d}"
    return None

def format_jalali_date(dt):
    if not dt:
        return ""
    if isinstance(dt, datetime.datetime):
        if dj_timezone.is_aware(dt):
            dt = dj_timezone.localtime(dt).date()
        else:
            dt = dt.date()
    elif isinstance(dt, datetime.date):
        pass
    else:
        return ""
    try:
        jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
        return f"{jy:04d}/{jm:02d}/{jd:02d}"
    except ValueError:
        return ""


def get_jalali_year(dt=None) -> int:
    if dt is None:
        dt = dj_timezone.now()
    if isinstance(dt, datetime.datetime):
        if dj_timezone.is_aware(dt):
            dt = dj_timezone.localtime(dt).date()
        else:
            dt = dt.date()
    elif isinstance(dt, datetime.date):
        pass
    else:
        dt = dj_timezone.localtime(dj_timezone.now()).date()

    try:
        jy, _, _ = gregorian_to_jalali(dt.year, dt.month, dt.day)
    except ValueError:
        now_dt = dj_timezone.localtime(dj_timezone.now()).date()
        jy, _, _ = gregorian_to_jalali(now_dt.year, now_dt.month, now_dt.day)
    return jy

