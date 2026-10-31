import { apiClient } from './client';
import {
  DashboardStats,
  BrandSalesStat,
  ProfitabilityStat,
  InventoryValueResponse,
  SalesByDateRangeResponse,
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

  getInventoryValue: async (): Promise<InventoryValueResponse> => {
    const response = await apiClient.get<InventoryValueResponse>('/analytics/inventory-value/');
    return response.data;
  },

  getSalesByDateRange: async (startDate?: string, endDate?: string): Promise<SalesByDateRangeResponse> => {
    const response = await apiClient.get<SalesByDateRangeResponse>('/analytics/sales-by-date/', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },
};
