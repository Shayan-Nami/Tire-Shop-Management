import { apiClient } from './client';
import {
  ReceiptVoucher,
  PaymentVoucher,
  CustomerRefundVoucher,
  PaginatedResponse,
} from '../types';

export const financeApi = {
  // اسناد دریافت وجه از مشتری
  getReceipts: async (params?: {
    sales_invoice?: number;
    is_cancelled?: boolean;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<ReceiptVoucher>> => {
    const response = await apiClient.get<PaginatedResponse<ReceiptVoucher>>('/treasury/receipts/', { params });
    return response.data;
  },

  createReceipt: async (data: {
    sales_invoice: number;
    amount: number | string;
    payment_method: 'CASH' | 'POS' | 'CARD_TO_CARD' | 'CHEQUE';
    reference_number?: string;
    notes?: string;
  }): Promise<ReceiptVoucher> => {
    const response = await apiClient.post<ReceiptVoucher>('/treasury/receipts/', data);
    return response.data;
  },

  cancelReceipt: async (id: number, reason: string): Promise<ReceiptVoucher> => {
    const response = await apiClient.post<ReceiptVoucher>(`/treasury/receipts/${id}/cancel/`, { reason });
    return response.data;
  },

  // اسناد پرداخت به تأمین‌کننده
  getPayments: async (params?: {
    purchase_invoice?: number;
    is_cancelled?: boolean;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<PaymentVoucher>> => {
    const response = await apiClient.get<PaginatedResponse<PaymentVoucher>>('/treasury/payments/', { params });
    return response.data;
  },

  createPayment: async (data: {
    purchase_invoice: number;
    amount: number | string;
    payment_method: 'CASH' | 'BANK_TRANSFER' | 'CHEQUE';
    reference_number?: string;
    notes?: string;
  }): Promise<PaymentVoucher> => {
    const response = await apiClient.post<PaymentVoucher>('/treasury/payments/', data);
    return response.data;
  },

  cancelPayment: async (id: number, reason: string): Promise<PaymentVoucher> => {
    const response = await apiClient.post<PaymentVoucher>(`/treasury/payments/${id}/cancel/`, { reason });
    return response.data;
  },

  // اسناد استرداد وجه به مشتری (مازاد مرجوعی)
  getCustomerRefunds: async (params?: {
    sales_invoice?: number;
    is_cancelled?: boolean;
    search?: string;
    page?: number;
  }): Promise<PaginatedResponse<CustomerRefundVoucher>> => {
    const response = await apiClient.get<PaginatedResponse<CustomerRefundVoucher>>('/treasury/customer-refunds/', { params });
    return response.data;
  },

  createCustomerRefund: async (data: {
    sales_invoice: number;
    sales_return?: number;
    amount: number | string;
    payment_method?: string;
    notes?: string;
  }): Promise<CustomerRefundVoucher> => {
    const response = await apiClient.post<CustomerRefundVoucher>('/treasury/customer-refunds/', data);
    return response.data;
  },

  cancelCustomerRefund: async (id: number, reason: string): Promise<CustomerRefundVoucher> => {
    const response = await apiClient.post<CustomerRefundVoucher>(`/treasury/customer-refunds/${id}/cancel/`, { reason });
    return response.data;
  },
};
