import { useLanguage } from './context/LanguageContext';
import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import { RoleGuard } from './components/layout/RoleGuard';
import { MainLayout } from './components/layout/MainLayout';

// بارگذاری تنبل صفحات جهت کاهش حجم باندل اولیه (Code Splitting)
const Login = React.lazy(() => import('./pages/Login').then((m) => ({ default: m.Login })));
const Dashboard = React.lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const SalesInvoices = React.lazy(() => import('./pages/SalesInvoices').then((m) => ({ default: m.SalesInvoices })));
const CreateInvoice = React.lazy(() => import('./pages/CreateInvoice').then((m) => ({ default: m.CreateInvoice })));
const PurchaseInvoices = React.lazy(() => import('./pages/PurchaseInvoices').then((m) => ({ default: m.PurchaseInvoices })));
const TiresCatalog = React.lazy(() => import('./pages/TiresCatalog').then((m) => ({ default: m.TiresCatalog })));
const StockMovements = React.lazy(() => import('./pages/StockMovements').then((m) => ({ default: m.StockMovements })));
const Treasury = React.lazy(() => import('./pages/Treasury').then((m) => ({ default: m.Treasury })));
const Customers = React.lazy(() => import('./pages/Customers').then((m) => ({ default: m.Customers })));
const ServicesPage = React.lazy(() => import('./pages/ServicesPage').then((m) => ({ default: m.ServicesPage })));
const SuppliersPage = React.lazy(() => import('./pages/SuppliersPage').then((m) => ({ default: m.SuppliersPage })));
const ReportsPage = React.lazy(() => import('./pages/ReportsPage').then((m) => ({ default: m.ReportsPage })));
const UsersPage = React.lazy(() => import('./pages/UsersPage').then((m) => ({ default: m.UsersPage })));

const PageLoadingFallback: React.FC = () => {
  const { t } = useLanguage();
  return (
  <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-slate-400">
    <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
    <span className="text-xs font-medium">{t("در حال بارگذاری صفحه...")}</span>
  </div>
);
};

const RootRedirect: React.FC = () => {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;

  if (user.role === 'TECHNICIAN') {
    return <Navigate to="/invoices/create" replace />;
  }
  if (user.role === 'WAREHOUSE') {
    return <Navigate to="/catalog/tires" replace />;
  }
  return <Navigate to="/dashboard" replace />;
};

export const App: React.FC = () => {
  return (
    <LanguageProvider>
      <AuthProvider>
        <BrowserRouter>
          <Suspense fallback={<PageLoadingFallback />}>
            <Routes>
              {/* صفحه عمومی لاگین */}
              <Route path="/login" element={<Login />} />

              {/* مسیرهای محافظت‌شده با گارد احراز هویت */}
              <Route element={<RoleGuard />}>
                <Route element={<MainLayout />}>
                  <Route path="/" element={<RootRedirect />} />

                  {/* داشبورد و شاخص‌ها */}
                  <Route element={<RoleGuard allowedRoles={['MANAGER']} />}>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/reports" element={<ReportsPage />} />
                    <Route path="/treasury" element={<Treasury />} />
                  </Route>

                  {/* فاکتور فروش و صندوق */}
                  <Route element={<RoleGuard allowedRoles={['MANAGER', 'TECHNICIAN']} />}>
                    <Route path="/invoices/create" element={<CreateInvoice />} />
                  </Route>

                  <Route
                    path="/invoices/sales"
                    element={<SalesInvoices />}
                  />

                  {/* انبار و خرید */}
                  <Route
                    path="/catalog/tires"
                    element={<TiresCatalog />}
                  />

                  <Route element={<RoleGuard allowedRoles={['MANAGER', 'WAREHOUSE']} />}>
                    <Route path="/invoices/purchases" element={<PurchaseInvoices />} />
                    <Route path="/suppliers" element={<SuppliersPage />} />
                  </Route>

                  <Route element={<RoleGuard allowedRoles={['MANAGER', 'WAREHOUSE']} />}>
                    <Route path="/catalog/movements" element={<StockMovements />} />
                  </Route>

                  {/* مشتریان و خودروها */}
                  <Route path="/customers" element={<Customers />} />

                  {/* خدمات کارگاهی */}
                  <Route element={<RoleGuard allowedRoles={['MANAGER', 'TECHNICIAN']} />}>
                    <Route path="/services" element={<ServicesPage />} />
                  </Route>

                  {/* مدیریت کاربران فقط مدیر */}
                  <Route element={<RoleGuard allowedRoles={['MANAGER']} />}>
                    <Route path="/users" element={<UsersPage />} />
                  </Route>
                </Route>
              </Route>

              {/* ریدایرکت برای مسیرهای نامعتبر */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </LanguageProvider>
  );
};

export default App;
