import React, { useState } from 'react';
import {
  X,
  Printer,
  CheckCircle2,
  XCircle,
  RotateCcw,
  CreditCard,
  User as UserIcon,
  Car,
  Receipt,
  FileText,
} from 'lucide-react';
import { SalesInvoice } from '../../types';
import { IranianPlateBadge } from '../plates/IranianPlateBadge';
import { formatCurrency, formatIsoToJalali } from '../../utils/formatters';
import { useAuth } from '../../context/AuthContext';
import { invoicesApi } from '../../api/invoices';

interface InvoiceDetailModalProps {
  invoice: SalesInvoice | null;
  onClose: () => void;
  onUpdated: () => void;
  onOpenReturn?: (invoice: SalesInvoice) => void;
  onOpenReceipt?: (invoice: SalesInvoice) => void;
}

export const InvoiceDetailModal: React.FC<InvoiceDetailModalProps> = ({
  invoice,
  onClose,
  onUpdated,
  onOpenReturn,
  onOpenReceipt,
}) => {
  const { user, currencyUnit } = useAuth();
  const [printFormat, setPrintFormat] = useState<'A4' | 'THERMAL'>('A4');
  const [loadingAction, setLoadingAction] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!invoice) return null;

  const handleConfirm = async () => {
    if (!confirm('آیا از تایید نهایی فاکتور و کسر اقلام از موجودی انبار اطمینان دارید؟')) return;
    setLoadingAction(true);
    setErrorMessage(null);
    try {
      await invoicesApi.confirmSalesInvoice(invoice.sales_invoice_id);
      onUpdated();
      onClose();
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'خطا در تایید فاکتور');
    } finally {
      setLoadingAction(false);
    }
  };

  const handleCancel = async () => {
    if (!confirm('آیا از لغو این فاکتور و بازگشت اقلام به انبار اطمینان دارید؟')) return;
    setLoadingAction(true);
    setErrorMessage(null);
    try {
      await invoicesApi.cancelSalesInvoice(invoice.sales_invoice_id);
      onUpdated();
      onClose();
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'خطا در لغو فاکتور');
    } finally {
      setLoadingAction(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 invoice-modal-overlay">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-4xl w-full overflow-hidden flex flex-col max-h-[90vh] invoice-modal-card">
        {/* هدر مدال */}
        <div className="flex flex-wrap items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850 gap-3 no-print">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <span className="text-base sm:text-lg font-bold text-slate-800 dark:text-slate-100">
              فاکتور {invoice.invoice_number}
            </span>
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                invoice.status === 'CONFIRMED'
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                  : invoice.status === 'DRAFT'
                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                  : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
              }`}
            >
              {invoice.status_display || invoice.status}
            </span>
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                invoice.payment_status === 'PAID'
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                  : invoice.payment_status === 'PARTIAL'
                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                  : 'bg-slate-500/10 text-slate-600 dark:text-slate-400'
              }`}
            >
              {invoice.payment_status_display || invoice.payment_status}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* انتخاب فرمت چاپ بین A4 و فیش حرارتی */}
            <div className="flex items-center bg-slate-200 dark:bg-slate-800 p-0.5 rounded-lg text-xs font-semibold">
              <button
                type="button"
                onClick={() => setPrintFormat('A4')}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-all ${
                  printFormat === 'A4'
                    ? 'bg-white dark:bg-slate-700 text-brand-600 dark:text-brand-400 shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
                title="نمایش و چاپ در ابعاد استاندارد A4"
              >
                <FileText className="w-3.5 h-3.5" />
                <span>فاکتور A4</span>
              </button>
              <button
                type="button"
                onClick={() => setPrintFormat('THERMAL')}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-all ${
                  printFormat === 'THERMAL'
                    ? 'bg-white dark:bg-slate-700 text-brand-600 dark:text-brand-400 shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
                title="نمایش و چاپ در قالب فیش حرارتی ۸۰ میلی‌متری (رول صندوق)"
              >
                <Receipt className="w-3.5 h-3.5" />
                <span>فیش ۸۰mm</span>
              </button>
            </div>

            <button
              onClick={handlePrint}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
            >
              <Printer className="w-4 h-4" />
              <span className="hidden sm:inline">چاپ</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {errorMessage && (
          <div className="mx-6 mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-600 text-sm no-print">
            {errorMessage}
          </div>
        )}

        {/* ۱. بدنه فاکتور در قالب استاندارد A4 */}
        {printFormat === 'A4' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 text-slate-800 dark:text-slate-200 font-sans print:p-0">
            {/* سربرگ رسمی در حالت چاپ */}
            <div className="border-b-2 border-slate-800 pb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-slate-900 text-white flex items-center justify-center text-2xl font-black">
                  🛞
                </div>
                <div>
                  <h2 className="text-xl font-black text-slate-900 dark:text-white">
                    فروشگاه و خدمات تخصصی لاستیک
                  </h2>
                  <p className="text-xs text-slate-500">فاکتور رسمی فروش کالا و خدمات فنی خودرو</p>
                </div>
              </div>
              <div className="text-left space-y-1 text-xs">
                <p>
                  <span className="text-slate-500">شماره فاکتور: </span>
                  <span className="font-bold text-slate-900 dark:text-white">{invoice.invoice_number}</span>
                </p>
                <p>
                  <span className="text-slate-500">تاریخ صدور: </span>
                  <span className="font-medium">{invoice.jalali_date || formatIsoToJalali(invoice.invoice_date)}</span>
                </p>
                <p>
                  <span className="text-slate-500">صادرکننده: </span>
                  <span className="font-medium">{invoice.created_by_name || 'کاربر سیستم'}</span>
                </p>
              </div>
            </div>

            {/* کارت اطلاعات مشتری و خودرو */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
              <div className="space-y-1.5 text-sm">
                <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase">
                  <UserIcon className="w-3.5 h-3.5" />
                  <span>مشخصات خریدار</span>
                </div>
                <p className="font-bold text-slate-900 dark:text-white">{invoice.customer_name}</p>
                <p className="text-xs text-slate-500">تلفن تماس: {invoice.customer_phone}</p>
              </div>

              <div className="space-y-1.5 text-sm flex flex-col md:items-end">
                <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase">
                  <Car className="w-3.5 h-3.5" />
                  <span>مشخصات خودرو</span>
                </div>
                <p className="font-bold text-slate-900 dark:text-white">{invoice.vehicle_model || 'خودرو سواری'}</p>
                <div className="pt-1">
                  <IranianPlateBadge plateString={invoice.vehicle_plate} size="sm" />
                </div>
              </div>
            </div>

            {/* جدول اقلام تایرها */}
            {invoice.tire_items && invoice.tire_items.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  اقلام کالا (تایرها)
                </h3>
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                  <table className="w-full text-sm text-right">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 text-xs text-slate-500 border-b border-slate-200 dark:border-slate-800">
                      <tr>
                        <th className="py-2.5 px-3">ردیف</th>
                        <th className="py-2.5 px-3">شرح کالا</th>
                        <th className="py-2.5 px-3">برند / سایز</th>
                        <th className="py-2.5 px-3 text-center">تعداد (حلقه)</th>
                        <th className="py-2.5 px-3">قیمت واحد ({currencyUnit === 'toman' ? 'تومان' : 'ریال'})</th>
                        <th className="py-2.5 px-3">جمع کل</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                      {invoice.tire_items.map((item, idx) => (
                        <tr key={item.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                          <td className="py-2.5 px-3 font-medium text-slate-400">{idx + 1}</td>
                          <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-slate-100">
                            {item.tire_name}
                          </td>
                          <td className="py-2.5 px-3 text-slate-500">
                            {item.brand_name} - {item.size_name}
                          </td>
                          <td className="py-2.5 px-3 text-center font-bold text-slate-800 dark:text-slate-200">
                            {item.quantity}
                          </td>
                          <td className="py-2.5 px-3 tabular-nums">
                            {formatCurrency(item.unit_price, false, currencyUnit)}
                          </td>
                          <td className="py-2.5 px-3 font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                            {formatCurrency(item.total_price, true, currencyUnit)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* جدول خدمات فنی */}
            {invoice.service_items && invoice.service_items.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  خدمات فنی و کارگاهی
                </h3>
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                  <table className="w-full text-sm text-right">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 text-xs text-slate-500 border-b border-slate-200 dark:border-slate-800">
                      <tr>
                        <th className="py-2.5 px-3">ردیف</th>
                        <th className="py-2.5 px-3">شرح خدمت</th>
                        <th className="py-2.5 px-3 text-center">تعداد / دفعات</th>
                        <th className="py-2.5 px-3">تعرفه واحد ({currencyUnit === 'toman' ? 'تومان' : 'ریال'})</th>
                        <th className="py-2.5 px-3">جمع کل</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                      {invoice.service_items.map((item, idx) => (
                        <tr key={item.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                          <td className="py-2.5 px-3 font-medium text-slate-400">{idx + 1}</td>
                          <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-slate-100">
                            {item.service_name}
                          </td>
                          <td className="py-2.5 px-3 text-center font-bold text-slate-800 dark:text-slate-200">
                            {item.quantity}
                          </td>
                          <td className="py-2.5 px-3 tabular-nums">
                            {formatCurrency(item.unit_price, false, currencyUnit)}
                          </td>
                          <td className="py-2.5 px-3 font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                            {formatCurrency(item.total_price, true, currencyUnit)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* جمع‌ها و مبالغ مالی */}
            <div className="flex flex-col md:flex-row justify-between items-start gap-4 pt-2">
              <div className="flex-1 text-xs text-slate-500 space-y-1">
                {invoice.notes && (
                  <p>
                    <span className="font-semibold text-slate-700 dark:text-slate-300">توضیحات: </span>
                    {invoice.notes}
                  </p>
                )}
              </div>

              <div className="w-full md:w-80 rounded-xl bg-slate-50 dark:bg-slate-800/60 p-4 space-y-2 border border-slate-200 dark:border-slate-800 text-xs">
                <div className="flex justify-between text-slate-600 dark:text-slate-400">
                  <span>جمع ناخالص فاکتور:</span>
                  <span className="font-bold tabular-nums">
                    {formatCurrency(invoice.total_amount, true, currencyUnit)}
                  </span>
                </div>

                {(parseFloat(String(invoice.discount_amount)) > 0 || parseFloat(String(invoice.discount_percent)) > 0) && (
                  <div className="flex justify-between text-emerald-600 dark:text-emerald-400">
                    <span>تخفیف:</span>
                    <span className="font-bold tabular-nums">
                      - {formatCurrency(invoice.discount_amount, true, currencyUnit)}
                    </span>
                  </div>
                )}

                {parseFloat(String(invoice.returned_amount || 0)) > 0 && (
                  <div className="flex justify-between text-rose-600 dark:text-rose-400">
                    <span>مبلغ مرجوعی کالا:</span>
                    <span className="font-bold tabular-nums">
                      - {formatCurrency(invoice.returned_amount, true, currencyUnit)}
                    </span>
                  </div>
                )}

                <div className="border-t border-slate-200 dark:border-slate-700 pt-2 flex justify-between text-sm font-extrabold text-slate-900 dark:text-white">
                  <span>مبلغ قابل پرداخت خالص:</span>
                  <span className="text-brand-600 dark:text-brand-400 tabular-nums">
                    {formatCurrency(invoice.net_amount || invoice.total_amount, true, currencyUnit)}
                  </span>
                </div>
              </div>
            </div>

            {/* بخش مهر و امضا در حالت پرینت */}
            <div className="pt-12 hidden print:grid grid-cols-2 text-center text-xs">
              <div>
                <p className="font-bold text-slate-800">امضا و مهر فروشگاه لاستیک</p>
              </div>
              <div>
                <p className="font-bold text-slate-800">امضای خریدار و تحویل‌گیرنده</p>
              </div>
            </div>
          </div>
        )}

        {/* ۲. بدنه فاکتور در قالب فیش حرارتی ۸۰ میلی‌متری (Thermal Receipt) */}
        {printFormat === 'THERMAL' && (
          <div className="flex-1 overflow-y-auto p-6 flex justify-center bg-slate-100 dark:bg-slate-950/60 print:bg-white print:p-0">
            <div className="w-[340px] max-w-full bg-white dark:bg-slate-900 p-5 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 text-xs space-y-3 font-mono shadow-sm thermal-receipt-mode">
              {/* سربرگ فیش */}
              <div className="text-center space-y-1 pb-2 border-b border-dashed border-slate-300 dark:border-slate-700">
                <div className="text-2xl mb-1">🛞</div>
                <h3 className="font-black text-sm text-slate-900 dark:text-white">فروشگاه و خدمات لاستیک</h3>
                <p className="text-[10px] text-slate-500">رسید صندوق و فیش مشتری (۸۰mm)</p>
              </div>

              {/* مشخصات سند */}
              <div className="space-y-1 text-[11px] pb-2 border-b border-dashed border-slate-300 dark:border-slate-700">
                <div className="flex justify-between">
                  <span className="text-slate-500">شماره:</span>
                  <span className="font-bold">{invoice.invoice_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">تاریخ:</span>
                  <span>{invoice.jalali_date || formatIsoToJalali(invoice.invoice_date)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">خریدار:</span>
                  <span className="font-bold">{invoice.customer_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">موبایل:</span>
                  <span>{invoice.customer_phone}</span>
                </div>
                {invoice.vehicle_plate && (
                  <div className="flex justify-between items-center pt-1">
                    <span className="text-slate-500">پلاک:</span>
                    <span className="font-bold dir-ltr">{invoice.vehicle_plate}</span>
                  </div>
                )}
              </div>

              {/* جدول اقلام */}
              <div className="space-y-2 pb-2 border-b border-dashed border-slate-300 dark:border-slate-700 text-[11px]">
                <div className="flex justify-between font-bold text-slate-600 dark:text-slate-400 pb-1 border-b border-slate-200 dark:border-slate-800">
                  <span>شرح</span>
                  <div className="flex gap-4">
                    <span>تعداد</span>
                    <span>مبلغ ({currencyUnit === 'toman' ? 'تومان' : 'ریال'})</span>
                  </div>
                </div>

                {invoice.tire_items?.map((item) => (
                  <div key={item.id} className="space-y-0.5">
                    <div className="font-bold text-slate-900 dark:text-slate-100 truncate">
                      {item.tire_name}
                    </div>
                    <div className="flex justify-between text-slate-500 text-[10px]">
                      <span>{item.brand_name}</span>
                      <div className="flex gap-4">
                        <span>×{item.quantity}</span>
                        <span className="font-bold text-slate-800 dark:text-slate-200 tabular-nums">
                          {formatCurrency(item.total_price, false, currencyUnit)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}

                {invoice.service_items?.map((item) => (
                  <div key={item.id} className="space-y-0.5">
                    <div className="font-bold text-slate-900 dark:text-slate-100 truncate">
                      {item.service_name}
                    </div>
                    <div className="flex justify-between text-slate-500 text-[10px]">
                      <span>خدمت فنی</span>
                      <div className="flex gap-4">
                        <span>×{item.quantity}</span>
                        <span className="font-bold text-slate-800 dark:text-slate-200 tabular-nums">
                          {formatCurrency(item.total_price, false, currencyUnit)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* سرجمع مالی */}
              <div className="space-y-1.5 text-[11px] pb-2 border-b border-dashed border-slate-300 dark:border-slate-700">
                <div className="flex justify-between text-slate-500">
                  <span>جمع کل:</span>
                  <span className="tabular-nums">{formatCurrency(invoice.total_amount, true, currencyUnit)}</span>
                </div>
                {parseFloat(String(invoice.discount_amount || 0)) > 0 && (
                  <div className="flex justify-between text-emerald-600 dark:text-emerald-400">
                    <span>تخفیف:</span>
                    <span className="tabular-nums">- {formatCurrency(invoice.discount_amount, true, currencyUnit)}</span>
                  </div>
                )}
                {parseFloat(String(invoice.returned_amount || 0)) > 0 && (
                  <div className="flex justify-between text-rose-600 dark:text-rose-400">
                    <span>مرجوعی:</span>
                    <span className="tabular-nums">- {formatCurrency(invoice.returned_amount, true, currencyUnit)}</span>
                  </div>
                )}
                <div className="flex justify-between text-sm font-black pt-1 border-t border-slate-200 dark:border-slate-800">
                  <span>مبلغ قابل پرداخت:</span>
                  <span className="text-brand-600 dark:text-brand-400 tabular-nums">
                    {formatCurrency(invoice.net_amount || invoice.total_amount, true, currencyUnit)}
                  </span>
                </div>
                <div className="flex justify-between text-[10px] text-slate-500 pt-0.5">
                  <span>وضعیت پرداخت:</span>
                  <span className="font-bold">{invoice.payment_status_display || invoice.payment_status}</span>
                </div>
              </div>

              {/* پانویس حرارتی */}
              <div className="text-center pt-1 text-[10px] text-slate-400 space-y-1">
                <p className="font-bold text-slate-600 dark:text-slate-300">از اعتماد و انتخاب شما سپاسگزاریم</p>
                <p>ارائه فیش جهت خدمات گارانتی الزامی است.</p>
              </div>
            </div>
          </div>
        )}

        {/* فوتر اکشن‌ها و دکمه‌های عملیاتی */}
        <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850 flex flex-wrap items-center justify-between gap-3 no-print">
          <div className="flex items-center gap-2">
            {invoice.status === 'DRAFT' && (
              <button
                onClick={handleConfirm}
                disabled={loadingAction}
                className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl shadow-sm transition-colors"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>تایید نهایی و کسر از انبار</span>
              </button>
            )}

            {user?.role === 'MANAGER' && invoice.status === 'CONFIRMED' && invoice.payment_status !== 'PAID' && onOpenReceipt && (
              <button
                onClick={() => onOpenReceipt(invoice)}
                className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-xl shadow-sm transition-colors"
              >
                <CreditCard className="w-4 h-4" />
                <span>ثبت دریافت وجه</span>
              </button>
            )}

            {user?.role === 'MANAGER' && invoice.status === 'CONFIRMED' && onOpenReturn && (
              <button
                onClick={() => onOpenReturn(invoice)}
                className="flex items-center gap-1.5 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-xl shadow-sm transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                <span>ثبت مرجوعی کالا</span>
              </button>
            )}

            {user?.role === 'MANAGER' && invoice.status !== 'CANCELLED' && (
              <button
                onClick={handleCancel}
                disabled={loadingAction}
                className="flex items-center gap-1.5 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold rounded-xl shadow-sm transition-colors"
              >
                <XCircle className="w-4 h-4" />
                <span>لغو فاکتور و بازگشت به انبار</span>
              </button>
            )}
          </div>

          <button
            onClick={onClose}
            className="px-4 py-2 border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-semibold rounded-xl transition-colors"
          >
            بستن
          </button>
        </div>
      </div>
    </div>
  );
};
