export type UserRole = 'MANAGER' | 'WAREHOUSE' | 'TECHNICIAN';

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: UserRole;
  role_display?: string;
  phone_number?: string | null;
  is_active?: boolean;
  date_joined?: string;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface UpdateProfilePayload {
  full_name?: string;
  phone_number?: string | null;
}

export interface ChangePasswordPayload {
  old_password: string;
  new_password: string;
}

export interface PaginatedResponse<T> {
  count: number;
  total_pages: number;
  current_page: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Brand {
  brand_id: number;
  brand_name: string;
  tires_count?: number;
}

export interface Size {
  size_id: number;
  size_name: string;
  tires_count?: number;
}

export interface Tire {
  tire_id: number;
  tire_name: string;
  brand: number;
  brand_name: string;
  size: number;
  size_name: string;
  stock_quantity: number;
  sale_price: string | number;
  purchase_price?: string | number;
  min_stock_alert: number;
  is_low_stock?: boolean;
}

export type StockMovementType = 'INITIAL_STOCK' | 'PURCHASE' | 'PURCHASE_CANCEL' | 'SALE' | 'SALE_CANCEL' | 'SALE_RETURN' | 'MANUAL_ADJUSTMENT';

export interface StockMovement {
  movement_id: number;
  tire: number;
  tire_name: string;
  brand_name: string;
  quantity: number;
  movement_type: StockMovementType | string;
  movement_type_display: string;
  balance_after: number;
  sales_invoice?: number | null;
  purchase_invoice?: number | null;
  unit_cost?: string | number;
  user?: number;
  user_name?: string;
  description?: string;
  created_at: string;
  jalali_date?: string;
}

export interface Customer {
  customer_id: number;
  full_name: string;
  phone_number: string;
  national_code?: string;
  address?: string;
  created_at?: string;
  vehicles?: Vehicle[];
}

export interface Vehicle {
  vehicle_id: number;
  customer: number;
  customer_name?: string;
  license_plate: string;
  model: string;
  year?: string;
  tire_size_recommended?: string;
}

export interface TechnicalService {
  service_id: number;
  service_name: string;
  price: string | number;
  description?: string;
  is_active?: boolean;
}

export interface Supplier {
  supplier_id: number;
  supplier_name: string;
  phone_number?: string;
  address?: string;
}

export interface SalesInvoiceTireItem {
  id: number;
  tire: number;
  tire_name: string;
  brand_name: string;
  size_name: string;
  quantity: number;
  unit_price: string | number;
  unit_cost?: string | number;
  total_price: string | number;
}

export interface SalesInvoiceServiceItem {
  id: number;
  service: number;
  service_name: string;
  quantity: number;
  unit_price: string | number;
  total_price: string | number;
}

export interface SalesInvoice {
  sales_invoice_id: number;
  invoice_number: string;
  invoice_date: string;
  jalali_date?: string;
  customer: number;
  customer_name: string;
  customer_phone: string;
  vehicle: number;
  vehicle_plate: string;
  vehicle_model: string;
  status: 'DRAFT' | 'CONFIRMED' | 'CANCELLED';
  status_display?: string;
  payment_status: 'UNPAID' | 'PARTIAL' | 'PAID';
  payment_status_display?: string;
  paid_amount?: string | number;
  remaining_amount?: string | number;
  discount_amount: string | number;
  discount_percent: string | number;
  total_amount: string | number;
  returned_amount?: string | number;
  net_amount?: string | number;
  excess_amount?: string | number;
  notes?: string;
  created_by?: number;
  created_by_name?: string;
  tire_items: SalesInvoiceTireItem[];
  service_items: SalesInvoiceServiceItem[];
}

export interface PurchaseInvoiceTireItem {
  id: number;
  tire: number;
  tire_name: string;
  brand_name: string;
  size_name: string;
  quantity: number;
  unit_cost: string | number;
  total_cost: string | number;
}

export interface PurchaseInvoice {
  purchase_invoice_id: number;
  invoice_number: string;
  invoice_date: string;
  jalali_date?: string;
  supplier: number;
  supplier_name: string;
  status: 'CONFIRMED' | 'CANCELLED';
  status_display?: string;
  payment_status: 'UNPAID' | 'PARTIAL' | 'PAID';
  payment_status_display?: string;
  total_amount: string | number;
  notes?: string;
  created_by?: number;
  created_by_name?: string;
  tire_items: PurchaseInvoiceTireItem[];
}

export interface SalesReturn {
  sales_return_id: number;
  sales_invoice: number;
  customer_name?: string;
  customer_phone?: string;
  return_date: string;
  jalali_date?: string;
  reason?: string;
  total_refund_amount: string | number;
  created_by?: number;
  created_by_name?: string;
  items: SalesReturnItem[];
}

export interface SalesReturnItem {
  id: number;
  sales_invoice_tire_item: number;
  tire: number;
  tire_name?: string;
  brand_name?: string;
  quantity: number;
  unit_price: string | number;
  unit_cost?: string | number;
  refund_amount: string | number;
}

export interface ReceiptVoucher {
  receipt_id: number;
  voucher_id?: number;
  sales_invoice: number;
  customer_name?: string;
  amount: string | number;
  payment_method: string;
  payment_method_display?: string;
  reference_number?: string;
  receipt_date: string;
  jalali_date?: string;
  is_cancelled: boolean;
  cancellation_reason?: string;
  notes?: string;
  created_by?: number;
  created_by_name?: string;
  cancelled_at?: string | null;
  cancelled_by?: number | null;
  cancelled_by_name?: string | null;
}

export interface PaymentVoucher {
  payment_id: number;
  voucher_id?: number;
  purchase_invoice: number;
  supplier_name?: string;
  amount: string | number;
  payment_method: string;
  payment_method_display?: string;
  reference_number?: string;
  payment_date: string;
  jalali_date?: string;
  is_cancelled: boolean;
  cancellation_reason?: string;
  notes?: string;
  created_by?: number;
  created_by_name?: string;
  cancelled_at?: string | null;
  cancelled_by?: number | null;
  cancelled_by_name?: string | null;
}

export interface CustomerRefundVoucher {
  refund_id: number;
  voucher_id?: number;
  sales_invoice: number;
  sales_return?: number | null;
  customer_name?: string;
  amount: string | number;
  payment_method: string;
  payment_method_display?: string;
  reference_number?: string | null;
  refund_date: string;
  jalali_date?: string;
  is_cancelled: boolean;
  cancellation_reason?: string;
  notes?: string;
  created_by?: number;
  created_by_name?: string;
  cancelled_at?: string | null;
  cancelled_by?: number | null;
  cancelled_by_name?: string | null;
}

export interface DashboardStats {
  today_revenue: number;
  today_invoices_count: number;
  total_receivables: number;
  unpaid_invoices_count: number;
  total_inventory_value: number;
  total_tires_stock: number;
  low_stock_count: number;
}

export interface BrandSalesStat {
  brand_name: string;
  total_quantity: number;
  total_revenue: number;
}

export interface ProfitabilityStat {
  tire_id: number;
  tire_name: string;
  brand_name: string;
  size_name: string;
  total_sold: number;
  total_revenue: number;
  total_cost: number;
  total_profit: number;
}
