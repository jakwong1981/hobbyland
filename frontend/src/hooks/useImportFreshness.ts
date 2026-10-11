// frontend/src/hooks/useImportFreshness.ts
import { useQuery } from '@tanstack/react-query';
import { fetchImportFreshness } from '../api/import.api';
import type { Grade, ImportFreshness } from '../types';

export const IMPORT_FRESHNESS_KEY = 'import-freshness';

export function useImportFreshness(grade: Grade) {
  return useQuery<ImportFreshness>({
    queryKey: [IMPORT_FRESHNESS_KEY, grade],
    queryFn: () => fetchImportFreshness(grade),
  });
}
