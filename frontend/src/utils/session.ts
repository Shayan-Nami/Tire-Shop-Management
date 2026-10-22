import { apiClient } from '../api/client';

/** Clear local credentials without contacting endpoints that may now reject them. */
export function clearLocalSession(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user_info');
  delete apiClient.defaults.headers.common.Authorization;
}
