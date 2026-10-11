// backend/src/routes/index.ts
import { Router } from 'express';
import multer from 'multer';
import type { ProductController } from '../controllers/product.controller.js';
import type { ImportController } from '../controllers/import.controller.js';

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
});

export function createApiRouter(
  productController: ProductController,
  importController: ImportController,
): Router {
  const router = Router();
  router.get('/comparisons', productController.getComparisons);
  router.get('/products', productController.getProducts);
  router.get('/imports/freshness', productController.getImportFreshness);
  router.get('/imports', productController.getImports);
  router.post('/import', upload.single('file'), importController.postImport);
  return router;
}
