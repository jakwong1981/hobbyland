// frontend/tests/series-stats.test.ts
import { describe, expect, it } from 'vitest';
import { countBySeries } from '../src/utils/seriesStats';
import { seriesLabel } from '../src/series';
import { buildRow } from './fixtures';

describe('countBySeries', () => {
  it('counts rows per series, sorted by count desc', () => {
    const rows = [
      buildRow({ sku: '1', series: 'zeta' }),
      buildRow({ sku: '2', series: 'zeta' }),
      buildRow({ sku: '3', series: 'seed' }),
    ];

    expect(countBySeries(rows)).toEqual([
      { series: 'zeta', count: 2 },
      { series: 'seed', count: 1 },
    ]);
  });

  it('excludes unclassified rows', () => {
    const rows = [buildRow({ sku: '1', series: null }), buildRow({ sku: '2', series: 'seed' })];

    expect(countBySeries(rows)).toEqual([{ series: 'seed', count: 1 }]);
  });

  it('returns an empty list when nothing is classified', () => {
    expect(countBySeries([buildRow({ series: null })])).toEqual([]);
  });
});

describe('seriesLabel', () => {
  it('maps known ids to their display name', () => {
    expect(seriesLabel('iron_blooded_orphans')).toBe('鐵血的孤兒');
    expect(seriesLabel('unknown')).toBe('無法確定');
  });

  it('falls back to the raw id for an unmapped series and to a dash for null', () => {
    expect(seriesLabel('some_future_series')).toBe('some_future_series');
    expect(seriesLabel(null)).toBe('—');
  });
});
