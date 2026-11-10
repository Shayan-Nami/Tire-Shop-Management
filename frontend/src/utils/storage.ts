// localStorage can throw (blocked storage, Safari private mode, quota); UI must keep working without it.
export function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Preference is simply not persisted.
  }
}

export function removeStorage(...keys: string[]): void {
  for (const key of keys) {
    try {
      window.localStorage.removeItem(key);
    } catch {
      // Nothing to clean up when storage is unavailable.
    }
  }
}
