// frontend/src/api/scrape.api.ts
import { apiGet, apiPost } from './client';
import type { ScrapeJobStatus } from '../types';

export function startScrape(): Promise<ScrapeJobStatus> {
  return apiPost<ScrapeJobStatus>('/api/scrape');
}

export function fetchScrapeStatus(): Promise<ScrapeJobStatus> {
  return apiGet<ScrapeJobStatus>('/api/scrape/status');
}
