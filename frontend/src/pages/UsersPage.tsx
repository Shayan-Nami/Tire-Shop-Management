import React, { useEffect, useState } from 'react';
import { UserPlus, Trash2, Edit2, ShieldAlert } from 'lucide-react';
import { authApi } from '../api/auth';
import { User, UserRole } from '../types';
import { useAuth } from '../context/AuthContext';
import { parseApiError } from '../utils/errorParser';

export const UsersPage: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // فرم ایجاد/ویرایش کاربر
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

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await authApi.getUsers();
      setUsers(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Mounting intentionally starts the users network load.
    void fetchUsers();
  }, []);

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

    try {
      if (editingUser) {
        await authApi.updateUser(editingUser.id, {
          username,
          full_name: fullName,
          phone_number: phone || null,
          role,
          is_active: isActive,
          ...(password ? { password } : {}),
        });
      } else {
        if (!password) {
          setErrorMessage('تعیین کلمه عبور برای کاربر جدید الزامی است.');
          setSubmitting(false);
          return;
        }
        await authApi.createUser({
          username,
          password,
          full_name: fullName,
          phone_number: phone || null,
          role,
          is_active: isActive,
        });
      }
      setShowModal(false);
      fetchUsers();
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, 'خطا در ثبت کاربر'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (u: User) => {
    if (u.id === currentUser?.id) {
      alert('امکان حذف حساب کاربری خودتان وجود ندارد.');
      return;
    }
    if (!confirm(`آیا از حذف حساب کاربری '${u.full_name || u.username}' اطمینان دارید؟`)) return;

    try {
      await authApi.deleteUser(u.id);
      fetchUsers();
    } catch (err: unknown) {
      alert(parseApiError(err, 'خطا در حذف کاربر'));
    }
  };

  return (
    <div className="space-y-6">
      {/* سربرگ */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">
            مدیریت کاربران و سطح دسترسی (RBAC)
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            تعریف پرسنل، انتصاب نقش‌های سازمانی (مدیر، حسابدار، انباردار، تکنسین)
          </p>
        </div>

        <button
          onClick={handleOpenAdd}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-600/30 transition-all active:scale-[0.98]"
        >
          <UserPlus className="w-4 h-4" />
          <span>تعریف کاربر جدید</span>
        </button>
      </div>

      {/* جدول کاربران */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-400">در حال دریافت کاربران...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-right">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">نام و نام خانوادگی</th>
                  <th className="py-3 px-4">نام کاربری</th>
                  <th className="py-3 px-4">شماره تماس</th>
                  <th className="py-3 px-4 text-center">نقش سازمانی</th>
                  <th className="py-3 px-4 text-center">وضعیت</th>
                  <th className="py-3 px-4 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-4 font-bold text-slate-900 dark:text-white">
                      {u.full_name || u.username}
                      {u.id === currentUser?.id && (
                        <span className="mr-2 text-[10px] text-brand-600 font-normal">(حساب شما)</span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-600 dark:text-slate-400">
                      {u.username}
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
                        {u.role_display || u.role}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {u.is_active ? (
                        <span className="text-emerald-600 font-semibold">فعال</span>
                      ) : (
                        <span className="text-rose-600 font-semibold">مسدود</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          onClick={() => handleOpenEdit(u)}
                          className="p-1 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        {u.id !== currentUser?.id && (
                          <button
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

      {/* مدال ایجاد/ویرایش کاربر */}
      {showModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">
                {editingUser ? 'ویرایش حساب کاربر' : 'تعریف کاربر جدید'}
              </h2>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
              {errorMessage && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 rounded-xl flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">
                  نام و نام خانوادگی:
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="مثلاً: علی صادقی"
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">نام کاربری:</label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="مثلاً: asadeghi"
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-left font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">
                  {editingUser ? 'تغییر گذرواژه (در صورت نیاز):' : 'کلمه عبور:'}
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={editingUser ? 'خالی بگذارید تا تغییر نکند' : 'حداقل ۸ کاراکتر'}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-left"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">
                  شماره موبایل:
                </label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="09121112233"
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-left font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700 dark:text-slate-300 block">
                  نقش سازمانی در سامانه:
                </label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as UserRole)}
                  className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                >
                  <option value="MANAGER">مدیر کل (MANAGER) - دسترسی کامل</option>
                  <option value="WAREHOUSE">انباردار (WAREHOUSE) - ورود کالا و انبارداری</option>
                  <option value="TECHNICIAN">تکنسین (TECHNICIAN) - صدور فاکتور فروش و خدمات</option>
                </select>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="userActive"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="rounded text-brand-600 focus:ring-brand-500"
                />
                <label htmlFor="userActive" className="text-xs text-slate-700 dark:text-slate-300">
                  حساب کاربری فعال باشد
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >
                  {submitting ? 'در حال ثبت...' : 'ذخیره کاربر'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
