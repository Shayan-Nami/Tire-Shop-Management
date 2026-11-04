import { useLanguage } from '../context/LanguageContext';
import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  TrendingUp,
  AlertTriangle,
  Package,
  PlusCircle,
  Coins,
  ArrowUpRight,
  Boxes,
} from 'lucide-react';
import { reportsApi } from '../api/reports';
import { catalogApi } from '../api/catalog';
import { DashboardStats, BrandSalesStat, ProfitabilityStat, Tire } from '../types';
import { formatCurrency } from '../utils/formatters';
import { parseApiError } from '../utils/errorParser';
import { useAuth } from '../context/AuthContext';
import { StockAdjustmentModal } from '../components/catalog/StockAdjustmentModal';

export const Dashboard: React.FC = () => {
  const { t, language } = useLanguage();
  const { currencyUnit, user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [brandSales, setBrandSales] = useState<BrandSalesStat[]>([]);
  const [profitability, setProfitability] = useState<ProfitabilityStat[]>([]);
  const [lowStockTires, setLowStockTires] = useState<Tire[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedTireForAdjust, setSelectedTireForAdjust] = useState<Tire | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [statsData, brandData, profitData, lowTiresData] = await Promise.all([
        reportsApi.getDashboardStats(),
        reportsApi.getSalesByBrand(),
        reportsApi.getProfitability(),
        catalogApi.getLowStockTires(),
      ]);

      if (statsData) setStats(statsData);
      setBrandSales(brandData);
      setProfitability(profitData);
      setLowStockTires(lowTiresData);
    } catch (e) {
      setError(parseApiError(e, t("دریافت اطلاعات ناموفق بود. اتصال را بررسی کنید و دوباره تلاش کنید."), language));
    } finally {
      setLoading(false);
    }
  }, [t, language]);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Mounting intentionally starts the dashboard network load.
    void loadData();
  }, [loadData]);

  const maxBrandRevenue = Math.max(1, ...brandSales.map((brand) => brand.total_revenue));

  return (
    <div className="page-stack">
      {/* سربرگ داشبورد و خوش‌آمدگویی */}
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("میز کار مدیریت و آمار تحلیلی")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("خلاصه شاخص‌های فروش، گردش کالا و وضعیت مالی در یک نگاه")}</p>
        </div>

        {/* دکمه‌های اقدام سریع */}
        <div className="flex items-center gap-2">
          {(user?.role === 'MANAGER' || user?.role === 'TECHNICIAN') && (
            <Link
              to="/invoices/create"
              className="action-primary inline-flex items-center gap-2 px-3.5 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
            >
              <PlusCircle className="w-4 h-4" />
              <span>{t("صدور فاکتور فروش")}</span>
            </Link>
          )}
          {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
            <Link
              to="/invoices/purchases"
              className="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold rounded-xl transition-all"
            >
              <Boxes className="w-4 h-4" />
              <span>{t("ورود کالا به انبار")}</span>
            </Link>
          )}
        </div>
      </div>

      {error ? (
        <div className="surface-panel p-5 space-y-3" role="alert">
          <p>{error}</p>
          <button className="action-secondary" onClick={() => void loadData()}>{t("تلاش دوباره")}</button>
        </div>
      ) : loading && !stats ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
          <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs">{t("در حال بارگذاری شاخص‌های داشبورد...")}</span>
        </div>
      ) : (
        <>
          {/* ردیف کارت‌های شاخص‌های کلیدی (KPIs) */}
          <div className="dashboard-stats surface-panel">
        {/* ۱. فروش خالص امروز */}
        <div className="summary-cell space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold">{t("فروش خالص امروز")}</span>
            <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-black text-slate-900 dark:text-white tabular-nums">
            {formatCurrency(stats?.today_revenue ?? 0, true, currencyUnit, language)}
          </div>
          <p className="text-[11px] text-slate-400">{t("تعداد فاکتورهای امروز:")}<span className="font-bold text-slate-700 dark:text-slate-300">{stats?.today_invoices_count ?? 0}</span>
          </p>
        </div>

        {/* ۲. مطالبات معوق فاکتورها */}
        <div className="summary-cell space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold">{t("مطالبات معوق فروشگاه")}</span>
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400">
              <Coins className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-black text-slate-900 dark:text-white tabular-nums">
            {formatCurrency(stats?.total_receivables ?? 0, true, currencyUnit, language)}
          </div>
          <p className="text-[11px] text-slate-400">{t("فاکتورهای تسویه‌نشده:")}<span className="font-bold text-rose-600 dark:text-rose-400">{stats?.unpaid_invoices_count ?? 0} {' '}{t("مورد")}</span>
          </p>
        </div>

        {/* ۳. ارزش ریالی موجودی انبار */}
        <div className="summary-cell space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold">{t("ارزش ریالی موجودی انبار")}</span>
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
              <Package className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-black text-slate-900 dark:text-white tabular-nums">
            {formatCurrency(stats?.total_inventory_value ?? 0, true, currencyUnit, language)}
          </div>
          <p className="text-[11px] text-slate-400">{t("مجموع لاستیک‌های موجود:")}<span className="font-bold text-slate-700 dark:text-slate-300">{stats?.total_tires_stock ?? 0} {' '}{t("حلقه")}</span>
          </p>
        </div>

        {/* ۴. هشدارهای کسری موجودی تایرها */}
        <div className="summary-cell space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold">{t("هشدارهای کمبود موجودی")}</span>
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-black text-amber-600 dark:text-amber-400 tabular-nums">
            {stats?.low_stock_count ?? lowStockTires.length}{' '}{t("قلم")}</div>
          <p className="text-[11px] text-slate-400">{t("نیاز فوری به سفارش‌گذاری خرید")}</p>
        </div>
      </div>


      {/* بخش نمودارها */}
      <div className="dashboard-middle"><section className="surface-panel" aria-labelledby="brand-sales-title">
          <div className="panel-heading">
            <div>
              <h2 id="brand-sales-title">{t("میزان فروش به تفکیک برند تایرها")}</h2>
              <p>{t("با کسر اقلام مرجوعی · مبالغ به")} {currencyUnit === 'toman' ? t("تومان") : t("ریال")}</p>
            </div>
          </div>
          <div className="brand-sales-chart">
            {brandSales.length === 0 ? (
              <div className="empty-state">{t("اطلاعات آماری فروشی جهت نمایش موجود نیست")}</div>
            ) : (
              <ul className="brand-sales-list" aria-label={t("مقایسه فروش خالص برندها")}>
                {brandSales.map((brand) => (
                  <li key={brand.brand_name} className="brand-sales-item">
                    <div className="brand-sales-label">
                      <strong dir="auto"><bdi dir="auto">{brand.brand_name}</bdi></strong>
                      <bdi className="brand-sales-amount">{formatCurrency(brand.total_revenue, true, currencyUnit, language)}</bdi>
                    </div>
                    <div className="brand-sales-track" aria-hidden="true">
                      <div className="brand-sales-bar" style={{ width: `${brand.total_revenue / maxBrandRevenue * 100}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section><section className="surface-panel" aria-label={t("نیازمند رسیدگی")}>
        <div className="panel-heading"><h2>{t("نیازمند رسیدگی")}</h2><p>{t("پیگیری فروش و موجودی فروشگاه")}</p></div>
        <div className="flex flex-col">
          <Link to="/invoices/sales" className="attention-row"><span className="attention-count">{stats?.unpaid_invoices_count ?? 0}</span><div><strong>{t("فاکتورهای تسویه‌نشده")}</strong><p>{t("مشاهده و پیگیری وضعیت پرداخت")}</p></div><ArrowUpRight className="w-4 h-4 ms-auto" /></Link>
          <Link to="/catalog/tires" className="attention-row"><span className="attention-count">{stats?.low_stock_count ?? lowStockTires.length}</span><div><strong>{t("اقلام با کمبود موجودی")}</strong><p>{t("بررسی موجودی و نقطهٔ سفارش")}</p></div><ArrowUpRight className="w-4 h-4 ms-auto" /></Link>
        </div>
      </section></div><div className="dashboard-bottom">
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/40 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-5 h-5" />
              <h2 className="text-sm font-bold">{t("تایرهای نیازمند سفارش و شارژ انبار (موجودی کمتر یا مساوی نقطه سفارش)")}</h2>
            </div>
            <Link
              to="/catalog/tires"
              className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-white"
            >{t("مشاهده تمام تایرها")}</Link>
          </div>

          {lowStockTires.length === 0 && <p className="empty-state">{t("در حال حاضر تایری با کمبود موجودی وجود ندارد.")}</p>}<div className="table-scroll overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
            <table className="data-table w-full text-xs text-start">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">{t("نام و مشخصات تایر")}</th>
                  <th className="py-2.5 px-3">{t("برند / سایز")}</th>
                  <th className="py-2.5 px-3 text-center">{t("موجودی فعلی")}</th>
                  <th className="py-2.5 px-3 text-center">{t("حداقل هشدار")}</th>
                  <th className="py-2.5 px-3 text-center">{t("عملیات انبار")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {lowStockTires.map((tire) => (
                  <tr key={tire.tire_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-2.5 px-3 font-semibold text-slate-800 dark:text-slate-200">
                      <bdi dir="auto">{tire.tire_name}</bdi>
                    </td>
                    <td className="py-2.5 px-3 text-slate-500">
                      <bdi dir="auto">{tire.brand_name}</bdi> - <bdi dir="auto">{tire.size_name}</bdi>
                    </td>
                    <td className="py-2.5 px-3 text-center font-bold text-rose-600 tabular-nums">
                      {tire.stock_quantity}{' '}{t("حلقه")}</td>
                    <td className="py-2.5 px-3 text-center text-slate-500 tabular-nums">
                      {tire.min_stock_alert}{' '}{t("حلقه")}</td>
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={() => setSelectedTireForAdjust(tire)}
                        className="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-lg text-[11px] font-medium transition-colors"
                      >{t("انبارگردانی")}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      <div className="surface-panel p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">{t("برترین محصولات از نظر سودآوری خالص")}</h2>
            <Link to="/reports" className="text-xs text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1">
              <span>{t("گزارش تفصیلی")}</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="h-64 w-full overflow-y-auto space-y-2">
            {profitability.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">{t("اطلاعات سودآوری هنوز در سیستم محاسبه نشده است")}</div>
            ) : (
              profitability.slice(0, 5).map((item, idx) => (
                <div
                  key={item.tire_id}
                  className="profit-row"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="w-5 h-5 rounded-md bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 font-bold flex items-center justify-center text-[10px]">
                      {idx + 1}
                    </span>
                    <div className="truncate">
                      <p className="font-bold text-slate-800 dark:text-slate-200 truncate"><bdi dir="auto">{item.tire_name}</bdi></p>
                      <p className="text-[10px] text-slate-400">{t("فروش:")}{item.total_sold} {' '}{t("حلقه | برند:")} <bdi dir="auto">{item.brand_name}</bdi>
                      </p>
                    </div>
                  </div>
                  <div className="text-end font-bold text-emerald-600 dark:text-emerald-400 tabular-nums shrink-0 ms-2">
                    {formatCurrency(item.total_profit, true, currencyUnit, language)}
                  </div>
                </div>
              ))
            )}
          </div>
        </div></div>

      {/* جدول تایرهای با کسری یا هشدار موجودی */}

        </>
      )}

      {/* مدال انبارگردانی سریع */}
      {selectedTireForAdjust && (
        <StockAdjustmentModal
          tire={selectedTireForAdjust}
          onClose={() => setSelectedTireForAdjust(null)}
          onSuccess={loadData}
        />
      )}
    </div>
  );
};
