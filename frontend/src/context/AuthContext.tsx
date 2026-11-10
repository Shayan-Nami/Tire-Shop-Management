import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole } from '../types';
import { authApi } from '../api/auth';
import { clearLocalSession } from '../utils/session';
import { SESSION_KEYS, readStorage, removeStorage, writeStorage } from '../utils/storage';

type CurrencyUnit = 'rial' | 'toman';

function readSavedUser(): User | null {
  const saved = readStorage('user_info');
  if (!saved) return null;
  try {
    return JSON.parse(saved) as User;
  } catch {
    return null;
  }
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  currencyUnit: CurrencyUnit;
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
  const [currencyUnit, setCurrencyUnit] = useState<CurrencyUnit>(() => {
    return readStorage('preferred_currency') === 'rial' ? 'rial' : 'toman';
  });

  useEffect(() => {
    const initAuth = async () => {
      const token = readStorage('access_token');
      const savedUser = readSavedUser();

      if (token && savedUser) {
        setUser(savedUser);
        try {
          const freshUser = await authApi.getCurrentUser();
          setUser(freshUser);
          writeStorage('user_info', JSON.stringify(freshUser));
        } catch (error) {
          // A 401 here means the refresh token was rejected; an outage keeps the cached session.
          if ((error as { response?: { status?: number } })?.response?.status === 401) {
            removeStorage(...SESSION_KEYS);
            setUser(null);
          }
        }
      } else if (token || savedUser) {
        removeStorage(...SESSION_KEYS);
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  useEffect(() => {
    // Mirror sign-out and sign-in performed in another tab.
    const onStorage = (event: StorageEvent) => {
      if (event.key !== null && event.key !== 'access_token' && event.key !== 'user_info') return;
      if (!readStorage('access_token')) {
        setUser(null);
        if (!window.location.pathname?.startsWith('/login')) window.location.href = '/login';
      } else if (event.key === 'user_info') {
        const saved = readSavedUser();
        if (saved) setUser(saved);
      }
    };
    const target = window;
    target.addEventListener('storage', onStorage);
    return () => target.removeEventListener('storage', onStorage);
  }, []);

  const login = async (username: string, password: string) => {
    const data = await authApi.login(username, password);
    writeStorage('access_token', data.access);
    writeStorage('refresh_token', data.refresh);
    writeStorage('user_info', JSON.stringify(data.user));
    setUser(data.user);
  };

  const endLocalSession = (reason?: 'password-changed') => {
    clearLocalSession();
    setUser(null);
    window.location.href = reason === 'password-changed' ? '/login?reason=password-changed' : '/login';
  };

  const logout = async () => {
    const refreshToken = readStorage('refresh_token');
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
    writeStorage('user_info', JSON.stringify(updated));
  };

  const hasRole = (roles: UserRole[]) => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  const toggleCurrencyUnit = () => {
    setCurrencyUnit((prev) => {
      const next = prev === 'rial' ? 'toman' : 'rial';
      writeStorage('preferred_currency', next);
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

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
