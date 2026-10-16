// backend/src/config.ts
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { z } from 'zod';

const DEFAULT_DATA_DIR = resolve(import.meta.dirname, '../../data');
const DEFAULT_TLS_CERT_PATH = resolve(import.meta.dirname, '../../certs/server.pem');
const DEFAULT_TLS_KEY_PATH = resolve(import.meta.dirname, '../../certs/server-key.pem');
export const DEFAULT_CORS_ORIGINS = 'capacitor://localhost,https://localhost,http://localhost';

const envSchema = z.object({
  PORT: z.coerce.number().int().min(1).max(65535).default(8089),
  DATA_DIR: z.string().min(1).default(DEFAULT_DATA_DIR),
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  CSV_DIR: z.string().optional(),
  // Comma-separated origins allowed to call the API cross-origin. Defaults cover
  // the Capacitor WebView origins (capacitor://localhost on iOS, https://localhost on Android).
  CORS_ORIGINS: z.string().default(DEFAULT_CORS_ORIGINS),
  TLS_CERT_PATH: z.string().min(1).optional(),
  TLS_KEY_PATH: z.string().min(1).optional(),
});

export type AppConfig = z.infer<typeof envSchema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  const config = envSchema.parse(env);
  // Fall back to the repo's ./certs directory (populated by scripts/generate-cert.sh)
  // so `pnpm dev` serves HTTPS without extra env setup once a certificate exists.
  if (!config.TLS_CERT_PATH && !config.TLS_KEY_PATH
    && existsSync(DEFAULT_TLS_CERT_PATH) && existsSync(DEFAULT_TLS_KEY_PATH)) {
    config.TLS_CERT_PATH = DEFAULT_TLS_CERT_PATH;
    config.TLS_KEY_PATH = DEFAULT_TLS_KEY_PATH;
  }
  return config;
}
