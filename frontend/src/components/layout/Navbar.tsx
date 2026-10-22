import React, { useState, useRef, useEffect } from 'react';
import {
  LogOut,
  PlusCircle,
  ArrowRightLeft,
  User as UserIcon,
  KeyRound,
  ChevronDown,
  Menu,
  Sun,
  Moon,
  Languages,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';
import { Link } from 'react-router-dom';
import { ProfileModal } from '../auth/ProfileModal';
import { ChangePasswordModal } from '../auth/ChangePasswordModal';

interface NavbarProps {
  onToggleSidebar?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onToggleSidebar }) => {
  const { user, logout, currencyUnit, toggleCurrencyUnit } = useAuth();
  const { language, toggleLanguage, t } = useLanguage();
  const [isDropdownOpen, setIsDropdownOpen] = useState<boolean>(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState<boolean>(false);
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState<boolean>(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // تم تیره / روشن با ماندگاری در localStorage و کلاس dark روی documentElement
  const [isDark, setIsDark] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('theme');
      if (saved) return saved === 'dark';
      return document.documentElement.classList.contains('dark') ||
        window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);

  const toggleDarkMode = () => {
    setIsDark((prev) => !prev);
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const getRoleLabel = (role?: string, display?: string) => {
    if (language === 'en') {
      switch (role) {
        case 'MANAGER':
          return 'System Manager';
        case 'TECHNICIAN':
          return 'Technical Technician';
        case 'WAREHOUSE':
          return 'Warehouse Keeper';
        default:
          return role || '';
      }
    }
    if (display) return display;
    switch (role) {
      case 'MANAGER':
        return 'مدیر سیستم';
      case 'TECHNICIAN':
        return 'تکنسین فنی';
      case 'WAREHOUSE':
        return 'انباردار';
      default:
        return role || '';
    }
  };

  return (
    <header className="h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-4 sm:px-6 flex items-center justify-between z-20 shrink-0 no-print">
      {/* سمت راست در RTL / چپ در LTR: دکمه همبرگری موبایل، نام فروشگاه و وضعیت */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-2 rtl:-mr-1 ltr:-ml-1 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 md:hidden transition-colors"
          aria-label={t('openMenu', 'باز کردن منو')}
        >
          <Menu className="w-5 h-5" />
        </button>

        <h1 className="text-sm sm:text-base font-bold text-slate-800 dark:text-slate-100 truncate">
          {t('appTitle', 'سامانه فروشگاه و انبار لاستیک')}
        </h1>
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-medium">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>{t('connectedStatus', 'سامانه متصل')}</span>
        </div>
      </div>

      {/* سمت چپ در RTL / راست در LTR: اقدامات سریع، تغییر زبان، دارک‌مود، تغییر واحد پول، اطلاعات کاربر و خروج */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* دکمه سریع صدور فاکتور برای مدیر و تکنسین */}
        {(user?.role === 'MANAGER' || user?.role === 'TECHNICIAN') && (
          <Link
            to="/invoices/create"
            className="hidden lg:inline-flex items-center gap-2 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold rounded-lg shadow-sm shadow-brand-500/20 transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{t('newSaleInvoice', 'فاکتور فروش جدید')}</span>
          </Link>
        )}

        {/* دکمه تغییر زبان بین فارسی و انگلیسی (FA / EN) */}
        <button
          type="button"
          onClick={toggleLanguage}
          className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-750 transition-colors"
          title={language === 'fa' ? 'تغییر زبان به انگلیسی (Switch to English)' : 'Switch language to Persian (تغییر به فارسی)'}
          aria-label={t('langToggleAria', 'تغییر زبان بین فارسی و انگلیسی (FA / EN)')}
          data-testid="language-toggle-btn"
        >
          <Languages className="w-4 h-4 text-slate-500 dark:text-slate-400 shrink-0" />
          <span className="font-bold text-brand-600 dark:text-brand-400 tracking-wider">
            {language === 'fa' ? 'FA' : 'EN'}
          </span>
          <span className="text-[10px] text-slate-400 hidden sm:inline">
            {language === 'fa' ? 'فارسی' : 'English'}
          </span>
        </button>

        {/* دکمه تعویض دارک‌مود / لایت‌مود */}
        <button
          onClick={toggleDarkMode}
          className="flex items-center justify-center p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-750 transition-colors"
          title={isDark ? t('themeToggleDay', 'تغییر به حالت روز (روشن)') : t('themeToggleNight', 'تغییر به حالت شب (تاریک)')}
          aria-label={t('themeAria', 'تغییر تم تاریک و روشن')}
        >
          {isDark ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-slate-500" />
          )}
        </button>

        {/* سوئیچ واحد پولی بین ریال و تومان */}
        <button
          onClick={toggleCurrencyUnit}
          className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-750 transition-colors"
          title={t('currencyUnitTitle', 'تغییر واحد پولی پیش‌فرض نمایش ارقام')}
        >
          <ArrowRightLeft className="w-3.5 h-3.5 text-slate-400 hidden sm:inline" />
          <span className="hidden sm:inline">{t('currencyUnitLabel', 'واحد:')}</span>
          <span className="font-bold text-brand-600 dark:text-brand-400">
            {currencyUnit === 'toman' ? t('toman', 'تومان') : t('rial', 'ریال')}
          </span>
        </button>

        {/* منوی پروفایل کاربر */}
        {user && (
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setIsDropdownOpen((prev) => !prev)}
              className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-750 transition-colors rtl:text-right ltr:text-left"
              title={t('userSettings', 'حساب کاربری و تنظیمات')}
            >
              <div className="w-7 h-7 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center font-bold text-xs">
                {user.full_name?.charAt(0) || user.username?.charAt(0) || (language === 'en' ? 'U' : 'ک')}
              </div>
              <div className="hidden sm:block rtl:text-right ltr:text-left">
                <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 leading-tight">
                  {user.full_name || user.username}
                </p>
                <p className="text-[10px] text-brand-600 dark:text-brand-400 font-medium">
                  {getRoleLabel(user.role, user.role_display)}
                </p>
              </div>
              <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {isDropdownOpen && (
              <div className="absolute rtl:left-0 ltr:right-0 mt-2 w-56 bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 py-1.5 z-30">
                <div className="px-4 py-2 border-b border-slate-100 dark:border-slate-800">
                  <p className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">
                    {user.full_name || user.username}
                  </p>
                  <p className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
                    @{user.username}
                  </p>
                  <span className="inline-block mt-1 px-2 py-0.5 rounded-md text-[10px] font-semibold bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400">
                    {getRoleLabel(user.role, user.role_display)}
                  </span>
                </div>

                <div className="py-1">
                  <button
                    onClick={() => {
                      setIsDropdownOpen(false);
                      setIsProfileModalOpen(true);
                    }}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors rtl:text-right ltr:text-left"
                  >
                    <UserIcon className="w-4 h-4 text-slate-400" />
                    <span>{t('editProfile', 'ویرایش مشخصات فردی')}</span>
                  </button>

                  <button
                    onClick={() => {
                      setIsDropdownOpen(false);
                      setIsPasswordModalOpen(true);
                    }}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors rtl:text-right ltr:text-left"
                  >
                    <KeyRound className="w-4 h-4 text-slate-400" />
                    <span>{t('changePassword', 'تغییر کلمه عبور')}</span>
                  </button>
                </div>

                <div className="border-t border-slate-100 dark:border-slate-800 pt-1">
                  <button
                    onClick={() => {
                      setIsDropdownOpen(false);
                      logout();
                    }}
                    className="w-full flex items-center gap-2.5 px-4 py-2 text-xs font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors rtl:text-right ltr:text-left"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>{t('logoutAccount', 'خروج از حساب')}</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* دکمه خروج مستقیم */}
        <button
          onClick={logout}
          className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg text-xs font-medium text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors"
          title={t('logoutDirect', 'خروج از حساب کاربری')}
        >
          <LogOut className="w-4 h-4" />
          <span className="hidden sm:inline">{t('logoutDirect', 'خروج')}</span>
        </button>
      </div>

      {/* مدال‌های پروفایل و تغییر کلمه عبور */}
      <ProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
      />
      <ChangePasswordModal
        isOpen={isPasswordModalOpen}
        onClose={() => setIsPasswordModalOpen(false)}
      />
    </header>
  );
};
