import axios from 'axios';
import {
  clearAuthStorage,
  getAccessToken,
  getRefreshToken,
  touchSessionActivity,
  updateRotatedTokens,
} from '../utils/authStorage';
import { parseApiError } from '../utils/errorParser';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL?.trim() || '/api/v1').replace(/\/+$/, '');

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (config.url === '/auth/logout/') {
      const refresh = getRefreshToken();
      if (refresh) config.data = { refresh };
    }
    return config;
  },
  (error) => Promise.reject(error)
);

const extractBearerToken = (headers: unknown): string | null => {
  if (!headers || typeof headers !== 'object') return null;
  const record = headers as {
    get?: (name: string) => unknown;
    Authorization?: unknown;
    authorization?: unknown;
  };
  const raw =
    typeof record.get === 'function'
      ? record.get('Authorization')
      : record.Authorization ?? record.authorization;
  if (typeof raw !== 'string') return null;
  const match = raw.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : null;
};

function runWithRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks = globalThis.navigator?.locks;
  if (locks && typeof locks.request === 'function') {
    return locks.request('tire_shop_token_refresh', () => fn());
  }
  return fn();
}

const clearAuthStorageAndRedirect = () => {
  clearAuthStorage();
  delete apiClient.defaults.headers.common.Authorization;
  if (typeof window !== 'undefined') {
    window.location.href = '/login?reason=session-expired';
  }
};

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    try {
      if (error) {
        prom.reject(error);
      } else {
        prom.resolve(token);
      }
    } catch (e) {
      console.error('Error processing queued request:', e);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => {
    if (!response.config?.url?.includes('/auth/token/refresh/') && getAccessToken()) {
      touchSessionActivity();
    }
    return response;
  },
  async (error) => {
    if (error && typeof error === 'object') {
      (error as { userMessage?: string }).userMessage = parseApiError(error);
    }

    const originalRequest = error?.config;
    if (!originalRequest) {
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (originalRequest.url?.includes('/auth/login/') || originalRequest.url?.includes('/auth/token/refresh/')) {
        return Promise.reject(error);
      }

      originalRequest._retry = true;
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers = originalRequest.headers || {};
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      const failedAccessToken = extractBearerToken(originalRequest.headers);
      isRefreshing = true;

      let nextAccessToken: string | null = null;
      let refreshFailure: unknown = null;

      try {
        nextAccessToken = await runWithRefreshLock(async () => {
          const latestAccessToken = getAccessToken();
          if (failedAccessToken && latestAccessToken && latestAccessToken !== failedAccessToken) {
            touchSessionActivity();
            apiClient.defaults.headers.common.Authorization = `Bearer ${latestAccessToken}`;
            return latestAccessToken;
          }

          const refreshToken = getRefreshToken();
          if (!refreshToken) {
            clearAuthStorageAndRedirect();
            throw error;
          }

          try {
            const response = await axios.post<{ access: string; refresh?: string }>(
              `${API_BASE_URL}/auth/token/refresh/`,
              { refresh: refreshToken },
            );

            const newAccessToken = response.data.access;
            updateRotatedTokens({
              access: newAccessToken,
              refresh: response.data.refresh,
            });

            apiClient.defaults.headers.common.Authorization = `Bearer ${newAccessToken}`;
            return newAccessToken;
          } catch (refreshError) {
            const currentRefresh = getRefreshToken();
            const currentAccess = getAccessToken();
            if (currentRefresh && currentRefresh !== refreshToken && currentAccess) {
              touchSessionActivity();
              apiClient.defaults.headers.common.Authorization = `Bearer ${currentAccess}`;
              return currentAccess;
            }

            clearAuthStorageAndRedirect();
            throw refreshError;
          }
        });
      } catch (refreshErr) {
        refreshFailure = refreshErr;
      } finally {
        isRefreshing = false;
      }

      if (nextAccessToken) {
        processQueue(null, nextAccessToken);
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`;
        return apiClient(originalRequest);
      }

      processQueue(refreshFailure ?? error, null);
      return Promise.reject(refreshFailure ?? error);
    }

    return Promise.reject(error);
  }
);
