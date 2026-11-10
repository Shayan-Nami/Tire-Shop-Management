import { apiClient } from './client';
import {
  SalesInvoice,
  PurchaseInvoice,
  SalesReturn,
  PaginatedResponse,
} from '../types';

export interface CreateSalesInvoicePayload {
  customer: number;
  vehicle: number;
  tire_items: Array<{ tire: number; quantity: number; unit_price?: number | string }>;
  service_items?: Array<{ service: number; quantity: number; unit_price?: number | string }>;
  discount_amount?: number | string;
  discount_percent?: number | string;
  status?: 'DRAFT' | 'CONFIRMED';
  payment_status?: 'UNPAID' | 'PAID';
  payment_method?: string;
  reference_number?: string;
  notes?: string;
}

export interface CreatePurchaseInvoicePayload {
  supplier: number;
  tire_items: Array<{ tire: number; quantity: number; unit_cost: number | string }>;
}

export interface CreateSalesReturnPayload {
  sales_invoice: number;
  items: Array<{ sales_invoice_tire_item_id: number; quantity: number }>;
  reason: string;
  return_date?: string;
}

export const invoicesApi = {
  getSalesInvoices: async (params?: {
    search?: string;
    status?: string;
    payment_status?: string;
    start_date?: string;
    end_date?: string;
    page?: number;
  }): Promise<PaginatedResponse<SalesInvoice>> => {
    const response = await apiClient.get<PaginatedResponse<SalesInvoice>>('/invoices/sales/', { params });
    return response.data;
  },

  getSalesInvoice: async (id: number): Promise<SalesInvoice> => {
    const response = await apiClient.get<SalesInvoice>(`/invoices/sales/${id}/`);
    return response.data;
  },

  createSalesInvoice: async (data: CreateSalesInvoicePayload): Promise<SalesInvoice> => {
    const response = await apiClient.post<SalesInvoice>('/invoices/sales/', data);
    return response.data;
  },

  confirmSalesInvoice: async (id: number): Promise<{ message: string; invoice: SalesInvoice }> => {
    const response = await apiClient.post(`/invoices/sales/${id}/confirm/`);
    return response.data;
  },

  cancelSalesInvoice: async (id: number): Promise<{ message: string; invoice: SalesInvoice }> => {
    const response = await apiClient.post(`/invoices/sales/${id}/cancel/`);
    return response.data;
  },

  getPurchaseInvoices: async (params?: {
    search?: string;
    status?: string;
    payment_status?: string;
    page?: number;
  }): Promise<PaginatedResponse<PurchaseInvoice>> => {
    const response = await apiClient.get<PaginatedResponse<PurchaseInvoice>>('/invoices/purchases/', { params });
    return response.data;
  },

  getPurchaseInvoice: async (id: number): Promise<PurchaseInvoice> => {
    const response = await apiClient.get<PurchaseInvoice>(`/invoices/purchases/${id}/`);
    return response.data;
  },

  createPurchaseInvoice: async (data: CreatePurchaseInvoicePayload): Promise<PurchaseInvoice> => {
    const response = await apiClient.post<PurchaseInvoice>('/invoices/purchases/', data);
    return response.data;
  },

  cancelPurchaseInvoice: async (id: number): Promise<{ message: string; invoice: PurchaseInvoice }> => {
    const response = await apiClient.post(`/invoices/purchases/${id}/cancel/`);
    return response.data;
  },

  getSalesReturns: async (params?: { page?: number }): Promise<PaginatedResponse<SalesReturn>> => {
    const response = await apiClient.get<PaginatedResponse<SalesReturn>>('/invoices/returns/', { params });
    return response.data;
  },

  createSalesReturn: async (data: CreateSalesReturnPayload): Promise<SalesReturn> => {
    const response = await apiClient.post<SalesReturn>('/invoices/returns/', data);
    return response.data;
  },
};
