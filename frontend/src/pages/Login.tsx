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
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const { login, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const passwordChanged = new URLSearchParams(window.location.search).get('reason') === 'password-changed';

  useEffect(() => {
    if (isAuthenticated && user) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, user, navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;

    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      navigate('/');
    } catch (err: any) {
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
          {passwordChanged && <p role="status" className="p-3 rounded-lg bg-emerald-50 text-emerald-800">{t("کلمه عبور با موفقیت تغییر یافت و نشست شما پایان یافت. لطفاً با کلمه عبور جدید دوباره وارد شوید.")}</p>}
          {error && <div role="alert" id="login-error" className="p-3 rounded-lg bg-rose-50 text-rose-800 text-sm flex gap-2"><ShieldAlert className="shrink-0 w-5 h-5" /><span>{error}</span></div>}
          <form onSubmit={handleLogin} className="space-y-5" aria-busy={loading}>
            <div><label htmlFor="login-username">{t("نام کاربری")}</label><div className="relative"><input id="login-username" autoComplete="username" type="text" value={username} onChange={(e) => setUsername(e.target.value)} required placeholder={t("نام کاربری خود را وارد کنید")} className="ui-field border" /><User className="field-icon w-4 h-4" /></div></div>
            <div><label htmlFor="login-password">{t("کلمه عبور")}</label><div className="relative"><input id="login-password" autoComplete="current-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder={t("کلمه عبور خود را وارد کنید")} className="ui-field border" /><KeyRound className="field-icon w-4 h-4" /></div></div>
            <button type="submit" disabled={loading} className="action-primary w-full !min-h-12"><span>{loading ? t("در حال ورود...") : t("ورود به سامانه")}</span><ArrowLeft className="w-4 h-4" /></button>
          </form>
          <p className="text-xs text-slate-500 dark:text-slate-300 leading-7">{t("برای دسترسی به سامانه، از حسابی که مدیر فروشگاه در اختیارتان قرار داده استفاده کنید.")}</p>
        </div>
      </main>
    </div>
  );
};
