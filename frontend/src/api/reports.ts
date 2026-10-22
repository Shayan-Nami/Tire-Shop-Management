import { apiClient } from './client';
import {
  DashboardStats,
  BrandSalesStat,
  ProfitabilityStat,
} from '../types';

export const reportsApi = {
  getDashboardStats: async (): Promise<DashboardStats> => {
    const response = await apiClient.get<DashboardStats>('/analytics/dashboard-stats/');
    return response.data;
  },

  getSalesByBrand: async (brandId?: number): Promise<BrandSalesStat[]> => {
    const response = await apiClient.get<BrandSalesStat[]>('/analytics/sales-by-brand/', {
      params: brandId ? { brand_id: brandId } : undefined,
    });
    return response.data;
  },

  getProfitability: async (): Promise<ProfitabilityStat[]> => {
    const response = await apiClient.get<ProfitabilityStat[]>('/analytics/profitability/');
    return response.data;
  },

  getInventoryValue: async (): Promise<{
    total_inventory_value: number;
    items: Array<{
      tire_id: number;
      tire_name: string;
      brand_name: string;
      size_name: string;
      stock_quantity: number;
      purchase_price: number;
      inventory_value: number;
    }>;
  }> => {
    const response = await apiClient.get('/analytics/inventory-value/');
    return response.data;
  },

  getSalesByDateRange: async (startDate?: string, endDate?: string): Promise<{
    total_invoices: number;
    total_sales_amount: number;
    start_date?: string;
    end_date?: string;
  }> => {
    const response = await apiClient.get('/analytics/sales-by-date/', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },
};
