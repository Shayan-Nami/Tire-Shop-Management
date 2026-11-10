import { useLanguage } from '../../context/LanguageContext';
import React, { useEffect, useRef, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Navbar } from './Navbar';

export const MainLayout: React.FC = () => {
  const { t } = useLanguage();
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);

  const { pathname } = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    mainRef.current?.scrollTo(0, 0);
  }, [pathname]);

  return (
    <div className="app-shell flex h-dvh bg-slate-50 dark:bg-slate-950 overflow-hidden font-sans">
      <a href="#main-content" className="skip-link">{t("رفتن به محتوای اصلی")}</a>
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Navbar onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)} />

        <main ref={mainRef} id="main-content" tabIndex={-1} className="workspace flex-1 overflow-y-auto">
          <div className="max-w-[1440px] mx-auto w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
