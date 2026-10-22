import { apiClient } from './client';
import { TechnicalService, PaginatedResponse } from '../types';

export const servicesApi = {
  getServices: async (params?: { search?: string; page?: number; page_size?: number }): Promise<PaginatedResponse<TechnicalService>> => {
    const response = await apiClient.get<PaginatedResponse<TechnicalService>>('/workshop/services/', { params });
    return response.data;
  },

  createService: async (data: {
    service_name: string;
    price: number | string;
    description?: string;
  }): Promise<TechnicalService> => {
    const response = await apiClient.post<TechnicalService>('/workshop/services/', data);
    return response.data;
  },

  updateService: async (id: number, data: Partial<TechnicalService>): Promise<TechnicalService> => {
    const response = await apiClient.patch<TechnicalService>(`/workshop/services/${id}/`, data);
    return response.data;
  },

  deleteService: async (id: number): Promise<void> => {
    await apiClient.delete(`/workshop/services/${id}/`);
  },
};
