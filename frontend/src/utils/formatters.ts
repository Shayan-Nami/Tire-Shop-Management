import type { Language } from './i18n.ts';
export function toPersianDigits(num: string | number | null | undefined): string {
  if (num === null || num === undefined) return '';
  const str = String(num);
  const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
  return str.replace(/\d/g, (x) => persianDigits[parseInt(x, 10)]);
}

export function truncateToTwoDecimals(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined) return '0';
  const rawStr = String(raw).trim();
  if (!rawStr) return '0';
  const numeric = parseFloat(rawStr);
  if (!Number.isFinite(numeric) || numeric <= 0) return '0';
  const plainDecimal = rawStr.match(/^(\d+)(?:\.(\d+))?$/);
  if (plainDecimal) {
    const intPart = String(Number(plainDecimal[1]));
    const fracPart = (plainDecimal[2] || '').slice(0, 2).replace(/0+$/, '');
    return fracPart ? `${intPart}.${fracPart}` : intPart;
  }
  const truncated = Math.floor(Number((numeric * 100).toFixed(6))) / 100;
  return String(truncated);
}

export function formatCurrency(
  amount: number | string | null | undefined,
  showUnit: boolean = true,
  unit: 'rial' | 'toman' = 'rial',
  language: Language = 'fa'
): string {
  if (amount === null || amount === undefined || amount === '') return language === 'en' ? '0' : '۰';

  let numeric = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (!Number.isFinite(numeric)) return language === 'en' ? '0' : '۰';

  if (unit === 'toman') {
    numeric = Math.trunc(numeric / 10);
  }

  const formatted = (Math.trunc(numeric) || 0).toLocaleString('en-US');
  const persianFormatted = language === 'fa' ? toPersianDigits(formatted) : formatted;

  if (!showUnit) return persianFormatted;
  const label = language === 'en' ? (unit === 'toman' ? 'Toman' : 'IRR') : (unit === 'toman' ? 'تومان' : 'ریال');
  return `${persianFormatted} ${label}`;
}

export function formatIsoToJalali(isoString?: string | null, language: Language = 'fa'): string {
  if (!isoString) return '-';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;

    const formatter = new Intl.DateTimeFormat(language === 'en' ? 'en-GB' : 'fa-IR-u-ca-persian', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

    return formatter.format(date);
  } catch {
    return isoString;
  }
}

const PERSIAN_ARABIC_DIGIT_MAP: Record<string, string> = {
  '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
  '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
  '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
  '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
};

export function normalizeDigits(value?: string | null): string {
  if (!value) return '';
  return String(value).replace(/[۰-۹٠-٩]/g, (char) => PERSIAN_ARABIC_DIGIT_MAP[char] || char);
}

export interface ParsedPlate {
  part1: string;
  letter: string;
  part2: string;
  iranCode: string;
  isValid: boolean;
}

export function parseIranianPlate(plateStr?: string | null): ParsedPlate {
  const invalid: ParsedPlate = { part1: '', letter: '', part2: '', iranCode: '', isValid: false };
  if (!plateStr?.trim()) return invalid;

  const normalized = normalizeDigits(plateStr);
  const clean = normalized.replace(/\s+/g, '');
  const match = clean.match(/^(\d{2})(الف|[بپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی])(\d{3})(?:-?ایران|-)?(\d{2})$/);

  if (match) {
    return {
      part1: toPersianDigits(match[1]),
      letter: match[2],
      part2: toPersianDigits(match[3]),
      iranCode: toPersianDigits(match[4]),
      isValid: true,
    };
  }

  return invalid;
}
