import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { User, UserRole } from '../types';
import { authApi } from '../api/auth';
import {
  clearLocalSession,
  getAccessToken,
  getIdleTimeoutMs,
  getLastActivityAt,
  getRefreshToken,
  getSavedUserRaw,
  getSessionPersistenceMode,
  isIdleExpired,
  purgeLegacyLocalTokens,
  saveSessionTokens,
  saveUserInfo,
  touchSessionActivity,
  type LogoutReason,
  type SessionPersistenceMode,
} from '../utils/session';

const ACTIVITY_THROTTLE_MS = 15_000;
const IDLE_CHECK_INTERVAL_MS = 15_000;
const LOGOUT_TIMEOUT_MS = 2_000;
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'mousemove', 'scroll', 'touchstart'] as const;

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  currencyUnit: 'rial' | 'toman';
  login: (username: string, password: string, rememberMe?: boolean) => Promise<void>;
  logout: () => Promise<void>;
  endLocalSession: (reason?: LogoutReason) => void;
  updateUser: (updated: User) => void;
  hasRole: (roles: UserRole[]) => boolean;
  toggleCurrencyUnit: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function isUserRole(role: unknown): role is UserRole {
  return role === 'MANAGER' || role === 'TECHNICIAN' || role === 'WAREHOUSE';
}

function parseStoredUser(raw: string | null): User | null {
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    if (!('id' in parsed) || typeof parsed.id !== 'number') return null;
    if (!('username' in parsed) || typeof parsed.username !== 'string') return null;
    if (!('role' in parsed) || !isUserRole(parsed.role)) return null;
    return parsed as User;
  } catch {
    return null;
  }
}

function isLoginRoute(): boolean {
  if (typeof window === 'undefined' || !window.location) return false;
  if (typeof window.location.pathname === 'string') {
    return window.location.pathname.startsWith('/login');
  }
  return typeof window.location.href === 'string' && window.location.href.startsWith('/login');
}

async function bestEffortServerLogout(refreshToken: string): Promise<void> {
  if (typeof authApi.logout !== 'function') return;
  let timerId: ReturnType<typeof setTimeout> | undefined;
  try {
    const logoutPromise = Promise.resolve(authApi.logout(refreshToken)).catch((err) => {
      console.warn('Idle timeout server logout failed:', err);
    });
    const timeoutPromise = new Promise<void>((resolve) => {
      timerId = setTimeout(resolve, LOGOUT_TIMEOUT_MS);
    });
    await Promise.race([logoutPromise, timeoutPromise]);
  } finally {
    if (timerId !== undefined) {
      clearTimeout(timerId);
    }
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [currencyUnit, setCurrencyUnit] = useState<'rial' | 'toman'>(() => {
    try {
      return typeof localStorage !== 'undefined' && localStorage.getItem('preferred_currency') === 'rial'
        ? 'rial'
        : 'toman';
    } catch {
      return 'toman';
    }
  });

  const userRef = useRef<User | null>(null);
  const persistenceRef = useRef<SessionPersistenceMode>('session');
  const isExpiringIdleRef = useRef<boolean>(false);

  useEffect(() => {
    userRef.current = user;
  }, [user]);

  useEffect(() => {
    let active = true;

    const initAuth = async () => {
      purgeLegacyLocalTokens();
      const token = getAccessToken();
      const savedUser = getSavedUserRaw();
      const hasStoredSession = Boolean(token || savedUser || getRefreshToken());

      if (hasStoredSession && isIdleExpired(getLastActivityAt(), Date.now(), getIdleTimeoutMs())) {
        clearLocalSession();
        if (active) {
          persistenceRef.current = 'session';
          setUser(null);
        }
        if (typeof window !== 'undefined' && !isLoginRoute()) {
          window.location.href = '/login?reason=idle-timeout';
        }
        if (active) setIsLoading(false);
        return;
      }

      if (token && savedUser) {
        const parsedUser = parseStoredUser(savedUser);
        if (!parsedUser) {
          clearLocalSession();
          if (active) {
            persistenceRef.current = 'session';
            setUser(null);
            setIsLoading(false);
          }
          return;
        }
        try {
          persistenceRef.current = getSessionPersistenceMode();
          setUser(parsedUser);
          const freshUser = await authApi.getCurrentUser();
          if (!active) return;
          setUser(freshUser);
          saveUserInfo(freshUser);
          touchSessionActivity();
        } catch {
          clearLocalSession();
          if (active) {
            persistenceRef.current = 'session';
            setUser(null);
          }
        }
      } else if (hasStoredSession) {
        clearLocalSession();
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
      if (event.key === 'preferred_currency') {
        setCurrencyUnit(event.newValue === 'rial' ? 'rial' : 'toman');
        return;
      }

      const mode = getSessionPersistenceMode();
      if (userRef.current !== null && persistenceRef.current === 'session') {
        if (event.key === null) {
          setCurrencyUnit('toman');
        }
        return;
      }

      if (event.key === null) {
        if (persistenceRef.current === 'persistent' || mode === 'persistent') {
          persistenceRef.current = 'session';
          setUser(null);
        }
        setCurrencyUnit('toman');
        return;
      }

      if (event.key === 'auth_persistence') {
        if (event.newValue === 'persistent') {
          if (mode === 'persistent' && !isIdleExpired(getLastActivityAt(), Date.now(), getIdleTimeoutMs())) {
            const parsedUser = parseStoredUser(getSavedUserRaw());
            if (parsedUser) {
              persistenceRef.current = 'persistent';
              setUser(parsedUser);
            }
          }
          return;
        }
        if (persistenceRef.current === 'persistent') {
          persistenceRef.current = 'session';
          setUser(null);
        }
        return;
      }

      if (event.key === 'access_token') {
        if (!event.newValue) {
          if (persistenceRef.current === 'persistent' || mode === 'persistent') {
            persistenceRef.current = 'session';
            setUser(null);
          }
          return;
        }
        if (mode !== 'persistent' || isIdleExpired(getLastActivityAt(), Date.now(), getIdleTimeoutMs())) {
          return;
        }
        const parsedUser = parseStoredUser(getSavedUserRaw());
        if (parsedUser) {
          persistenceRef.current = 'persistent';
          setUser(parsedUser);
        } else {
          setUser(null);
        }
        return;
      }

      if (event.key === 'user_info') {
        if (!event.newValue) {
          if (persistenceRef.current === 'persistent' || mode === 'persistent') {
            persistenceRef.current = 'session';
            setUser(null);
          }
          return;
        }
        if (mode !== 'persistent') {
          return;
        }
        const parsedUser = parseStoredUser(event.newValue);
        if (parsedUser) {
          persistenceRef.current = 'persistent';
          setUser(parsedUser);
        } else {
          setUser(null);
        }
      }
    };

    window.addEventListener('storage', handleStorage);
    return () => {
      if (typeof window !== 'undefined' && typeof window.removeEventListener === 'function') {
        window.removeEventListener('storage', handleStorage);
      }
    };
  }, []);

  const endLocalSession = useCallback((reason?: LogoutReason) => {
    clearLocalSession();
    persistenceRef.current = 'session';
    setUser(null);
    if (typeof window !== 'undefined') {
      window.location.href = reason ? `/login?reason=${reason}` : '/login';
    }
  }, []);

  const isAuthenticated = Boolean(user);

  useEffect(() => {
    if (!isAuthenticated) {
      isExpiringIdleRef.current = false;
      return;
    }

    let active = true;
    isExpiringIdleRef.current = false;
    const timeoutMs = getIdleTimeoutMs();
    let lastTouchWriteAt = 0;
    let idleTimerId: ReturnType<typeof setTimeout> | undefined;

    const clearIdleTimer = () => {
      if (idleTimerId !== undefined) {
        clearTimeout(idleTimerId);
        idleTimerId = undefined;
      }
    };

    const expireIdleSession = async () => {
      if (isExpiringIdleRef.current) return;
      isExpiringIdleRef.current = true;
      clearIdleTimer();
      const refreshToken = getRefreshToken();
      try {
        if (refreshToken) {
          await bestEffortServerLogout(refreshToken);
        }
      } finally {
        if (active) {
          endLocalSession('idle-timeout');
        } else {
          clearLocalSession();
        }
      }
    };

    const scheduleRemainingTimeout = (delayMs: number) => {
      clearIdleTimer();
      const boundedDelay = Math.max(1, Math.min(delayMs, timeoutMs));
      idleTimerId = setTimeout(() => {
        checkIdleAndReschedule();
      }, boundedDelay);
    };

    const checkIdleAndReschedule = () => {
      if (!active || isExpiringIdleRef.current) return;
      const now = Date.now();
      const latestActivity = getLastActivityAt();
      if (isIdleExpired(latestActivity, now, timeoutMs)) {
        void expireIdleSession();
        return;
      }
      if (latestActivity !== null) {
        const elapsed = Math.max(0, now - latestActivity);
        scheduleRemainingTimeout(timeoutMs - elapsed);
      }
    };

    const handleUserActivity = () => {
      if (!active || isExpiringIdleRef.current) return;
      const now = Date.now();
      if (isIdleExpired(getLastActivityAt(), now, timeoutMs)) {
        void expireIdleSession();
        return;
      }
      if (now - lastTouchWriteAt >= ACTIVITY_THROTTLE_MS) {
        touchSessionActivity(now);
        lastTouchWriteAt = now;
        scheduleRemainingTimeout(timeoutMs);
      }
    };

    const handleVisibilityOrFocus = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        return;
      }
      handleUserActivity();
    };

    checkIdleAndReschedule();
    const intervalId = setInterval(checkIdleAndReschedule, IDLE_CHECK_INTERVAL_MS);

    if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
      for (const eventName of ACTIVITY_EVENTS) {
        window.addEventListener(eventName, handleUserActivity);
      }
      window.addEventListener('focus', handleVisibilityOrFocus);
    }
    if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
      document.addEventListener('visibilitychange', handleVisibilityOrFocus);
    }

    return () => {
      active = false;
      clearIdleTimer();
      clearInterval(intervalId);
      if (typeof window !== 'undefined' && typeof window.removeEventListener === 'function') {
        for (const eventName of ACTIVITY_EVENTS) {
          window.removeEventListener(eventName, handleUserActivity);
        }
        window.removeEventListener('focus', handleVisibilityOrFocus);
      }
      if (typeof document !== 'undefined' && typeof document.removeEventListener === 'function') {
        document.removeEventListener('visibilitychange', handleVisibilityOrFocus);
      }
    };
  }, [isAuthenticated, endLocalSession]);

  const login = async (username: string, password: string, rememberMe = false) => {
    const data = await authApi.login(username, password);
    saveSessionTokens(data, rememberMe);
    persistenceRef.current = rememberMe ? 'persistent' : 'session';
    setUser(data.user);
  };

  const logout = async () => {
    const refreshToken = getRefreshToken();
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
    saveUserInfo(updated);
  };

  const hasRole = (roles: UserRole[]) => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  const toggleCurrencyUnit = () => {
    setCurrencyUnit((prev) => {
      const next = prev === 'rial' ? 'toman' : 'rial';
      try {
        localStorage.setItem('preferred_currency', next);
      } catch {
      }
      return next;
    });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
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
