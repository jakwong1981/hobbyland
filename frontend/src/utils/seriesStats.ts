// frontend/src/utils/seriesStats.ts
import type { ComparisonRow } from '../types';

export interface SeriesCount {
  series: string;
  count: number;
}

// Rows without a classification (series === null) are excluded: they are
// reported through the filter's "未分類" option, not as a series of their own.
export function countBySeries(rows: ComparisonRow[]): SeriesCount[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    if (row.series === null) continue;
    counts.set(row.series, (counts.get(row.series) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([series, count]) => ({ series, count }))
    .sort((a, b) => b.count - a.count || a.series.localeCompare(b.series));
}
