import type {
  Customer, Supplier, StockMovement, SalesInvoice, PurchaseInvoiceTireItem,
  SalesReturn, ReceiptVoucher, PaymentVoucher, CustomerRefundVoucher,
  InventoryValueResponse, SalesByDateRangeResponse,
} from '../src/types/index.ts';
import type { CreateSalesInvoicePayload, CreateSalesReturnPayload } from '../src/api/invoices.ts';
import type { crmApi } from '../src/api/crm.ts';
import type { suppliersApi } from '../src/api/suppliers.ts';
import type { reportsApi } from '../src/api/reports.ts';

export const customer: Customer = { customer_id: 1, full_name: 'Customer', phone_number: null, national_code: null, address: null };
export const supplier: Supplier = { supplier_id: 1, supplier_name: 'Supplier', phone_number: null, address: null };
export const customerInput: Parameters<typeof crmApi.createCustomer>[0] = { full_name: 'Customer', phone_number: null, national_code: null, address: null };
export const customerWithoutPhone: Parameters<typeof crmApi.createCustomer>[0] = { full_name: 'Customer' };
export const supplierInput: Parameters<typeof suppliersApi.createSupplier>[0] = { supplier_name: 'Supplier', phone_number: null, address: null };
export const movementNulls: Pick<StockMovement, 'unit_cost' | 'user'> = { unit_cost: null, user: null };
export const invoiceNulls: Pick<SalesInvoice, 'customer_phone' | 'vehicle' | 'created_by'> = { customer_phone: null, vehicle: null, created_by: null };
export const returnNulls: Pick<SalesReturn, 'customer_phone' | 'created_by'> = { customer_phone: null, created_by: null };
export const receiptNulls: Pick<ReceiptVoucher, 'reference_number' | 'created_by'> = { reference_number: null, created_by: null };
export const paymentNulls: Pick<PaymentVoucher, 'reference_number' | 'created_by'> = { reference_number: null, created_by: null };
export const refundNulls: Pick<CustomerRefundVoucher, 'sales_return' | 'reference_number' | 'created_by'> = { sales_return: null, reference_number: null, created_by: null };

export const purchaseItem: PurchaseInvoiceTireItem = { id: 1, tire: 2, tire_name: 'Tire', quantity: 4, unit_cost: '100.00' };
// @ts-expect-error
void purchaseItem.total_cost;
// @ts-expect-error
void purchaseItem.brand_name;
// @ts-expect-error
void purchaseItem.size_name;

export const invoiceInput: CreateSalesInvoicePayload = { customer: 1, vehicle: 2, tire_items: [], payment_status: 'UNPAID' };
// @ts-expect-error
export const partialCreation: CreateSalesInvoicePayload['payment_status'] = 'PARTIAL';
export const partialResponse: SalesInvoice['payment_status'] = 'PARTIAL';
export const returnInput: CreateSalesReturnPayload = { sales_invoice: 1, items: [{ sales_invoice_tire_item_id: 1, quantity: 1 }], reason: 'Wrong size' };
// @ts-expect-error
export const returnWithoutReason: CreateSalesReturnPayload = { sales_invoice: 1, items: [] };

export const dateReport: SalesByDateRangeResponse = {
  total_invoices: 0, total_sales_amount: -100, gross_sales_amount: 0, total_refund_amount: 100,
  start_date: null, end_date: null,
};
export const datedReport: SalesByDateRangeResponse = { ...dateReport, start_date: '2026-01-01', end_date: '2026-01-31' };
export const inventoryReport: InventoryValueResponse = {
  total_inventory_value: 400,
  items: [{ tire_id: 1, tire_name: 'Tire', brand_name: 'Brand', size_name: 'Size', stock_quantity: 4, purchase_price: 100, inventory_value: 400 }],
};
export const dateApiResponse: Awaited<ReturnType<typeof reportsApi.getSalesByDateRange>> = dateReport;
export const inventoryApiResponse: Awaited<ReturnType<typeof reportsApi.getInventoryValue>> = inventoryReport;
// @ts-expect-error
export const incompleteDateReport: Awaited<ReturnType<typeof reportsApi.getSalesByDateRange>> = { total_invoices: 0, total_sales_amount: 0 };
// @ts-expect-error
export const requiredPhone: string = customer.phone_number;
