import { useLanguage } from '../../context/LanguageContext';
import React, { useState, useEffect } from 'react';
import { X, KeyRound, Lock, AlertCircle, Save, Loader2 } from 'lucide-react';
import { authApi } from '../../api/auth';
import { parseApiError } from '../../utils/errorParser';
import { useAuth } from '../../context/AuthContext';

interface ChangePasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ChangePasswordModal: React.FC<ChangePasswordModalProps> = ({ isOpen, onClose }) => {
  const { t, language } = useLanguage();
  const { endLocalSession } = useAuth();
  const [oldPassword, setOldPassword] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);


  useEffect(() => {
    if (isOpen) {
      // oxlint-disable-next-line react/set-state-in-effect -- Reopening must clear password fields; preserve the existing modal lifecycle.
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setErrorMessage(null);

    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);


    if (!oldPassword) {
      setErrorMessage(t("لطفاً کلمه عبور فعلی را وارد نمایید."));
      return;
    }

    if (!newPassword) {
      setErrorMessage(t("لطفاً کلمه عبور جدید را وارد نمایید."));
      return;
    }

    if (newPassword.length < 8) {
      setErrorMessage(t("کلمه عبور جدید باید حداقل ۸ کاراکتر باشد."));
      return;
    }

    if (newPassword === oldPassword) {
      setErrorMessage(t("کلمه عبور جدید نمی‌تواند مشابه کلمه عبور فعلی باشد."));
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMessage(t("تکرار کلمه عبور با کلمه عبور جدید مطابقت ندارد."));
      return;
    }

    setSubmitting(true);
    try {
      await authApi.changePassword({
        old_password: oldPassword,
        new_password: newPassword,
      });
      // Password changes revoke the current tokens; do not call logout or refresh.
      endLocalSession('password-changed');
    } catch (err: unknown) {
      setErrorMessage(parseApiError(err, t("خطا در تغییر کلمه عبور"), language));
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 flex items-center justify-center p-4">
      <div className="relative w-full max-w-md bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
        {/* هدر مدال */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
              <KeyRound className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">{t("تغییر کلمه عبور")}</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">{t("امنیت حساب کاربری خود را به‌روزرسانی کنید")}</p>
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
            <div role="alert" className="flex items-center gap-2 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-400 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}


          {/* کلمه عبور فعلی */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">{t("کلمه عبور فعلی")}</label>
            <div className="relative">
              <input
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                placeholder="••••••••"
                dir="ltr"
                className="ui-field w-full px-3.5 py-2.5 ps-9 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none transition-all"
              />
              <Lock className="w-4 h-4 text-slate-400 absolute start-3 top-3 pointer-events-none" />
            </div>
          </div>

          {/* کلمه عبور جدید */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">{t("کلمه عبور جدید")}</label>
            <div className="relative">
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••"
                dir="ltr"
                className="ui-field w-full px-3.5 py-2.5 ps-9 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none transition-all"
              />
              <KeyRound className="w-4 h-4 text-slate-400 absolute start-3 top-3 pointer-events-none" />
            </div>
            <p className="mt-1 text-[11px] text-slate-400">{t("حداقل ۸ کاراکتر شامل حروف و اعداد")}</p>
          </div>

          {/* تکرار کلمه عبور جدید */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">{t("تکرار کلمه عبور جدید")}</label>
            <div className="relative">
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                dir="ltr"
                className="ui-field w-full px-3.5 py-2.5 ps-9 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none transition-all"
              />
              <Lock className="w-4 h-4 text-slate-400 absolute start-3 top-3 pointer-events-none" />
            </div>
          </div>

          {/* دکمه‌های اقدام */}
          <div className="pt-2 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors"
            >{t("انصراف")}</button>
            <button
              type="submit"
              disabled={submitting}
              className="action-primary inline-flex items-center gap-1.5 px-5 py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-sm shadow-brand-500/20 transition-colors"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{t("در حال ذخیره...")}</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>{t("تغییر کلمه عبور")}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
