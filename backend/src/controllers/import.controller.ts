// backend/src/controllers/import.controller.ts
import type { Request, Response } from 'express';
import { z } from 'zod';
import type { ProductRepository } from '../repositories/product.repository.js';
import { importProducts, parseProductCsv } from '../services/import.service.js';
import { GRADES, SHOP_CODES, type ApiResponse, type ImportResult } from '../types/index.js';
import { AppError } from '../utils/app-error.js';

const importFieldsSchema = z.object({
  shop: z.enum(SHOP_CODES),
  grade: z.enum(GRADES),
});

export class ImportController {
  constructor(private readonly repo: ProductRepository) {}

  postImport = (req: Request, res: Response): void => {
    const fields = importFieldsSchema.parse(req.body);
    if (!req.file) {
      throw new AppError(400, 'CSV file is required (multipart field "file")');
    }
    const { records, skipped } = parseProductCsv(req.file.buffer.toString('utf-8'));
    if (records.length === 0) {
      throw new AppError(422, 'CSV contains no valid product rows');
    }
    const result = importProducts(
      this.repo,
      fields.shop,
      fields.grade,
      req.file.originalname,
      records,
      skipped,
    );
    const body: ApiResponse<ImportResult> = {
      code: 0,
      message: 'ok',
      data: result,
      timestamp: new Date().toISOString(),
    };
    res.status(201).json(body);
  };
}
