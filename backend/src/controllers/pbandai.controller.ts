// backend/src/controllers/pbandai.controller.ts
import type { Request, Response } from 'express';
import { z } from 'zod';
import type { PbandaiRepository } from '../repositories/pbandai.repository.js';
import type { ApiResponse, PbandaiItem } from '../types/index.js';

const pbandaiQuerySchema = z.object({
  q: z.string().trim().max(200).optional(),
});

export class PbandaiController {
  constructor(private readonly repo: PbandaiRepository) {}

  getItems = (req: Request, res: Response): void => {
    const query = pbandaiQuerySchema.parse(req.query);
    const body: ApiResponse<PbandaiItem[]> = {
      code: 0,
      message: 'ok',
      data: this.repo.findAll(query.q || undefined),
      timestamp: new Date().toISOString(),
    };
    res.json(body);
  };
}
