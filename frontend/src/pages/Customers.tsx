import { useLanguage } from '../context/LanguageContext';
import React, { useCallback, useEffect, useState } from 'react';
import { Search, PlusCircle, Plus } from 'lucide-react';
import { crmApi } from '../api/crm';
import { Customer } from '../types';
import { IranianPlateBadge } from '../components/plates/IranianPlateBadge';
import { parseApiError } from '../utils/errorParser';

export const Customers: React.FC = () => {
  const { t, language } = useLanguage();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const [showAddCustomerModal, setShowAddCustomerModal] = useState<boolean>(false);
  const [name, setName] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [nationalCode, setNationalCode] = useState<string>('');
  const [address, setAddress] = useState<string>('');

  const [selectedCustomerForVehicle, setSelectedCustomerForVehicle] = useState<Customer | null>(null);
  const [plate, setPlate] = useState<string>('');
  const [model, setModel] = useState<string>(t("پژو ۲۰۶"));

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await crmApi.getCustomers({
        search: debouncedSearch.trim() || undefined,
        page: currentPage,
      });
      setCustomers(data.results || []);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.count || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, currentPage]);

  useEffect(() => {
    void fetchCustomers();
  }, [fetchCustomers]);

  const handleCreateCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await crmApi.createCustomer({
        full_name: name,
        phone_number: phone,
        national_code: nationalCode || undefined,
        address: address || undefined,
      });
      setShowAddCustomerModal(false);
      setName('');
      setPhone('');
      setNationalCode('');
      setAddress('');
      fetchCustomers();
    } catch (err: unknown) {
      alert(parseApiError(err, t("خطا در ثبت مشتری"), language));
    }
  };

  const handleAddVehicle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustomerForVehicle) return;
    try {
      await crmApi.createVehicle({
        customer: selectedCustomerForVehicle.customer_id,
        license_plate: plate,
        model,
      });
      setSelectedCustomerForVehicle(null);
      setPlate('');
      fetchCustomers();
    } catch (err: unknown) {
      alert(parseApiError(err, t("خطا در ثبت خودرو"), language));
    }
  };

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("مشتریان و وسایل نقلیه (CRM)")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("بانک اطلاعات مشتریان، پرونده پلاک‌های خودرویی و تاریخچه فاکتورها (مجموع:")}{totalCount}{' '}{t("پرونده)")}</p>
        </div>

        <button
          onClick={() => setShowAddCustomerModal(true)}
          className="action-primary inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
        >
          <PlusCircle className="w-4 h-4" />
          <span>{t("ثبت مشتری جدید")}</span>
        </button>
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
            placeholder={t("جستجو در نام، شماره موبایل، کد ملی یا پلاک...")}
            className="ui-field w-full pe-3 ps-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 start-3" />
        </div>
      </div>

      <div className="surface-panel overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("در حال دریافت مشتریان...")}</div>
        ) : customers.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-400">{t("مشتری با این مشخصات یافت نشد.")}</div>
        ) : (
          <div className="table-scroll overflow-x-auto">
            <table className="data-table w-full text-xs text-start">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">{t("نام مشتری")}</th>
                  <th className="py-3 px-4">{t("شماره تماس")}</th>
                  <th className="py-3 px-4">{t("کد ملی")}</th>
                  <th className="py-3 px-4">{t("وسایل نقلیه و پلاک‌ها")}</th>
                  <th className="py-3 px-4 text-center">{t("افزودن پلاک")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {customers.map((c) => (
                  <tr key={c.customer_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      <bdi dir="auto">{c.full_name}</bdi>
                      {c.address && (
                        <span className="block text-[10px] text-slate-400 font-normal">
                          {c.address}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-700 dark:text-slate-300">
                      <bdi dir="auto">{c.phone_number}</bdi>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-500">
                      {c.national_code || '-'}
                    </td>
                    <td className="py-3 px-4">
                      {c.vehicles && c.vehicles.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {c.vehicles.map((v) => (
                            <div key={v.vehicle_id} className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
                              <span className="text-[10px] text-slate-600 dark:text-slate-400 font-medium">
                                <bdi dir="auto">{v.model}</bdi>:
                              </span>
                              <IranianPlateBadge plateString={v.license_plate} size="sm" />
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span className="text-slate-400 text-[11px]">{t("بدون خودروی ثبت‌شده")}</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => setSelectedCustomerForVehicle(c)}
                        className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-brand-600 dark:text-brand-400 text-[11px] font-semibold flex items-center gap-1 mx-auto"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>{t("پلاک جدید")}</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="p-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
            <span>{t("صفحه")}{' '}{currentPage} {' '}{t("از")} {totalPages} {t("(مجموع")} {totalCount}{' '}{t("پرونده)")}</span>
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

      {showAddCustomerModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">{t("ثبت مشتری جدید")}</h2>
              <button
                type="button"
                onClick={() => setShowAddCustomerModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
               aria-label={t("بستن پنجره")}>
                ×
              </button>
            </div>

            <form onSubmit={handleCreateCustomer} className="p-6 space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("نام کامل:")}</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={t("مثلاً: علی عباسی")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("شماره موبایل:")}</label>
                <input
                  type="text"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="09141122334"
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("کد ملی (اختیاری):")}</label>
                <input
                  type="text"
                  value={nationalCode}
                  onChange={(e) => setNationalCode(e.target.value)}
                  placeholder={t("10 رقمی")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("آدرس:")}</label>
                <textarea
                  rows={2}
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder={t("آدرس محل سکونت یا محل کار...")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddCustomerModal(false)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >{t("انصراف")}</button>
                <button
                  type="submit"
                  className="action-primary px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >{t("ثبت مشتری")}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {selectedCustomerForVehicle && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">{t("افزودن پلاک برای")}{' '}{selectedCustomerForVehicle.full_name}
              </h2>
              <button
                type="button"
                onClick={() => setSelectedCustomerForVehicle(null)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
               aria-label={t("بستن پنجره")}>
                ×
              </button>
            </div>

            <form onSubmit={handleAddVehicle} className="p-6 space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("مدل خودرو:")}</label>
                <input
                  type="text"
                  required
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder={t("مثلاً: تیبا ۲، تارا، هایما...")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">{t("شماره پلاک (فرمت: 12ب345-ایران11):")}</label>
                <input
                  type="text"
                  required
                  value={plate}
                  onChange={(e) => setPlate(e.target.value)}
                  placeholder={t("12ب345-ایران11")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl font-mono text-end"
                />
                <div className="pt-2">
                  <IranianPlateBadge plateString={plate} size="sm" />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSelectedCustomerForVehicle(null)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >{t("انصراف")}</button>
                <button
                  type="submit"
                  className="action-primary px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >{t("ثبت خودرو")}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
