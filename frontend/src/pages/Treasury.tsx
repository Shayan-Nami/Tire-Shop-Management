import { useLanguage } from '../context/LanguageContext';
import React, { useCallback, useEffect, useState } from 'react';
import {
  ArrowDownLeft,
  ArrowUpRight,
  RotateCcw,
  Ban,
} from 'lucide-react';
import { financeApi } from '../api/finance';
import { ReceiptVoucher, PaymentVoucher, CustomerRefundVoucher } from '../types';
import { formatCurrency, formatIsoToJalali } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';
import { CancelVoucherModal } from '../components/finance/CancelVoucherModal';

export const Treasury: React.FC = () => {
  const { t, language } = useLanguage();
  const { currencyUnit, user } = useAuth();
  const [activeTab, setActiveTab] = useState<'receipts' | 'payments' | 'refunds'>('receipts');
  const [loading, setLoading] = useState<boolean>(true);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const [receipts, setReceipts] = useState<ReceiptVoucher[]>([]);
  const [payments, setPayments] = useState<PaymentVoucher[]>([]);
  const [refunds, setRefunds] = useState<CustomerRefundVoucher[]>([]);

  const [cancelModalOpen, setCancelModalOpen] = useState<boolean>(false);
  const [cancelTarget, setCancelTarget] = useState<{
    id: number;
    type: 'receipt' | 'payment' | 'refund';
    title: string;
  } | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      if (activeTab === 'receipts') {
        const res = await financeApi.getReceipts({ page: currentPage });
        setReceipts(res.results || []);
        setTotalPages(res.total_pages || 1);
        setTotalCount(res.count || 0);
      } else if (activeTab === 'payments') {
        const res = await financeApi.getPayments({ page: currentPage });
        setPayments(res.results || []);
        setTotalPages(res.total_pages || 1);
        setTotalCount(res.count || 0);
      } else {
        const res = await financeApi.getCustomerRefunds({ page: currentPage });
        setRefunds(res.results || []);
        setTotalPages(res.total_pages || 1);
        setTotalCount(res.count || 0);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [activeTab, currentPage]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleOpenCancel = (id: number, type: 'receipt' | 'payment' | 'refund', title: string) => {
    setCancelTarget({ id, type, title });
    setCancelModalOpen(true);
  };

  const handleConfirmCancel = async (reason: string) => {
    if (!cancelTarget) return;
    if (cancelTarget.type === 'receipt') {
      await financeApi.cancelReceipt(cancelTarget.id, reason);
    } else if (cancelTarget.type === 'payment') {
      await financeApi.cancelPayment(cancelTarget.id, reason);
    } else {
      await financeApi.cancelCustomerRefund(cancelTarget.id, reason);
    }
    loadData();
  };

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("خزانه‌داری و مدیریت اسناد مالی")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("دفتر دریافت وجوه نقد/کارتخوان از مشتریان، پرداخت به تأمین‌کنندگان و استرداد مازاد مرجوعی")}</p>
        </div>
      </div>

      <div className="tab-bar">
        <button
          onClick={() => {
            setActiveTab('receipts');
            setCurrentPage(1);
          }}
          className={`flex items-center gap-2 py-3 px-4 font-bold text-xs border-b-2 transition-all ${
            activeTab === 'receipts'
              ? 'border-brand-600 text-brand-600 dark:text-brand-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          <ArrowDownLeft className="w-4 h-4" />
          <span>{t("اسناد دریافت از مشتری (Receipts)")}</span>
        </button>

        <button
          onClick={() => {
            setActiveTab('payments');
            setCurrentPage(1);
          }}
          className={`flex items-center gap-2 py-3 px-4 font-bold text-xs border-b-2 transition-all ${
            activeTab === 'payments'
              ? 'border-brand-600 text-brand-600 dark:text-brand-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          <ArrowUpRight className="w-4 h-4" />
          <span>{t("اسناد پرداخت به تأمین‌کننده (Payments)")}</span>
        </button>

        <button
          onClick={() => {
            setActiveTab('refunds');
            setCurrentPage(1);
          }}
          className={`flex items-center gap-2 py-3 px-4 font-bold text-xs border-b-2 transition-all ${
            activeTab === 'refunds'
              ? 'border-brand-600 text-brand-600 dark:text-brand-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          <RotateCcw className="w-4 h-4" />
          <span>{t("اسناد استرداد وجه به مشتری (Customer Refunds)")}</span>
        </button>
      </div>

      <div className="surface-panel overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("در حال بارگذاری اسناد مالی...")}</div>
        ) : activeTab === 'receipts' ? (
          receipts.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-400">{t("هیچ سند دریافتی ثبت نشده است.")}</div>
          ) : (
            <div className="table-scroll overflow-x-auto">
              <table className="data-table w-full text-xs text-start">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4">{t("شماره سند")}</th>
                    <th className="py-3 px-4">{t("تاریخ دریافت")}</th>
                    <th className="py-3 px-4">{t("نام مشتری")}</th>
                    <th className="py-3 px-4">{t("مبلغ دریافتی")}</th>
                    <th className="py-3 px-4">{t("روش پرداخت")}</th>
                    <th className="py-3 px-4">{t("شماره پیگیری")}</th>
                    <th className="py-3 px-4 text-center">{t("وضعیت سند")}</th>
                    {user?.role === 'MANAGER' && <th className="py-3 px-4 text-center">{t("ابطال")}</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {receipts.map((r) => {
                    const rId = r.receipt_id ?? r.voucher_id ?? 0;
                    return (
                      <tr key={rId} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-3 px-4 font-mono text-slate-400">#{rId}</td>
                        <td className="py-3 px-4 text-slate-500">
                          {(language === 'fa' && r.jalali_date) || formatIsoToJalali(r.receipt_date, language)}
                        </td>
                        <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                          {r.customer_name || t("مشتری فاکتور")}
                        </td>
                        <td className="py-3 px-4 font-black text-emerald-600 dark:text-emerald-400 tabular-nums">
                          {formatCurrency(r.amount, true, currencyUnit, language)}
                        </td>
                        <td className="py-3 px-4 text-slate-600 dark:text-slate-300 font-medium">
                          {language === 'en' ? t(r.payment_method) : (r.payment_method_display || t(r.payment_method))}
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-400">{r.reference_number || '-'}</td>
                        <td className="py-3 px-4 text-center">
                          {r.is_cancelled ? (
                            <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600" title={r.cancellation_reason}>{t("ابطال‌شده")}</span>
                          ) : (
                            <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600">{t("معتبر")}</span>
                          )}
                        </td>
                        {user?.role === 'MANAGER' && (
                          <td className="py-3 px-4 text-center">
                            {!r.is_cancelled && (
                              <button
                                onClick={() => handleOpenCancel(rId, 'receipt', t("ابطال سند دریافت شماره #{0}", undefined, { 0: rId }))}
                                className="p-1 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30"
                                title={t("ابطال سند با ذکر دلیل")}
                              >
                                <Ban className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        ) : activeTab === 'payments' ? (
          payments.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-400">{t("هیچ سند پرداختی ثبت نشده است.")}</div>
          ) : (
            <div className="table-scroll overflow-x-auto">
              <table className="data-table w-full text-xs text-start">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4">{t("شماره سند")}</th>
                    <th className="py-3 px-4">{t("تاریخ پرداخت")}</th>
                    <th className="py-3 px-4">{t("تأمین‌کننده")}</th>
                    <th className="py-3 px-4">{t("مبلغ پرداختی")}</th>
                    <th className="py-3 px-4">{t("روش پرداخت")}</th>
                    <th className="py-3 px-4">{t("شماره ارجاع")}</th>
                    <th className="py-3 px-4 text-center">{t("وضعیت")}</th>
                    {user?.role === 'MANAGER' && <th className="py-3 px-4 text-center">{t("ابطال")}</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {payments.map((p) => {
                    const pId = p.payment_id ?? p.voucher_id ?? 0;
                    return (
                      <tr key={pId} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-3 px-4 font-mono text-slate-400">#{pId}</td>
                        <td className="py-3 px-4 text-slate-500">
                          {(language === 'fa' && p.jalali_date) || formatIsoToJalali(p.payment_date, language)}
                        </td>
                        <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                          {p.supplier_name || t("تأمین‌کننده")}
                        </td>
                        <td className="py-3 px-4 font-black text-rose-600 dark:text-rose-400 tabular-nums">
                          {formatCurrency(p.amount, true, currencyUnit, language)}
                        </td>
                        <td className="py-3 px-4 text-slate-600 dark:text-slate-300">
                          {language === 'en' ? t(p.payment_method) : (p.payment_method_display || t(p.payment_method))}
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-400">{p.reference_number || '-'}</td>
                        <td className="py-3 px-4 text-center">
                          {p.is_cancelled ? (
                            <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600" title={p.cancellation_reason}>{t("ابطال‌شده")}</span>
                          ) : (
                            <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600">{t("معتبر")}</span>
                          )}
                        </td>
                        {user?.role === 'MANAGER' && (
                          <td className="py-3 px-4 text-center">
                            {!p.is_cancelled && (
                              <button
                                onClick={() => handleOpenCancel(pId, 'payment', t("ابطال سند پرداخت شماره #{0}", undefined, { 0: pId }))}
                                className="p-1 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30"
                                title={t("ابطال سند با ذکر دلیل")}
                              >
                                <Ban className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        ) : (
          refunds.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-400">{t("هیچ سند استردادی به مشتریان ثبت نشده است.")}</div>
          ) : (
            <div className="table-scroll overflow-x-auto">
              <table className="data-table w-full text-xs text-start">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4">{t("شماره سند")}</th>
                    <th className="py-3 px-4">{t("تاریخ استرداد")}</th>
                    <th className="py-3 px-4">{t("مشتری")}</th>
                    <th className="py-3 px-4">{t("مبلغ استردادی")}</th>
                    <th className="py-3 px-4">{t("روش پرداخت")}</th>
                    <th className="py-3 px-4 text-center">{t("وضعیت")}</th>
                    {user?.role === 'MANAGER' && <th className="py-3 px-4 text-center">{t("ابطال")}</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {refunds.map((rf) => {
                    const rfId = rf.refund_id ?? rf.voucher_id ?? 0;
                    return (
                      <tr key={rfId} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-3 px-4 font-mono text-slate-400">#{rfId}</td>
                        <td className="py-3 px-4 text-slate-500">
                          {(language === 'fa' && rf.jalali_date) || formatIsoToJalali(rf.refund_date, language)}
                        </td>
                        <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                          {rf.customer_name || t("مشتری")}
                        </td>
                        <td className="py-3 px-4 font-black text-amber-600 dark:text-amber-400 tabular-nums">
                          {formatCurrency(rf.amount, true, currencyUnit, language)}
                        </td>
                        <td className="py-3 px-4 text-slate-600 dark:text-slate-300">
                          {language === 'en' ? t(rf.payment_method) : (rf.payment_method_display || t(rf.payment_method))}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {rf.is_cancelled ? (
                            <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600" title={rf.cancellation_reason}>{t("ابطال‌شده")}</span>
                          ) : (
                            <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600">{t("معتبر")}</span>
                          )}
                        </td>
                        {user?.role === 'MANAGER' && (
                          <td className="py-3 px-4 text-center">
                            {!rf.is_cancelled && (
                              <button
                                onClick={() => handleOpenCancel(rfId, 'refund', t("ابطال سند استرداد شماره #{0}", undefined, { 0: rfId }))}
                                className="p-1 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30"
                                title={t("ابطال سند با ذکر دلیل")}
                              >
                                <Ban className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )
        )}

        {totalPages > 1 && (
          <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
            <span>{t("صفحه")}{' '}{currentPage} {' '}{t("از")} {totalPages} {t("(مجموع")} {totalCount}{' '}{t("سند)")}</span>
            <div className="flex gap-1">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => p - 1)}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              >{t("قبلی")}</button>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              >{t("بعدی")}</button>
            </div>
          </div>
        )}
      </div>

      <CancelVoucherModal
        isOpen={cancelModalOpen}
        title={cancelTarget?.title || t("ابطال سند مالی")}
        onClose={() => {
          setCancelModalOpen(false);
          setCancelTarget(null);
        }}
        onConfirm={handleConfirmCancel}
      />
    </div>
  );
};
