@echo off
chcp 65001 > nul
echo ===================================================
echo   سیستم مدیریت فروشگاه لاستیک (Tire Shop Management)
echo ===================================================
echo در حال اجرای سرور بک‌اند (Django)...
start "Backend - Django" cmd /k "cd /d %~dp0backend && python manage.py runserver 127.0.0.1:8000"

echo در حال اجرای سرور فرانت‌اند (Vite + React)...
start "Frontend - Vite" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo سرویس‌ها در دو پنجره مجزا اجرا شدند:
echo فرانت‌اند: http://localhost:5173
echo بک‌اند: http://127.0.0.1:8000
echo ===================================================
pause
