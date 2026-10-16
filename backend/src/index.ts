// backend/src/index.ts
import { readFileSync } from 'node:fs';
import https from 'node:https';
import { loadConfig } from './config.js';
import { createDatabase } from './db/client.js';
import { createApp } from './app.js';
import { logger } from './utils/logger.js';

const config = loadConfig();
const db = createDatabase(config.DATA_DIR);
const app = createApp(db);

const tlsConfigured = Boolean(config.TLS_CERT_PATH) || Boolean(config.TLS_KEY_PATH);

if (tlsConfigured) {
  if (!config.TLS_CERT_PATH || !config.TLS_KEY_PATH) {
    throw new Error('TLS_CERT_PATH and TLS_KEY_PATH must be set together');
  }
  const options = {
    cert: readFileSync(config.TLS_CERT_PATH),
    key: readFileSync(config.TLS_KEY_PATH),
  };
  https.createServer(options, app).listen(config.PORT, () => {
    logger.info({ port: config.PORT, dataDir: config.DATA_DIR, env: config.NODE_ENV, tls: true }, 'server started');
  });
} else {
  app.listen(config.PORT, () => {
    logger.info({ port: config.PORT, dataDir: config.DATA_DIR, env: config.NODE_ENV, tls: false }, 'server started');
  });
}
