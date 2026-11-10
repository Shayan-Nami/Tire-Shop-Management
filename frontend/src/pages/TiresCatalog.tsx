import { useLanguage } from '../context/LanguageContext';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Search,
  PlusCircle,
  SlidersHorizontal,
  AlertTriangle,
  CheckCircle2,
  Filter,
  Edit3,
} from 'lucide-react';
import { catalogApi } from '../api/catalog';
import { Tire, Brand, Size } from '../types';
import { formatCurrency } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';
import { StockAdjustmentModal } from '../components/catalog/StockAdjustmentModal';
import { parseApiError } from '../utils/errorParser';
import { createRequestSequence } from '../utils/invoiceRequests';

export const TiresCatalog: React.FC = () => {
  const { t, language } = useLanguage();
  const { currencyUnit, user } = useAuth();
  const [tires, setTires] = useState<Tire[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [sizes, setSizes] = useState<Size[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [brandFilter, setBrandFilter] = useState<number | ''>('');
  const [sizeFilter, setSizeFilter] = useState<number | ''>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const [adjustingTire, setAdjustingTire] = useState<Tire | null>(null);

  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newTireName, setNewTireName] = useState<string>('');
  const [newBrandId, setNewBrandId] = useState<number | ''>('');
  const [newSizeId, setNewSizeId] = useState<number | ''>('');
  const [newSalePrice, setNewSalePrice] = useState<string>('');
  const [newPurchasePrice, setNewPurchasePrice] = useState<string>('');
  const [newMinStock, setNewMinStock] = useState<number>(4);
  const [submittingNew, setSubmittingNew] = useState<boolean>(false);

  const [isCustomBrand, setIsCustomBrand] = useState<boolean>(false);
  const [customBrandName, setCustomBrandName] = useState<string>('');
  const [isCustomSize, setIsCustomSize] = useState<boolean>(false);
  const [customSizeName, setCustomSizeName] = useState<string>('');

  const [editingTire, setEditingTire] = useState<Tire | null>(null);
  const [editTireName, setEditTireName] = useState<string>('');
  const [editSalePrice, setEditSalePrice] = useState<string>('');

  const [editMinStock, setEditMinStock] = useState<number>(4);
  const [submittingEdit, setSubmittingEdit] = useState<boolean>(false);

  const tireRequests = useRef(createRequestSequence());

  useEffect(() => () => tireRequests.current.invalidate(), []);

  const fetchTires = useCallback(async () => {
    const request = tireRequests.current.begin();
    setLoading(true);
    try {
      const data = await catalogApi.getTires({
        search: search.trim() || undefined,
        brand: brandFilter !== '' ? Number(brandFilter) : undefined,
        size: sizeFilter !== '' ? Number(sizeFilter) : undefined,
        page: currentPage,
      });
      if (!tireRequests.current.isCurrent(request)) return;
      setTires(data.results || []);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.count || 0);
    } catch (e) {
      if (tireRequests.current.isCurrent(request)) console.error(e);
    } finally {
      if (tireRequests.current.isCurrent(request)) setLoading(false);
    }
  }, [search, brandFilter, sizeFilter, currentPage]);

  useEffect(() => {
    catalogApi.getBrands().then(setBrands).catch(console.error);
    catalogApi.getSizes().then(setSizes).catch(console.error);
  }, []);

  useEffect(() => {
    void fetchTires();
  }, [fetchTires]);

  const handleCreateTire = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!newTireName || (!newBrandId && !isCustomBrand) || (!newSizeId && !isCustomSize) || !newSalePrice) {
      alert(t("لطفاً مشخصات الزامی تایر (نام مدل، برند، سایز و قیمت فروش) را تکمیل فرمایید."));
      return;
    }

    setSubmittingNew(true);
    try {
      let finalBrandId = Number(newBrandId);
      if (isCustomBrand) {
        const trimmedBrand = customBrandName.trim();
        if (!trimmedBrand) {
          alert(t("لطفاً نام برند جدید را وارد فرمایید."));
          setSubmittingNew(false);
          return;
        }
        const existing = brands.find((b) => b.brand_name.toLowerCase() === trimmedBrand.toLowerCase());
        if (existing) {
          finalBrandId = existing.brand_id;
        } else {
          try {
            const createdBrand = await catalogApi.createBrand({ brand_name: trimmedBrand });
            finalBrandId = createdBrand.brand_id;
            setBrands((prev) => [...prev, createdBrand]);
          } catch (err: unknown) {
            const refreshed = await catalogApi.getBrands();
            setBrands(refreshed);
            const match = refreshed.find((b) => b.brand_name.toLowerCase() === trimmedBrand.toLowerCase());
            if (match) {
              finalBrandId = match.brand_id;
            } else {
              alert(parseApiError(err, t("خطا در ثبت برند جدید"), language));
              setSubmittingNew(false);
              return;
            }
          }
        }
      }

      let finalSizeId = Number(newSizeId);
      if (isCustomSize) {
        const trimmedSize = customSizeName.trim();
        if (!trimmedSize) {
          alert(t("لطفاً سایز جدید تایر را وارد فرمایید."));
          setSubmittingNew(false);
          return;
        }
        const existing = sizes.find((s) => s.size_name.toLowerCase() === trimmedSize.toLowerCase());
        if (existing) {
          finalSizeId = existing.size_id;
        } else {
          try {
            const createdSize = await catalogApi.createSize({ size_name: trimmedSize });
            finalSizeId = createdSize.size_id;
            setSizes((prev) => [...prev, createdSize]);
          } catch (err: unknown) {
            const refreshed = await catalogApi.getSizes();
            setSizes(refreshed);
            const match = refreshed.find((s) => s.size_name.toLowerCase() === trimmedSize.toLowerCase());
            if (match) {
              finalSizeId = match.size_id;
            } else {
              alert(parseApiError(err, t("خطا در ثبت سایز جدید"), language));
              setSubmittingNew(false);
              return;
            }
          }
        }
      }

      await catalogApi.createTire({
        tire_name: newTireName.trim(),
        brand: finalBrandId,
        size: finalSizeId,
        sale_price: parseFloat(newSalePrice),
        purchase_price: newPurchasePrice ? parseFloat(newPurchasePrice) : undefined,
        min_stock_alert: newMinStock,
      });

      setShowAddModal(false);
      setNewTireName('');
      setNewBrandId('');
      setNewSizeId('');
      setIsCustomBrand(false);
      setCustomBrandName('');
      setIsCustomSize(false);
      setCustomSizeName('');
      setNewSalePrice('');
      setNewPurchasePrice('');
      fetchTires();
    } catch (err: unknown) {
      alert(parseApiError(err, t("خطا در ثبت تایر جدید"), language));
    } finally {
      setSubmittingNew(false);
    }
  };

  const openEditModal = (tire: Tire) => {
    setEditingTire(tire);
    setEditTireName(tire.tire_name);
    setEditSalePrice(String(tire.sale_price));

    setEditMinStock(tire.min_stock_alert);
  };

  const handleUpdateTire = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTire || !editSalePrice) return;

    setSubmittingEdit(true);
    try {
      await catalogApi.updateTire(editingTire.tire_id, {
        tire_name: editTireName.trim(),
        sale_price: parseFloat(editSalePrice),

        min_stock_alert: editMinStock,
      });
      setEditingTire(null);
      fetchTires();
    } catch (err: unknown) {
      alert(parseApiError(err, t("خطا در ویرایش اطلاعات تایر"), language));
    } finally {
      setSubmittingEdit(false);
    }
  };

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("کاتالوگ و انبار تایرها")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("مشاهده موجودی انبار، سایزبندی، نرخ‌گذاری و اجرای انبارگردانی دوره‌ای (مجموع:")}{totalCount}{' '}{t("کالا)")}</p>
        </div>

        {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
          <button
            onClick={() => setShowAddModal(true)}
            className="action-primary inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{t("تعریف تایر جدید")}</span>
          </button>
        )}
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
            placeholder={t("جستجو در نام تایر، برند و سایز...")}
            className="ui-field w-full pe-3 ps-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 start-3" />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          <select
            aria-label={t("فیلتر برند")}
            value={brandFilter}
            onChange={(e) => {
              setBrandFilter(e.target.value ? Number(e.target.value) : '');
              setCurrentPage(1);
            }}
            className="ui-field px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs outline-none"
          >
            <option value="">{t("همه برندها")}</option>
            {brands.map((b) => (
              <option key={b.brand_id} value={b.brand_id}>
                {b.brand_name}
              </option>
            ))}
          </select>

          <select
            aria-label={t("فیلتر سایز")}
            value={sizeFilter}
            onChange={(e) => {
              setSizeFilter(e.target.value ? Number(e.target.value) : '');
              setCurrentPage(1);
            }}
            className="ui-field px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs outline-none"
          >
            <option value="">{t("همه سایزها")}</option>
            {sizes.map((s) => (
              <option key={s.size_id} value={s.size_id}>
                {s.size_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="surface-panel overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("در حال دریافت کاتالوگ...")}</div>
        ) : tires.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("تایری با این مشخصات یافت نشد.")}</div>
        ) : (
          <div className="table-scroll overflow-x-auto">
            <table className="data-table w-full text-xs text-start">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">{t("شرح و نام تایر")}</th>
                  <th className="py-3 px-4">{t("برند")}</th>
                  <th className="py-3 px-4">{t("سایز")}</th>
                  <th className="py-3 px-4 text-center">{t("موجودی انبار")}</th>
                  <th className="py-3 px-4">{t("قیمت فروش پایه")}</th>
                  {user?.role !== 'TECHNICIAN' && <th className="py-3 px-4">{t("آخرین قیمت خرید")}</th>}
                  <th className="py-3 px-4 text-center">{t("وضعیت موجودی")}</th>
                  {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
                    <th className="py-3 px-4 text-center">{t("عملیات")}</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {tires.map((tire) => (
                  <tr key={tire.tire_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      <bdi dir="auto">{tire.tire_name}</bdi>
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-300 font-medium">
                      <bdi dir="auto">{tire.brand_name}</bdi>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-500"><bdi dir="auto">{tire.size_name}</bdi></td>
                    <td className="py-3 px-4 text-center font-black text-slate-900 dark:text-white tabular-nums">
                      {tire.stock_quantity}{' '}{t("حلقه")}</td>
                    <td className="py-3 px-4 font-bold text-brand-600 dark:text-brand-400 tabular-nums">
                      {formatCurrency(tire.sale_price, true, currencyUnit, language)}
                    </td>
                    {user?.role !== 'TECHNICIAN' && (
                      <td className="py-3 px-4 text-slate-500 tabular-nums">
                        {tire.purchase_price
                          ? formatCurrency(tire.purchase_price, true, currencyUnit, language)
                          : '-'}
                      </td>
                    )}
                    <td className="py-3 px-4 text-center">
                      {tire.stock_quantity <= 0 ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600 dark:text-rose-400">{t("اتمام موجودی")}</span>
                      ) : tire.is_low_stock ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400">
                          <AlertTriangle className="w-3 h-3" />
                          <span>{t("کسری موجودی")}</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>{t("موجود کافی")}</span>
                        </span>
                      )}
                    </td>
                    {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            onClick={() => openEditModal(tire)}
                            title={t("ویرایش نرخ و مشخصات تایر")}
                            className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-brand-600 dark:text-brand-400 transition-colors"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setAdjustingTire(tire)}
                            title={t("ثبت انبارگردانی و اصلاح موجودی")}
                            className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 transition-colors"
                          >
                            <SlidersHorizontal className="w-3.5 h-3.5" />
                          </button>
                        </div>
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

      {adjustingTire && (
        <StockAdjustmentModal
          tire={adjustingTire}
          onClose={() => setAdjustingTire(null)}
          onSuccess={fetchTires}
        />
      )}

      {showAddModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">{t("تعریف تایر جدید در کاتالوگ")}</h2>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
               aria-label={t("بستن پنجره")}>
                ×
              </button>
            </div>

            <form onSubmit={handleCreateTire} className="p-6 space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("نام کامل تایر (گل / مدل):")}</label>
                <input
                  type="text"
                  required
                  value={newTireName}
                  onChange={(e) => setNewTireName(e.target.value)}
                  placeholder={t("مثلاً: بارز پریمیوم گریپ P648")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("برند:")}</label>
                    <button
                      type="button"
                      onClick={() => {
                        setIsCustomBrand(!isCustomBrand);
                        if (!isCustomBrand) setNewBrandId('');
                      }}
                      className="text-[11px] text-brand-600 dark:text-brand-400 hover:underline font-semibold"
                    >
                      {isCustomBrand ? t("انتخاب از لیست") : t("+ برند جدید")}
                    </button>
                  </div>

                  {isCustomBrand ? (
                    <input
                      type="text"
                      required
                      value={customBrandName}
                      onChange={(e) => setCustomBrandName(e.target.value)}
                      placeholder={t("نام برند جدید (مثلاً: پیرلی)")}
                      className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-brand-400 dark:border-brand-600 rounded-xl focus:ring-2 focus:ring-brand-500 outline-none font-semibold text-xs"
                      autoFocus
                    />
                  ) : (
                    <select
                      required
                      value={newBrandId}
                      onChange={(e) => {
                        if (e.target.value === '__NEW__') {
                          setIsCustomBrand(true);
                          setNewBrandId('');
                        } else {
                          setNewBrandId(Number(e.target.value));
                        }
                      }}
                      className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium"
                    >
                      <option value="">{t("انتخاب برند...")}</option>
                      <option value="__NEW__" className="font-bold text-brand-600 dark:text-brand-400">{t("+ تعریف برند جدید...")}</option>
                      {brands.map((b) => (
                        <option key={b.brand_id} value={b.brand_id}>
                          {b.brand_name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("سایز:")}</label>
                    <button
                      type="button"
                      onClick={() => {
                        setIsCustomSize(!isCustomSize);
                        if (!isCustomSize) setNewSizeId('');
                      }}
                      className="text-[11px] text-brand-600 dark:text-brand-400 hover:underline font-semibold"
                    >
                      {isCustomSize ? t("انتخاب از لیست") : t("+ سایز جدید")}
                    </button>
                  </div>

                  {isCustomSize ? (
                    <input
                      type="text"
                      required
                      value={customSizeName}
                      onChange={(e) => setCustomSizeName(e.target.value)}
                      placeholder={t("سایز جدید (مثلاً: 215/55R17)")}
                      className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-brand-400 dark:border-brand-600 rounded-xl focus:ring-2 focus:ring-brand-500 outline-none font-mono text-xs text-end"
                      autoFocus
                    />
                  ) : (
                    <select
                      required
                      value={newSizeId}
                      onChange={(e) => {
                        if (e.target.value === '__NEW__') {
                          setIsCustomSize(true);
                          setNewSizeId('');
                        } else {
                          setNewSizeId(Number(e.target.value));
                        }
                      }}
                      className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium"
                    >
                      <option value="">{t("انتخاب سایز...")}</option>
                      <option value="__NEW__" className="font-bold text-brand-600 dark:text-brand-400">{t("+ تعریف سایز جدید...")}</option>
                      {sizes.map((s) => (
                        <option key={s.size_id} value={s.size_id}>
                          {s.size_name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("قیمت فروش پایه (ریال):")}</label>
                  <input
                    type="number"
                    required
                    min={0}
                    step={10000}
                    value={newSalePrice}
                    onChange={(e) => setNewSalePrice(e.target.value)}
                    placeholder={t("مثلاً: 25000000")}
                    className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end font-bold tabular-nums"
                  />
                  {newSalePrice && (
                    <p className="text-[10px] text-slate-400">{t("معادل:")}{formatCurrency(newSalePrice, true, currencyUnit, language)}
                    </p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("قیمت خرید اولیه (ریال):")}</label>
                  <input
                    type="number"
                    min={0}
                    step={10000}
                    value={newPurchasePrice}
                    onChange={(e) => setNewPurchasePrice(e.target.value)}
                    placeholder={t("اختیاری")}
                    className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end font-bold tabular-nums"
                  />
                  {newPurchasePrice && (
                    <p className="text-[10px] text-slate-400">{t("معادل:")}{formatCurrency(newPurchasePrice, true, currencyUnit, language)}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("حداقل آستانه هشدار کسری انبار (حلقه):")}</label>
                <input
                  type="number"
                  min={1}
                  value={newMinStock}
                  onChange={(e) => setNewMinStock(parseInt(e.target.value) || 4)}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-center font-bold"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >{t("انصراف")}</button>
                <button
                  type="submit"
                  disabled={submittingNew}
                  className="action-primary px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >
                  {submittingNew ? t("در حال ثبت...") : t("ثبت تایر")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingTire && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <div>
                <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">{t("ویرایش نرخ و مشخصات تایر")}</h2>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  <bdi dir="auto">{editingTire.brand_name}</bdi> - <bdi dir="auto">{editingTire.size_name}</bdi>
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEditingTire(null)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
               aria-label={t("بستن پنجره")}>
                ×
              </button>
            </div>

            <form onSubmit={handleUpdateTire} className="p-6 space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("نام کامل تایر (گل / مدل):")}</label>
                <input
                  type="text"
                  required
                  value={editTireName}
                  onChange={(e) => setEditTireName(e.target.value)}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("نرخ فروش پایه کاتالوگ (ریال):")}</label>
                  <input
                    type="number"
                    required
                    min={0}
                    step={10000}
                    value={editSalePrice}
                    onChange={(e) => setEditSalePrice(e.target.value)}
                    className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end font-bold tabular-nums"
                  />
                  {editSalePrice && (
                    <p className="text-[10px] text-slate-400">{t("معادل:")}{formatCurrency(editSalePrice, true, currencyUnit, language)}
                    </p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="edit-tire-purchase-price" className="font-bold text-slate-700 dark:text-slate-300 block">{t("بهای خرید فعلی (ریال، فقط خواندنی):")}</label>
                  <input
                    id="edit-tire-purchase-price"
                    type="number"
                    readOnly
                    value={editingTire.purchase_price ?? ''}
                    aria-describedby="edit-tire-purchase-price-help"
                    placeholder={t("ثبت نشده")}
                    className="ui-field w-full px-3 py-2 bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end font-bold tabular-nums"
                  />
                  <p id="edit-tire-purchase-price-help" className="text-[10px] text-slate-500 dark:text-slate-400">{t("بهای خرید پس از ایجاد تایر، از طریق فاکتورهای خرید تعیین می‌شود و در کاتالوگ قابل ویرایش نیست.")}</p>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("حداقل آستانه هشدار کسری انبار (حلقه):")}</label>
                <input
                  type="number"
                  min={1}
                  value={editMinStock}
                  onChange={(e) => setEditMinStock(parseInt(e.target.value) || 4)}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-center font-bold"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingTire(null)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >{t("انصراف")}</button>
                <button
                  type="submit"
                  disabled={submittingEdit}
                  className="action-primary px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >
                  {submittingEdit ? t("در حال ذخیره...") : t("ذخیره تغییرات")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
