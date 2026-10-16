// backend/tests/config.test.ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { existsSync } from 'node:fs';
import { loadConfig } from '../src/config.js';

vi.mock('node:fs', () => ({
  existsSync: vi.fn(() => false),
}));

const mockExistsSync = vi.mocked(existsSync);

beforeEach(() => {
  mockExistsSync.mockReturnValue(false);
});

describe('loadConfig', () => {
  it('defaults PORT to 8089 and leaves TLS unset when no certificate exists', () => {
    const config = loadConfig({});
    expect(config.PORT).toBe(8089);
    expect(config.TLS_CERT_PATH).toBeUndefined();
    expect(config.TLS_KEY_PATH).toBeUndefined();
  });

  it('falls back to the repo ./certs pair when both files exist', () => {
    mockExistsSync.mockReturnValue(true);
    const config = loadConfig({});
    expect(config.TLS_CERT_PATH).toMatch(/certs\/server\.pem$/);
    expect(config.TLS_KEY_PATH).toMatch(/certs\/server-key\.pem$/);
  });

  it('does not fall back when only one certificate file exists', () => {
    mockExistsSync.mockImplementation((path) => String(path).endsWith('server.pem'));
    const config = loadConfig({});
    expect(config.TLS_CERT_PATH).toBeUndefined();
    expect(config.TLS_KEY_PATH).toBeUndefined();
  });

  it('prefers explicit env paths over the ./certs fallback', () => {
    mockExistsSync.mockReturnValue(true);
    const config = loadConfig({
      TLS_CERT_PATH: '/etc/tls/fullchain.pem',
      TLS_KEY_PATH: '/etc/tls/privkey.pem',
    });
    expect(config.TLS_CERT_PATH).toBe('/etc/tls/fullchain.pem');
    expect(config.TLS_KEY_PATH).toBe('/etc/tls/privkey.pem');
  });

  it('passes a lone explicit TLS path through for index.ts to reject', () => {
    const config = loadConfig({ TLS_CERT_PATH: '/etc/tls/fullchain.pem' });
    expect(config.TLS_CERT_PATH).toBe('/etc/tls/fullchain.pem');
    expect(config.TLS_KEY_PATH).toBeUndefined();
  });

  it('rejects an out-of-range PORT', () => {
    expect(() => loadConfig({ PORT: '70000' })).toThrow();
  });
});
