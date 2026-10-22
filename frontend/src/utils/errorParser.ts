import axios from 'axios';

const FIELD_LABELS_FA: Record<string, string> = {
  phone_number: 'شماره تماس',
  national_code: 'کد ملی',
  full_name: 'نام و نام خانوادگی',
  license_plate: 'شماره پلاک',
  model: 'مدل خودرو',
  amount: 'مبلغ',
  unit_price: 'قیمت واحد',
  unit_cost: 'بهای تمام‌شده واحد',
  quantity: 'تعداد',
  reason: 'علت / دلیل',
  notes: 'توضیحات',
  username: 'نام کاربری',
  password: 'کلمه عبور',
  reference_number: 'شماره پیگیری / مرجع',
  customer: 'مشتری',
  vehicle: 'خودرو',
  supplier: 'تأمین‌کننده',
  sales_invoice: 'فاکتور فروش',
  purchase_invoice: 'فاکتور خرید',
  sales_invoice_tire_item_id: 'شناسه قلم فاکتور',
  tire_items: 'اقلام تایر',
  service_items: 'خدمات فنی',
  payment_method: 'روش پرداخت',
  payment_status: 'وضعیت پرداخت',
  tire: 'تایر',
  size: 'سایز',
  brand: 'برند',
  stock: 'موجودی',
  stock_quantity: 'تعداد موجودی',
  non_field_errors: 'خطا',
  detail: 'پیام',
};

/**
 * استخراج پیام خطای فارسی خوانا از پاسخ‌های استاندارد و سفارشی Django REST Framework
 * ساختار پاسخ سرور: { success: false, status_code: number, errors: ... }
 */
export function parseApiError(
  error: unknown,
  fallback: string = 'خطایی در انجام عملیات رخ داده است.'
): string {
  if (!error) return fallback;

  if (axios.isAxiosError(error)) {
    // خطای عدم برقراری ارتباط با شبکه / قطعی سرور
    if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
      return 'خطا در برقراری ارتباط با سرور. لطفاً اتصال اینترنت یا فعال بودن سرور را بررسی فرمایید.';
    }

    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      return 'مهلت زمانی ارتباط با سرور به پایان رسید. لطفاً مجدداً تلاش فرمایید.';
    }

    const serverError = 'خطای داخلی سرور رخ داده است. لطفاً با پشتیبانی سیستم تماس بگیرید.';
    if ((error.response?.status ?? 0) >= 500) return serverError;

    const data = error.response?.data;
    const isHtml = (value: string) => /<!doctype\s+html|<\/?[a-z][^>]*>/i.test(value);
    if (typeof data === 'string' && isHtml(data)) return serverError;
    if (!data) {
      if (error.response?.status === 403) {
        return 'شما مجوز دسترسی به این عملیات را ندارید.';
      }
      if (error.response?.status === 404) {
        return 'اطلاعات مورد نظر در سرور یافت نشد.';
      }
      return error.message || fallback;
    }

    // بررسی وجود آبجکت errors در ساختار پاسخ DRF
    const rawErrors = data.errors !== undefined ? data.errors : data;

    const visited = new WeakSet<object>();
    const collectMessages = (value: unknown, depth = 0): string => {
      if (typeof value === 'string') return isHtml(value) ? serverError : value;
      if (value === null || typeof value !== 'object' || depth > 10 || visited.has(value)) return '';
      visited.add(value);
      if (Array.isArray(value)) {
        return value.map((item) => collectMessages(item, depth + 1)).filter(Boolean).join(' | ');
      }
      const fields = value as Record<string, unknown>;
      for (const key of ['detail', 'non_field_errors', 'message']) {
        if (key in fields) {
          const message = collectMessages(fields[key], depth + 1);
          if (message) return message;
        }
      }
      return Object.entries(fields).map(([key, val]) => {
        const message = collectMessages(val, depth + 1);
        return message ? `${FIELD_LABELS_FA[key] || key}: ${message}` : '';
      }).filter(Boolean).join('\n');
    };

    const message = collectMessages(rawErrors);
    if (message) return message;
    return fallback;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}
