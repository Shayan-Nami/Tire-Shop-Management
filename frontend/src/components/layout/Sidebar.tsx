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
  CircleDot,
  ChevronLeft,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';
import { UserRole } from '../../types';
import { Modal } from '../ui/Modal';

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

  const groups = [
    { name: language === 'fa' ? t("نمای کلی") : 'Overview', paths: ['/dashboard', '/reports'] },
    { name: language === 'fa' ? t("فروش و مشتریان") : 'Sales & customers', paths: ['/invoices/create', '/invoices/sales', '/customers', '/services'] },
    { name: language === 'fa' ? t("انبار و خرید") : 'Inventory & purchasing', paths: ['/catalog/tires', '/invoices/purchases', '/catalog/movements', '/suppliers'] },
    { name: language === 'fa' ? t("مالی و مدیریت") : 'Finance & management', paths: ['/treasury', '/users'] },
  ];

  const content = (
    <>
        <div className="sidebar-brand flex items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <div className="brand-mark">
              <CircleDot className="w-6 h-6" aria-hidden="true" />
            </div>
            <div className="flex flex-col">
              <span className="font-extrabold text-white text-base leading-tight">
                {t('appName', 'تایر منیجر')}
              </span>
              <span className="text-[10px] text-slate-300 font-medium mt-1">
                {t('appSubtitle', 'سامانه هوشمند فروشگاه و خدمات')}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="ui-button flex items-center justify-center text-slate-300 hover:text-white md:hidden"
            aria-label={t('closeMenu', 'بستن منو')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav aria-label={t('operationalMenu', 'منوی عملیاتی')} className="flex-1 overflow-y-auto px-3 py-5">
          {groups.map((group) => {
            const items = filteredNavItems.filter((item) => group.paths.includes(item.path));
            if (!items.length) return null;
            return <section key={group.name} className="sidebar-section">
              <h2>{group.name}</h2>
              {items.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onClose}
                title={item.name}
                className="sidebar-link"
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="min-w-0 whitespace-normal">{item.name}</span>
                <ChevronLeft className="nav-indicator w-3.5 h-3.5 shrink-0 ltr:rotate-180" aria-hidden="true" />
              </NavLink>
            );
              })}
            </section>;
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center font-bold text-brand-300 text-sm">
              {user?.full_name?.charAt(0) || user?.username?.charAt(0) || (language === 'en' ? 'U' : t("ک"))}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-200 truncate">{user?.full_name || user?.username}</p>
              <span className="text-[11px] text-slate-300 font-medium">
                {getRoleLabel(user?.role, user?.role_display)}
              </span>
            </div>
          </div>
        </div>
    </>
  );

  return <>
    <aside className="sidebar hidden md:flex flex-col shrink-0 no-print">{content}</aside>
    {isOpen && <Modal label={t('operationalMenu', 'منوی عملیاتی')} onClose={() => onClose?.()} className="sidebar-drawer no-print">{content}</Modal>}
  </>;
};
