import { apiClient } from './client';
import { Supplier, PaginatedResponse } from '../types';

export const suppliersApi = {
  getSuppliers: async (params?: { search?: string; page?: number; page_size?: number }): Promise<PaginatedResponse<Supplier>> => {
    const response = await apiClient.get<PaginatedResponse<Supplier>>('/procurement/suppliers/', { params });
    return response.data;
  },

  createSupplier: async (data: {
    supplier_name: string;
    phone_number?: string;
    address?: string;
  }): Promise<Supplier> => {
    const response = await apiClient.post<Supplier>('/procurement/suppliers/', data);
    return response.data;
  },

  updateSupplier: async (id: number, data: Partial<Supplier>): Promise<Supplier> => {
    const response = await apiClient.patch<Supplier>(`/procurement/suppliers/${id}/`, data);
    return response.data;
  },

  deleteSupplier: async (id: number): Promise<void> => {
    await apiClient.delete(`/procurement/suppliers/${id}/`);
  },
};
