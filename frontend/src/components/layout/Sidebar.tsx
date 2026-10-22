import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ShoppingCart,
  FilePlus,
  Package,
  Layers,
  History,
  Coins,
  Users,
  Wrench,
  Truck,
  BarChart3,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';
import { UserRole } from '../../types';

interface NavItem {
  name: string;
  path: string;
  icon: React.ElementType;
  roles?: UserRole[];
}

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen = false, onClose }) => {
  const { user } = useAuth();
  const { language, t } = useLanguage();

  const navItems: NavItem[] = [
    {
      name: t('navDashboard', 'میز کار و داشبورد'),
      path: '/dashboard',
      icon: LayoutDashboard,
      roles: ['MANAGER'],
    },
    {
      name: t('navCreateInvoice', 'صدور فاکتور فروش (صندوق)'),
      path: '/invoices/create',
      icon: FilePlus,
      roles: ['MANAGER', 'TECHNICIAN'],
    },
    {
      name: t('navSalesInvoices', 'فاکتورهای فروش'),
      path: '/invoices/sales',
      icon: ShoppingCart,
      roles: ['MANAGER', 'WAREHOUSE', 'TECHNICIAN'],
    },
    {
      name: t('navTiresCatalog', 'کاتالوگ و موجودی تایرها'),
      path: '/catalog/tires',
      icon: Package,
      roles: ['MANAGER', 'WAREHOUSE', 'TECHNICIAN'],
    },
    {
      name: t('navPurchaseInvoices', 'فاکتورهای خرید (ورود به انبار)'),
      path: '/invoices/purchases',
      icon: Layers,
      roles: ['MANAGER', 'WAREHOUSE'],
    },
    {
      name: t('navStockMovements', 'دفتر گردش انبار (حسابرسی)'),
      path: '/catalog/movements',
      icon: History,
      roles: ['MANAGER', 'WAREHOUSE'],
    },
    {
      name: t('navTreasury', 'خزانه‌داری و اسناد مالی'),
      path: '/treasury',
      icon: Coins,
      roles: ['MANAGER'],
    },
    {
      name: t('navCustomers', 'مشتریان و وسایل نقلیه'),
      path: '/customers',
      icon: Users,
      roles: ['MANAGER', 'WAREHOUSE', 'TECHNICIAN'],
    },
    {
      name: t('navServices', 'تعرفه خدمات کارگاه'),
      path: '/services',
      icon: Wrench,
      roles: ['MANAGER', 'TECHNICIAN'],
    },
    {
      name: t('navSuppliers', 'تأمین‌کنندگان لاستیک'),
      path: '/suppliers',
      icon: Truck,
      roles: ['MANAGER', 'WAREHOUSE'],
    },
    {
      name: t('navReports', 'گزارش‌های تحلیلی و سودآوری'),
      path: '/reports',
      icon: BarChart3,
      roles: ['MANAGER'],
    },
    {
      name: t('navUsers', 'مدیریت کاربران و نقش‌ها'),
      path: '/users',
      icon: ShieldCheck,
      roles: ['MANAGER'],
    },
  ];

  const filteredNavItems = navItems.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

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
    <>
      {/* بک‌دراپ تاریک روی موبایل */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-30 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* پنل کشویی سایدبار (ثابت در دسکتاپ و آف‌کانواس در موبایل) */}
      <aside
        className={`fixed inset-y-0 rtl:right-0 ltr:left-0 z-40 w-64 bg-slate-900 rtl:border-l ltr:border-r border-slate-800 flex flex-col shrink-0 select-none text-slate-300 transition-transform duration-300 ease-in-out md:static md:translate-x-0 ${
          isOpen ? 'translate-x-0' : 'rtl:translate-x-full ltr:-translate-x-full'
        }`}
      >
        {/* لوگو و نام سامانه */}
        <div className="h-16 flex items-center justify-between px-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-rose-500 flex items-center justify-center shadow-lg shadow-brand-500/20 text-white font-black text-xl">
              🛞
            </div>
            <div className="flex flex-col">
              <span className="font-extrabold text-white text-base leading-tight">
                {t('appName', 'تایر منیجر')}
              </span>
              <span className="text-[11px] text-slate-400 font-medium">
                {t('appSubtitle', 'سامانه هوشمند فروشگاه و خدمات')}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white md:hidden"
            aria-label={t('closeMenu', 'بستن منو')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* لیست آیتم‌های ناوبری */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">
            {t('operationalMenu', 'منوی عملیاتی')}
          </div>
          {filteredNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-brand-600 text-white shadow-md shadow-brand-600/30 font-semibold'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{item.name}</span>
              </NavLink>
            );
          })}
        </div>

        {/* وضعیت کاربر جاری در انتهای سایدبار */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/40">
          <div className="flex items-center gap-3 p-2 rounded-xl bg-slate-800/40 border border-slate-800">
            <div className="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center font-bold text-brand-400 text-sm">
              {user?.full_name?.charAt(0) || user?.username?.charAt(0) || (language === 'en' ? 'U' : 'ک')}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-200 truncate">{user?.full_name || user?.username}</p>
              <span className="inline-block px-1.5 py-0.5 text-[10px] rounded bg-brand-500/10 text-brand-400 font-medium">
                {getRoleLabel(user?.role, user?.role_display)}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
