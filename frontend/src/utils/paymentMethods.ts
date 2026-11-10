// Voucher payment methods: the API stores either one of these codes or legacy free text.
export type ReceiptMethod = 'POS' | 'CASH' | 'CARD_TO_CARD' | 'CHEQUE';
export type SupplierPaymentMethod = 'CASH' | 'BANK_TRANSFER' | 'CHEQUE';
export type PaymentMethodCode = ReceiptMethod | SupplierPaymentMethod;

export const PAYMENT_METHOD_LABELS: Record<PaymentMethodCode, string> = {
  POS: 'کارتخوان بانکی (POS)',
  CASH: 'وجه نقد (صندوق)',
  CARD_TO_CARD: 'کارت‌به‌کارت / حواله پایا',
  CHEQUE: 'چک صیادی بانکی',
  BANK_TRANSFER: 'حواله بانکی',
};

export const RECEIPT_METHODS: ReceiptMethod[] = ['POS', 'CASH', 'CARD_TO_CARD', 'CHEQUE'];
export const SUPPLIER_PAYMENT_METHODS: SupplierPaymentMethod[] = ['BANK_TRANSFER', 'CASH', 'CHEQUE'];

export function isPaymentMethodCode(value: unknown): value is PaymentMethodCode {
  return typeof value === 'string' && Object.hasOwn(PAYMENT_METHOD_LABELS, value);
}

/** Persian source label for a stored payment method; pass the result through t() for display. */
export function paymentMethodLabel(value?: string | null): string {
  if (!value) return '-';
  return isPaymentMethodCode(value) ? PAYMENT_METHOD_LABELS[value] : value;
}
