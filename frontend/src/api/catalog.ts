import { apiClient } from './client';
import { getAllResults } from './pagination';
import { Brand, Size, Tire, StockMovement, PaginatedResponse } from '../types';

export const catalogApi = {
  getBrands: async (): Promise<Brand[]> => {
    return getAllResults<Brand>('/catalog/brands/');
  },

  createBrand: async (data: { brand_name: string }): Promise<Brand> => {
    const response = await apiClient.post<Brand>('/catalog/brands/', data);
    return response.data;
  },

  getSizes: async (): Promise<Size[]> => {
    return getAllResults<Size>('/catalog/sizes/');
  },

  createSize: async (data: { size_name: string }): Promise<Size> => {
    const response = await apiClient.post<Size>('/catalog/sizes/', data);
    return response.data;
  },

  getTires: async (params?: {
    search?: string;
    brand?: number;
    size?: number;
    ordering?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Tire>> => {
    const response = await apiClient.get<PaginatedResponse<Tire>>('/catalog/tires/', { params });
    return response.data;
  },

  getLowStockTires: async (): Promise<Tire[]> => {
    return getAllResults<Tire>('/catalog/tires/low-stock/');
  },

  createTire: async (data: {
    tire_name: string;
    brand: number;
    size: number;
    sale_price: number | string;
    purchase_price?: number | string;
    min_stock_alert: number;
  }): Promise<Tire> => {
    const response = await apiClient.post<Tire>('/catalog/tires/', data);
    return response.data;
  },

  updateTire: async (
    id: number,
    data: Partial<Pick<Tire, 'tire_name' | 'brand' | 'size' | 'sale_price' | 'min_stock_alert'>>
  ): Promise<Tire> => {
    const response = await apiClient.patch<Tire>(`/catalog/tires/${id}/`, data);
    return response.data;
  },

  adjustStock: async (
    tireId: number,
    data: { counted_quantity: number; reason: string }
  ): Promise<{ message: string; difference: number; current_stock: number }> => {
    const response = await apiClient.post(`/catalog/tires/${tireId}/adjust-stock/`, data);
    return response.data;
  },

  getStockMovements: async (params?: {
    tire?: number;
    movement_type?: string;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<StockMovement>> => {
    const response = await apiClient.get<PaginatedResponse<StockMovement>>('/catalog/stock-movements/', { params });
    return response.data;
  },
};
