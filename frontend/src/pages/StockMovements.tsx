import React, { useCallback, useEffect, useState } from 'react';
import { Search, Filter, ArrowDownLeft, ArrowUpRight, SlidersHorizontal } from 'lucide-react';
import { catalogApi } from '../api/catalog';
import { StockMovement } from '../types';
import { formatIsoToJalali } from '../utils/formatters';

export const StockMovements: React.FC = () => {
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const fetchMovements = useCallback(async () => {
    setLoading(true);
    try {
      const data = await catalogApi.getStockMovements({
        search: search.trim() || undefined,
        movement_type: typeFilter || undefined,
        page: currentPage,
      });
      setMovements(data.results || []);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.count || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [search, typeFilter, currentPage]);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Query changes intentionally enter the network loading state.
    void fetchMovements();
  }, [fetchMovements]);

  const getMovementBadge = (type: string, display: string) => {
    switch (type) {
      case 'PURCHASE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <ArrowDownLeft className="w-3 h-3" />
            <span>خرید (ورود به انبار)</span>
          </span>
        );
      case 'SALE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400">
            <ArrowUpRight className="w-3 h-3" />
            <span>فروش (خروج از انبار)</span>
          </span>
        );
      case 'SALE_RETURN':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400">
            <ArrowDownLeft className="w-3 h-3" />
            <span>مرجوعی فروش (ورود سالم)</span>
          </span>
        );
      case 'PURCHASE_CANCEL':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600 dark:text-rose-400">
            <ArrowUpRight className="w-3 h-3" />
            <span>لغو فاکتور خرید</span>
          </span>
        );
      case 'MANUAL_ADJUSTMENT':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/10 text-purple-600 dark:text-purple-400">
            <SlidersHorizontal className="w-3 h-3" />
            <span>انبارگردانی / اصلاح موجودی</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-500/10 text-slate-600 dark:text-slate-400">
            {display || type}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* سربرگ */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">
            دفتر حسابرسی گردش انبار (Stock Movement Ledger)
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            ردیابی کامل و خطاپوش هرگونه تغییر، ورود، خروج و انبارگردانی لاستیک‌ها (مجموع: {totalCount} سند حسابرسی)
          </p>
        </div>
      </div>

      {/* فیلترها و جستجو */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="relative w-full md:w-80">
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="جستجو در شرح یا نام تایر..."
            className="w-full pl-3 pr-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 right-3" />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs outline-none"
          >
            <option value="">همه انواع گردش انبار</option>
            <option value="PURCHASE">فاکتور خرید (ورود)</option>
            <option value="SALE">فاکتور فروش (خروج)</option>
            <option value="SALE_RETURN">مرجوعی فروش</option>
            <option value="MANUAL_ADJUSTMENT">انبارگردانی دستی</option>
            <option value="PURCHASE_CANCEL">لغو فاکتور خرید</option>
            <option value="INITIAL_STOCK">موجودی اولیه سیستم</option>
          </select>
        </div>
      </div>

      {/* جدول گردش انبار */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">در حال دریافت گردش حساب‌ها...</div>
        ) : movements.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-400">رکوردی یافت نشد.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-right">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">شناسه</th>
                  <th className="py-3 px-4">تاریخ و زمان</th>
                  <th className="py-3 px-4">نام تایر و برند</th>
                  <th className="py-3 px-4 text-center">نوع رویداد انبار</th>
                  <th className="py-3 px-4 text-center">تغییر تعداد</th>
                  <th className="py-3 px-4 text-center">مانده پس از رویداد</th>
                  <th className="py-3 px-4">ثبت‌کننده</th>
                  <th className="py-3 px-4">توضیحات و علت</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {movements.map((m) => (
                  <tr key={m.movement_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-mono text-slate-400">#{m.movement_id}</td>
                    <td className="py-3 px-4 text-slate-500">
                      {m.jalali_date || formatIsoToJalali(m.created_at)}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      {m.tire_name}
                      <span className="block text-[10px] text-slate-400 font-normal">
                        {m.brand_name}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {getMovementBadge(m.movement_type, m.movement_type_display)}
                    </td>
                    <td className="py-3 px-4 text-center font-bold tabular-nums">
                      <span
                        className={
                          m.quantity > 0
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : m.quantity < 0
                            ? 'text-rose-600 dark:text-rose-400'
                            : 'text-slate-500'
                        }
                      >
                        {m.quantity > 0 ? `+${m.quantity}` : m.quantity} حلقه
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center font-black text-slate-800 dark:text-slate-200 tabular-nums">
                      {m.balance_after} حلقه
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-400">
                      {m.user_name || 'سیستم'}
                    </td>
                    <td className="py-3 px-4 text-slate-500 max-w-xs truncate" title={m.description}>
                      {m.description || '-'}
                    </td>
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
    </div>
  );
};
