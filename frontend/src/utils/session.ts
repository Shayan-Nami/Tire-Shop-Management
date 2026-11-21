import { apiClient } from '../api/client';
import { clearAuthStorage } from './authStorage';

export * from './authStorage';

export function clearLocalSession(): void {
  clearAuthStorage();
  delete apiClient.defaults.headers.common.Authorization;
}
