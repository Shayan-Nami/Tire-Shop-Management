import React, { useEffect, useState } from 'react';
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
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { reportsApi } from '../api/reports';
import { catalogApi } from '../api/catalog';
import { DashboardStats, BrandSalesStat, ProfitabilityStat, Tire } from '../types';
import { formatCurrency } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';
import { StockAdjustmentModal } from '../components/catalog/StockAdjustmentModal';

export const Dashboard: React.FC = () => {
  const { currencyUnit, user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [brandSales, setBrandSales] = useState<BrandSalesStat[]>([]);
  const [profitability, setProfitability] = useState<ProfitabilityStat[]>([]);
  const [lowStockTires, setLowStockTires] = useState<Tire[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedTireForAdjust, setSelectedTireForAdjust] = useState<Tire | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsData, brandData, profitData, lowTiresData] = await Promise.all([
        reportsApi.getDashboardStats().catch(() => null),
        reportsApi.getSalesByBrand().catch(() => []),
        reportsApi.getProfitability().catch(() => []),
        catalogApi.getLowStockTires().catch(() => []),
      ]);

      if (statsData) setStats(statsData);
      setBrandSales(brandData);
      setProfitability(profitData);
      setLowStockTires(lowTiresData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Mounting intentionally starts the dashboard network load.
    void loadData();
  }, []);

  const BRAND_COLORS = ['#dc2626', '#2563eb', '#059669', '#d97706', '#7c3aed', '#db2777'];

  return (
    <div className="space-y-6">
      {/* سربرگ داشبورد و خوش‌آمدگویی */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">
            میز کار مدیریت و آمار تحلیلی
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            خلاصه شاخص‌های فروش، گردش کالا و وضعیت مالی در یک نگاه
          </p>
        </div>

        {/* دکمه‌های اقدام سریع */}
        <div className="flex items-center gap-2">
          {(user?.role === 'MANAGER' || user?.role === 'TECHNICIAN') && (
            <Link
              to="/invoices/create"
              className="inline-flex items-center gap-2 px-3.5 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
            >
              <PlusCircle className="w-4 h-4" />
              <span>صدور فاکتور فروش</span>
            </Link>
          )}
          {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
            <Link
              to="/invoices/purchases"
              className="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold rounded-xl transition-all"
            >
              <Boxes className="w-4 h-4" />
              <span>ورود کالا به انبار</span>
            </Link>
          )}
        </div>
      </div>

      {loading && !stats ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
          <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs">در حال بارگذاری شاخص‌های داشبورد...</span>
        </div>
      ) : (
        <>
          {/* ردیف کارت‌های شاخص‌های کلیدی (KPIs) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* ۱. فروش خالص امروز */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold">فروش خالص امروز</span>
            <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-black text-slate-900 dark:text-white tabular-nums">
            {formatCurrency(stats?.today_revenue ?? 0, true, currencyUnit)}
          </div>
          <p className="text-[11px] text-slate-400">
            تعداد فاکتورهای امروز: <span className="font-bold text-slate-700 dark:text-slate-300">{stats?.today_invoices_count ?? 0}</span>
          </p>
        </div>

        {/* ۲. مطالبات معوق فاکتورها */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold">مطالبات معوق فروشگاه</span>
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400">
              <Coins className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-black text-slate-900 dark:text-white tabular-nums">
            {formatCurrency(stats?.total_receivables ?? 0, true, currencyUnit)}
          </div>
          <p className="text-[11px] text-slate-400">
            فاکتورهای تسویه‌نشده: <span className="font-bold text-rose-600 dark:text-rose-400">{stats?.unpaid_invoices_count ?? 0} مورد</span>
          </p>
        </div>

        {/* ۳. ارزش ریالی موجودی انبار */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold">ارزش ریالی موجودی انبار</span>
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
              <Package className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-black text-slate-900 dark:text-white tabular-nums">
            {formatCurrency(stats?.total_inventory_value ?? 0, true, currencyUnit)}
          </div>
          <p className="text-[11px] text-slate-400">
            مجموع لاستیک‌های موجود: <span className="font-bold text-slate-700 dark:text-slate-300">{stats?.total_tires_stock ?? 0} حلقه</span>
          </p>
        </div>

        {/* ۴. هشدارهای کسری موجودی تایرها */}
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold">هشدارهای کمبود موجودی</span>
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-xl font-black text-amber-600 dark:text-amber-400 tabular-nums">
            {stats?.low_stock_count ?? lowStockTires.length} قلم
          </div>
          <p className="text-[11px] text-slate-400">نیاز فوری به سفارش‌گذاری خرید</p>
        </div>
      </div>

      {/* بخش نمودارها */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* نمودار ۱: فروش بر اساس برند */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              میزان فروش به تفکیک برند تایرها
            </h2>
            <span className="text-[11px] text-slate-400">با کسر اقلام مرجوعی</span>
          </div>

          <div className="h-64 w-full">
            {brandSales.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                اطلاعات آماری فروشی جهت نمایش موجود نیست
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={brandSales} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.15} />
                  <XAxis dataKey="brand_name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip
                    formatter={(val: any) => [formatCurrency(val, true, currencyUnit), 'فروش']}
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderRadius: '0.75rem',
                      border: 'none',
                      color: '#fff',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="total_revenue" radius={[6, 6, 0, 0]}>
                    {brandSales.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={BRAND_COLORS[index % BRAND_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* نمودار ۲: سودآورترین محصولات */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white">
              برترین محصولات از نظر سودآوری خالص
            </h2>
            <Link to="/reports" className="text-xs text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1">
              <span>گزارش تفصیلی</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="h-64 w-full overflow-y-auto space-y-2">
            {profitability.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                اطلاعات سودآوری هنوز در سیستم محاسبه نشده است
              </div>
            ) : (
              profitability.slice(0, 5).map((item, idx) => (
                <div
                  key={item.tire_id}
                  className="flex items-center justify-between p-2.5 rounded-xl border border-slate-100 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-800/30 text-xs"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="w-5 h-5 rounded-md bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300 font-bold flex items-center justify-center text-[10px]">
                      {idx + 1}
                    </span>
                    <div className="truncate">
                      <p className="font-bold text-slate-800 dark:text-slate-200 truncate">{item.tire_name}</p>
                      <p className="text-[10px] text-slate-400">
                        فروش: {item.total_sold} حلقه | برند: {item.brand_name}
                      </p>
                    </div>
                  </div>
                  <div className="text-left font-bold text-emerald-600 dark:text-emerald-400 tabular-nums shrink-0 mr-2">
                    {formatCurrency(item.total_profit, true, currencyUnit)}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* جدول تایرهای با کسری یا هشدار موجودی */}
      {lowStockTires.length > 0 && (
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/40 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-5 h-5" />
              <h2 className="text-sm font-bold">
                تایرهای نیازمند سفارش و شارژ انبار (موجودی کمتر یا مساوی نقطه سفارش)
              </h2>
            </div>
            <Link
              to="/catalog/tires"
              className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-white"
            >
              مشاهده تمام تایرها
            </Link>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
            <table className="w-full text-xs text-right">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">نام و مشخصات تایر</th>
                  <th className="py-2.5 px-3">برند / سایز</th>
                  <th className="py-2.5 px-3 text-center">موجودی فعلی</th>
                  <th className="py-2.5 px-3 text-center">حداقل هشدار</th>
                  <th className="py-2.5 px-3 text-center">عملیات انبار</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {lowStockTires.map((tire) => (
                  <tr key={tire.tire_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-2.5 px-3 font-semibold text-slate-800 dark:text-slate-200">
                      {tire.tire_name}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500">
                      {tire.brand_name} - {tire.size_name}
                    </td>
                    <td className="py-2.5 px-3 text-center font-bold text-rose-600 tabular-nums">
                      {tire.stock_quantity} حلقه
                    </td>
                    <td className="py-2.5 px-3 text-center text-slate-500 tabular-nums">
                      {tire.min_stock_alert} حلقه
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={() => setSelectedTireForAdjust(tire)}
                        className="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-lg text-[11px] font-medium transition-colors"
                      >
                        انبارگردانی
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
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
