// frontend/src/api/comparison.api.ts
import { apiGet } from './client';
import type { ComparisonRow, Grade, ShopCode } from '../types';

export interface ComparisonQuery {
  grade?: Grade;
  q?: string;
  cheaper?: ShopCode;
}

export function fetchComparisons(query: ComparisonQuery): Promise<ComparisonRow[]> {
  const params = new URLSearchParams();
  if (query.grade) params.set('grade', query.grade);
  if (query.q) params.set('q', query.q);
  if (query.cheaper) params.set('cheaper', query.cheaper);
  const qs = params.toString();
  return apiGet<ComparisonRow[]>(`/api/comparisons${qs ? `?${qs}` : ''}`);
}
