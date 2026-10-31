import React, { useCallback, useEffect, useState } from 'react';
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

export const TiresCatalog: React.FC = () => {
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

  // انبارگردانی
  const [adjustingTire, setAdjustingTire] = useState<Tire | null>(null);

  // تعریف تایر جدید
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newTireName, setNewTireName] = useState<string>('');
  const [newBrandId, setNewBrandId] = useState<number | ''>('');
  const [newSizeId, setNewSizeId] = useState<number | ''>('');
  const [newSalePrice, setNewSalePrice] = useState<string>('');
  const [newPurchasePrice, setNewPurchasePrice] = useState<string>('');
  const [newMinStock, setNewMinStock] = useState<number>(4);
  const [submittingNew, setSubmittingNew] = useState<boolean>(false);

  // برند و سایز جدید پویا
  const [isCustomBrand, setIsCustomBrand] = useState<boolean>(false);
  const [customBrandName, setCustomBrandName] = useState<string>('');
  const [isCustomSize, setIsCustomSize] = useState<boolean>(false);
  const [customSizeName, setCustomSizeName] = useState<string>('');

  // ویرایش نرخ و مشخصات تایر در کاتالوگ
  const [editingTire, setEditingTire] = useState<Tire | null>(null);
  const [editTireName, setEditTireName] = useState<string>('');
  const [editSalePrice, setEditSalePrice] = useState<string>('');

  const [editMinStock, setEditMinStock] = useState<number>(4);
  const [submittingEdit, setSubmittingEdit] = useState<boolean>(false);

  const fetchTires = useCallback(async () => {
    setLoading(true);
    try {
      const data = await catalogApi.getTires({
        search: search.trim() || undefined,
        brand: brandFilter !== '' ? Number(brandFilter) : undefined,
        size: sizeFilter !== '' ? Number(sizeFilter) : undefined,
        page: currentPage,
      });
      setTires(data.results || []);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.count || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [search, brandFilter, sizeFilter, currentPage]);

  useEffect(() => {
    catalogApi.getBrands().then(setBrands).catch(console.error);
    catalogApi.getSizes().then(setSizes).catch(console.error);
  }, []);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Query changes intentionally enter the network loading state.
    void fetchTires();
  }, [fetchTires]);

  const handleCreateTire = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!newTireName || (!newBrandId && !isCustomBrand) || (!newSizeId && !isCustomSize) || !newSalePrice) {
      alert('لطفاً مشخصات الزامی تایر (نام مدل، برند، سایز و قیمت فروش) را تکمیل فرمایید.');
      return;
    }

    setSubmittingNew(true);
    try {
      let finalBrandId = Number(newBrandId);
      if (isCustomBrand) {
        const trimmedBrand = customBrandName.trim();
        if (!trimmedBrand) {
          alert('لطفاً نام برند جدید را وارد فرمایید.');
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
              alert(parseApiError(err, 'خطا در ثبت برند جدید'));
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
          alert('لطفاً سایز جدید تایر را وارد فرمایید.');
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
              alert(parseApiError(err, 'خطا در ثبت سایز جدید'));
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
      alert(parseApiError(err, 'خطا در ثبت تایر جدید'));
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
      alert(parseApiError(err, 'خطا در ویرایش اطلاعات تایر'));
    } finally {
      setSubmittingEdit(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* سربرگ */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">
            کاتالوگ و انبار تایرها
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            مشاهده موجودی انبار، سایزبندی، نرخ‌گذاری و اجرای انبارگردانی دوره‌ای (مجموع: {totalCount} کالا)
          </p>
        </div>

        {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
          >
            <PlusCircle className="w-4 h-4" />
            <span>تعریف تایر جدید</span>
          </button>
        )}
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
            placeholder="جستجو در نام تایر، برند و سایز..."
            className="w-full pl-3 pr-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 right-3" />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          <select
            value={brandFilter}
            onChange={(e) => {
              setBrandFilter(e.target.value ? Number(e.target.value) : '');
              setCurrentPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs outline-none"
          >
            <option value="">همه برندها</option>
            {brands.map((b) => (
              <option key={b.brand_id} value={b.brand_id}>
                {b.brand_name}
              </option>
            ))}
          </select>

          <select
            value={sizeFilter}
            onChange={(e) => {
              setSizeFilter(e.target.value ? Number(e.target.value) : '');
              setCurrentPage(1);
            }}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs outline-none"
          >
            <option value="">همه سایزها</option>
            {sizes.map((s) => (
              <option key={s.size_id} value={s.size_id}>
                {s.size_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* جدول تایرها */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">در حال دریافت کاتالوگ...</div>
        ) : tires.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-400">تایری با این مشخصات یافت نشد.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-right">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">شرح و نام تایر</th>
                  <th className="py-3 px-4">برند</th>
                  <th className="py-3 px-4">سایز</th>
                  <th className="py-3 px-4 text-center">موجودی انبار</th>
                  <th className="py-3 px-4">قیمت فروش پایه</th>
                  {user?.role !== 'TECHNICIAN' && <th className="py-3 px-4">آخرین قیمت خرید</th>}
                  <th className="py-3 px-4 text-center">وضعیت موجودی</th>
                  {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
                    <th className="py-3 px-4 text-center">عملیات</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {tires.map((tire) => (
                  <tr key={tire.tire_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      {tire.tire_name}
                    </td>
                    <td className="py-3 px-4 text-slate-600 dark:text-slate-300 font-medium">
                      {tire.brand_name}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-500">{tire.size_name}</td>
                    <td className="py-3 px-4 text-center font-black text-slate-900 dark:text-white tabular-nums">
                      {tire.stock_quantity} حلقه
                    </td>
                    <td className="py-3 px-4 font-bold text-brand-600 dark:text-brand-400 tabular-nums">
                      {formatCurrency(tire.sale_price, true, currencyUnit)}
                    </td>
                    {user?.role !== 'TECHNICIAN' && (
                      <td className="py-3 px-4 text-slate-500 tabular-nums">
                        {tire.purchase_price
                          ? formatCurrency(tire.purchase_price, true, currencyUnit)
                          : '-'}
                      </td>
                    )}
                    <td className="py-3 px-4 text-center">
                      {tire.stock_quantity <= 0 ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600 dark:text-rose-400">
                          اتمام موجودی
                        </span>
                      ) : tire.is_low_stock ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400">
                          <AlertTriangle className="w-3 h-3" />
                          <span>کسری موجودی</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>موجود کافی</span>
                        </span>
                      )}
                    </td>
                    {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            onClick={() => openEditModal(tire)}
                            title="ویرایش نرخ و مشخصات تایر"
                            className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-brand-600 dark:text-brand-400 transition-colors"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setAdjustingTire(tire)}
                            title="ثبت انبارگردانی و اصلاح موجودی"
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

      {/* مدال انبارگردانی */}
      {adjustingTire && (
        <StockAdjustmentModal
          tire={adjustingTire}
          onClose={() => setAdjustingTire(null)}
          onSuccess={fetchTires}
        />
      )}

      {/* مدال افزودن تایر جدید */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
                تعریف تایر جدید در کاتالوگ
              </h2>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTire} className="p-6 space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">
                  نام کامل تایر (گل / مدل):
                </label>
                <input
                  type="text"
                  required
                  value={newTireName}
                  onChange={(e) => setNewTireName(e.target.value)}
                  placeholder="مثلاً: بارز پریمیوم گریپ P648"
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                {/* انتخاب یا تعریف برند */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="font-bold text-slate-700 dark:text-slate-300 block">برند:</label>
                    <button
                      type="button"
                      onClick={() => {
                        setIsCustomBrand(!isCustomBrand);
                        if (!isCustomBrand) setNewBrandId('');
                      }}
                      className="text-[11px] text-brand-600 dark:text-brand-400 hover:underline font-semibold"
                    >
                      {isCustomBrand ? 'انتخاب از لیست' : '+ برند جدید'}
                    </button>
                  </div>

                  {isCustomBrand ? (
                    <input
                      type="text"
                      required
                      value={customBrandName}
                      onChange={(e) => setCustomBrandName(e.target.value)}
                      placeholder="نام برند جدید (مثلاً: پیرلی)"
                      className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-brand-400 dark:border-brand-600 rounded-xl focus:ring-2 focus:ring-brand-500 outline-none font-semibold text-xs"
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
                      className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium"
                    >
                      <option value="">انتخاب برند...</option>
                      <option value="__NEW__" className="font-bold text-brand-600 dark:text-brand-400">
                        + تعریف برند جدید...
                      </option>
                      {brands.map((b) => (
                        <option key={b.brand_id} value={b.brand_id}>
                          {b.brand_name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {/* انتخاب یا تعریف سایز */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="font-bold text-slate-700 dark:text-slate-300 block">سایز:</label>
                    <button
                      type="button"
                      onClick={() => {
                        setIsCustomSize(!isCustomSize);
                        if (!isCustomSize) setNewSizeId('');
                      }}
                      className="text-[11px] text-brand-600 dark:text-brand-400 hover:underline font-semibold"
                    >
                      {isCustomSize ? 'انتخاب از لیست' : '+ سایز جدید'}
                    </button>
                  </div>

                  {isCustomSize ? (
                    <input
                      type="text"
                      required
                      value={customSizeName}
                      onChange={(e) => setCustomSizeName(e.target.value)}
                      placeholder="سایز جدید (مثلاً: 215/55R17)"
                      className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-brand-400 dark:border-brand-600 rounded-xl focus:ring-2 focus:ring-brand-500 outline-none font-mono text-xs text-left"
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
                      className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-medium"
                    >
                      <option value="">انتخاب سایز...</option>
                      <option value="__NEW__" className="font-bold text-brand-600 dark:text-brand-400">
                        + تعریف سایز جدید...
                      </option>
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
                  <label className="font-bold text-slate-700 dark:text-slate-300 block">
                    قیمت فروش پایه (ریال):
                  </label>
                  <input
                    type="number"
                    required
                    min={0}
                    step={10000}
                    value={newSalePrice}
                    onChange={(e) => setNewSalePrice(e.target.value)}
                    placeholder="مثلاً: 25000000"
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-left font-bold tabular-nums"
                  />
                  {newSalePrice && (
                    <p className="text-[10px] text-slate-400">
                      معادل: {formatCurrency(newSalePrice, true, currencyUnit)}
                    </p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <label className="font-bold text-slate-700 dark:text-slate-300 block">
                    قیمت خرید اولیه (ریال):
                  </label>
                  <input
                    type="number"
                    min={0}
                    step={10000}
                    value={newPurchasePrice}
                    onChange={(e) => setNewPurchasePrice(e.target.value)}
                    placeholder="اختیاری"
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-left font-bold tabular-nums"
                  />
                  {newPurchasePrice && (
                    <p className="text-[10px] text-slate-400">
                      معادل: {formatCurrency(newPurchasePrice, true, currencyUnit)}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">
                  حداقل آستانه هشدار کسری انبار (حلقه):
                </label>
                <input
                  type="number"
                  min={1}
                  value={newMinStock}
                  onChange={(e) => setNewMinStock(parseInt(e.target.value) || 4)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-center font-bold"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={submittingNew}
                  className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >
                  {submittingNew ? 'در حال ثبت...' : 'ثبت تایر'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* مدال ویرایش اطلاعات و به‌روزرسانی نرخ تایر در کاتالوگ */}
      {editingTire && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <div>
                <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
                  ویرایش نرخ و مشخصات تایر
                </h2>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {editingTire.brand_name} - {editingTire.size_name}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setEditingTire(null)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUpdateTire} className="p-6 space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">
                  نام کامل تایر (گل / مدل):
                </label>
                <input
                  type="text"
                  required
                  value={editTireName}
                  onChange={(e) => setEditTireName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-bold text-slate-700 dark:text-slate-300 block">
                    نرخ فروش پایه کاتالوگ (ریال):
                  </label>
                  <input
                    type="number"
                    required
                    min={0}
                    step={10000}
                    value={editSalePrice}
                    onChange={(e) => setEditSalePrice(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-left font-bold tabular-nums"
                  />
                  {editSalePrice && (
                    <p className="text-[10px] text-slate-400">
                      معادل: {formatCurrency(editSalePrice, true, currencyUnit)}
                    </p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="edit-tire-purchase-price" className="font-bold text-slate-700 dark:text-slate-300 block">
                    بهای خرید فعلی (ریال، فقط خواندنی):
                  </label>
                  <input
                    id="edit-tire-purchase-price"
                    type="number"
                    readOnly
                    value={editingTire.purchase_price ?? ''}
                    aria-describedby="edit-tire-purchase-price-help"
                    placeholder="ثبت نشده"
                    className="w-full px-3 py-2 bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-left font-bold tabular-nums"
                  />
                  <p id="edit-tire-purchase-price-help" className="text-[10px] text-slate-500 dark:text-slate-400">
                    بهای خرید پس از ایجاد تایر، از طریق فاکتورهای خرید تعیین می‌شود و در کاتالوگ قابل ویرایش نیست.
                  </p>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">
                  حداقل آستانه هشدار کسری انبار (حلقه):
                </label>
                <input
                  type="number"
                  min={1}
                  value={editMinStock}
                  onChange={(e) => setEditMinStock(parseInt(e.target.value) || 4)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-center font-bold"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingTire(null)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={submittingEdit}
                  className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >
                  {submittingEdit ? 'در حال ذخیره...' : 'ذخیره تغییرات'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
