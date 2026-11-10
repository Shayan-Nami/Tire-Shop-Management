import { useLanguage } from '../../context/LanguageContext';
import React from 'react';
import { parseIranianPlate } from '../../utils/formatters';

interface IranianPlateBadgeProps {
  plateString?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const IranianPlateBadge: React.FC<IranianPlateBadgeProps> = ({
  plateString,
  size = 'md',
  className = '',
}) => {
  const { t } = useLanguage();
  const { part1, letter, part2, iranCode, isValid } = parseIranianPlate(plateString);

  const sizeClasses = {
    sm: 'h-7 text-xs px-1',
    md: 'h-9 text-sm px-1.5',
    lg: 'h-11 text-base px-2',
  };

  if (!isValid) {
    return (
      <span
        dir="auto"
        className={`inline-flex items-center rounded-md border border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 ${sizeClasses[size]} ${className}`}
        title={plateString?.trim() ? t("پلاک با فرمت نامعتبر") : t("پلاک ثبت نشده است")}
      >
        {plateString?.trim() ? plateString : t("پلاک ثبت نشده است")}
      </span>
    );
  }

  return (
    <div
      dir="ltr"
      className={`inline-flex items-center bg-white text-slate-900 border-2 border-slate-800 rounded-md font-bold tracking-tight shadow-sm select-none ${sizeClasses[size]} ${className}`}
      style={{ fontFamily: 'Vazirmatn, sans-serif' }}
      title={t("پلاک خودرو: {0}", undefined, { 0: plateString || t("تعیین‌نشده") })}
    >
      <div className="flex flex-col items-center justify-between bg-blue-700 text-white h-full px-1 py-0.5 rounded-l-[2px] mr-1.5 text-[8px] leading-none">
        <div className="flex flex-col items-center space-y-0.5">
          <div className="w-3.5 h-2 rounded-[1px] overflow-hidden flex flex-col shadow-xs">
            <div className="h-1/3 bg-emerald-600"></div>
            <div className="h-1/3 bg-white"></div>
            <div className="h-1/3 bg-red-600"></div>
          </div>
          <span className="font-sans font-semibold tracking-tighter text-[6px]">I.R.</span>
          <span className="font-sans font-semibold tracking-tighter text-[6px]">IRAN</span>
        </div>
      </div>

      <span className="px-1 text-slate-900 tabular-nums">{part1}</span>

      <span className="px-1 text-blue-900 font-extrabold">{letter}</span>

      <span className="px-1 text-slate-900 tabular-nums tracking-wide">{part2}</span>

      <div className="h-full w-[2px] bg-slate-800 mx-1"></div>

      <div className="flex flex-col items-center justify-center px-1 leading-none">
        <span className="text-[9px] text-slate-600 font-medium">{t("ایران")}</span>
        <span className="text-slate-900 tabular-nums font-black">{iranCode}</span>
      </div>
    </div>
  );
};
