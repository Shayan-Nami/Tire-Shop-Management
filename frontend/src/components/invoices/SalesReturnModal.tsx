import React, { useRef, useState } from 'react';
import { X, RotateCcw, AlertTriangle } from 'lucide-react';
import { SalesInvoice } from '../../types';
import { invoicesApi } from '../../api/invoices';
import { formatCurrency } from '../../utils/formatters';
import { useAuth } from '../../context/AuthContext';
import { parseApiError } from '../../utils/errorParser';

interface SalesReturnModalProps {
  invoice: SalesInvoice | null;
  onClose: () => void;
  onSuccess: () => void;
}

export const SalesReturnModal: React.FC<SalesReturnModalProps> = ({
  invoice,
  onClose,
  onSuccess,
}) => {
  const { currencyUnit } = useAuth();
  const [returnItems, setReturnItems] = useState<{ [itemId: number]: number }>({});
  const [reason, setReason] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const submitBusy = useRef(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!invoice) return null;

  const handleQtyChange = (itemId: number, qty: number, maxQty: number) => {
    const val = Math.max(0, Math.min(qty, maxQty));
    setReturnItems((prev) => ({
      ...prev,
      [itemId]: val,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitBusy.current) return;
    setErrorMessage(null);

    const itemsToReturn = Object.entries(returnItems)
      .filter(([, qty]) => qty > 0)
      .map(([itemId, qty]) => ({
        sales_invoice_tire_item_id: Number(itemId),
        quantity: qty,
      }));

    if (itemsToReturn.length === 0) {
      setErrorMessage('حداقل باید یک حلقه تایر را برای مرجوعی انتخاب فرمایید.');
      return;
    }

    submitBusy.current = true;
    setSubmitting(true);
    try {
      await invoicesApi.createSalesReturn({
        sales_invoice: invoice.sales_invoice_id,
        items: itemsToReturn,
        reason: reason.trim() || 'مرجوعی توسط مشتری با توافق فروشگاه',
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMessage(parseApiError(err, 'خطا در ثبت سند مرجوعی کالا'));
    } finally {
      submitBusy.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-xl w-full overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
          <div className="flex items-center gap-2">
            <RotateCcw className="w-5 h-5 text-amber-500" />
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
              ثبت سند مرجوعی فروش (فاکتور {invoice.invoice_number})
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5 text-slate-800 dark:text-slate-200 text-sm">
          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-400 text-xs flex gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              کالای مرجوعی فوراً به موجودی قابل فروش در انبار اضافه می‌گردد و سهم تخفیف فاکتور بر مبلغ استردادی اعمال خواهد شد.
            </span>
          </div>

          {errorMessage && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl text-xs">
              {errorMessage}
            </div>
          )}

          <div className="space-y-3">
            <label className="text-xs font-bold text-slate-600 dark:text-slate-400 block">
              اقلام تایر خریداری‌شده در فاکتور:
            </label>

            {invoice.tire_items.map((item) => {
              const currentReturnQty = returnItems[item.id] || 0;
              return (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-xs text-slate-900 dark:text-slate-100 truncate">
                      {item.tire_name}
                    </p>
                    <p className="text-[11px] text-slate-500">
                      خریداری‌شده: {item.quantity} حلقه | نرخ: {formatCurrency(item.unit_price, true, currencyUnit)}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0 mr-3">
                    <span className="text-xs text-slate-500">تعداد مرجوعی:</span>
                    <input
                      type="number"
                      min={0}
                      max={item.quantity}
                      value={currentReturnQty}
                      onChange={(e) => handleQtyChange(item.id, parseInt(e.target.value) || 0, item.quantity)}
                      className="w-16 px-2 py-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-center text-xs font-bold"
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-600 dark:text-slate-400 block">
              علت مرجوعی کالا:
            </label>
            <textarea
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="مثلاً: عدم تطابق سایز با رینگ خودرو..."
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-amber-500 outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              انصراف
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-semibold shadow-sm transition-colors"
            >
              {submitting ? 'در حال ثبت...' : 'تایید و ثبت مرجوعی'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
