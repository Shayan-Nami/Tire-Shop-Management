import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, User, ArrowLeft, ShieldAlert } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { parseApiError } from '../utils/errorParser';

export const Login: React.FC = () => {
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
        parseApiError(err, 'نام کاربری یا کلمه عبور وارد شده نادرست است.')
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden font-sans selection:bg-brand-600 selection:text-white">
      {/* هاله‌های نوری پس‌زمینه */}
      <div className="absolute top-1/4 -right-20 w-96 h-96 bg-brand-600/15 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-1/4 -left-20 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none"></div>

      {/* پوسته دولایه خارجی (Double-Bezel Shell) */}
      <div className="w-full max-w-md p-2 rounded-[2rem] bg-slate-900/60 border border-slate-800/80 shadow-2xl backdrop-blur-xl relative z-10">
        <div className="p-6 sm:p-8 rounded-[calc(2rem-0.5rem)] bg-slate-900 border border-slate-800/50 space-y-6">
          {/* لوگو و سربرگ فرم */}
          <div className="text-center space-y-2">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-brand-600 to-rose-500 shadow-xl shadow-brand-600/30 text-3xl mb-2">
              🛞
            </div>
            <h1 className="text-2xl font-black text-white tracking-tight">
              سامانه جامع فروشگاه لاستیک
            </h1>
            <p className="text-xs text-slate-400">
              ورود امن به پنل مدیریت، صندوق فروش و انبارداری
            </p>
          </div>

          {passwordChanged && (
            <p role="status" className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs">
              کلمه عبور با موفقیت تغییر یافت و نشست شما پایان یافت. لطفاً با کلمه عبور جدید دوباره وارد شوید.
            </p>
          )}

          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* فرم لاگین */}
          <form onSubmit={handleLogin} className="space-y-4 text-xs">
            <div className="space-y-1.5">
              <label className="font-semibold text-slate-300 block">نام کاربری:</label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="نام کاربری شما..."
                  required
                  className="w-full px-4 py-3 pr-10 bg-slate-800/60 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none transition-all"
                />
                <User className="w-4 h-4 text-slate-400 absolute top-3.5 right-3.5" />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="font-semibold text-slate-300 block">کلمه عبور:</label>
              <div className="relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="گذرواژه..."
                  required
                  className="w-full px-4 py-3 pr-10 bg-slate-800/60 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none transition-all"
                />
                <KeyRound className="w-4 h-4 text-slate-400 absolute top-3.5 right-3.5" />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 px-4 bg-gradient-to-r from-brand-600 to-rose-600 hover:from-brand-500 hover:to-rose-500 text-white font-bold rounded-xl shadow-lg shadow-brand-600/30 flex items-center justify-center gap-2 text-sm transition-all duration-200 active:scale-[0.98] disabled:opacity-50"
            >
              <span>{loading ? 'در حال ورود...' : 'ورود به سامانه'}</span>
              <ArrowLeft className="w-4 h-4" />
            </button>
          </form>


        </div>
      </div>
    </div>
  );
};
