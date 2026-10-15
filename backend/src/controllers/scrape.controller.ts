// backend/src/controllers/scrape.controller.ts
import type { Request, Response } from 'express';
import type { ScrapeService } from '../services/scrape.service.js';
import type { ApiResponse, ScrapeJobStatus } from '../types/index.js';

export class ScrapeController {
  constructor(private readonly scrapeService: ScrapeService) {}

  postScrape = (_req: Request, res: Response): void => {
    const status = this.scrapeService.start();
    const body: ApiResponse<ScrapeJobStatus> = {
      code: 0,
      message: 'ok',
      data: status,
      timestamp: new Date().toISOString(),
    };
    res.status(202).json(body);
  };

  getScrapeStatus = (_req: Request, res: Response): void => {
    const body: ApiResponse<ScrapeJobStatus> = {
      code: 0,
      message: 'ok',
      data: this.scrapeService.getStatus(),
      timestamp: new Date().toISOString(),
    };
    res.json(body);
  };
}
