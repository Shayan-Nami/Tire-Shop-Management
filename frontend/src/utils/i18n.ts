import { englishMessages } from './englishMessages.ts';
export type Language = 'fa' | 'en';
export type Direction = 'rtl' | 'ltr';

export const translations: Record<string, { fa: string; en: string }> = {
  // Brand & Shell
  appTitle: { fa: 'سامانه فروشگاه و انبار لاستیک', en: 'Tire Shop & Inventory System' },
  appName: { fa: 'تایر منیجر', en: 'Tire Manager' },
  appSubtitle: { fa: 'سامانه هوشمند فروشگاه و خدمات', en: 'Smart Shop & Workshop System' },
  connectedStatus: { fa: 'سامانه متصل', en: 'System Connected' },
  operationalMenu: { fa: 'منوی عملیاتی', en: 'Operational Menu' },

  // Quick Actions & Controls
  newSaleInvoice: { fa: 'فاکتور فروش جدید', en: 'New Sales Invoice' },
  themeToggleDay: { fa: 'تغییر به حالت روز (روشن)', en: 'Switch to Light Mode' },
  themeToggleNight: { fa: 'تغییر به حالت شب (تاریک)', en: 'Switch to Dark Mode' },
  themeAria: { fa: 'تغییر تم تاریک و روشن', en: 'Toggle Dark/Light Mode' },
  currencyUnitTitle: { fa: 'تغییر واحد پولی پیش‌فرض نمایش ارقام', en: 'Toggle Currency Display Unit' },
  currencyUnitLabel: { fa: 'واحد:', en: 'Unit:' },
  toman: { fa: 'تومان', en: 'Toman' },
  rial: { fa: 'ریال', en: 'Rial' },
  langToggleTitle: { fa: 'تغییر زبان به انگلیسی (Switch to English)', en: 'Switch to Persian' },
  langToggleAria: { fa: 'تغییر زبان بین فارسی و انگلیسی (FA / EN)', en: 'Toggle Language between Persian and English (FA / EN)' },
  langLabel: { fa: 'زبان:', en: 'Lang:' },
  langFa: { fa: 'فارسی', en: 'Persian' },
  langEn: { fa: 'انگلیسی', en: 'English' },

  // User Roles
  roleManager: { fa: 'مدیر سیستم', en: 'System Manager' },
  roleTechnician: { fa: 'تکنسین فنی', en: 'Technician' },
  roleWarehouse: { fa: 'انباردار', en: 'Warehouse staff' },

  // User Dropdown & Profile
  userSettings: { fa: 'حساب کاربری و تنظیمات', en: 'Account Settings' },
  editProfile: { fa: 'ویرایش مشخصات فردی', en: 'Edit Profile' },
  changePassword: { fa: 'تغییر کلمه عبور', en: 'Change Password' },
  logoutAccount: { fa: 'خروج از حساب', en: 'Sign Out' },
  logoutDirect: { fa: 'خروج', en: 'Logout' },
  openMenu: { fa: 'باز کردن منو', en: 'Open menu' },
  closeMenu: { fa: 'بستن منو', en: 'Close menu' },

  // Sidebar Nav Items
  navDashboard: { fa: 'میز کار و داشبورد', en: 'Dashboard' },
  navCreateInvoice: { fa: 'صدور فاکتور فروش (صندوق)', en: 'New Sales Invoice (POS)' },
  navSalesInvoices: { fa: 'فاکتورهای فروش', en: 'Sales Invoices' },
  navTiresCatalog: { fa: 'کاتالوگ و موجودی تایرها', en: 'Tire Catalog & Stock' },
  navPurchaseInvoices: { fa: 'فاکتورهای خرید (ورود به انبار)', en: 'Purchase Invoices' },
  navStockMovements: { fa: 'دفتر گردش انبار (حسابرسی)', en: 'Stock Ledger & Audit' },
  navTreasury: { fa: 'خزانه‌داری و اسناد مالی', en: 'Treasury & Payments' },
  navCustomers: { fa: 'مشتریان و وسایل نقلیه', en: 'Customers & Vehicles' },
  navServices: { fa: 'تعرفه خدمات کارگاه', en: 'Workshop Services' },
  navSuppliers: { fa: 'تأمین‌کنندگان لاستیک', en: 'Tire Suppliers' },
  navReports: { fa: 'گزارش‌های تحلیلی و سودآوری', en: 'Reports & Analytics' },
  navUsers: { fa: 'مدیریت کاربران و نقش‌ها', en: 'User Management' },
};

// Existing semantic keys and source-copy keys share the same language contract.
for (const [fa, en] of Object.entries(englishMessages)) translations[fa] = { fa, en };

export function translateMessage(message: string, language: Language): string {
  return language === 'en' ? (translations[message]?.en || message) : message;
}

Object.assign(translations, { MANAGER: { fa: 'مدیر سیستم', en: 'Manager' }, TECHNICIAN: { fa: 'تکنسین فنی', en: 'Technician' }, WAREHOUSE: { fa: 'انباردار', en: 'Warehouse staff' } });
