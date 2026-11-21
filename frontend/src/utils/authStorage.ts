export type SessionPersistenceMode = 'session' | 'persistent';
export type LogoutReason = 'password-changed' | 'idle-timeout' | 'session-expired';

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_INFO_KEY = 'user_info';
const LAST_ACTIVITY_KEY = 'last_activity_at';
const AUTH_PERSISTENCE_KEY = 'auth_persistence';

const DEFAULT_IDLE_TIMEOUT_MINUTES = 15;
const MS_PER_MINUTE = 60_000;

const AUTH_STORAGE_KEYS = [
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  USER_INFO_KEY,
  LAST_ACTIVITY_KEY,
  AUTH_PERSISTENCE_KEY,
] as const;

interface StorageLike {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
}

function isStorageLike(value: unknown): value is StorageLike {
  if (!value || typeof value !== 'object') return false;
  return (
    'getItem' in value && typeof value.getItem === 'function' &&
    'setItem' in value && typeof value.setItem === 'function' &&
    'removeItem' in value && typeof value.removeItem === 'function'
  );
}

function getStorage(kind: 'sessionStorage' | 'localStorage'): StorageLike | null {
  try {
    const candidate = kind === 'sessionStorage' ? globalThis.sessionStorage : globalThis.localStorage;
    return isStorageLike(candidate) ? candidate : null;
  } catch {
    return null;
  }
}

function hasAnyToken(storage: StorageLike | null): boolean {
  if (!storage) return false;
  return Boolean(storage.getItem(ACCESS_TOKEN_KEY) || storage.getItem(REFRESH_TOKEN_KEY));
}

export function purgeLegacyLocalTokens(): void {
  const local = getStorage('localStorage');
  if (!local) return;
  if (local.getItem(AUTH_PERSISTENCE_KEY) === 'persistent') return;
  const hasLegacyKey = AUTH_STORAGE_KEYS.some((key) => local.getItem(key) !== null);
  if (!hasLegacyKey) return;
  for (const key of AUTH_STORAGE_KEYS) {
    local.removeItem(key);
  }
}

export function getSessionPersistenceMode(): SessionPersistenceMode {
  const session = getStorage('sessionStorage');
  if (hasAnyToken(session)) {
    return 'session';
  }
  const local = getStorage('localStorage');
  if (local?.getItem(AUTH_PERSISTENCE_KEY) === 'persistent' && hasAnyToken(local)) {
    return 'persistent';
  }
  return 'session';
}

function getActiveStorage(): StorageLike | null {
  purgeLegacyLocalTokens();
  const session = getStorage('sessionStorage');
  if (hasAnyToken(session)) {
    return session;
  }
  const local = getStorage('localStorage');
  if (local?.getItem(AUTH_PERSISTENCE_KEY) === 'persistent' && hasAnyToken(local)) {
    return local;
  }
  return null;
}

export function getAccessToken(): string | null {
  return getActiveStorage()?.getItem(ACCESS_TOKEN_KEY) ?? null;
}

export function getRefreshToken(): string | null {
  return getActiveStorage()?.getItem(REFRESH_TOKEN_KEY) ?? null;
}

export function getSavedUserRaw(): string | null {
  return getActiveStorage()?.getItem(USER_INFO_KEY) ?? null;
}

export function getLastActivityAt(): number | null {
  const raw = getActiveStorage()?.getItem(LAST_ACTIVITY_KEY);
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export function clearAuthStorage(): void {
  for (const storage of [getStorage('sessionStorage'), getStorage('localStorage')]) {
    if (!storage) continue;
    for (const key of AUTH_STORAGE_KEYS) {
      storage.removeItem(key);
    }
  }
}

export function saveSessionTokens(
  payload: { access: string; refresh: string; user: unknown },
  rememberMe: boolean,
  nowMs?: number,
): void {
  clearAuthStorage();
  const target = rememberMe ? getStorage('localStorage') : getStorage('sessionStorage');
  if (!target) return;
  if (rememberMe) {
    target.setItem(AUTH_PERSISTENCE_KEY, 'persistent');
  }
  target.setItem(ACCESS_TOKEN_KEY, payload.access);
  target.setItem(REFRESH_TOKEN_KEY, payload.refresh);
  target.setItem(USER_INFO_KEY, JSON.stringify(payload.user));
  target.setItem(LAST_ACTIVITY_KEY, String(nowMs ?? Date.now()));
}

export function updateRotatedTokens(
  payload: { access: string; refresh?: string },
  nowMs?: number,
): void {
  const active = getActiveStorage();
  if (!active) return;
  active.setItem(ACCESS_TOKEN_KEY, payload.access);
  if (payload.refresh) {
    active.setItem(REFRESH_TOKEN_KEY, payload.refresh);
  }
  active.setItem(LAST_ACTIVITY_KEY, String(nowMs ?? Date.now()));
}

export function saveUserInfo(user: unknown): void {
  const active = getActiveStorage();
  if (!active) return;
  active.setItem(USER_INFO_KEY, JSON.stringify(user));
}

export function touchSessionActivity(nowMs?: number): void {
  const active = getActiveStorage();
  if (!active || !active.getItem(ACCESS_TOKEN_KEY)) return;
  active.setItem(LAST_ACTIVITY_KEY, String(nowMs ?? Date.now()));
}

export function parseIdleTimeoutMinutes(raw?: string | number | null): number {
  if (raw === undefined || raw === null) return DEFAULT_IDLE_TIMEOUT_MINUTES;
  if (typeof raw === 'number') {
    return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_IDLE_TIMEOUT_MINUTES;
  }
  const trimmed = raw.trim();
  if (!trimmed) return DEFAULT_IDLE_TIMEOUT_MINUTES;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_IDLE_TIMEOUT_MINUTES;
}

export function getIdleTimeoutMs(): number {
  const env = import.meta.env as Record<string, unknown> | undefined;
  const raw = env?.VITE_IDLE_TIMEOUT_MINUTES;
  const normalized = typeof raw === 'string' || typeof raw === 'number' ? raw : null;
  return parseIdleTimeoutMinutes(normalized) * MS_PER_MINUTE;
}

export function isIdleExpired(
  lastActivityAtMs: number | null,
  nowMs: number,
  timeoutMs: number,
): boolean {
  if (lastActivityAtMs === null || !Number.isFinite(lastActivityAtMs)) {
    return true;
  }
  if (!Number.isFinite(nowMs) || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    return true;
  }
  return nowMs - lastActivityAtMs >= timeoutMs;
}
