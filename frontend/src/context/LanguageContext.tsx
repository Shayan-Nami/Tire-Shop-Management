import React, { createContext, useContext, useState, useEffect } from 'react';
import { translations, type Language, type Direction } from '../utils/i18n';

export type { Language, Direction };

export interface LanguageContextType {
  language: Language;
  direction: Direction;
  isRTL: boolean;
  toggleLanguage: () => void;
  setLanguage: (lang: Language) => void;
  t: (key: string, defaultText?: string) => string;
}

const applyDocumentLanguage = (lang: Language): void => {
  if (typeof document !== 'undefined') {
    const dir: Direction = lang === 'fa' ? 'rtl' : 'ltr';
    document.documentElement.setAttribute('dir', dir);
    document.documentElement.setAttribute('lang', lang);
    if (document.body) {
      document.body.setAttribute('dir', dir);
    }
  }
};

const getStoredLanguage = (): Language => {
  if (typeof window !== 'undefined') {
    try {
      const saved = localStorage.getItem('language');
      if (saved === 'en' || saved === 'fa') return saved;
      if (document.documentElement?.getAttribute('lang') === 'en') return 'en';
    } catch {
      // Fallback if localStorage or DOM is inaccessible
    }
  }
  return 'fa';
};

const defaultLanguageContext: LanguageContextType = {
  language: 'fa',
  direction: 'rtl',
  isRTL: true,
  toggleLanguage: () => {},
  setLanguage: () => {},
  t: (key: string, defaultText?: string) => translations[key]?.fa || defaultText || key,
};

const LanguageContext = createContext<LanguageContextType>(defaultLanguageContext);

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<Language>(getStoredLanguage);

  useEffect(() => {
    applyDocumentLanguage(language);
    try {
      localStorage.setItem('language', language);
    } catch {
      // Ignore storage errors in restricted contexts
    }
  }, [language]);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
  };

  const toggleLanguage = () => {
    setLanguageState((prev) => (prev === 'fa' ? 'en' : 'fa'));
  };

  const t = (key: string, defaultText?: string): string => {
    const entry = translations[key];
    if (entry) {
      return entry[language] || defaultText || entry.fa;
    }
    return defaultText || key;
  };

  const direction: Direction = language === 'fa' ? 'rtl' : 'ltr';

  return (
    <LanguageContext.Provider
      value={{
        language,
        direction,
        isRTL: language === 'fa',
        toggleLanguage,
        setLanguage,
        t,
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
};

// oxlint-disable-next-line react/only-export-components -- Keep the existing context hook API alongside provider
export const useLanguage = (): LanguageContextType => {
  const context = useContext(LanguageContext);
  return context || defaultLanguageContext;
};
