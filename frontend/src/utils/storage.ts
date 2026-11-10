// localStorage can throw (blocked storage, Safari private mode, quota); UI must keep working without it.
export function readStorage(key: string): string | null {
  try {
    return globalThis.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStorage(key: string, value: string): void {
  try {
    globalThis.localStorage.setItem(key, value);
  } catch {
    // Preference is simply not persisted.
  }
}

export function removeStorage(...keys: string[]): void {
  for (const key of keys) {
    try {
      globalThis.localStorage.removeItem(key);
    } catch {
      // Nothing to clean up when storage is unavailable.
    }
  }
}

export const SESSION_KEYS = ['access_token', 'refresh_token', 'user_info'] as const;
