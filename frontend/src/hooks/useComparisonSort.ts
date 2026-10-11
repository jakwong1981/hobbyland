// frontend/src/hooks/useComparisonSort.ts
import { useCallback, useMemo, useState } from 'react';
import type { ComparisonRow, ShopCode, SortDirection, SortKey, SortState } from '../types';

function priceOf(row: ComparisonRow, shop: ShopCode): number | null {
  return row.offers.find((o) => o.shop === shop)?.price ?? null;
}

function compareRows(a: ComparisonRow, b: ComparisonRow, sort: SortState): number {
  const sign = sort.direction === 'asc' ? 1 : -1;

  if (sort.key === 'title') {
    return sign * a.title.localeCompare(b.title, 'zh-Hant');
  }

  const left = priceOf(a, sort.key);
  const right = priceOf(b, sort.key);
  // A shop that does not carry the SKU has no price to rank, so it always trails.
  if (left === null && right === null) return 0;
  if (left === null) return 1;
  if (right === null) return -1;
  return sign * (left - right);
}

export function useComparisonSort(rows: ComparisonRow[]): {
  sorted: ComparisonRow[];
  sort: SortState | null;
  toggleSort: (key: SortKey) => void;
} {
  const [sort, setSort] = useState<SortState | null>(null);

  const sorted = useMemo(
    () => (sort === null ? rows : [...rows].sort((a, b) => compareRows(a, b, sort))),
    [rows, sort],
  );

  const toggleSort = useCallback((key: SortKey) => {
    setSort((prev) => {
      if (prev === null || prev.key !== key) return { key, direction: 'asc' };
      const direction: SortDirection = prev.direction === 'asc' ? 'desc' : 'asc';
      return { key, direction };
    });
  }, []);

  return { sorted, sort, toggleSort };
}
