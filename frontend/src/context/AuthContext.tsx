import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole } from '../types';
import { authApi } from '../api/auth';
import { clearLocalSession } from '../utils/session';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  currencyUnit: 'rial' | 'toman';
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  endLocalSession: (reason?: 'password-changed') => void;
  updateUser: (updated: User) => void;
  hasRole: (roles: UserRole[]) => boolean;
  toggleCurrencyUnit: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [currencyUnit, setCurrencyUnit] = useState<'rial' | 'toman'>(() => {
    return (localStorage.getItem('preferred_currency') as 'rial' | 'toman') || 'toman';
  });

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token');
      const savedUser = localStorage.getItem('user_info');

      if (token && savedUser) {
        try {
          setUser(JSON.parse(savedUser));
          // تایید اعتبار با دریافت پروفایل زنده
          const freshUser = await authApi.getCurrentUser();
          setUser(freshUser);
          localStorage.setItem('user_info', JSON.stringify(freshUser));
        } catch {
          // در صورت بروز خطا در اعتبارسنجی
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user_info');
          setUser(null);
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = async (username: string, password: string) => {
    const data = await authApi.login(username, password);
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    localStorage.setItem('user_info', JSON.stringify(data.user));
    setUser(data.user);
  };

  const endLocalSession = (reason?: 'password-changed') => {
    clearLocalSession();
    setUser(null);
    window.location.href = reason === 'password-changed' ? '/login?reason=password-changed' : '/login';
  };

  const logout = async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } catch (err) {
      console.warn('Server logout failed or token already blacklisted:', err);
    } finally {
      endLocalSession();
    }
  };

  const updateUser = (updated: User) => {
    setUser(updated);
    localStorage.setItem('user_info', JSON.stringify(updated));
  };

  const hasRole = (roles: UserRole[]) => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  const toggleCurrencyUnit = () => {
    setCurrencyUnit((prev) => {
      const next = prev === 'rial' ? 'toman' : 'rial';
      localStorage.setItem('preferred_currency', next);
      return next;
    });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        currencyUnit,
        login,
        logout,
        endLocalSession,
        updateUser,
        hasRole,
        toggleCurrencyUnit,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// oxlint-disable-next-line react/only-export-components -- Keep the existing public context hook API; no auth-module migration in this phase.
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
