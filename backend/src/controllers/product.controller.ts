// backend/src/controllers/product.controller.ts
import type { Request, Response } from 'express';
import { z } from 'zod';
import type { ProductRepository } from '../repositories/product.repository.js';
import { buildComparisons } from '../services/comparison.service.js';
import { buildFreshness } from '../services/import.service.js';
import type {
  ApiResponse,
  ComparisonRow,
  ImportBatchDto,
  ImportFreshness,
  ProductRow,
} from '../types/index.js';

const comparisonQuerySchema = z.object({
  grade: z.enum(['hg', 'mg', 'rg']).optional(),
  q: z.string().trim().max(200).optional(),
  cheaper: z.enum(['hobbyland', 'animes-pro']).optional(),
});

const freshnessQuerySchema = z.object({
  grade: z.enum(['hg', 'mg', 'rg']).optional(),
});

const productQuerySchema = z.object({
  shop: z.enum(['hobbyland', 'animes-pro']).optional(),
  grade: z.enum(['hg', 'mg', 'rg']).optional(),
  q: z.string().trim().max(200).optional(),
});

function ok<T>(res: Response, data: T): void {
  const body: ApiResponse<T> = {
    code: 0,
    message: 'ok',
    data,
    timestamp: new Date().toISOString(),
  };
  res.json(body);
}

export class ProductController {
  constructor(private readonly repo: ProductRepository) {}

  getComparisons = (req: Request, res: Response): void => {
    const query = comparisonQuerySchema.parse(req.query);
    const filters = {
      ...(query.grade ? { grade: query.grade } : {}),
      ...(query.q ? { q: query.q } : {}),
    };
    const products = this.repo.findProducts(filters);
    let rows = buildComparisons(products);
    if (query.cheaper) {
      rows = rows.filter((r) => r.cheapestShop === query.cheaper);
    }
    ok<ComparisonRow[]>(res, rows);
  };

  getProducts = (req: Request, res: Response): void => {
    const query = productQuerySchema.parse(req.query);
    const filters = {
      ...(query.shop ? { shop: query.shop } : {}),
      ...(query.grade ? { grade: query.grade } : {}),
      ...(query.q ? { q: query.q } : {}),
    };
    ok<ProductRow[]>(res, this.repo.findProducts(filters));
  };

  getImports = (_req: Request, res: Response): void => {
    ok<ImportBatchDto[]>(res, this.repo.listBatches(20));
  };

  getImportFreshness = (req: Request, res: Response): void => {
    const query = freshnessQuerySchema.parse(req.query);
    const rows = this.repo.findLatestImportPerShop(query.grade);
    ok<ImportFreshness>(res, buildFreshness(rows, query.grade ?? null));
  };
}
