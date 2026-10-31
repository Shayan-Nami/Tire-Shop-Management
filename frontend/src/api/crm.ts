import { apiClient } from './client';
import { Customer, Vehicle, PaginatedResponse } from '../types';

export const crmApi = {
  getCustomers: async (params?: {
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Customer>> => {
    const response = await apiClient.get<PaginatedResponse<Customer>>('/crm/customers/', { params });
    return response.data;
  },

  getCustomer: async (id: number): Promise<Customer> => {
    const response = await apiClient.get<Customer>(`/crm/customers/${id}/`);
    return response.data;
  },

  createCustomer: async (data: {
    full_name: string;
    phone_number?: string | null;
    national_code?: string | null;
    address?: string | null;
  }): Promise<Customer> => {
    const response = await apiClient.post<Customer>('/crm/customers/', data);
    return response.data;
  },

  updateCustomer: async (id: number, data: Partial<Customer>): Promise<Customer> => {
    const response = await apiClient.patch<Customer>(`/crm/customers/${id}/`, data);
    return response.data;
  },

  getVehicles: async (params?: {
    customer?: number;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Vehicle>> => {
    const response = await apiClient.get<PaginatedResponse<Vehicle>>('/crm/vehicles/', { params });
    return response.data;
  },

  createVehicle: async (data: {
    customer: number;
    license_plate: string;
    model: string;
    year?: string;
    tire_size_recommended?: string;
  }): Promise<Vehicle> => {
    const response = await apiClient.post<Vehicle>('/crm/vehicles/', data);
    return response.data;
  },

  updateVehicle: async (id: number, data: Partial<Vehicle>): Promise<Vehicle> => {
    const response = await apiClient.patch<Vehicle>(`/crm/vehicles/${id}/`, data);
    return response.data;
  },
};
