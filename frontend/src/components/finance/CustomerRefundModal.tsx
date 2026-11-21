import React, { useEffect, useRef, useState } from 'react';
import { X, RotateCcw, AlertCircle } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { useAuth } from '../../context/AuthContext';
import { financeApi } from '../../api/finance';
import { invoicesApi } from '../../api/invoices';
import { SalesInvoice, PaymentMethod } from '../../types';
import { formatCurrency, truncateToTwoDecimals } from '../../utils/formatters';
import { parseApiError } from '../../utils/errorParser';
import { fetchAllPages } from '../../utils/invoiceRequests';
import { PAYMENT_METHOD_OPTIONS } from '../../utils/i18n';
import { Modal } from '../ui/Modal';

interface CustomerRefundModalProps {
  isOpen: boolean;
  salesInvoice?: SalesInvoice | null;
  onClose: () => void;
  onSuccess: () => void;
}

function getDefaultRefundAmount(invoice?: SalesInvoice | null): string {
  if (!invoice) return '0';
  return truncateToTwoDecimals(invoice.excess_amount ?? 0);
}

export const CustomerRefundModal: React.FC<CustomerRefundModalProps> = ({
  isOpen,
  salesInvoice = null,
  onClose,
  onSuccess,
}) => {
  const { t, language } = useLanguage();
  const { currencyUnit } = useAuth();

  const [availableInvoices, setAvailableInvoices] = useState<SalesInvoice[]>([]);
  const [loadingInvoices, setLoadingInvoices] = useState<boolean>(false);
  const [invoicesErrorCause, setInvoicesErrorCause] = useState<{ error: unknown } | null>(null);
  const [invoicesRetryToken, setInvoicesRetryToken] = useState<number>(0);

  const [selectedInvoiceId, setSelectedInvoiceId] = useState<number | ''>(
    () => salesInvoice?.sales_invoice_id ?? '',
  );
  const [amount, setAmount] = useState<string>(() => getDefaultRefundAmount(salesInvoice));
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('POS');
  const [referenceNumber, setReferenceNumber] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const submitBusy = useRef(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setSelectedInvoiceId(salesInvoice?.sales_invoice_id ?? '');
    setAmount(getDefaultRefundAmount(salesInvoice));
    setPaymentMethod('POS');
    setReferenceNumber('');
    setNotes('');
    setErrorMessage(null);
    setInvoicesErrorCause(null);
  }, [isOpen, salesInvoice]);

  useEffect(() => {
    if (!isOpen || salesInvoice) {
      setAvailableInvoices([]);
      setLoadingInvoices(false);
      setInvoicesErrorCause(null);
      return;
    }

    let active = true;
    setLoadingInvoices(true);
    setInvoicesErrorCause(null);

    const loadRefundableSales = async () => {
      try {
        const confirmed = await fetchAllPages(
          (page) => invoicesApi.getSalesInvoices({ status: 'CONFIRMED', page, page_size: 100 }),
          () => active,
          language,
        );
        if (!active) return;
        setAvailableInvoices(
          confirmed.filter((inv) => parseFloat(String(inv.excess_amount ?? 0)) > 0),
        );
      } catch (error) {
        if (active) setInvoicesErrorCause({ error });
      } finally {
        if (active) setLoadingInvoices(false);
      }
    };

    void loadRefundableSales();
    return () => {
      active = false;
    };
  }, [isOpen, salesInvoice, invoicesRetryToken, language]);

  if (!isOpen) return null;

  const activeInvoice =
    salesInvoice ??
    availableInvoices.find((inv) => inv.sales_invoice_id === selectedInvoiceId) ??
    null;

  const invoicesLoadError = invoicesErrorCause
    ? parseApiError(invoicesErrorCause.error, t("خطا در دریافت فاکتورهای دارای مازاد قابل استرداد"), language)
    : null;

  const handleInvoiceSelect = (rawId: string) => {
    const id = rawId ? Number(rawId) : '';
    setSelectedInvoiceId(id);
    const chosen = availableInvoices.find((inv) => inv.sales_invoice_id === id) ?? null;
    setAmount(getDefaultRefundAmount(chosen));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitBusy.current) return;

    const targetInvoiceId = salesInvoice?.sales_invoice_id ?? selectedInvoiceId;
    if (!targetInvoiceId) {
      setErrorMessage(t("لطفاً فاکتور فروش را انتخاب فرمایید."));
      return;
    }

    const numericAmount = parseFloat(amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setErrorMessage(t("مبلغ استردادی باید عددی مثبت و بزرگ‌تر از صفر باشد."));
      return;
    }

    submitBusy.current = true;
    setSubmitting(true);
    setErrorMessage(null);
    try {
      await financeApi.createCustomerRefund({
        sales_invoice: Number(targetInvoiceId),
        amount: numericAmount,
        payment_method: paymentMethod,
        reference_number: referenceNumber.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, t("خطا در ثبت سند استرداد وجه"), language));
    } finally {
      submitBusy.current = false;
      setSubmitting(false);
    }
  };

  const selectorBlocked =
    !salesInvoice && (loadingInvoices || Boolean(invoicesLoadError) || availableInvoices.length === 0);

  return (
    <Modal label={t("ثبت سند استرداد وجه به مشتری")} onClose={onClose} busy={submitting} className="max-w-md">
      <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 w-full overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
          <div className="flex items-center gap-2">
            <RotateCcw className="w-5 h-5 text-amber-600 dark:text-amber-400" />
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
              {t("ثبت سند استرداد وجه به مشتری")}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label={t("بستن")}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {!salesInvoice && (
            <div className="space-y-1.5">
              <label htmlFor="refund-sales-invoice" className="font-bold text-slate-700 dark:text-slate-300 block">
                {t("انتخاب فاکتور فروش:")}
              </label>
              {loadingInvoices ? (
                <div role="status" className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl text-slate-500">
                  {t("در حال دریافت فاکتورهای دارای مازاد قابل استرداد...")}
                </div>
              ) : invoicesLoadError ? (
                <div role="alert" className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl flex items-center justify-between gap-2">
                  <span>{invoicesLoadError}</span>
                  <button
                    type="button"
                    onClick={() => setInvoicesRetryToken((v) => v + 1)}
                    className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-semibold shrink-0"
                  >
                    {t("تلاش مجدد")}
                  </button>
                </div>
              ) : availableInvoices.length === 0 ? (
                <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl text-slate-500">
                  {t("هیچ فاکتوری با مازاد قابل استرداد یافت نشد.")}
                </div>
              ) : (
                <select
                  id="refund-sales-invoice"
                  value={selectedInvoiceId}
                  onChange={(e) => handleInvoiceSelect(e.target.value)}
                  required
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-amber-500 outline-none"
                >
                  <option value="">{t("انتخاب فاکتور فروش...")}</option>
                  {availableInvoices.map((inv) => (
                    <option key={inv.sales_invoice_id} value={inv.sales_invoice_id}>
                      {inv.invoice_number} — {inv.customer_name} ({formatCurrency(inv.excess_amount ?? 0, true, currencyUnit, language)})
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {activeInvoice && (
            <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-800 space-y-1">
              <p className="font-bold text-slate-900 dark:text-white">
                {t("فاکتور فروش:")} <bdi dir="auto">{activeInvoice.invoice_number}</bdi>
              </p>
              <p className="text-slate-500">
                {t("مشتری:")} <bdi dir="auto">{activeInvoice.customer_name}</bdi>
              </p>
              <p className="text-slate-700 dark:text-slate-300">
                {t("مازاد قابل استرداد:")}{' '}
                <span className="font-bold text-amber-600 dark:text-amber-400">
                  {formatCurrency(activeInvoice.excess_amount ?? 0, true, currencyUnit, language)}
                </span>
              </p>
            </div>
          )}

          {errorMessage && (
            <div role="alert" className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="refund-amount" className="font-bold text-slate-700 dark:text-slate-300 block">
              {t("مبلغ استردادی (ریال):")}
            </label>
            <input
              id="refund-amount"
              type="number"
              min={0.01}
              step="any"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-bold text-sm text-end focus:ring-2 focus:ring-amber-500 outline-none tabular-nums"
            />
            <p className="text-[11px] text-slate-400">
              {t("معادل:")}{' '}
              <span className="font-bold text-slate-600 dark:text-slate-200">
                {formatCurrency(amount, true, 'toman', language)}
              </span>
            </p>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="refund-method" className="font-bold text-slate-700 dark:text-slate-300 block">
              {t("روش استرداد وجه:")}
            </label>
            <select
              id="refund-method"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-amber-500 outline-none"
            >
              {PAYMENT_METHOD_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{t(option.labelKey)}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="refund-reference" className="font-bold text-slate-700 dark:text-slate-300 block">
              {t("شماره پیگیری / شماره ارجاع تراکنش:")}
            </label>
            <input
              id="refund-reference"
              type="text"
              value={referenceNumber}
              onChange={(e) => setReferenceNumber(e.target.value)}
              placeholder={t("مثلاً: 1234567890")}
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-amber-500 outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="refund-notes" className="font-bold text-slate-700 dark:text-slate-300 block">
              {t("توضیحات و بابت:")}
            </label>
            <input
              id="refund-notes"
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("مثلاً: استرداد مازاد پرداختی مشتری...")}
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-amber-500 outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
            >
              {t("انصراف")}
            </button>
            <button
              type="submit"
              disabled={submitting || selectorBlocked}
              className="px-5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-semibold shadow-sm transition-colors disabled:opacity-50"
            >
              {submitting ? t("در حال ثبت...") : t("ثبت سند استرداد")}
            </button>
          </div>
        </form>
      </div>
    </Modal>
  );
};
