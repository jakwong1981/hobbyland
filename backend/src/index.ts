// backend/src/index.ts
import { loadConfig } from './config.js';
import { createDatabase } from './db/client.js';
import { createApp } from './app.js';
import { logger } from './utils/logger.js';

const config = loadConfig();
const db = createDatabase(config.DATA_DIR);
const app = createApp(db);

app.listen(config.PORT, () => {
  logger.info({ port: config.PORT, dataDir: config.DATA_DIR, env: config.NODE_ENV }, 'server started');
});
