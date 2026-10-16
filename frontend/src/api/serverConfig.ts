// frontend/src/api/serverConfig.ts
export const API_BASE_STORAGE_KEY = 'hobbyland:api-base';

// Mirror of the last value whose persistence FAILED (privacy mode / quota).
// While set, it keeps the choice effective for the rest of the session even
// though it could not be written to localStorage. `undefined` = the last write
// succeeded (or none happened) — localStorage is the source of truth.
let memoryFallback: string | null | undefined;

function readStoredApiBase(): string | null {
  try {
    return window.localStorage.getItem(API_BASE_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredApiBase(value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(API_BASE_STORAGE_KEY);
    else window.localStorage.setItem(API_BASE_STORAGE_KEY, value);
    memoryFallback = undefined;
  } catch {
    // localStorage unavailable (privacy mode); keep the change effective for
    // this session via memoryFallback — it simply will not persist.
    memoryFallback = value;
  }
}

export function normalizeApiBase(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, '');
  if (trimmed === '') return '';
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error(`無效的伺服器地址：${trimmed}`);
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error('伺服器地址必須以 http:// 或 https:// 開頭');
  }
  if (parsed.pathname !== '/' || parsed.search !== '' || parsed.hash !== '') {
    throw new Error('伺服器地址不可包含路徑，例如 https://host:8089');
  }
  return parsed.origin;
}

function buildDefaultApiBase(): string {
  return (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');
}

export function getApiBase(): string {
  // A failed write must not silently revert requests to the previously stored
  // server — the memory mirror wins until a write succeeds again.
  if (memoryFallback !== undefined) return memoryFallback ?? buildDefaultApiBase();
  const stored = readStoredApiBase();
  if (stored !== null) return stored;
  return buildDefaultApiBase();
}

export function setApiBase(url: string): string {
  const normalized = normalizeApiBase(url);
  writeStoredApiBase(normalized);
  return normalized;
}

export function clearApiBase(): string {
  writeStoredApiBase(null);
  return buildDefaultApiBase();
}
