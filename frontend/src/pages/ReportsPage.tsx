import { useLanguage } from '../context/LanguageContext';
import React, { useEffect, useState } from 'react';
import {
  TrendingUp,
  Package,
  Calendar,
} from 'lucide-react';
import { reportsApi } from '../api/reports';
import { InventoryValueResponse, ProfitabilityStat, SalesByDateRangeResponse } from '../types';
import { formatCurrency } from '../utils/formatters';
import { parseApiError } from '../utils/errorParser';
import { useAuth } from '../context/AuthContext';

export const ReportsPage: React.FC = () => {
  const { t, language } = useLanguage();
  const { currencyUnit } = useAuth();
  const [activeTab, setActiveTab] = useState<'profitability' | 'inventory_value' | 'by_date'>('profitability');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState<boolean>(true);

  const [profitabilityData, setProfitabilityData] = useState<ProfitabilityStat[]>([]);

  const [inventoryValueData, setInventoryValueData] = useState<InventoryValueResponse | null>(null);

  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [dateSalesResult, setDateSalesResult] = useState<SalesByDateRangeResponse | null>(null);

  const loadReport = async () => {
    setLoading(true);
    setError('');
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
      setError(parseApiError(e, t("دریافت اطلاعات ناموفق بود. اتصال را بررسی کنید و دوباره تلاش کنید."), language));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadReport();
  }, [activeTab]);

  const handleDateFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadReport();
  };

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("گزارش‌های تحلیلی، سودآوری و ارزش انبار")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("محاسبه دقیق حاشیه سود تایرها، ارزش ریالی موجودی کالا و درآمد خالص فروش")}</p>
        </div>
      </div>

      <div className="tab-bar">
        <button
          onClick={() => setActiveTab('profitability')}
          aria-pressed={activeTab === 'profitability'}
          className={`flex items-center gap-2 py-3 px-4 font-bold text-xs border-b-2 transition-all ${
            activeTab === 'profitability'
              ? 'border-brand-600 text-brand-600 dark:text-brand-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          <span>{t("سودآوری تایرها (Profitability)")}</span>
        </button>

        <button
          onClick={() => setActiveTab('inventory_value')}
          aria-pressed={activeTab === 'inventory_value'}
          className={`flex items-center gap-2 py-3 px-4 font-bold text-xs border-b-2 transition-all ${
            activeTab === 'inventory_value'
              ? 'border-brand-600 text-brand-600 dark:text-brand-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          <Package className="w-4 h-4" />
          <span>{t("ارزش ریالی موجودی انبار (Inventory Valuation)")}</span>
        </button>

        <button
          onClick={() => setActiveTab('by_date')}
          aria-pressed={activeTab === 'by_date'}
          className={`flex items-center gap-2 py-3 px-4 font-bold text-xs border-b-2 transition-all ${
            activeTab === 'by_date'
              ? 'border-brand-600 text-brand-600 dark:text-brand-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>{t("گزارش فروش بازه تاریخی")}</span>
        </button>
      </div>

      {error && (
        <div className="surface-panel p-5 space-y-3" role="alert">
          <p>{error}</p>
          <button className="action-secondary" onClick={() => void loadReport()}>{t("تلاش دوباره")}</button>
        </div>
      )}

      {!error && activeTab === 'profitability' && (
        <div className="surface-panel overflow-hidden">
          {loading ? (
            <div className="py-16 text-center text-xs text-slate-400">{t("در حال محاسبه حاشیه سود...")}</div>
          ) : profitabilityData.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-400">{t("اطلاعاتی یافت نشد.")}</div>
          ) : (
            <div className="table-scroll overflow-x-auto">
              <table className="data-table w-full text-xs text-start">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4">{t("نام و مشخصات تایر")}</th>
                    <th className="py-3 px-4">{t("برند / سایز")}</th>
                    <th className="py-3 px-4 text-center">{t("تعداد فروش خالص")}</th>
                    <th className="py-3 px-4">{t("درآمد ناخالص")}</th>
                    <th className="py-3 px-4">{t("بهای تمام‌شده خرید")}</th>
                    <th className="py-3 px-4">{t("سود خالص فروش")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {profitabilityData.map((item) => (
                    <tr key={item.tire_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                        <bdi dir="auto">{item.tire_name}</bdi>
                      </td>
                      <td className="py-3 px-4 text-slate-500">
                        <bdi dir="auto">{item.brand_name}</bdi> - <bdi dir="auto">{item.size_name}</bdi>
                      </td>
                      <td className="py-3 px-4 text-center font-bold tabular-nums">
                        {item.total_sold}{' '}{t("حلقه")}</td>
                      <td className="py-3 px-4 font-bold text-slate-700 dark:text-slate-300 tabular-nums">
                        {formatCurrency(item.total_revenue, true, currencyUnit, language)}
                      </td>
                      <td className="py-3 px-4 text-slate-500 tabular-nums">
                        {formatCurrency(item.total_cost, true, currencyUnit, language)}
                      </td>
                      <td className="py-3 px-4 font-black text-emerald-600 dark:text-emerald-400 tabular-nums">
                        {formatCurrency(item.total_profit, true, currencyUnit, language)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!error && activeTab === 'inventory_value' && (
        <div className="space-y-4">
          <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-900 to-slate-850 text-white flex items-center justify-between border border-slate-800 shadow-md">
            <div>
              <span className="text-xs text-slate-400 block">{t("ارزش ریالی کل موجودی انبار لاستیک:")}</span>
              <div className="text-2xl font-black text-white tabular-nums mt-1">
                {formatCurrency(inventoryValueData?.total_inventory_value ?? 0, true, currencyUnit, language)}
              </div>
            </div>
            <div className="p-3 bg-white/10 rounded-xl text-white">
              <Package className="w-8 h-8" />
            </div>
          </div>

          <div className="surface-panel overflow-hidden">
            {loading ? (
              <div className="py-16 text-center text-xs text-slate-400">{t("در حال ارزیابی موجودی انبار...")}</div>
            ) : !inventoryValueData || inventoryValueData.items.length === 0 ? (
              <div className="py-16 text-center text-xs text-slate-400">{t("انباری خالی است.")}</div>
            ) : (
              <div className="table-scroll overflow-x-auto">
                <table className="data-table w-full text-xs text-start">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-3 px-4">{t("نام تایر")}</th>
                      <th className="py-3 px-4">{t("برند و سایز")}</th>
                      <th className="py-3 px-4 text-center">{t("موجودی فیزیکی")}</th>
                      <th className="py-3 px-4">{t("نرخ خرید واحد")}</th>
                      <th className="py-3 px-4">{t("ارزش کل موجودی کالا")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {inventoryValueData.items.map((item) => (
                      <tr key={item.tire_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                          <bdi dir="auto">{item.tire_name}</bdi>
                        </td>
                        <td className="py-3 px-4 text-slate-500">
                          <bdi dir="auto">{item.brand_name}</bdi> - <bdi dir="auto">{item.size_name}</bdi>
                        </td>
                        <td className="py-3 px-4 text-center font-bold tabular-nums">
                          {item.stock_quantity}{' '}{t("حلقه")}</td>
                        <td className="py-3 px-4 text-slate-500 tabular-nums">
                          {formatCurrency(item.purchase_price, true, currencyUnit, language)}
                        </td>
                        <td className="py-3 px-4 font-black text-slate-900 dark:text-white tabular-nums">
                          {formatCurrency(item.inventory_value, true, currencyUnit, language)}
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

      {!error && activeTab === 'by_date' && (
        <div className="space-y-4">
          <form
            onSubmit={handleDateFilterSubmit}
            className="p-4 surface-panel flex flex-wrap gap-4 items-end"
          >
            <div className="space-y-1 text-xs">
              <label className="font-bold text-slate-700 dark:text-slate-300">{t("از تاریخ (شمسی / میلادی):")}</label>
              <input
                type="text"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                placeholder={t("1403/01/01 یا 2026-01-01")}
                className="ui-field px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end"
              />
            </div>

            <div className="space-y-1 text-xs">
              <label className="font-bold text-slate-700 dark:text-slate-300">{t("تا تاریخ (شمسی / میلادی):")}</label>
              <input
                type="text"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                placeholder={t("1403/12/29 یا 2026-12-31")}
                className="ui-field px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end"
              />
            </div>

            <button
              type="submit"
              className="action-primary px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold text-xs shadow-sm"
            >{t("محاسبه گزارش فروش")}</button>
          </form>

          {dateSalesResult && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-5 surface-panel">
                <span className="text-xs text-slate-500">{t("تعداد فاکتورهای تاییدشده در بازه:")}</span>
                <div className="text-2xl font-black text-slate-900 dark:text-white tabular-nums mt-1">
                  {dateSalesResult.total_invoices}{' '}{t("فاکتور")}</div>
              </div>

              <div className="p-5 surface-panel">
                <span className="text-xs text-slate-500">{t("مجموع فروش خالص (پس از کسر مرجوعی):")}</span>
                <div className="text-2xl font-black text-brand-600 dark:text-brand-400 tabular-nums mt-1">
                  {formatCurrency(dateSalesResult.total_sales_amount, true, currencyUnit, language)}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
