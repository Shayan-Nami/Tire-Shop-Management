import { useLanguage } from '../context/LanguageContext';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { UserPlus, Trash2, Edit2, ShieldAlert, Search } from 'lucide-react';
import { authApi } from '../api/auth';
import { User, UserRole } from '../types';
import { useAuth } from '../context/AuthContext';
import { parseApiError } from '../utils/errorParser';
import { Modal } from '../components/ui/Modal';
import { createRequestSequence } from '../utils/invoiceRequests';

export const UsersPage: React.FC = () => {
  const { t, language } = useLanguage();
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');

  const [showModal, setShowModal] = useState<boolean>(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [fullName, setFullName] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [role, setRole] = useState<UserRole>('TECHNICIAN');
  const [isActive, setIsActive] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const userRequests = useRef(createRequestSequence());

  useEffect(() => () => userRequests.current.invalidate(), []);

  useEffect(() => {
    if (search === debouncedSearch) return;
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search, debouncedSearch]);

  const fetchUsers = useCallback(async () => {
    const request = userRequests.current.begin();
    setLoading(true);
    setLoadError(null);
    try {
      const data = await authApi.getUsers();
      if (!userRequests.current.isCurrent(request)) return;
      setUsers(data);
    } catch (e) {
      if (!userRequests.current.isCurrent(request)) return;
      setLoadError(parseApiError(e, t("دریافت اطلاعات ناموفق بود. اتصال را بررسی کنید و دوباره تلاش کنید."), language));
    } finally {
      if (userRequests.current.isCurrent(request)) {
        setLoading(false);
      }
    }
  }, [language, t]);

  useEffect(() => {
    void fetchUsers();
  }, [fetchUsers]);

  const getRoleLabel = useCallback((userRole: UserRole, roleDisplay?: string) => {
    switch (userRole) {
      case 'MANAGER':
        return t("مدیر سیستم");
      case 'WAREHOUSE':
        return t("انباردار");
      case 'TECHNICIAN':
        return t("تکنسین فنی");
      default:
        return roleDisplay || userRole;
    }
  }, [t]);

  const filteredUsers = useMemo(() => {
    const term = debouncedSearch.trim().toLowerCase();
    if (!term) return users;
    return users.filter((u) => {
      const roleLabel = getRoleLabel(u.role, u.role_display).toLowerCase();
      return (
        u.username.toLowerCase().includes(term) ||
        (u.full_name || '').toLowerCase().includes(term) ||
        (u.phone_number || '').toLowerCase().includes(term) ||
        u.role.toLowerCase().includes(term) ||
        roleLabel.includes(term)
      );
    });
  }, [users, debouncedSearch, getRoleLabel]);

  const isEditingSelf = Boolean(editingUser && currentUser && editingUser.id === currentUser.id);

  const handleOpenAdd = () => {
    setEditingUser(null);
    setUsername('');
    setPassword('');
    setFullName('');
    setPhone('');
    setRole('TECHNICIAN');
    setIsActive(true);
    setErrorMessage(null);
    setShowModal(true);
  };

  const handleOpenEdit = (u: User) => {
    setEditingUser(u);
    setUsername(u.username);
    setPassword('');
    setFullName(u.full_name);
    setPhone(u.phone_number || '');
    setRole(u.role);
    setIsActive(u.is_active ?? true);
    setErrorMessage(null);
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);

    const effectiveRole = isEditingSelf && editingUser ? editingUser.role : role;
    const effectiveIsActive = isEditingSelf && editingUser ? (editingUser.is_active ?? true) : isActive;

    try {
      if (editingUser) {
        await authApi.updateUser(editingUser.id, {
          username,
          full_name: fullName,
          phone_number: phone || null,
          role: effectiveRole,
          is_active: effectiveIsActive,
          ...(password ? { password } : {}),
        });
      } else {
        if (!password) {
          setErrorMessage(t("تعیین کلمه عبور برای کاربر جدید الزامی است."));
          setSubmitting(false);
          return;
        }
        await authApi.createUser({
          username,
          password,
          full_name: fullName,
          phone_number: phone || null,
          role: effectiveRole,
          is_active: effectiveIsActive,
        });
      }
      setShowModal(false);
      void fetchUsers();
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, t("خطا در ثبت کاربر"), language));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (u: User) => {
    if (u.id === currentUser?.id) {
      alert(t("امکان حذف حساب کاربری خودتان وجود ندارد."));
      return;
    }
    if (!confirm(t("آیا از حذف حساب کاربری '{0}' اطمینان دارید؟", undefined, { 0: u.full_name || u.username }))) return;

    try {
      await authApi.deleteUser(u.id);
      void fetchUsers();
    } catch (err: unknown) {
      alert(parseApiError(err, t("خطا در حذف کاربر"), language));
    }
  };

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("مدیریت کاربران و سطح دسترسی (RBAC)")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("تعریف پرسنل، انتصاب نقش‌های سازمانی (مدیر، انباردار، تکنسین)")}</p>
        </div>

        <button
          type="button"
          onClick={handleOpenAdd}
          className="action-primary inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
        >
          <UserPlus className="w-4 h-4" />
          <span>{t("تعریف کاربر جدید")}</span>
        </button>
      </div>

      <div className="filter-bar">
        <div className="relative w-full md:w-80">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label={t("جستجو در نام، نام کاربری یا شماره موبایل...")}
            placeholder={t("جستجو در نام، نام کاربری یا شماره موبایل...")}
            className="ui-field w-full pe-3 ps-9 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none"
          />
          <Search className="w-4 h-4 text-slate-400 absolute top-2.5 start-3" />
        </div>
      </div>

      {loadError ? (
        <div className="surface-panel p-5 space-y-3" role="alert">
          <p className="text-xs text-rose-600 dark:text-rose-400">{loadError}</p>
          <button type="button" className="action-secondary" onClick={() => void fetchUsers()}>{t("تلاش دوباره")}</button>
        </div>
      ) : (
        <div className="surface-panel overflow-hidden">
          {loading ? (
            <div className="py-16 text-center text-xs text-slate-500 dark:text-slate-400">{t("در حال دریافت کاربران...")}</div>
          ) : filteredUsers.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-500 dark:text-slate-400">{t("کاربری با این مشخصات یافت نشد.")}</div>
          ) : (
            <div className="table-scroll overflow-x-auto">
              <table className="data-table w-full text-xs text-start">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-3 px-4">{t("نام و نام خانوادگی")}</th>
                    <th className="py-3 px-4">{t("نام کاربری")}</th>
                    <th className="py-3 px-4">{t("شماره تماس")}</th>
                    <th className="py-3 px-4 text-center">{t("نقش سازمانی")}</th>
                    <th className="py-3 px-4 text-center">{t("وضعیت")}</th>
                    <th className="py-3 px-4 text-center">{t("عملیات")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {filteredUsers.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                        {u.full_name || u.username}
                        {u.id === currentUser?.id && (
                          <span className="ms-2 text-[10px] text-brand-600 font-normal">{t("(حساب شما)")}</span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-400">
                        <bdi dir="auto">{u.username}</bdi>
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-500">
                        {u.phone_number || '-'}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                            u.role === 'MANAGER'
                              ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                              : u.role === 'WAREHOUSE'
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              : 'bg-purple-500/10 text-purple-600 dark:text-purple-400'
                          }`}
                        >
                          {getRoleLabel(u.role, u.role_display)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        {u.is_active ? (
                          <span className="text-emerald-600 font-semibold">{t("فعال")}</span>
                        ) : (
                          <span className="text-rose-600 font-semibold">{t("مسدود")}</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <div className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            aria-label={t("ویرایش کاربر")}
                            title={t("ویرایش کاربر")}
                            onClick={() => handleOpenEdit(u)}
                            className="p-1 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          {u.id !== currentUser?.id && (
                            <button
                              type="button"
                              aria-label={t("حذف کاربر")}
                              title={t("حذف کاربر")}
                              onClick={() => handleDelete(u)}
                              className="p-1 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {showModal && (
        <Modal
          onClose={() => setShowModal(false)}
          label={editingUser ? t("ویرایش حساب کاربر") : t("تعریف کاربر جدید")}
          busy={submitting}
        >
          <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
                {editingUser ? t("ویرایش حساب کاربر") : t("تعریف کاربر جدید")}
              </h2>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="p-1 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 rounded-lg"
                aria-label={t("بستن پنجره")}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
              {errorMessage && (
                <div role="alert" className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="user-full-name" className="font-bold text-slate-700 dark:text-slate-300 block">{t("نام و نام خانوادگی:")}</label>
                <input
                  id="user-full-name"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder={t("مثلاً: علی صادقی")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="user-username" className="font-bold text-slate-700 dark:text-slate-300 block">{t("نام کاربری:")}</label>
                <input
                  id="user-username"
                  type="text"
                  required
                  dir="ltr"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={t("مثلاً: asadeghi")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-start font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="user-password" className="font-bold text-slate-700 dark:text-slate-300 block">
                  {editingUser ? t("تغییر گذرواژه (در صورت نیاز):") : t("کلمه عبور:")}
                </label>
                <input
                  id="user-password"
                  type="password"
                  dir="ltr"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={editingUser ? t("خالی بگذارید تا تغییر نکند") : t("حداقل ۸ کاراکتر")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-start"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="user-phone" className="font-bold text-slate-700 dark:text-slate-300 block">{t("شماره موبایل:")}</label>
                <input
                  id="user-phone"
                  type="text"
                  dir="ltr"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="09121112233"
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-start font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="user-role" className="font-bold text-slate-700 dark:text-slate-300 block">{t("نقش سازمانی در سامانه:")}</label>
                <select
                  id="user-role"
                  value={role}
                  disabled={isEditingSelf}
                  onChange={(e) => setRole(e.target.value as UserRole)}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <option value="MANAGER">{t("مدیر کل (MANAGER) - دسترسی کامل")}</option>
                  <option value="WAREHOUSE">{t("انباردار (WAREHOUSE) - ورود کالا و انبارداری")}</option>
                  <option value="TECHNICIAN">{t("تکنسین (TECHNICIAN) - صدور فاکتور فروش و خدمات")}</option>
                </select>
              </div>

              <div className="space-y-1.5 pt-2">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="userActive"
                    checked={isActive}
                    disabled={isEditingSelf}
                    onChange={(e) => setIsActive(e.target.checked)}
                    className="rounded text-brand-600 focus:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed"
                  />
                  <label htmlFor="userActive" className="text-xs text-slate-700 dark:text-slate-300">{t("حساب کاربری فعال باشد")}</label>
                </div>
                {isEditingSelf && (
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    {t("برای جلوگیری از قفل شدن دسترسی، امکان تغییر نقش یا غیرفعال‌سازی حساب خودتان وجود ندارد.")}
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >{t("انصراف")}</button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="action-primary px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >
                  {submitting ? t("در حال ثبت...") : t("ذخیره کاربر")}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}
    </div>
  );
};
