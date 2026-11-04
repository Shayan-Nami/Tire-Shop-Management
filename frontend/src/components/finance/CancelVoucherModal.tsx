import { useLanguage } from '../../context/LanguageContext';
import React, { useState } from 'react';
import { X, AlertCircle } from 'lucide-react';
import { parseApiError } from '../../utils/errorParser';

interface CancelVoucherModalProps {
  title: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}

export const CancelVoucherModal: React.FC<CancelVoucherModalProps> = ({
  title,
  isOpen,
  onClose,
  onConfirm,
}) => {
  const { t, language } = useLanguage();
  const [reason, setReason] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setErrorMessage(t("ثبت دلیل ابطال سند الزامی است."));
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    try {
      await onConfirm(reason.trim());
      onClose();
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, t("خطا در ابطال سند مالی"), language));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
          <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">{title}</h2>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {errorMessage && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("دلیل و انگیزه ابطال سند مالی (الزامی):")}</label>
            <textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={t("مثلاً: اشتباه در شماره ارجاع تراکنش، برگشت وجه، ثبت تکراری...")}
              required
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-rose-500 outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            >{t("انصراف")}</button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-semibold shadow-sm transition-colors"
            >
              {submitting ? t("در حال ابطال...") : t("تایید و ابطال سند")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
