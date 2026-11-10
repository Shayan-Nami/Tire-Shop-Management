import { apiClient } from '../api/client';
import { SESSION_KEYS, removeStorage } from './storage';

export function clearLocalSession(): void {
  removeStorage(...SESSION_KEYS);
  delete apiClient.defaults.headers.common.Authorization;
}
