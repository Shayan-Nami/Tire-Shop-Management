import React, { useCallback, useEffect, useState } from 'react';
import {
  Search,
  PackagePlus,
  Trash2,
  XCircle,
} from 'lucide-react';
import { invoicesApi } from '../api/invoices';
import { catalogApi } from '../api/catalog';
import { suppliersApi } from '../api/suppliers';
import { PaginatedResponse, PurchaseInvoice, Supplier, Tire } from '../types';
import { parseApiError } from '../utils/errorParser';
import { formatCurrency, formatIsoToJalali } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';

async function fetchAllPages<T>(
  fetchPage: (page: number) => Promise<PaginatedResponse<T>>,
  isActive: () => boolean
): Promise<T[]> {
  const results: T[] = [];
  for (let page = 1; isActive(); page += 1) {
    const data = await fetchPage(page);
    if (!isActive()) return [];
    if (data.current_page !== page || (data.next && data.results.length === 0)) {
      throw new Error('پاسخ صفحه‌بندی سرور معتبر نیست. لطفاً دوباره تلاش کنید.');
    }
    results.push(...data.results);
    if (!data.next) return results;
  }
  return [];
}

export const PurchaseInvoices: React.FC = () => {
  const { currencyUnit, user } = useAuth();
  const [invoices, setInvoices] = useState<PurchaseInvoice[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [tires, setTires] = useState<Tire[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  // فرم ثبت فاکتور خرید جدید
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | ''>('');
  const [purchaseItems, setPurchaseItems] = useState<
    Array<{ tireId: number; tire: Tire; quantity: number; unitCost: number }>
  >([]);
  const [selectorsLoading, setSelectorsLoading] = useState(true);
  const [selectorsError, setSelectorsError] = useState('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  const fetchPurchases = useCallback(async () => {
    setLoading(true);
    try {
      const data = await invoicesApi.getPurchaseInvoices({
        search: search.trim() || undefined,
        page: currentPage,
      });
      setInvoices(data.results || []);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.count || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [search, currentPage]);

  useEffect(() => {
    let active = true;
    const isActive = () => active;
    const loadSelectors = async () => {
      try {
        const [allSuppliers, allTires] = await Promise.all([
          fetchAllPages((page) => suppliersApi.getSuppliers({ page, page_size: 100 }), isActive),
          fetchAllPages((page) => catalogApi.getTires({ page, page_size: 100 }), isActive),
        ]);
        if (!active) return;
        setSuppliers(allSuppliers);
        setTires(allTires);
      } catch (error) {
        if (active) {
          setSelectorsError(parseApiError(error, 'خطا در دریافت فهرست تأمین‌کنندگان و تایرها. لطفاً صفحه را دوباره بارگذاری کنید.'));
        }
      } finally {
        if (active) setSelectorsLoading(false);
      }
    };
    void loadSelectors();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Query changes intentionally enter the network loading state.
    void fetchPurchases();
  }, [fetchPurchases]);

  const handleAddTireRow = (tireId: number) => {
    const tire = tires.find((t) => t.tire_id === tireId);
    if (!tire) return;

    const existing = purchaseItems.find((item) => item.tireId === tireId);
    if (existing) {
      setPurchaseItems(
        purchaseItems.map((item) =>
          item.tireId === tireId ? { ...item, quantity: item.quantity + 1 } : item
        )
      );
    } else {
      setPurchaseItems([
        ...purchaseItems,
        {
          tireId: tire.tire_id,
          tire,
          quantity: 4,
          unitCost: parseFloat(String(tire.purchase_price || tire.sale_price)) || 0,
        },
      ]);
    }
  };

  const handleUpdateItemQty = (tireId: number, qty: number) => {
    if (qty <= 0) {
      setPurchaseItems(purchaseItems.filter((item) => item.tireId !== tireId));
      return;
    }
    setPurchaseItems(
      purchaseItems.map((item) =>
        item.tireId === tireId ? { ...item, quantity: qty } : item
      )
    );
  };

  const handleUpdateItemCost = (tireId: number, cost: number) => {
    setPurchaseItems(
      purchaseItems.map((item) =>
        item.tireId === tireId ? { ...item, unitCost: cost } : item
      )
    );
  };

  const handleRemoveRow = (tireId: number) => {
    setPurchaseItems(purchaseItems.filter((item) => item.tireId !== tireId));
  };

  const handleCreatePurchase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSupplierId) {
      alert('لطفاً تأمین‌کننده را انتخاب فرمایید.');
      return;
    }
    if (purchaseItems.length === 0) {
      alert('حداقل یک ردیف تایر جهت ورود به انبار انتخاب کنید.');
      return;
    }

    setSubmitting(true);
    try {
      await invoicesApi.createPurchaseInvoice({
        supplier: Number(selectedSupplierId),
        tire_items: purchaseItems.map((i) => ({
          tire: i.tireId,
          quantity: i.quantity,
          unit_cost: i.unitCost,
        })),
      });

      setShowCreateModal(false);
      setPurchaseItems([]);
      fetchPurchases();
    } catch (err) {
      alert(parseApiError(err, 'خطا در ثبت ورود کالا به انبار'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelPurchase = async (inv: PurchaseInvoice) => {
    if (
      !confirm(
        `آیا از لغو فاکتور خرید ${inv.invoice_number} اطمینان دارید؟ اقلام به صورت خودکار از موجودی انبار کسر خواهد شد.`
      )
    ) {
      return;
    }

    try {
      await invoicesApi.cancelPurchaseInvoice(inv.purchase_invoice_id);
      fetchPurchases();
    } catch (err) {
      alert(parseApiError(err, 'امکان لغو فاکتور خرید وجود ندارد.'));
    }
  };

  const purchaseTotal = purchaseItems.reduce(
    (acc, curr) => acc + curr.quantity * curr.unitCost,
    0
  );

  return (
    <div className="space-y-6">
      {/* سربرگ */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">
            فاکتورهای خرید و ورود به انبار
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            ثبت اسناد خرید از نمایندگی‌ها و تأمین‌کنندگان، شارژ خودکار موجودی و اصلاح نرخ تمام‌شده (مجموع: {totalCount} سند)
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          disabled={selectorsLoading || !!selectorsError}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
        >
          <PackagePlus className="w-4 h-4" />
          <span>ثبت فاکتور خرید (ورود کالا)</span>
        </button>
      </div>

      {selectorsError && (
        <p role="alert" className="text-xs text-rose-600 dark:text-rose-400">{selectorsError}</p>
      )}
      {selectorsLoading && (
        <p role="status" className="text-xs text-slate-500">در حال دریافت فهرست کامل تأمین‌کنندگان و تایرها...</p>
      )}

      {/* جستجو */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
        <div className="relative w-full md:w-80">
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="جستجو در شماره فاکتور، نام تأمین‌کننده..."
            className="w-full pl-3 pr-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 right-3" />
        </div>
      </div>

      {/* جدول فاکتورهای خرید */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">در حال دریافت فاکتورهای خرید...</div>
        ) : invoices.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-400">سند خریدی یافت نشد.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-right">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">شماره فاکتور</th>
                  <th className="py-3 px-4">تاریخ ورود</th>
                  <th className="py-3 px-4">تأمین‌کننده</th>
                  <th className="py-3 px-4 text-center">تعداد اقلام تایر</th>
                  <th className="py-3 px-4">مبلغ کل فاکتور</th>
                  <th className="py-3 px-4 text-center">وضعیت</th>
                  <th className="py-3 px-4 text-center">تسویه</th>
                  {user?.role === 'MANAGER' && <th className="py-3 px-4 text-center">عملیات</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {invoices.map((inv) => (
                  <tr key={inv.purchase_invoice_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      {inv.invoice_number}
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {inv.jalali_date || formatIsoToJalali(inv.invoice_date)}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-800 dark:text-slate-200">
                      {inv.supplier_name}
                    </td>
                    <td className="py-3 px-4 text-center tabular-nums font-bold">
                      {inv.tire_items ? inv.tire_items.reduce((s, i) => s + i.quantity, 0) : 0} حلقه
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white tabular-nums">
                      {formatCurrency(inv.total_amount, true, currencyUnit)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-block px-2.5 py-1 rounded-full text-[10px] font-bold ${
                          inv.status === 'CONFIRMED'
                            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                            : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                        }`}
                      >
                        {inv.status_display || inv.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-block px-2.5 py-1 rounded-full text-[10px] font-bold ${
                          inv.payment_status === 'PAID'
                            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                            : inv.payment_status === 'PARTIAL'
                            ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                            : 'bg-slate-500/10 text-slate-600 dark:text-slate-400'
                        }`}
                      >
                        {inv.payment_status_display || inv.payment_status}
                      </span>
                    </td>
                    {user?.role === 'MANAGER' && (
                      <td className="py-3 px-4 text-center">
                        {inv.status === 'CONFIRMED' && (
                          <button
                            onClick={() => handleCancelPurchase(inv)}
                            title="لغو فاکتور خرید و کسر از انبار"
                            className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 transition-colors"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
            <span>
              صفحه {currentPage} از {totalPages}
            </span>
            <div className="flex gap-1">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => p - 1)}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40"
              >
                قبلی
              </button>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40"
              >
                بعدی
              </button>
            </div>
          </div>
        )}
      </div>

      {/* مدال ثبت فاکتور خرید */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-2xl w-full overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
                ثبت ورود کالا و فاکتور خرید از تأمین‌کننده
              </h2>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreatePurchase} className="p-6 space-y-4 text-xs overflow-y-auto flex-1">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">
                  تأمین‌کننده کالا:
                </label>
                <select
                  required
                  value={selectedSupplierId}
                  onChange={(e) => setSelectedSupplierId(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                >
                  <option value="">انتخاب تأمین‌کننده...</option>
                  {suppliers.map((s) => (
                    <option key={s.supplier_id} value={s.supplier_id}>
                      {s.supplier_name} ({s.phone_number || 'بدون شماره'})
                    </option>
                  ))}
                </select>
              </div>

              {/* افزودن تایر */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    اقلام تایر خریداری‌شده:
                  </label>
                  <select
                    onChange={(e) => {
                      if (e.target.value) {
                        handleAddTireRow(Number(e.target.value));
                        e.target.value = '';
                      }
                    }}
                    className="w-56 px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-xs"
                  >
                    <option value="">+ افزودن تایر به فاکتور...</option>
                    {tires.map((t) => (
                      <option key={t.tire_id} value={t.tire_id}>
                        {t.tire_name} ({t.brand_name})
                      </option>
                    ))}
                  </select>
                </div>

                {purchaseItems.length === 0 ? (
                  <div className="p-4 text-center text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                    هیچ کالایی انتخاب نشده است.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                    <table className="w-full text-xs text-right">
                      <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                        <tr>
                          <th className="py-2.5 px-3">نام تایر</th>
                          <th className="py-2.5 px-3 text-center">تعداد (حلقه)</th>
                          <th className="py-2.5 px-3">نرخ خرید واحد (ریال)</th>
                          <th className="py-2.5 px-3">جمع</th>
                          <th className="py-2.5 px-3 text-center">حذف</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {purchaseItems.map((item) => (
                          <tr key={item.tireId}>
                            <td className="py-2.5 px-3 font-semibold text-slate-800 dark:text-slate-200">
                              {item.tire.tire_name}
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              <input
                                type="number"
                                min={1}
                                value={item.quantity}
                                onChange={(e) =>
                                  handleUpdateItemQty(item.tireId, parseInt(e.target.value) || 0)
                                }
                                className="w-16 px-2 py-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-center font-bold"
                              />
                            </td>
                            <td className="py-2.5 px-3">
                              <input
                                type="number"
                                min={0}
                                value={item.unitCost}
                                onChange={(e) =>
                                  handleUpdateItemCost(item.tireId, parseFloat(e.target.value) || 0)
                                }
                                className="w-28 px-2 py-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg font-bold tabular-nums text-left"
                              />
                            </td>
                            <td className="py-2.5 px-3 font-bold tabular-nums">
                              {formatCurrency(item.quantity * item.unitCost, true, currencyUnit)}
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              <button
                                type="button"
                                onClick={() => handleRemoveRow(item.tireId)}
                                className="p-1 text-slate-400 hover:text-rose-600"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="flex justify-between items-center p-3 rounded-xl bg-slate-50 dark:bg-slate-800 font-bold">
                <span>جمع کل فاکتور خرید:</span>
                <span className="text-sm text-brand-600 dark:text-brand-400 tabular-nums">
                  {formatCurrency(purchaseTotal, true, currencyUnit)}
                </span>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >
                  {submitting ? 'در حال ثبت...' : 'ثبت ورود به انبار'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
