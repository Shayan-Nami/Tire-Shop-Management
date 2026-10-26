import React, { useEffect, useState } from 'react';
import {
  TrendingUp,
  Package,
  Calendar,
} from 'lucide-react';
import { reportsApi } from '../api/reports';
import { ProfitabilityStat } from '../types';
import { formatCurrency } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';

export const ReportsPage: React.FC = () => {
  const { currencyUnit } = useAuth();
  const [activeTab, setActiveTab] = useState<'profitability' | 'inventory_value' | 'by_date'>('profitability');
  const [loading, setLoading] = useState<boolean>(true);

  // داده‌های سودآوری
  const [profitabilityData, setProfitabilityData] = useState<ProfitabilityStat[]>([]);

  // داده‌های ارزش انبار
  const [inventoryValueData, setInventoryValueData] = useState<{
    total_inventory_value: number;
    items: any[];
  } | null>(null);

  // فروش بر اساس تاریخ
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [dateSalesResult, setDateSalesResult] = useState<{
    total_invoices: number;
    total_sales_amount: number;
  } | null>(null);

  const loadReport = async () => {
    setLoading(true);
    try {
      if (activeTab === 'profitability') {
        const data = await reportsApi.getProfitability();
        setProfitabilityData(data);
      } else if (activeTab === 'inventory_value') {
        const data = await reportsApi.getInventoryValue();
        setInventoryValueData(data);
      } else {
        const data = await reportsApi.getSalesByDateRange(startDate || undefined, endDate || undefined);
        setDateSalesResult(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Switching reports intentionally enters the network loading state.
    void loadReport();
    // oxlint-disable-next-line react-hooks/exhaustive-deps -- Dates are applied by form submission, not on every keystroke.
  }, [activeTab]);

  const handleDateFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadReport();
  };

  return (
    <div className="space-y-6">
      {/* سربرگ */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">
            گزارش‌های تحلیلی، سودآوری و ارزش انبار
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            محاسبه دقیق حاشیه سود تایرها، ارزش ریالی موجودی کالا و درآمد خالص فروش
          </p>
        </div>
      </div>

      {/* تب‌های گزارشات */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-2">
        <button
          onClick={() => setActiveTab('profitability')}
          className={`flex items-center gap-2 py-3 px-4 font-bold text-xs border-b-2 transition-all ${
            activeTab === 'profitability'
              ? 'border-brand-600 text-brand-600 dark:text-brand-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          <span>سودآوری تایرها (Profitability)</span>
        </button>

        <button
          onClick={() => setActiveTab('inventory_value')}
          className={`flex items-center gap-2 py-3 px-4 font-bold text-xs border-b-2 transition-all ${
            activeTab === 'inventory_value'
              ? 'border-brand-600 text-brand-600 dark:text-brand-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          <Package className="w-4 h-4" />
          <span>ارزش ریالی موجودی انبار (Inventory Valuation)</span>
        </button>

        <button
          onClick={() => setActiveTab('by_date')}
          className={`flex items-center gap-2 py-3 px-4 font-bold text-xs border-b-2 transition-all ${
            activeTab === 'by_date'
              ? 'border-brand-600 text-brand-600 dark:text-brand-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>گزارش فروش بازه تاریخی</span>
        </button>
      </div>

      {/* تب ۱: سودآوری تایرها */}
      {activeTab === 'profitability' && (
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          {loading ? (
            <div className="py-16 text-center text-xs text-slate-400">در حال محاسبه حاشیه سود...</div>
          ) : profitabilityData.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-400">اطلاعاتی یافت نشد.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-right">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4">نام و مشخصات تایر</th>
                    <th className="py-3 px-4">برند / سایز</th>
                    <th className="py-3 px-4 text-center">تعداد فروش خالص</th>
                    <th className="py-3 px-4">درآمد ناخالص</th>
                    <th className="py-3 px-4">بهای تمام‌شده خرید</th>
                    <th className="py-3 px-4">سود خالص فروش</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {profitabilityData.map((item) => (
                    <tr key={item.tire_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                        {item.tire_name}
                      </td>
                      <td className="py-3 px-4 text-slate-500">
                        {item.brand_name} - {item.size_name}
                      </td>
                      <td className="py-3 px-4 text-center font-bold tabular-nums">
                        {item.total_sold} حلقه
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-700 dark:text-slate-300 tabular-nums">
                        {formatCurrency(item.total_revenue, true, currencyUnit)}
                      </td>
                      <td className="py-3 px-4 text-slate-500 tabular-nums">
                        {formatCurrency(item.total_cost, true, currencyUnit)}
                      </td>
                      <td className="py-3 px-4 font-black text-emerald-600 dark:text-emerald-400 tabular-nums">
                        {formatCurrency(item.total_profit, true, currencyUnit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* تب ۲: ارزش ریالی انبار */}
      {activeTab === 'inventory_value' && (
        <div className="space-y-4">
          <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-900 to-slate-850 text-white flex items-center justify-between border border-slate-800 shadow-md">
            <div>
              <span className="text-xs text-slate-400 block">ارزش ریالی کل موجودی انبار لاستیک:</span>
              <div className="text-2xl font-black text-white tabular-nums mt-1">
                {formatCurrency(inventoryValueData?.total_inventory_value ?? 0, true, currencyUnit)}
              </div>
            </div>
            <div className="p-3 bg-white/10 rounded-xl text-white">
              <Package className="w-8 h-8" />
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            {loading ? (
              <div className="py-16 text-center text-xs text-slate-400">در حال ارزیابی موجودی انبار...</div>
            ) : !inventoryValueData || inventoryValueData.items.length === 0 ? (
              <div className="py-16 text-center text-xs text-slate-400">انباری خالی است.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-right">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-3 px-4">نام تایر</th>
                      <th className="py-3 px-4">برند و سایز</th>
                      <th className="py-3 px-4 text-center">موجودی فیزیکی</th>
                      <th className="py-3 px-4">نرخ خرید واحد</th>
                      <th className="py-3 px-4">ارزش کل موجودی کالا</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {inventoryValueData.items.map((item) => (
                      <tr key={item.tire_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                          {item.tire_name}
                        </td>
                        <td className="py-3 px-4 text-slate-500">
                          {item.brand_name} - {item.size_name}
                        </td>
                        <td className="py-3 px-4 text-center font-bold tabular-nums">
                          {item.stock_quantity} حلقه
                        </td>
                        <td className="py-3 px-4 text-slate-500 tabular-nums">
                          {formatCurrency(item.purchase_price, true, currencyUnit)}
                        </td>
                        <td className="py-3 px-4 font-black text-slate-900 dark:text-white tabular-nums">
                          {formatCurrency(item.inventory_value, true, currencyUnit)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* تب ۳: فروش بازه تاریخی */}
      {activeTab === 'by_date' && (
        <div className="space-y-4">
          <form
            onSubmit={handleDateFilterSubmit}
            className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-wrap gap-4 items-end"
          >
            <div className="space-y-1 text-xs">
              <label className="font-bold text-slate-700 dark:text-slate-300">از تاریخ (شمسی / میلادی):</label>
              <input
                type="text"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                placeholder="1403/01/01 یا 2026-01-01"
                className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-left"
              />
            </div>

            <div className="space-y-1 text-xs">
              <label className="font-bold text-slate-700 dark:text-slate-300">تا تاریخ (شمسی / میلادی):</label>
              <input
                type="text"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                placeholder="1403/12/29 یا 2026-12-31"
                className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-left"
              />
            </div>

            <button
              type="submit"
              className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold text-xs shadow-sm"
            >
              محاسبه گزارش فروش
            </button>
          </form>

          {dateSalesResult && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                <span className="text-xs text-slate-500">تعداد فاکتورهای تاییدشده در بازه:</span>
                <div className="text-2xl font-black text-slate-900 dark:text-white tabular-nums mt-1">
                  {dateSalesResult.total_invoices} فاکتور
                </div>
              </div>

              <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                <span className="text-xs text-slate-500">مجموع فروش خالص (پس از کسر مرجوعی):</span>
                <div className="text-2xl font-black text-brand-600 dark:text-brand-400 tabular-nums mt-1">
                  {formatCurrency(dateSalesResult.total_sales_amount, true, currencyUnit)}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
