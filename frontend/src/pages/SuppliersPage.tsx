import { useLanguage } from '../context/LanguageContext';
import React, { useCallback, useEffect, useState } from 'react';
import { Search, PlusCircle, Trash2, Edit2 } from 'lucide-react';
import { suppliersApi } from '../api/suppliers';
import { Supplier } from '../types';
import { useAuth } from '../context/AuthContext';
import { parseApiError } from '../utils/errorParser';

export const SuppliersPage: React.FC = () => {
  const { t, language } = useLanguage();
  const { user } = useAuth();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const [showModal, setShowModal] = useState<boolean>(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [name, setName] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [address, setAddress] = useState<string>('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchSuppliers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await suppliersApi.getSuppliers({
        search: debouncedSearch.trim() || undefined,
        page: currentPage,
      });
      setSuppliers(data.results || []);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.count || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, currentPage]);

  useEffect(() => {
    void fetchSuppliers();
  }, [fetchSuppliers]);

  const handleOpenAdd = () => {
    setEditingSupplier(null);
    setName('');
    setPhone('');
    setAddress('');
    setShowModal(true);
  };

  const handleOpenEdit = (sup: Supplier) => {
    setEditingSupplier(sup);
    setName(sup.supplier_name);
    setPhone(sup.phone_number || '');
    setAddress(sup.address || '');
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingSupplier) {
        await suppliersApi.updateSupplier(editingSupplier.supplier_id, {
          supplier_name: name,
          phone_number: phone || undefined,
          address: address || undefined,
        });
      } else {
        await suppliersApi.createSupplier({
          supplier_name: name,
          phone_number: phone || undefined,
          address: address || undefined,
        });
      }
      setShowModal(false);
      fetchSuppliers();
    } catch (err: unknown) {
      alert(parseApiError(err, t("خطا در ثبت تأمین‌کننده"), language));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm(t("آیا از حذف این تأمین‌کننده اطمینان دارید؟"))) return;
    try {
      await suppliersApi.deleteSupplier(id);
      fetchSuppliers();
    } catch (err: unknown) {
      alert(parseApiError(err, t("امکان حذف تأمین‌کننده به دلیل وجود فاکتورهای خرید ثبت‌شده وجود ندارد."), language));
    }
  };

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("تأمین‌کنندگان و نمایندگی‌های لاستیک")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("اطلاعات شرکت‌های پخش تایر، نمایندگی‌های رسمی کارخانجات و آدرس انبارها (مجموع:")}{totalCount}{' '}{t("شرکت)")}</p>
        </div>

        {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
          <button
            onClick={handleOpenAdd}
            className="action-primary inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{t("ثبت تأمین‌کننده جدید")}</span>
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
            placeholder={t("جستجو در نام شرکت یا تلفن یا نشانی...")}
            className="ui-field w-full pe-3 ps-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 start-3" />
        </div>
      </div>

      <div className="surface-panel overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("در حال دریافت اطلاعات تأمین‌کنندگان...")}</div>
        ) : suppliers.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("تأمین‌کننده‌ای با این مشخصات یافت نشد.")}</div>
        ) : (
          <div className="table-scroll overflow-x-auto">
            <table className="data-table w-full text-xs text-start">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">{t("نام شرکت / نمایندگی")}</th>
                  <th className="py-3 px-4">{t("شماره تلفن")}</th>
                  <th className="py-3 px-4">{t("نشانی و دفتر مرکزی")}</th>
                  {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
                    <th className="py-3 px-4 text-center">{t("عملیات")}</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {suppliers.map((sup) => (
                  <tr key={sup.supplier_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      <bdi dir="auto">{sup.supplier_name}</bdi>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-700 dark:text-slate-300">
                      {sup.phone_number || '-'}
                    </td>
                    <td className="py-3 px-4 text-slate-500">{sup.address || '-'}</td>
                    {(user?.role === 'MANAGER' || user?.role === 'WAREHOUSE') && (
                      <td className="py-3 px-4 text-center">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            aria-label={t("ویرایش تأمین‌کننده")}
                            title={t("ویرایش تأمین‌کننده")}
                            onClick={() => handleOpenEdit(sup)}
                            className="p-1 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          {user?.role === 'MANAGER' && (
                            <button
                              aria-label={t("حذف تأمین‌کننده")}
                            title={t("حذف تأمین‌کننده")}
                            onClick={() => handleDelete(sup.supplier_id)}
                              className="p-1 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
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
            <span>{t("صفحه")}{' '}{currentPage} {' '}{t("از")} {totalPages} {t("(مجموع")} {totalCount}{' '}{t("شرکت)")}</span>
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
                {editingSupplier ? t("ویرایش اطلاعات تأمین‌کننده") : t("ثبت تأمین‌کننده جدید")}
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
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("نام شرکت / تأمین‌کننده:")}</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("مثلاً: شرکت پخش لاستیک البرز")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("تلفن تماس:")}</label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="02188990011"
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("آدرس و انبار پخش:")}</label>
                <textarea
                  rows={2}
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder={t("آدرس، پلاک، شهر...")}
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
                >{t("ذخیره اطلاعات")}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
