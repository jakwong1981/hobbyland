// frontend/src/components/SeriesFilter.tsx
import { useMemo } from 'react';
import type { ComparisonRow, SeriesFilterValue } from '../types';
import { seriesLabel } from '../series';
import { countBySeries } from '../utils/seriesStats';

interface Props {
  value: SeriesFilterValue;
  onChange: (value: SeriesFilterValue) => void;
  rows: ComparisonRow[];
}

export function SeriesFilter({ value, onChange, rows }: Props) {
  const options = useMemo(() => countBySeries(rows), [rows]);
  const unclassified = useMemo(
    () => rows.filter((r) => r.series === null).length,
    [rows],
  );

  return (
    <label className="shop-filter series-filter">
      <span className="shop-filter-label">系列</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="all">全部系列</option>
        {options.map(({ series, count }) => (
          <option key={series} value={series}>
            {seriesLabel(series)} ({count})
          </option>
        ))}
        {unclassified > 0 && (
          <option value="__none__">未分類 ({unclassified})</option>
        )}
      </select>
    </label>
  );
}
