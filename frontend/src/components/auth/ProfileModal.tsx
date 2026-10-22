import React, { useState, useEffect } from 'react';
import { X, User, Phone, Shield, Save, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { authApi } from '../../api/auth';
import { parseApiError } from '../../utils/errorParser';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({ isOpen, onClose }) => {
  const { user, updateUser } = useAuth();
  const [fullName, setFullName] = useState<string>('');
  const [phoneNumber, setPhoneNumber] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user && isOpen) {
      // oxlint-disable-next-line react/set-state-in-effect -- Reopening resets the editable snapshot; preserve the existing modal lifecycle.
      setFullName(user.full_name || '');
      setPhoneNumber(user.phone_number || '');
      setErrorMessage(null);
      setSuccessMessage(null);
    }
  }, [user, isOpen]);

  if (!isOpen || !user) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const updated = await authApi.updateProfile({
        full_name: fullName.trim() || undefined,
        phone_number: phoneNumber.trim() || null,
      });
      updateUser(updated);
      setSuccessMessage('اطلاعات کاربری با موفقیت به‌روزرسانی شد.');
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, 'خطا در به‌روزرسانی مشخصات کاربری'));
    } finally {
      setSubmitting(false);
    }
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'MANAGER':
        return 'مدیر سیستم';
      case 'TECHNICIAN':
        return 'تکنسین فنی';
      case 'WAREHOUSE':
        return 'انباردار';
      default:
        return user.role_display || role;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
        {/* هدر مدال */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center">
              <User className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                ویرایش مشخصات فردی
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                مشاهده و ویرایش اطلاعات حساب کاربری
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* فرم */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMessage && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-400 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400 text-xs">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* نام کاربری و نقش (غیرقابل ویرایش) */}
          <div className="grid grid-cols-2 gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 text-xs">
            <div>
              <span className="text-slate-400 block mb-0.5">نام کاربری</span>
              <span className="font-semibold text-slate-700 dark:text-slate-300 font-mono">
                {user.username}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">نقش کاربری</span>
              <span className="inline-flex items-center gap-1 font-semibold text-brand-600 dark:text-brand-400">
                <Shield className="w-3.5 h-3.5" />
                {getRoleBadge(user.role)}
              </span>
            </div>
          </div>

          {/* فیلد نام و نام خانوادگی */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              نام و نام خانوادگی
            </label>
            <div className="relative">
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="مثال: علی محمدی"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none transition-all"
              />
            </div>
          </div>

          {/* فیلد شماره تماس */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              شماره همراه
            </label>
            <div className="relative">
              <input
                type="tel"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="09123456789"
                dir="ltr"
                className="w-full px-3.5 py-2.5 pr-9 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none transition-all font-mono text-right"
              />
              <Phone className="w-4 h-4 text-slate-400 absolute right-3 top-3 pointer-events-none" />
            </div>
            <p className="mt-1 text-[11px] text-slate-400">
              فرمت استاندارد: ۱۱ رقم با پیش‌شماره ۰۹
            </p>
          </div>

          {/* دکمه‌های اقدام */}
          <div className="pt-2 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors"
            >
              انصراف
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-1.5 px-5 py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-sm shadow-brand-500/20 transition-colors"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>در حال ذخیره...</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>ذخیره تغییرات</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
