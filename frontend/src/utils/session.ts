import { apiClient } from '../api/client';

export function clearLocalSession(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user_info');
  delete apiClient.defaults.headers.common.Authorization;
}
