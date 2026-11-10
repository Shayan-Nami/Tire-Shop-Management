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
    const handleEscape = (event: KeyboardEvent) => {
      if (isDropdownOpen && event.key === 'Escape') {
        setIsDropdownOpen(false);
        dropdownRef.current?.querySelector('button')?.focus();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isDropdownOpen]);

  const getRoleLabel = (role?: string, display?: string) => {
    if (language === 'en') {
      switch (role) {
        case 'MANAGER':
          return 'System Manager';
        case 'TECHNICIAN':
          return 'Technician';
        case 'WAREHOUSE':
          return 'Warehouse staff';
        default:
          return role || '';
      }
    }
    if (display) return display;
    switch (role) {
      case 'MANAGER':
        return t("مدیر سیستم");
      case 'TECHNICIAN':
        return t("تکنسین فنی");
      case 'WAREHOUSE':
        return t("انباردار");
      default:
        return role || '';
    }
  };

  return (
    <header className="app-navbar border-b border-slate-200 dark:border-slate-700 flex items-center justify-between z-20 shrink-0 no-print">
      <div className="navbar-identity flex items-center gap-2">
        <button
          onClick={onToggleSidebar}
          className="toolbar-button md:hidden"
          aria-label={t('openMenu', 'باز کردن منو')}
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="min-w-0">
          <p className="font-bold text-slate-900 dark:text-slate-100 text-sm truncate">
            <span className="hidden xl:inline">{t('appTitle', 'سامانه فروشگاه و انبار لاستیک')}</span>
            <span className="xl:hidden">{t('appName', 'تایر منیجر')}</span>
          </p>
          <p className="navbar-subtitle">{language === 'fa' ? t("فروش، خدمات و موجودی؛ یک فضای کاری") : 'Sales, services and inventory in one workspace'}</p>
        </div>
      </div>

      <div className="navbar-tools flex items-center">
        {(user?.role === 'MANAGER' || user?.role === 'TECHNICIAN') && (
          <Link
            to="/invoices/create"
            className="action-primary hidden 2xl:inline-flex"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{t('newSaleInvoice', 'فاکتور فروش جدید')}</span>
          </Link>
        )}

        <button
          type="button"
          onClick={toggleLanguage}
          className="toolbar-button"
          title={language === 'fa' ? t("تغییر زبان به انگلیسی (Switch to English)") : t("Switch language to Persian (تغییر به فارسی)")}
          aria-label={t('langToggleAria', 'تغییر زبان بین فارسی و انگلیسی (FA / EN)')}
          data-testid="language-toggle-btn"
        >
          <Languages className="w-4 h-4 shrink-0 hidden sm:block" aria-hidden="true" />
          <span className="font-bold text-brand-600 dark:text-brand-400 tracking-wider">
            {language === 'fa' ? 'FA' : 'EN'}
          </span>
        </button>

        <button
          onClick={toggleDarkMode}
          className="toolbar-button"
          aria-pressed={isDark}
          title={isDark ? t('themeToggleDay', 'تغییر به حالت روز (روشن)') : t('themeToggleNight', 'تغییر به حالت شب (تاریک)')}
          aria-label={t('themeAria', 'تغییر تم تاریک و روشن')}
        >
          {isDark ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-slate-500" />
          )}
        </button>

        <button
          onClick={toggleCurrencyUnit}
          className="toolbar-button"
          title={t('currencyUnitTitle', 'تغییر واحد پولی پیش‌فرض نمایش ارقام')}
        >
          <ArrowRightLeft className="w-3.5 h-3.5 text-slate-400 hidden sm:inline" />
          <span className="font-bold text-brand-600 dark:text-brand-400">
            {currencyUnit === 'toman' ? t('toman', 'تومان') : t('rial', 'ریال')}
          </span>
        </button>

        {user && (
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setIsDropdownOpen((prev) => !prev)}
              className="toolbar-button"
              aria-expanded={isDropdownOpen}
              aria-controls="account-menu"
              title={t('userSettings', 'حساب کاربری و تنظیمات')}
            >
              <div className="w-7 h-7 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center font-bold text-xs">
                {user.full_name?.charAt(0) || user.username?.charAt(0) || (language === 'en' ? 'U' : t("ک"))}
              </div>
              <div className="hidden xl:block rtl:text-right ltr:text-left max-w-32">
                <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 leading-tight">
                  {user.full_name || user.username}
                </p>
                <p className="text-[10px] text-brand-600 dark:text-brand-400 font-medium">
                  {getRoleLabel(user.role, user.role_display)}
                </p>
              </div>
              <ChevronDown className={`hidden sm:block w-3.5 h-3.5 transition-transform duration-150 ${isDropdownOpen ? 'rotate-180' : ''}`} />
            </button>

            {isDropdownOpen && (
              <div id="account-menu" className="profile-menu absolute rtl:left-0 ltr:right-0 mt-2 w-64 shadow-xl border py-1.5 z-30">
                <div className="px-4 py-2 border-b border-slate-100 dark:border-slate-800">
                  <p className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">
                    {user.full_name || user.username}
                  </p>
                  <p className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
                    @<bdi dir="auto">{user.username}</bdi>
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

      </div>

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
