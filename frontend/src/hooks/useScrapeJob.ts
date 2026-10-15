// frontend/src/hooks/useScrapeJob.ts
import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchScrapeStatus, startScrape } from '../api/scrape.api';
import { IMPORT_FRESHNESS_KEY } from './useImportFreshness';

export const SCRAPE_STATUS_KEY = 'scrape-status';

const POLL_INTERVAL_MS = 2000;

export function useScrapeJob() {
  const queryClient = useQueryClient();
  const statusQuery = useQuery({
    queryKey: [SCRAPE_STATUS_KEY],
    queryFn: fetchScrapeStatus,
    refetchInterval: (query) =>
      query.state.data?.state === 'running' ? POLL_INTERVAL_MS : false,
  });

  const startMutation = useMutation({
    mutationFn: startScrape,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [SCRAPE_STATUS_KEY] });
    },
  });

  const prevState = useRef(statusQuery.data?.state);
  useEffect(() => {
    const state = statusQuery.data?.state;
    if (prevState.current === 'running' && (state === 'completed' || state === 'failed')) {
      void queryClient.invalidateQueries({ queryKey: ['comparisons'] });
      void queryClient.invalidateQueries({ queryKey: [IMPORT_FRESHNESS_KEY] });
    }
    prevState.current = state;
  }, [statusQuery.data?.state, queryClient]);

  const state = statusQuery.data?.state ?? 'idle';
  return {
    running: state === 'running' || startMutation.isPending,
    failed: state === 'failed',
    start: startMutation.mutate,
    startError: startMutation.error,
  };
}
