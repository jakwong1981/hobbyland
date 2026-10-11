// frontend/src/hooks/useComparisons.ts
import { useQuery } from '@tanstack/react-query';
import { fetchComparisons, type ComparisonQuery } from '../api/comparison.api';
import type { ComparisonRow } from '../types';

export function useComparisons(query: ComparisonQuery) {
  return useQuery<ComparisonRow[]>({
    queryKey: ['comparisons', query],
    queryFn: () => fetchComparisons(query),
  });
}
