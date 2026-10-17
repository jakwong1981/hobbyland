// frontend/src/api/pbandai.api.ts
import { apiGet } from './client';
import type { PbandaiItem } from '../types';

export function fetchPbandaiItems(q?: string): Promise<PbandaiItem[]> {
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  const qs = params.toString();
  return apiGet<PbandaiItem[]>(`/api/pbandai${qs ? `?${qs}` : ''}`);
}
