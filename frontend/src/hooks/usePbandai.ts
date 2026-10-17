// frontend/src/hooks/usePbandai.ts
import { useQuery } from '@tanstack/react-query';
import { fetchPbandaiItems } from '../api/pbandai.api';
import type { PbandaiItem } from '../types';

export function usePbandai() {
  return useQuery<PbandaiItem[]>({
    queryKey: ['pbandai'],
    queryFn: () => fetchPbandaiItems(),
  });
}
