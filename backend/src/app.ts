// backend/src/app.ts
import express, { type Express } from 'express';
import cors from 'cors';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import type { DatabaseSync } from 'node:sqlite';
import { ProductController } from './controllers/product.controller.js';
import { ImportController } from './controllers/import.controller.js';
import { ScrapeController } from './controllers/scrape.controller.js';
import { PbandaiController } from './controllers/pbandai.controller.js';
import { ScrapeService } from './services/scrape.service.js';
import { createApiRouter } from './routes/index.js';
import { ProductRepository } from './repositories/product.repository.js';
import { PbandaiRepository } from './repositories/pbandai.repository.js';
import { errorMiddleware, notFoundMiddleware, traceIdMiddleware } from './middleware/error.middleware.js';
import { DEFAULT_CORS_ORIGINS } from './config.js';

const FRONTEND_DIST = resolve(import.meta.dirname, '../../frontend/dist');

export function createApp(
  db: DatabaseSync,
  scrapeService: ScrapeService = new ScrapeService(),
  corsOrigins: string = DEFAULT_CORS_ORIGINS,
): Express {
  const repo = new ProductRepository(db);
  const productController = new ProductController(repo);
  const importController = new ImportController(repo);
  const scrapeController = new ScrapeController(scrapeService);
  const pbandaiController = new PbandaiController(new PbandaiRepository(db));

  const app = express();
  app.use(cors({ origin: corsOrigins.split(',').map((o) => o.trim()).filter((o) => o !== '') }));
  app.use(traceIdMiddleware);
  app.use(express.json());
  app.use('/api', createApiRouter(productController, importController, scrapeController, pbandaiController));

  if (existsSync(FRONTEND_DIST)) {
    app.use(express.static(FRONTEND_DIST));
    app.get(/^\/(?!api\/).*/, (_req, res) => {
      res.sendFile(resolve(FRONTEND_DIST, 'index.html'));
    });
  }

  app.use('/api', notFoundMiddleware);
  app.use(errorMiddleware);
  return app;
}
