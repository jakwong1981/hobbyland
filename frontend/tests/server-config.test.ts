// frontend/tests/server-config.test.ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  API_BASE_STORAGE_KEY,
  clearApiBase,
  getApiBase,
  normalizeApiBase,
  setApiBase,
} from '../src/api/serverConfig';

afterEach(() => {
  vi.unstubAllEnvs();
  window.localStorage.clear();
});

describe('normalizeApiBase', () => {
  it('strips trailing slashes and keeps the origin', () => {
    expect(normalizeApiBase('https://localhost:8089/')).toBe('https://localhost:8089');
    expect(normalizeApiBase(' http://192.168.1.5:8089// ')).toBe('http://192.168.1.5:8089');
  });

  it('accepts an empty string as same-origin', () => {
    expect(normalizeApiBase('')).toBe('');
  });

  it('rejects non-http schemes, paths and junk', () => {
    expect(() => normalizeApiBase('ftp://host')).toThrow();
    expect(() => normalizeApiBase('https://host:8089/api')).toThrow();
    expect(() => normalizeApiBase('not a url')).toThrow();
  });
});

describe('getApiBase precedence', () => {
  it('prefers the persisted override over the build-time env', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://build.example');
    window.localStorage.setItem(API_BASE_STORAGE_KEY, 'https://override.example');

    expect(getApiBase()).toBe('https://override.example');
  });

  it('falls back to the build-time env, trailing slash stripped', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://build.example/');

    expect(getApiBase()).toBe('https://build.example');
  });

  it('falls back to same-origin when nothing is configured', () => {
    expect(getApiBase()).toBe('');
  });
});

describe('setApiBase / clearApiBase', () => {
  it('persists the normalized override', () => {
    expect(setApiBase('https://deploy.example:8089/')).toBe('https://deploy.example:8089');
    expect(window.localStorage.getItem(API_BASE_STORAGE_KEY)).toBe('https://deploy.example:8089');
    expect(getApiBase()).toBe('https://deploy.example:8089');
  });

  it('throws and does not persist an invalid URL', () => {
    expect(() => setApiBase('javascript:alert(1)')).toThrow();
    expect(window.localStorage.getItem(API_BASE_STORAGE_KEY)).toBeNull();
  });

  it('clearApiBase restores the build-time default', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://build.example');
    setApiBase('https://override.example');

    expect(clearApiBase()).toBe('https://build.example');
    expect(window.localStorage.getItem(API_BASE_STORAGE_KEY)).toBeNull();
  });

  it('keeps the override effective for the session when persistence fails', () => {
    const setItemSpy = vi.spyOn(window.localStorage, 'setItem');
    setItemSpy.mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    try {
      expect(setApiBase('https://session.example')).toBe('https://session.example');
      expect(getApiBase()).toBe('https://session.example');
    } finally {
      setItemSpy.mockRestore();
    }
  });
});
