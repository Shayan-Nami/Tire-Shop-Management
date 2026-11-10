import { apiClient } from './client';
import type { PaginatedResponse } from '../types';
import { fetchAllPages } from '../utils/invoiceRequests';

export async function getAllResults<T>(url: string): Promise<T[]> {
  const getPage = async (page: number) => {
    const response = await apiClient.get<PaginatedResponse<T> | T[]>(url, {
      params: { page, page_size: 100 },
    });
    return response.data;
  };
  const firstPage = await getPage(1);
  if (Array.isArray(firstPage)) return firstPage;

  return fetchAllPages(async (page) => {
    if (page === 1) return firstPage;
    const data = await getPage(page);
    if (Array.isArray(data)) throw new Error('پاسخ صفحه‌بندی سرور معتبر نیست.');
    return data;
  });
}
