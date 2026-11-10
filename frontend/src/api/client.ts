import axios from 'axios';
import { SESSION_KEYS, readStorage, removeStorage, writeStorage } from '../utils/storage';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL?.trim() || '/api/v1').replace(/\/+$/, '');

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = readStorage('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (config.url === '/auth/logout/') {
      const refresh = readStorage('refresh_token');
      if (refresh) config.data = { refresh };
    }
    return config;
  },
  (error) => Promise.reject(error)
);

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

const endSession = () => {
  removeStorage(...SESSION_KEYS);
  window.location.href = '/login';
};

/** Only an explicit rejection of the refresh token ends the session; outages, 5xx and 429 keep it. */
export const isRefreshTokenRejected = (error: unknown): boolean => {
  const status = (error as { response?: { status?: number } } | null)?.response?.status;
  return status === 400 || status === 401;
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
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

      isRefreshing = true;

      try {
        const refreshToken = readStorage('refresh_token');
        if (!refreshToken) {
          processQueue(error, null);
          endSession();
          return Promise.reject(error);
        }

        const response = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
          refresh: refreshToken,
        });

        const newAccessToken = response.data.access;
        writeStorage('access_token', newAccessToken);
        if (response.data.refresh) {
          writeStorage('refresh_token', response.data.refresh);
        }

        apiClient.defaults.headers.common.Authorization = `Bearer ${newAccessToken}`;
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;

        processQueue(null, newAccessToken);
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        if (isRefreshTokenRejected(refreshError)) {
          endSession();
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
