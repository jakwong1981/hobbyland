// backend/src/config.ts
import { resolve } from 'node:path';
import { z } from 'zod';

const DEFAULT_DATA_DIR = resolve(import.meta.dirname, '../../data');

const envSchema = z.object({
  PORT: z.coerce.number().int().min(1).max(65535).default(8080),
  DATA_DIR: z.string().min(1).default(DEFAULT_DATA_DIR),
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  CSV_DIR: z.string().optional(),
});

export type AppConfig = z.infer<typeof envSchema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  return envSchema.parse(env);
}
