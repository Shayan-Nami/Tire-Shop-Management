import { useLanguage } from '../../context/LanguageContext';
import React, { useEffect, useRef, useState } from 'react';
import { X, RotateCcw, AlertTriangle } from 'lucide-react';
import { SalesInvoice, PaymentMethod } from '../../types';
import { invoicesApi } from '../../api/invoices';
import { formatCurrency } from '../../utils/formatters';
import { useAuth } from '../../context/AuthContext';
import { parseApiError } from '../../utils/errorParser';
import { PAYMENT_METHOD_OPTIONS } from '../../utils/i18n';
import { Modal } from '../ui/Modal';

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
  const { t, language } = useLanguage();
  const { currencyUnit } = useAuth();
  const [returnItems, setReturnItems] = useState<{ [itemId: number]: number }>({});
  const [returnedByItem, setReturnedByItem] = useState<Record<number, number>>({});
  const [loadingReturns, setLoadingReturns] = useState<boolean>(false);
  const [returnsErrorCause, setReturnsErrorCause] = useState<{ error: unknown } | null>(null);
  const [returnsRetryToken, setReturnsRetryToken] = useState<number>(0);
  const [reason, setReason] = useState<string>('');
  const [autoRefund, setAutoRefund] = useState<boolean>(true);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('POS');
  const [referenceNumber, setReferenceNumber] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const submitBusy = useRef(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const activeInvoiceId = invoice?.sales_invoice_id ?? null;
  const canFetchPriorReturns = typeof invoicesApi.getSalesReturns === 'function';

  useEffect(() => {
    setReturnItems({});
    setReason('');
    setAutoRefund(true);
    setPaymentMethod('POS');
    setReferenceNumber('');
    setErrorMessage(null);
    setReturnedByItem({});
    setReturnsErrorCause(null);

    if (activeInvoiceId === null || !canFetchPriorReturns) {
      setLoadingReturns(false);
      return;
    }

    let active = true;
    setLoadingReturns(true);

    const loadPriorReturns = async () => {
      try {
        const totals: Record<number, number> = {};
        for (let page = 1; ; page += 1) {
          if (!active) return;
          const response = await invoicesApi.getSalesReturns({
            sales_invoice: activeInvoiceId,
            page,
            page_size: 100,
          });
          if (!active) return;

          const records = response.results || [];
          for (const ret of records) {
            if (ret.sales_invoice !== activeInvoiceId) continue;
            for (const retItem of ret.items || []) {
              totals[retItem.sales_invoice_tire_item] =
                (totals[retItem.sales_invoice_tire_item] || 0) + retItem.quantity;
            }
          }

          const hasMore = Boolean(response.next) || page < (response.total_pages || 1);
          if (!hasMore || records.length === 0) break;
        }
        if (active) {
          setReturnedByItem(totals);
        }
      } catch (err: unknown) {
        if (active) {
          setReturnsErrorCause({ error: err });
        }
      } finally {
        if (active) {
          setLoadingReturns(false);
        }
      }
    };

    void loadPriorReturns();
    return () => {
      active = false;
    };
  }, [activeInvoiceId, canFetchPriorReturns, returnsRetryToken]);

  if (!invoice) return null;

  const returnsLoadError = returnsErrorCause
    ? parseApiError(returnsErrorCause.error, t("خطا در دریافت سوابق مرجوعی فاکتور"), language)
    : null;

  const getRemainingQty = (itemId: number, purchasedQty: number): number =>
    Math.max(0, purchasedQty - (returnedByItem[itemId] || 0));

  const totalRemainingQty = invoice.tire_items.reduce(
    (sum, item) => sum + getRemainingQty(item.id, item.quantity),
    0
  );

  const handleQtyChange = (itemId: number, qty: number, maxQty: number) => {
    const val = Math.max(0, Math.min(qty, maxQty));
    setReturnItems((prev) => ({
      ...prev,
      [itemId]: val,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitBusy.current || loadingReturns) return;
    setErrorMessage(null);

    const remainingById = new Map(
      invoice.tire_items.map((item) => [item.id, getRemainingQty(item.id, item.quantity)])
    );

    const itemsToReturn = Object.entries(returnItems)
      .map(([itemId, qty]) => {
        const numericId = Number(itemId);
        const maxRemaining = remainingById.get(numericId) ?? 0;
        return {
          sales_invoice_tire_item_id: numericId,
          quantity: Math.min(qty, maxRemaining),
        };
      })
      .filter((item) => item.quantity > 0);

    if (itemsToReturn.length === 0) {
      setErrorMessage(t("حداقل باید یک حلقه تایر را برای مرجوعی انتخاب فرمایید."));
      return;
    }

    if (!reason.trim()) {
      setErrorMessage(t("ثبت علت مرجوعی کالا الزامی است."));
      return;
    }

    submitBusy.current = true;
    setSubmitting(true);
    try {
      await invoicesApi.createSalesReturn({
        sales_invoice: invoice.sales_invoice_id,
        items: itemsToReturn,
        reason: reason.trim(),
        auto_refund: autoRefund,
        ...(autoRefund
          ? {
              payment_method: paymentMethod,
              reference_number: referenceNumber.trim() || undefined,
            }
          : {}),
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, t("خطا در ثبت سند مرجوعی کالا"), language));
    } finally {
      submitBusy.current = false;
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!submitting) onClose();
  };

  return (
    <Modal
      label={`${t("ثبت سند مرجوعی فروش (فاکتور")} ${invoice.invoice_number})`}
      onClose={handleClose}
      busy={submitting}
    >
      <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-xl w-full overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
          <div className="flex items-center gap-2">
            <RotateCcw className="w-5 h-5 text-amber-500" />
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">{t("ثبت سند مرجوعی فروش (فاکتور")}{' '}{invoice.invoice_number})
            </h2>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={submitting}
            aria-label={t("بستن")}
            className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5 text-slate-800 dark:text-slate-200 text-sm">
          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-400 text-xs flex gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{t("کالای مرجوعی فوراً به موجودی قابل فروش در انبار اضافه می‌گردد و سهم تخفیف فاکتور بر مبلغ استردادی اعمال خواهد شد.")}</span>
          </div>

          {returnsLoadError && (
            <div role="alert" className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl text-xs flex items-center justify-between gap-2">
              <span>{returnsLoadError}</span>
              <button
                type="button"
                onClick={() => setReturnsRetryToken((prev) => prev + 1)}
                className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-semibold shrink-0"
              >
                {t("تلاش مجدد")}
              </button>
            </div>
          )}

          {errorMessage && (
            <div role="alert" className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl text-xs">
              {errorMessage}
            </div>
          )}

          <div className="space-y-3">
            <label className="text-xs font-bold text-slate-600 dark:text-slate-400 block">{t("اقلام تایر خریداری‌شده در فاکتور:")}</label>

            {invoice.tire_items.map((item) => {
              const returnedQty = returnedByItem[item.id] || 0;
              const remainingQty = getRemainingQty(item.id, item.quantity);
              const currentReturnQty = Math.min(returnItems[item.id] || 0, remainingQty);
              return (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-xs text-slate-900 dark:text-slate-100 truncate">
                      <bdi dir="auto">{item.tire_name}</bdi>
                    </p>
                    <p className="text-[11px] text-slate-500">
                      {t("خریداری‌شده:")}{item.quantity} {' '}{t("حلقه | نرخ:")} {formatCurrency(item.unit_price, true, currencyUnit, language)}
                    </p>
                    {returnedQty > 0 && (
                      <p className="text-[11px] text-amber-600 dark:text-amber-400 font-medium mt-0.5">
                        {t("مرجوع‌شده:")} {returnedQty} | {t("قابل مرجوعی:")} {remainingQty}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0 ms-3">
                    <span className="text-xs text-slate-500">{t("تعداد مرجوعی:")}</span>
                    <input
                      type="number"
                      min={0}
                      max={remainingQty}
                      disabled={loadingReturns || remainingQty === 0}
                      aria-label={t("تعداد مرجوعی:")}
                      value={currentReturnQty}
                      onChange={(e) => handleQtyChange(item.id, parseInt(e.target.value, 10) || 0, remainingQty)}
                      className="ui-field w-16 px-2 py-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-center text-xs font-bold disabled:opacity-50"
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="sales-return-reason" className="text-xs font-bold text-slate-600 dark:text-slate-400 block">{t("علت مرجوعی کالا:")}</label>
            <textarea
              id="sales-return-reason"
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={t("مثلاً: عدم تطابق سایز با رینگ خودرو...")}
              className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-amber-500 outline-none"
            />
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 space-y-3">
            <label htmlFor="sales-return-auto-refund" className="flex items-center gap-2 cursor-pointer text-xs font-bold text-slate-700 dark:text-slate-300">
              <input
                id="sales-return-auto-refund"
                type="checkbox"
                checked={autoRefund}
                onChange={(e) => setAutoRefund(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500"
              />
              <span>{t("ثبت خودکار سند استرداد وجه به مشتری")}</span>
            </label>

            {autoRefund && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label htmlFor="sales-return-payment-method" className="text-xs font-bold text-slate-600 dark:text-slate-400 block">
                    {t("روش استرداد وجه:")}
                  </label>
                  <select
                    id="sales-return-payment-method"
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
                    className="ui-field w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-amber-500 outline-none"
                  >
                    {PAYMENT_METHOD_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{t(option.labelKey)}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label htmlFor="sales-return-reference" className="text-xs font-bold text-slate-600 dark:text-slate-400 block">
                    {t("شماره پیگیری / شماره ارجاع تراکنش:")}
                  </label>
                  <input
                    id="sales-return-reference"
                    type="text"
                    value={referenceNumber}
                    onChange={(e) => setReferenceNumber(e.target.value)}
                    placeholder={t("مثلاً: 1234567890")}
                    className="ui-field w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-amber-500 outline-none"
                  />
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={handleClose}
              disabled={submitting}
              className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
            >{t("انصراف")}</button>
            <button
              type="submit"
              disabled={submitting || loadingReturns || Boolean(returnsLoadError) || totalRemainingQty === 0}
              className="px-5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
            >
              {submitting ? t("در حال ثبت...") : t("تایید و ثبت مرجوعی")}
            </button>
          </div>
        </form>
      </div>
    </Modal>
  );
};
