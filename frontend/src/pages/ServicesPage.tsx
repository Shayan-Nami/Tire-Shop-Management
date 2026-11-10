import { useLanguage } from '../context/LanguageContext';
import React, { useCallback, useEffect, useState } from 'react';
import { Search, PlusCircle, Trash2, Edit2 } from 'lucide-react';
import { servicesApi } from '../api/services';
import { TechnicalService } from '../types';
import { formatCurrency } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';
import { parseApiError } from '../utils/errorParser';

export const ServicesPage: React.FC = () => {
  const { t, language } = useLanguage();
  const { currencyUnit, user } = useAuth();
  const [services, setServices] = useState<TechnicalService[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const [showModal, setShowModal] = useState<boolean>(false);
  const [editingService, setEditingService] = useState<TechnicalService | null>(null);
  const [name, setName] = useState<string>('');
  const [price, setPrice] = useState<string>('');
  const [description, setDescription] = useState<string>('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchServices = useCallback(async () => {
    setLoading(true);
    try {
      const data = await servicesApi.getServices({
        search: debouncedSearch.trim() || undefined,
        page: currentPage,
      });
      setServices(data.results || []);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.count || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, currentPage]);

  useEffect(() => {
    void fetchServices();
  }, [fetchServices]);

  const handleOpenAdd = () => {
    setEditingService(null);
    setName('');
    setPrice('');
    setDescription('');
    setShowModal(true);
  };

  const handleOpenEdit = (srv: TechnicalService) => {
    setEditingService(srv);
    setName(srv.service_name);
    setPrice(String(srv.price));
    setDescription(srv.description || '');
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingService) {
        await servicesApi.updateService(editingService.service_id, {
          service_name: name,
          price: parseFloat(price),
          description: description || undefined,
        });
      } else {
        await servicesApi.createService({
          service_name: name,
          price: parseFloat(price),
          description: description || undefined,
        });
      }
      setShowModal(false);
      fetchServices();
    } catch (err: unknown) {
      alert(parseApiError(err, t("خطا در ثبت خدمت فنی"), language));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm(t("آیا از حذف این خدمت فنی اطمینان دارید؟"))) return;
    try {
      await servicesApi.deleteService(id);
      fetchServices();
    } catch (err: unknown) {
      alert(parseApiError(err, t("امکان حذف این خدمت به دلیل استفاده در فاکتورهای صادرشده وجود ندارد."), language));
    }
  };

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("تعرفه خدمات فنی و کارگاهی")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("مدیریت نرخ‌های مصوب تعویض تایر، بالانس درجا، نیتروژن و آپارات (مجموع:")}{totalCount}{' '}{t("خدمت)")}</p>
        </div>

        {user?.role === 'MANAGER' && (
          <button
            onClick={handleOpenAdd}
            className="action-primary inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{t("تعریف خدمت فنی جدید")}</span>
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
            placeholder={t("جستجو در نام خدمت کارگاهی یا توضیحات...")}
            className="ui-field w-full pe-3 ps-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 start-3" />
        </div>
      </div>

      <div className="surface-panel overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("در حال دریافت خدمات فنی...")}</div>
        ) : services.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("خدمتی با این مشخصات یافت نشد.")}</div>
        ) : (
          <div className="table-scroll overflow-x-auto">
            <table className="data-table w-full text-xs text-start">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">{t("عنوان خدمت کارگاهی")}</th>
                  <th className="py-3 px-4">{t("تعرفه مصوب")}</th>
                  <th className="py-3 px-4">{t("توضیحات و دامنه اجرا")}</th>
                  {user?.role === 'MANAGER' && <th className="py-3 px-4 text-center">{t("عملیات")}</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {services.map((srv) => (
                  <tr key={srv.service_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      <bdi dir="auto">{srv.service_name}</bdi>
                    </td>
                    <td className="py-3 px-4 font-black text-brand-600 dark:text-brand-400 tabular-nums">
                      {formatCurrency(srv.price, true, currencyUnit, language)}
                    </td>
                    <td className="py-3 px-4 text-slate-500">{srv.description || '-'}</td>
                    {user?.role === 'MANAGER' && (
                      <td className="py-3 px-4 text-center">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            aria-label={t("ویرایش خدمت")}
                            title={t("ویرایش خدمت")}
                            onClick={() => handleOpenEdit(srv)}
                            className="p-1 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            aria-label={t("حذف خدمت")}
                            title={t("حذف خدمت")}
                            onClick={() => handleDelete(srv.service_id)}
                            className="p-1 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
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
            <span>{t("صفحه")}{' '}{currentPage} {' '}{t("از")} {totalPages} {t("(مجموع")} {totalCount}{' '}{t("خدمت)")}</span>
            <div className="flex gap-1">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => p - 1)}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              >{t("قبلی")}</button>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
                className="px-3 py-1 rounded-lg border border-slate-300 dark:border-slate-700 disabled:opacity-40 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              >{t("بعدی")}</button>
            </div>
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
                {editingService ? t("ویرایش تعرفه خدمت") : t("تعریف خدمت کارگاهی جدید")}
              </h2>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
               aria-label={t("بستن پنجره")}>
                ×
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("عنوان خدمت:")}</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("مثلاً: تنظیم باد با نیتروژن ۴ چرخ")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("تعرفه مصوب (ریال):")}</label>
                <input
                  type="number"
                  required
                  min={0}
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder={t("مثلاً: 1500000")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end font-bold tabular-nums"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("توضیحات و شرح:")}</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("شامل باز و بست چرخ...")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >{t("انصراف")}</button>
                <button
                  type="submit"
                  className="action-primary px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >{t("ذخیره تعرفه")}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
