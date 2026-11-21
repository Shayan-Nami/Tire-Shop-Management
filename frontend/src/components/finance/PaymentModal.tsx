import React, { useEffect, useRef, useState } from 'react';
import { X, CreditCard, AlertCircle } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { useAuth } from '../../context/AuthContext';
import { financeApi } from '../../api/finance';
import { invoicesApi } from '../../api/invoices';
import { PurchaseInvoice, PaymentMethod } from '../../types';
import { formatCurrency, truncateToTwoDecimals } from '../../utils/formatters';
import { parseApiError } from '../../utils/errorParser';
import { fetchAllPages } from '../../utils/invoiceRequests';
import { Modal } from '../ui/Modal';

interface PaymentModalProps {
  isOpen: boolean;
  purchaseInvoice?: PurchaseInvoice | null;
  onClose: () => void;
  onSuccess: () => void;
}

function getDefaultPaymentAmount(invoice?: PurchaseInvoice | null): string {
  if (!invoice) return '0';
  const raw =
    invoice.remaining_amount !== undefined &&
    invoice.remaining_amount !== null &&
    String(invoice.remaining_amount).trim() !== ''
      ? invoice.remaining_amount
      : invoice.total_amount ?? 0;
  return truncateToTwoDecimals(raw);
}

export const PaymentModal: React.FC<PaymentModalProps> = ({
  isOpen,
  purchaseInvoice = null,
  onClose,
  onSuccess,
}) => {
  const { t, language } = useLanguage();
  const { currencyUnit } = useAuth();

  const [availableInvoices, setAvailableInvoices] = useState<PurchaseInvoice[]>([]);
  const [loadingInvoices, setLoadingInvoices] = useState<boolean>(false);
  const [invoicesErrorCause, setInvoicesErrorCause] = useState<{ error: unknown } | null>(null);
  const [invoicesRetryToken, setInvoicesRetryToken] = useState<number>(0);

  const [selectedInvoiceId, setSelectedInvoiceId] = useState<number | ''>(
    () => purchaseInvoice?.purchase_invoice_id ?? '',
  );
  const [amount, setAmount] = useState<string>(() => getDefaultPaymentAmount(purchaseInvoice));
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('BANK_TRANSFER');
  const [referenceNumber, setReferenceNumber] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const submitBusy = useRef(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setSelectedInvoiceId(purchaseInvoice?.purchase_invoice_id ?? '');
    setAmount(getDefaultPaymentAmount(purchaseInvoice));
    setPaymentMethod('BANK_TRANSFER');
    setReferenceNumber('');
    setNotes('');
    setErrorMessage(null);
    setInvoicesErrorCause(null);
  }, [isOpen, purchaseInvoice]);

  useEffect(() => {
    if (!isOpen || purchaseInvoice) {
      setAvailableInvoices([]);
      setLoadingInvoices(false);
      setInvoicesErrorCause(null);
      return;
    }

    let active = true;
    setLoadingInvoices(true);
    setInvoicesErrorCause(null);

    const loadUnpaidPurchases = async () => {
      try {
        const confirmed = await fetchAllPages(
          (page) => invoicesApi.getPurchaseInvoices({ status: 'CONFIRMED', page, page_size: 100 }),
          () => active,
          language,
        );
        if (!active) return;
        setAvailableInvoices(
          confirmed.filter((inv) => inv.status === 'CONFIRMED' && inv.payment_status !== 'PAID'),
        );
      } catch (error) {
        if (active) setInvoicesErrorCause({ error });
      } finally {
        if (active) setLoadingInvoices(false);
      }
    };

    void loadUnpaidPurchases();
    return () => {
      active = false;
    };
  }, [isOpen, purchaseInvoice, invoicesRetryToken, language]);

  if (!isOpen) return null;

  const activeInvoice =
    purchaseInvoice ??
    availableInvoices.find((inv) => inv.purchase_invoice_id === selectedInvoiceId) ??
    null;

  const invoicesLoadError = invoicesErrorCause
    ? parseApiError(invoicesErrorCause.error, t("خطا در دریافت فاکتورهای خرید تسویه‌نشده"), language)
    : null;

  const handleInvoiceSelect = (rawId: string) => {
    const id = rawId ? Number(rawId) : '';
    setSelectedInvoiceId(id);
    const chosen = availableInvoices.find((inv) => inv.purchase_invoice_id === id) ?? null;
    setAmount(getDefaultPaymentAmount(chosen));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitBusy.current) return;

    const targetInvoiceId = purchaseInvoice?.purchase_invoice_id ?? selectedInvoiceId;
    if (!targetInvoiceId) {
      setErrorMessage(t("لطفاً فاکتور خرید را انتخاب فرمایید."));
      return;
    }

    const numericAmount = parseFloat(amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setErrorMessage(t("مبلغ پرداختی باید عددی مثبت و بزرگ‌تر از صفر باشد."));
      return;
    }

    submitBusy.current = true;
    setSubmitting(true);
    setErrorMessage(null);
    try {
      await financeApi.createPayment({
        purchase_invoice: Number(targetInvoiceId),
        amount: numericAmount,
        payment_method: paymentMethod,
        reference_number: referenceNumber.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, t("خطا در ثبت سند پرداخت به تأمین‌کننده"), language));
    } finally {
      submitBusy.current = false;
      setSubmitting(false);
    }
  };

  const selectorBlocked =
    !purchaseInvoice && (loadingInvoices || Boolean(invoicesLoadError) || availableInvoices.length === 0);

  return (
    <Modal label={t("ثبت سند پرداخت به تأمین‌کننده")} onClose={onClose} busy={submitting} className="max-w-md">
      <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 w-full overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
          <div className="flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-brand-600 dark:text-brand-400" />
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
              {t("ثبت سند پرداخت به تأمین‌کننده")}
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
          {!purchaseInvoice && (
            <div className="space-y-1.5">
              <label htmlFor="payment-purchase-invoice" className="font-bold text-slate-700 dark:text-slate-300 block">
                {t("انتخاب فاکتور خرید:")}
              </label>
              {loadingInvoices ? (
                <div role="status" className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl text-slate-500">
                  {t("در حال دریافت فاکتورهای خرید تسویه‌نشده...")}
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
                  {t("هیچ فاکتور خرید تسویه‌نشده‌ای یافت نشد.")}
                </div>
              ) : (
                <select
                  id="payment-purchase-invoice"
                  value={selectedInvoiceId}
                  onChange={(e) => handleInvoiceSelect(e.target.value)}
                  required
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
                >
                  <option value="">{t("انتخاب فاکتور خرید...")}</option>
                  {availableInvoices.map((inv) => (
                    <option key={inv.purchase_invoice_id} value={inv.purchase_invoice_id}>
                      {inv.invoice_number} — {inv.supplier_name} ({formatCurrency(inv.remaining_amount ?? inv.total_amount, true, currencyUnit, language)})
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {activeInvoice && (
            <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-slate-200 dark:border-slate-800 space-y-1">
              <p className="font-bold text-slate-900 dark:text-white">
                {t("فاکتور خرید:")} <bdi dir="auto">{activeInvoice.invoice_number}</bdi>
              </p>
              <p className="text-slate-500">
                {t("تأمین‌کننده:")} <bdi dir="auto">{activeInvoice.supplier_name}</bdi>
              </p>
              <p className="text-slate-700 dark:text-slate-300">
                {t("مبلغ کل فاکتور:")}{' '}
                <span className="font-bold text-brand-600">
                  {formatCurrency(activeInvoice.total_amount, true, currencyUnit, language)}
                </span>
              </p>
              {activeInvoice.remaining_amount !== undefined && activeInvoice.remaining_amount !== null && (
                <p className="text-slate-700 dark:text-slate-300">
                  {t("مانده بدهی فاکتور:")}{' '}
                  <span className="font-bold text-rose-600 dark:text-rose-400">
                    {formatCurrency(activeInvoice.remaining_amount, true, currencyUnit, language)}
                  </span>
                </p>
              )}
            </div>
          )}

          {errorMessage && (
            <div role="alert" className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="payment-amount" className="font-bold text-slate-700 dark:text-slate-300 block">
              {t("مبلغ پرداختی (ریال):")}
            </label>
            <input
              id="payment-amount"
              type="number"
              min={0.01}
              step="any"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-bold text-sm text-end focus:ring-2 focus:ring-brand-500 outline-none tabular-nums"
            />
            <p className="text-[11px] text-slate-400">
              {t("معادل:")}{' '}
              <span className="font-bold text-slate-600 dark:text-slate-200">
                {formatCurrency(amount, true, 'toman', language)}
              </span>
            </p>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="payment-method" className="font-bold text-slate-700 dark:text-slate-300 block">
              {t("روش پرداخت:")}
            </label>
            <select
              id="payment-method"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
            >
              <option value="BANK_TRANSFER">{t("انتقال بانکی / حواله")}</option>
              <option value="CHEQUE">{t("چک صیادی بانکی")}</option>
              <option value="CASH">{t("وجه نقد (صندوق)")}</option>
              <option value="POS">{t("کارتخوان بانکی (POS)")}</option>
              <option value="CARD_TO_CARD">{t("کارت به کارت")}</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="payment-reference" className="font-bold text-slate-700 dark:text-slate-300 block">
              {t("شماره پیگیری / شماره ارجاع تراکنش:")}
            </label>
            <input
              id="payment-reference"
              type="text"
              value={referenceNumber}
              onChange={(e) => setReferenceNumber(e.target.value)}
              placeholder={t("مثلاً: 1234567890")}
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="payment-notes" className="font-bold text-slate-700 dark:text-slate-300 block">
              {t("توضیحات و بابت:")}
            </label>
            <input
              id="payment-notes"
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("مثلاً: تسویه فاکتور خرید...")}
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
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
              className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm transition-colors disabled:opacity-50"
            >
              {submitting ? t("در حال ثبت...") : t("ثبت سند پرداخت")}
            </button>
          </div>
        </form>
      </div>
    </Modal>
  );
};
