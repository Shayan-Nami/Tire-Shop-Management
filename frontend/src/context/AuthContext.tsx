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
    let active = true;

    const initAuth = async () => {
      const token = localStorage.getItem('access_token');
      const savedUser = localStorage.getItem('user_info');

      if (token && savedUser) {
        try {
          setUser(JSON.parse(savedUser));
          const freshUser = await authApi.getCurrentUser();
          if (!active) return;
          setUser(freshUser);
          localStorage.setItem('user_info', JSON.stringify(freshUser));
        } catch {
          clearLocalSession();
          if (active) setUser(null);
        }
      }
      if (active) setIsLoading(false);
    };

    void initAuth();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.addEventListener !== 'function') {
      return;
    }

    const handleStorage = (event: StorageEvent) => {
      if (event.key === null) {
        setUser(null);
        setCurrencyUnit('toman');
        return;
      }

      if (event.key === 'access_token') {
        if (!event.newValue) {
          setUser(null);
          return;
        }
        const savedUser = localStorage.getItem('user_info');
        if (savedUser) {
          try {
            setUser(JSON.parse(savedUser));
          } catch {
            setUser(null);
          }
        }
        return;
      }

      if (event.key === 'user_info') {
        if (!event.newValue) {
          setUser(null);
          return;
        }
        try {
          setUser(JSON.parse(event.newValue));
        } catch {
          setUser(null);
        }
        return;
      }

      if (event.key === 'preferred_currency') {
        setCurrencyUnit(event.newValue === 'rial' ? 'rial' : 'toman');
      }
    };

    window.addEventListener('storage', handleStorage);
    return () => {
      if (typeof window !== 'undefined' && typeof window.removeEventListener === 'function') {
        window.removeEventListener('storage', handleStorage);
      }
    };
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

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
