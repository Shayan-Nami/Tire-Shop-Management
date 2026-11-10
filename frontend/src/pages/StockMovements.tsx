import { useLanguage } from '../context/LanguageContext';
import React, { useCallback, useEffect, useState } from 'react';
import { Search, Filter, ArrowDownLeft, ArrowUpRight, SlidersHorizontal } from 'lucide-react';
import { catalogApi } from '../api/catalog';
import { StockMovement } from '../types';
import { formatIsoToJalali } from '../utils/formatters';

export const StockMovements: React.FC = () => {
  const { t, language } = useLanguage();
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
    void fetchMovements();
  }, [fetchMovements]);

  const getMovementBadge = (type: string, display: string) => {
    switch (type) {
      case 'PURCHASE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <ArrowDownLeft className="w-3 h-3" />
            <span>{t("خرید (ورود به انبار)")}</span>
          </span>
        );
      case 'SALE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400">
            <ArrowUpRight className="w-3 h-3" />
            <span>{t("فروش (خروج از انبار)")}</span>
          </span>
        );
      case 'SALE_RETURN':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400">
            <ArrowDownLeft className="w-3 h-3" />
            <span>{t("مرجوعی فروش (ورود سالم)")}</span>
          </span>
        );
      case 'PURCHASE_CANCEL':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600 dark:text-rose-400">
            <ArrowUpRight className="w-3 h-3" />
            <span>{t("لغو فاکتور خرید")}</span>
          </span>
        );
      case 'MANUAL_ADJUSTMENT':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/10 text-purple-600 dark:text-purple-400">
            <SlidersHorizontal className="w-3 h-3" />
            <span>{t("انبارگردانی / اصلاح موجودی")}</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-500/10 text-slate-600 dark:text-slate-400">
            {language === 'en' ? t(type) : (display || type)}
          </span>
        );
    }
  };

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("دفتر حسابرسی گردش انبار (Stock Movement Ledger)")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("ردیابی کامل و خطاپوش هرگونه تغییر، ورود، خروج و انبارگردانی لاستیک‌ها (مجموع:")}{totalCount}{' '}{t("سند حسابرسی)")}</p>
        </div>
      </div>

      <div className="filter-bar">
        <div className="relative w-full md:w-80">
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setCurrentPage(1);
            }}
            placeholder={t("جستجو در شرح یا نام تایر...")}
            className="ui-field w-full pe-3 ps-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 start-3" />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          <select
            aria-label={t("نوع گردش انبار")}
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="ui-field px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs outline-none"
          >
            <option value="">{t("همه انواع گردش انبار")}</option>
            <option value="PURCHASE">{t("فاکتور خرید (ورود)")}</option>
            <option value="SALE">{t("فاکتور فروش (خروج)")}</option>
            <option value="SALE_RETURN">{t("مرجوعی فروش")}</option>
            <option value="MANUAL_ADJUSTMENT">{t("انبارگردانی دستی")}</option>
            <option value="PURCHASE_CANCEL">{t("لغو فاکتور خرید")}</option>
            <option value="INITIAL_STOCK">{t("موجودی اولیه سیستم")}</option>
          </select>
        </div>
      </div>

      <div className="surface-panel overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("در حال دریافت گردش حساب‌ها...")}</div>
        ) : movements.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("رکوردی یافت نشد.")}</div>
        ) : (
          <div className="table-scroll overflow-x-auto">
            <table className="data-table w-full text-xs text-start">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">{t("شناسه")}</th>
                  <th className="py-3 px-4">{t("تاریخ و زمان")}</th>
                  <th className="py-3 px-4">{t("نام تایر و برند")}</th>
                  <th className="py-3 px-4 text-center">{t("نوع رویداد انبار")}</th>
                  <th className="py-3 px-4 text-center">{t("تغییر تعداد")}</th>
                  <th className="py-3 px-4 text-center">{t("مانده پس از رویداد")}</th>
                  <th className="py-3 px-4">{t("ثبت‌کننده")}</th>
                  <th className="py-3 px-4">{t("توضیحات و علت")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {movements.map((m) => (
                  <tr key={m.movement_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-mono text-slate-400">#{m.movement_id}</td>
                    <td className="py-3 px-4 text-slate-500">
                      {(language === 'fa' && m.jalali_date) || formatIsoToJalali(m.created_at, language)}
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      <bdi dir="auto">{m.tire_name}</bdi>
                      <span className="block text-[10px] text-slate-400 font-normal">
                        <bdi dir="auto">{m.brand_name}</bdi>
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
                        {m.quantity > 0 ? `+${m.quantity}` : m.quantity}{' '}{t("حلقه")}</span>
                    </td>
                    <td className="py-3 px-4 text-center font-black text-slate-800 dark:text-slate-200 tabular-nums">
                      {m.balance_after}{' '}{t("حلقه")}</td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-400">
                      {m.user_name || t("سیستم")}
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
            <span>{t("صفحه")}{' '}{currentPage} {' '}{t("از")} {totalPages}
            </span>
            <div className="flex gap-1">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => p - 1)}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40"
              >{t("قبلی")}</button>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40"
              >{t("بعدی")}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
