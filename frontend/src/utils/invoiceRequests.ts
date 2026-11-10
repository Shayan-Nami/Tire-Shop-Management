import type { PaginatedResponse, Vehicle } from '../types/index.ts';

export function createRequestSequence() {
  let sequence = 0;
  return {
    begin: () => ++sequence,
    invalidate: () => { ++sequence; },
    isCurrent: (request: number) => request === sequence,
  };
}

export async function fetchAllPages<T>(
  fetchPage: (page: number) => Promise<PaginatedResponse<T>>,
  isCurrent: () => boolean = () => true,
): Promise<T[]> {
  const results: T[] = [];
  for (let page = 1; ; page += 1) {
    if (!isCurrent()) return [];
    const response = await fetchPage(page);
    if (!isCurrent()) return [];
    if (response.current_page !== page) {
      throw new Error('پاسخ صفحه‌بندی نامعتبر است؛ صفحه درخواستی دریافت نشد.');
    }
    results.push(...response.results);
    const hasMore = Boolean(response.next) || page < response.total_pages;
    if (!hasMore) return results;
    if (response.results.length === 0) {
      throw new Error('پاسخ صفحه‌بندی نامعتبر است؛ دریافت همه گزینه‌ها ممکن نشد.');
    }
  }
}

export function isCurrentInvoiceVehicle(
  customerId: number | '',
  vehicleId: number | '',
  vehicles: Vehicle[],
  loading: boolean,
): boolean {
  return !loading && customerId !== '' && vehicleId !== '' && vehicles.some(
    (vehicle) => vehicle.vehicle_id === vehicleId && vehicle.customer === customerId,
  );
}

export function invoiceSubmitLabel(status: 'DRAFT' | 'CONFIRMED', submitting: boolean): string {
  if (status === 'DRAFT') return submitting ? 'در حال ذخیره پیش‌نویس...' : 'ذخیره پیش‌نویس فاکتور';
  return submitting ? 'در حال صدور فاکتور...' : 'صدور و نهایی‌سازی فاکتور';
}
