// frontend/tests/setup.ts
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Node >= 22 exposes an experimental `localStorage` global that yields undefined unless
// --localstorage-file is passed, and it shadows the Storage jsdom would otherwise provide.
function installStorageShim(target: object): void {
  const store = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => [...store.keys()][index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(target, 'localStorage', {
    value: storage,
    configurable: true,
    writable: true,
  });
}

if (typeof globalThis.localStorage?.getItem !== 'function') {
  installStorageShim(globalThis);
}
if (typeof window !== 'undefined' && window !== (globalThis as unknown as Window)) {
  if (typeof window.localStorage?.getItem !== 'function') {
    installStorageShim(window);
  }
}

afterEach(() => {
  cleanup();
});
