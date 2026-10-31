import React, { useRef, useState } from 'react';
import { X, Coins } from 'lucide-react';
import { financeApi } from '../../api/finance';
import { SalesInvoice } from '../../types';
import { formatCurrency } from '../../utils/formatters';
import { useAuth } from '../../context/AuthContext';
import { parseApiError } from '../../utils/errorParser';

interface ReceiptModalProps {
  invoice: SalesInvoice | null;
  onClose: () => void;
  onSuccess: () => void;
}

export const ReceiptModal: React.FC<ReceiptModalProps> = ({
  invoice,
  onClose,
  onSuccess,
}) => {
  const { currencyUnit } = useAuth();
  const rawAmount = invoice
    ? (invoice.remaining_amount !== undefined && invoice.remaining_amount !== null && String(invoice.remaining_amount).trim() !== ''
        ? invoice.remaining_amount
        : invoice.net_amount || invoice.total_amount || 0)
    : 0;
  const defaultAmount = Math.max(0, Math.round(parseFloat(String(rawAmount)) || 0));
  
  const [amount, setAmount] = useState<string>(defaultAmount.toString());
  const [paymentMethod, setPaymentMethod] = useState<'POS' | 'CASH' | 'CARD_TO_CARD' | 'CHEQUE'>('POS');
  const [referenceNumber, setReferenceNumber] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const submitBusy = useRef(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  React.useEffect(() => {
    if (invoice) {
      const raw = invoice.remaining_amount !== undefined && invoice.remaining_amount !== null && String(invoice.remaining_amount).trim() !== ''
        ? invoice.remaining_amount
        : invoice.net_amount || invoice.total_amount || 0;
      const def = Math.max(0, Math.round(parseFloat(String(raw)) || 0));
      // oxlint-disable-next-line react/set-state-in-effect -- A changed invoice resets the editable suggested receipt amount.
      setAmount(def.toString());
    }
  }, [invoice]);

  if (!invoice) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitBusy.current) return;
    const numericAmount = parseFloat(amount);
    if (isNaN(numericAmount) || numericAmount <= 0) {
      setErrorMessage('مبلغ دریافت وجه باید عددی مثبت و بزرگ‌تر از صفر باشد.');
      return;
    }

    submitBusy.current = true;
    setSubmitting(true);
    setErrorMessage(null);
    try {
      await financeApi.createReceipt({
        sales_invoice: invoice.sales_invoice_id,
        amount: numericAmount,
        payment_method: paymentMethod,
        reference_number: referenceNumber.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, 'خطا در ثبت سند دریافت وجه'));
    } finally {
      submitBusy.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
          <div className="flex items-center gap-2">
            <Coins className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
              ثبت سند دریافت وجه از مشتری
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-800 space-y-1">
            <p className="font-bold text-slate-900 dark:text-white">
              فاکتور فروش: {invoice.invoice_number}
            </p>
            <p className="text-slate-500">
              مشتری: {invoice.customer_name} ({invoice.customer_phone})
            </p>
            <p className="text-slate-700 dark:text-slate-300">
              مبلغ خالص فاکتور: <span className="font-bold text-brand-600">{formatCurrency(invoice.net_amount || invoice.total_amount, true, currencyUnit)}</span>
            </p>
            {invoice.remaining_amount !== undefined && invoice.remaining_amount !== null && (
              <p className="text-slate-700 dark:text-slate-300">
                مانده بدهی فاکتور: <span className="font-bold text-rose-600 dark:text-rose-400">{formatCurrency(invoice.remaining_amount, true, currencyUnit)}</span>
              </p>
            )}
          </div>

          {errorMessage && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl">
              {errorMessage}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="font-bold text-slate-700 dark:text-slate-300 block">
              مبلغ دریافتی (ریال):
            </label>
            <input
              type="number"
              min={1}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-bold text-sm text-left focus:ring-2 focus:ring-emerald-500 outline-none tabular-nums"
            />
            <p className="text-[11px] text-slate-400">
              معادل: <span className="font-bold text-slate-600 dark:text-slate-200">{formatCurrency(amount, true, 'toman')}</span>
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="font-bold text-slate-700 dark:text-slate-300 block">
              روش دریافت وجه:
            </label>
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as any)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-emerald-500 outline-none"
            >
              <option value="POS">کارتخوان بانکی (POS)</option>
              <option value="CASH">وجه نقد (صندوق)</option>
              <option value="CARD_TO_CARD">کارت‌به‌کارت / حواله پایا</option>
              <option value="CHEQUE">چک صیادی بانکی</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="font-bold text-slate-700 dark:text-slate-300 block">
              شماره پیگیری / شماره ارجاع تراکنش:
            </label>
            <input
              type="text"
              value={referenceNumber}
              onChange={(e) => setReferenceNumber(e.target.value)}
              placeholder="مثلاً: 1234567890"
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-emerald-500 outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label className="font-bold text-slate-700 dark:text-slate-300 block">
              توضیحات و بابت:
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="مثلاً: بیعانه اولیه، تسویه نهایی..."
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-emerald-500 outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              انصراف
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-semibold shadow-sm transition-colors"
            >
              {submitting ? 'در حال ثبت...' : 'ثبت سند دریافت'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
