import { useLanguage } from '../context/LanguageContext';
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, User, ArrowLeft, ShieldAlert, CircleDot, FileText, Package, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { parseApiError } from '../utils/errorParser';

export const Login: React.FC = () => {
  const { t, language, toggleLanguage } = useLanguage();
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [rememberMe, setRememberMe] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const { login, isAuthenticated, isLoading, user } = useAuth();
  const navigate = useNavigate();
  const reason = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('reason') : null;

  useEffect(() => {
    if (isLoading === false && isAuthenticated && user) {
      navigate('/', { replace: true });
    }
  }, [isLoading, isAuthenticated, user, navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;

    setLoading(true);
    setError(null);
    try {
      await login(username, password, rememberMe);
      navigate('/');
    } catch (err: unknown) {
      setError(
        parseApiError(err, t("نام کاربری یا کلمه عبور وارد شده نادرست است."), language)
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <button type="button" onClick={toggleLanguage} className="toolbar-button login-language-toggle" aria-label={t('langToggleAria')}>
        {language === 'en' ? 'فارسی' : 'English'}
      </button>
      <section className="login-brand">
        <div className="flex items-center gap-3"><div className="brand-mark"><CircleDot size={24} /></div><div><strong className="text-xl">{t("تایر منیجر")}</strong><p className="!mt-0 !text-xs">{t("سامانه فروشگاه و خدمات لاستیک")}</p></div></div>
        <div className="login-intro">
          <h2>{t("همهٔ کارهای فروشگاه، در یک نگاه.")}</h2>
          <p>{t("از صدور فاکتور تا پیگیری موجودی و تسویه؛ فضای کاری روزانهٔ فروشگاه شما.")}</p>
          <div className="login-document">
            <div><span>{t("فروش و خدمات")}</span><FileText size={20} /></div>
            <div><span>{t("موجودی و گردش انبار")}</span><Package size={20} /></div>
            <div><span>{t("مشتریان و اسناد مالی")}</span><Users size={20} /></div>
          </div>
        </div>
        <span className="login-footer text-xs text-slate-300">{t("مدیریت یکپارچهٔ فروشگاه لاستیک")}</span>
      </section>
      <main className="login-form-area">
        <div className="login-form-card space-y-7">
          <div><h1>{t("ورود به فضای کاری")}</h1><p className="text-sm text-slate-500 dark:text-slate-300 mt-2">{t("برای شروع، اطلاعات حساب خود را وارد کنید.")}</p></div>
          {reason === 'password-changed' && <p role="status" className="p-3 rounded-lg bg-emerald-50 text-emerald-800 text-sm">{t("کلمه عبور با موفقیت تغییر یافت و نشست شما پایان یافت. لطفاً با کلمه عبور جدید دوباره وارد شوید.")}</p>}
          {reason === 'idle-timeout' && <p role="status" className="p-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200 text-sm">{t("نشست شما به دلیل عدم فعالیت پایان یافت. لطفاً دوباره وارد شوید.")}</p>}
          {reason === 'session-expired' && <p role="status" className="p-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200 text-sm">{t("اعتبار نشست شما به پایان رسیده است. لطفاً دوباره وارد شوید.")}</p>}
          {error && <div role="alert" id="login-error" className="p-3 rounded-lg bg-rose-50 text-rose-800 text-sm flex gap-2"><ShieldAlert className="shrink-0 w-5 h-5" /><span>{error}</span></div>}
          <form onSubmit={handleLogin} className="space-y-5" aria-busy={loading}>
            <div><label htmlFor="login-username">{t("نام کاربری")}</label><div className="relative"><input id="login-username" autoComplete="username" type="text" value={username} onChange={(e) => setUsername(e.target.value)} required placeholder={t("نام کاربری خود را وارد کنید")} className="ui-field border" /><User className="field-icon w-4 h-4" /></div></div>
            <div><label htmlFor="login-password">{t("کلمه عبور")}</label><div className="relative"><input id="login-password" autoComplete="current-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder={t("کلمه عبور خود را وارد کنید")} className="ui-field border" /><KeyRound className="field-icon w-4 h-4" /></div></div>
            <div className="flex items-center gap-2.5">
              <input
                id="login-remember-me"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 dark:border-slate-600 accent-[#d18b23] cursor-pointer shrink-0"
              />
              <label
                htmlFor="login-remember-me"
                className="!mb-0 !font-normal text-xs text-slate-600 dark:text-slate-300 cursor-pointer select-none leading-6"
              >
                {t("مرا به خاطر بسپار (حفظ نشست پس از بستن مرورگر)")}
              </label>
            </div>
            <button type="submit" disabled={loading} className="action-primary w-full !min-h-12"><span>{loading ? t("در حال ورود...") : t("ورود به سامانه")}</span><ArrowLeft className="w-4 h-4 ltr:rotate-180" /></button>
          </form>
          <p className="text-xs text-slate-500 dark:text-slate-300 leading-7">{t("برای دسترسی به سامانه، از حسابی که مدیر فروشگاه در اختیارتان قرار داده استفاده کنید.")}</p>
        </div>
      </main>
    </div>
  );
};
