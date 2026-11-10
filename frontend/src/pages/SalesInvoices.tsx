import { useLanguage } from '../context/LanguageContext';
import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Search,
  PlusCircle,
  RotateCcw,
  CreditCard,
  Eye,
  Filter,
} from 'lucide-react';
import { invoicesApi } from '../api/invoices';
import { SalesInvoice } from '../types';
import { IranianPlateBadge } from '../components/plates/IranianPlateBadge';
import { formatCurrency, formatIsoToJalali } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';
import { InvoiceDetailModal } from '../components/invoices/InvoiceDetailModal';
import { SalesReturnModal } from '../components/invoices/SalesReturnModal';
import { ReceiptModal } from '../components/finance/ReceiptModal';
import { createRequestSequence } from '../utils/invoiceRequests';
import { parseApiError } from '../utils/errorParser';

export const SalesInvoices: React.FC = () => {
  const { t, language } = useLanguage();
  const { currencyUnit, user } = useAuth();
  const [invoices, setInvoices] = useState<SalesInvoice[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [paymentStatusFilter, setPaymentStatusFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const [selectedInvoice, setSelectedInvoice] = useState<SalesInvoice | null>(null);
  const [returnInvoice, setReturnInvoice] = useState<SalesInvoice | null>(null);
  const [receiptInvoice, setReceiptInvoice] = useState<SalesInvoice | null>(null);

  const [refreshVersion, setRefreshVersion] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const invoiceRequests = useRef(createRequestSequence());
  const fetchInvoices = () => {
    invoiceRequests.current.invalidate();
    setRefreshVersion((version) => version + 1);
  };

  useEffect(() => {
    const requests = invoiceRequests.current;
    const request = requests.begin();
    const isCurrent = () => requests.isCurrent(request);
    const loadInvoices = async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const data = await invoicesApi.getSalesInvoices({
          search: search.trim() || undefined,
          status: statusFilter || undefined,
          payment_status: paymentStatusFilter || undefined,
          page: currentPage,
        });
        if (!isCurrent()) return;
        setInvoices(data.results || []);
        setTotalPages(data.total_pages || 1);
        setTotalCount(data.count || 0);
      } catch (error) {
        if (!isCurrent()) return;
        setInvoices([]);
        setTotalCount(0);
        setTotalPages(1);
        setLoadError(parseApiError(error, t("خطا در دریافت فاکتورهای فروش"), language));
      } finally {
        if (isCurrent()) setLoading(false);
      }
    };
    void loadInvoices();
    return () => requests.invalidate();
  }, [search, statusFilter, paymentStatusFilter, currentPage, refreshVersion, t, language]);

  return (
    <div className="page-stack" aria-busy={loading}>
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("فهرست فاکتورهای فروش")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("مدیریت، پیگیری وضعیت تسویه، چاپ رسمی و ثبت مرجوعی فاکتورها (مجموع:")}{totalCount}{' '}{t("فاکتور)")}</p>
        </div>

        {(user?.role === 'MANAGER' || user?.role === 'TECHNICIAN') && (
          <Link
            to="/invoices/create"
            className="action-primary inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{t("صدور فاکتور جدید")}</span>
          </Link>
        )}
      </div>

      <div className="filter-bar">
        <div className="relative w-full md:w-80">
          <input
            type="text"
            aria-label={t("جستجوی فاکتور فروش")}
            value={search}
            onChange={(e) => {
              invoiceRequests.current.invalidate();
              setSearch(e.target.value);
              setCurrentPage(1);
            }}
            placeholder={t("جستجو در شماره فاکتور، نام، موبایل، پلاک...")}
            className="ui-field w-full pe-3 ps-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 start-3" />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          <select
            aria-label={t("وضعیت فاکتور")}
            value={statusFilter}
            onChange={(e) => {
              invoiceRequests.current.invalidate();
              setStatusFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="ui-field px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs outline-none"
          >
            <option value="">{t("همه وضعیت‌های فاکتور")}</option>
            <option value="CONFIRMED">{t("تاییدشده (قطعی)")}</option>
            <option value="DRAFT">{t("پیش‌نویس")}</option>
            <option value="CANCELLED">{t("لغوشده")}</option>
          </select>

          <select
            aria-label={t("وضعیت پرداخت")}
            value={paymentStatusFilter}
            onChange={(e) => {
              invoiceRequests.current.invalidate();
              setPaymentStatusFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="ui-field px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs outline-none"
          >
            <option value="">{t("همه وضعیت‌های پرداخت")}</option>
            <option value="PAID">{t("تسویه کامل (PAID)")}</option>
            <option value="PARTIAL">{t("پرداخت ناقص (اقساطی)")}</option>
            <option value="UNPAID">{t("تسویه‌نشده (UNPAID)")}</option>
          </select>
        </div>
      </div>

      {loadError && (
        <div role="alert" className="p-4 text-xs text-rose-700 dark:text-rose-300">
          {loadError}
          <button type="button" onClick={fetchInvoices} className="ms-3 underline">{t("تلاش مجدد")}</button>
        </div>
      )}

      <div className="surface-panel overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("در حال دریافت فاکتورها...")}</div>
        ) : loadError ? null : invoices.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("فاکتوری با مشخصات جستجویافته یافت نشد.")}</div>
        ) : (
          <div className="table-scroll overflow-x-auto">
            <table className="data-table w-full text-xs text-start">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">{t("شماره فاکتور")}</th>
                  <th className="py-3 px-4">{t("تاریخ صدور")}</th>
                  <th className="py-3 px-4">{t("مشتری")}</th>
                  <th className="py-3 px-4">{t("خودرو و پلاک")}</th>
                  <th className="py-3 px-4">{t("مبلغ قابل پرداخت")}</th>
                  <th className="py-3 px-4 text-center">{t("وضعیت فاکتور")}</th>
                  <th className="py-3 px-4 text-center">{t("وضعیت تسویه")}</th>
                  <th className="py-3 px-4 text-center">{t("عملیات")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {invoices.map((inv) => (
                  <tr key={inv.sales_invoice_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      <bdi dir="auto">{inv.invoice_number}</bdi>
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {(language === 'fa' && inv.jalali_date) || formatIsoToJalali(inv.invoice_date, language)}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-800 dark:text-slate-200">
                      <bdi dir="auto">{inv.customer_name}</bdi>
                      <span className="block text-[10px] text-slate-400 font-normal">
                        {inv.customer_phone}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-col gap-1">
                        <span className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                          {inv.vehicle_model}
                        </span>
                        <IranianPlateBadge plateString={inv.vehicle_plate} size="sm" />
                      </div>
                    </td>
                    <td className="py-3 px-4 font-black text-slate-900 dark:text-white tabular-nums">
                      {formatCurrency(inv.net_amount || inv.total_amount, true, currencyUnit, language)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-block px-2.5 py-1 rounded-full text-[10px] font-bold ${
                          inv.status === 'CONFIRMED'
                            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                            : inv.status === 'DRAFT'
                            ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                            : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                        }`}
                      >
                        {language === 'en' ? t(inv.status) : (inv.status_display || t(inv.status))}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-block px-2.5 py-1 rounded-full text-[10px] font-bold ${
                          inv.payment_status === 'PAID'
                            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                            : inv.payment_status === 'PARTIAL'
                            ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                            : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                        }`}
                      >
                        {language === 'en' ? t(inv.payment_status) : (inv.payment_status_display || t(inv.payment_status))}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          onClick={() => setSelectedInvoice(inv)}
                          title={t("مشاهده جزئیات و چاپ")}
                          className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        {user?.role === 'MANAGER' && inv.status === 'CONFIRMED' && inv.payment_status !== 'PAID' && (
                          <button
                            onClick={() => setReceiptInvoice(inv)}
                            title={t("ثبت دریافت وجه")}
                            className="p-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 dark:text-blue-400 transition-colors"
                          >
                            <CreditCard className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {user?.role === 'MANAGER' && inv.status === 'CONFIRMED' && (
                          <button
                            onClick={() => setReturnInvoice(inv)}
                            title={t("ثبت مرجوعی کالا")}
                            className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 transition-colors"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
            <span>{t("صفحه")}{' '}{currentPage} {' '}{t("از")} {totalPages}
            </span>
            <div className="flex gap-1">
              <button
                disabled={currentPage <= 1}
                onClick={() => {
                  invoiceRequests.current.invalidate();
                  setCurrentPage((page) => page - 1);
                }}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40"
              >{t("قبلی")}</button>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => {
                  invoiceRequests.current.invalidate();
                  setCurrentPage((page) => page + 1);
                }}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40"
              >{t("بعدی")}</button>
            </div>
          </div>
        )}
      </div>

      {selectedInvoice && (
        <InvoiceDetailModal
          invoice={selectedInvoice}
          onClose={() => setSelectedInvoice(null)}
          onUpdated={fetchInvoices}
          onOpenReturn={(inv) => {
            setSelectedInvoice(null);
            setReturnInvoice(inv);
          }}
          onOpenReceipt={(inv) => {
            setSelectedInvoice(null);
            setReceiptInvoice(inv);
          }}
        />
      )}

      {returnInvoice && (
        <SalesReturnModal
          invoice={returnInvoice}
          onClose={() => setReturnInvoice(null)}
          onSuccess={fetchInvoices}
        />
      )}

      {receiptInvoice && (
        <ReceiptModal
          invoice={receiptInvoice}
          onClose={() => setReceiptInvoice(null)}
          onSuccess={fetchInvoices}
        />
      )}
    </div>
  );
};
