import React, { useState } from 'react';
import { X, SlidersHorizontal, AlertCircle } from 'lucide-react';
import { Tire } from '../../types';
import { catalogApi } from '../../api/catalog';
import { parseApiError } from '../../utils/errorParser';

interface StockAdjustmentModalProps {
  tire: Tire | null;
  onClose: () => void;
  onSuccess: () => void;
}

export const StockAdjustmentModal: React.FC<StockAdjustmentModalProps> = ({
  tire,
  onClose,
  onSuccess,
}) => {
  const [countedQty, setCountedQty] = useState<number>(tire?.stock_quantity ?? 0);
  const [reason, setReason] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!tire) return null;

  const diff = countedQty - tire.stock_quantity;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setErrorMessage('ثبت دلیل یا شرح انبارگردانی الزامی است.');
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    try {
      await catalogApi.adjustStock(tire.tire_id, {
        counted_quantity: countedQty,
        reason: reason.trim(),
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, 'خطا در ثبت اصلاحیه موجودی انبار'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5 text-brand-600 dark:text-brand-400" />
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
              انبارگردانی و اصلاح موجودی تایر
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
            <p className="font-bold text-slate-900 dark:text-white text-sm">{tire.tire_name}</p>
            <p className="text-slate-500">
              برند: {tire.brand_name} | سایز: {tire.size_name}
            </p>
            <p className="text-slate-700 dark:text-slate-300">
              موجودی سیستمی فعلی: <span className="font-bold text-brand-600">{tire.stock_quantity} حلقه</span>
            </p>
          </div>

          {errorMessage && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="font-bold text-slate-700 dark:text-slate-300 block">
              موجودی واقعی شمارش‌شده در انبار (حلقه):
            </label>
            <input
              type="number"
              min={0}
              value={countedQty}
              onChange={(e) => setCountedQty(parseInt(e.target.value) || 0)}
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-center text-sm font-bold focus:ring-2 focus:ring-brand-500 outline-none"
            />
          </div>

          <div className="flex items-center justify-between p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-[11px]">
            <span className="text-slate-500">مغایرت موجودی انبار:</span>
            <span
              className={`font-black tabular-nums ${
                diff > 0
                  ? 'text-emerald-600'
                  : diff < 0
                  ? 'text-rose-600'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              {diff > 0 ? `+${diff} (مازاد انبار)` : diff < 0 ? `${diff} (کسری انبار)` : 'بدون تغییر (تطابق کامل)'}
            </span>
          </div>

          <div className="space-y-1.5">
            <label className="font-bold text-slate-700 dark:text-slate-300 block">
              دلیل / شرح انبارگردانی (الزامی):
            </label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="مثلاً: انبارگردانی پایان دوره، کشف خطای شمارش قبلی..."
              required
              className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-brand-500 outline-none text-xs"
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
              className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm transition-colors"
            >
              {submitting ? 'در حال اصلاح...' : 'ثبت قطعی اصلاحیه'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
