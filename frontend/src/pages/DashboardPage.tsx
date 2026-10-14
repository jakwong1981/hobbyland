// frontend/src/pages/DashboardPage.tsx
import { useMemo, useState } from 'react';
import { GradeTabs } from '../components/GradeTabs';
import { SearchBar } from '../components/SearchBar';
import { ShopFilter } from '../components/ShopFilter';
import { SeriesFilter } from '../components/SeriesFilter';
import { FreshnessBar } from '../components/FreshnessBar';
import { ComparisonTable } from '../components/ComparisonTable';
import { ComparisonGallery } from '../components/ComparisonGallery';
import { HeroBanner } from '../components/HeroBanner';
import { KitShowcase } from '../components/KitShowcase';
import { ViewToggle } from '../components/ViewToggle';
import { useComparisons } from '../hooks/useComparisons';
import { useImportFreshness } from '../hooks/useImportFreshness';
import type { ComparisonRow, DashboardView, Grade, SeriesFilterValue, ShopFilterValue } from '../types';
import { countBySeries } from '../utils/seriesStats';
import { withoutShop } from '../utils/withoutShop';
import { seriesLabel } from '../series';

const NO_ROWS: ComparisonRow[] = [];

export function DashboardPage() {
  const [grade, setGrade] = useState<Grade>('hg');
  const [q, setQ] = useState('');
  const [shop, setShop] = useState<ShopFilterValue>('all');
  const [series, setSeries] = useState<SeriesFilterValue>('all');
  const [view, setView] = useState<DashboardView>('table');
  const { data, isLoading, isError, error } = useComparisons({
    grade,
    ...(q.trim() ? { q: q.trim() } : {}),
  });
  const { data: freshness, isLoading: isFreshnessLoading } = useImportFreshness(grade);
  const rows = useMemo(() => withoutShop(data ?? NO_ROWS, 'hobbydigi'), [data]);

  const visible = useMemo(
    () =>
      rows.filter(
        (r) =>
          (shop === 'all' || r.offers.some((o) => o.shop === shop)) &&
          (series === 'all' ||
            (series === '__none__' ? r.series === null : r.series === series)),
      ),
    [rows, shop, series],
  );
  const seriesStats = useMemo(() => countBySeries(visible), [visible]);
  const filtering = shop !== 'all' || series !== 'all';

  return (
    <section className="dashboard">
      <HeroBanner rows={rows} grade={grade} />
      <KitShowcase rows={rows} />
      <div className="toolbar">
        <GradeTabs value={grade} onChange={setGrade} />
        <ShopFilter value={shop} onChange={setShop} />
        <SeriesFilter value={series} onChange={setSeries} rows={rows} />
        <SearchBar value={q} onChange={setQ} />
        <ViewToggle value={view} onChange={setView} />
      </div>
      <div className="status-row">
        {isLoading && <p className="status">載入中…</p>}
        {isError && <p className="status error">載入失敗：{error.message}</p>}
        <FreshnessBar freshness={freshness} isLoading={isFreshnessLoading} />
      </div>
      {data && (
        <>
          <p className="result-count">
            {filtering
              ? `${visible.length} / ${rows.length} 個 SKU`
              : `${rows.length} 個 SKU`}
          </p>
          {seriesStats.length > 0 && (
            <ul className="series-stats" aria-label="系列統計">
              {seriesStats.map(({ series: id, count }) => (
                <li key={id} className="series-stat">
                  <button
                    type="button"
                    className={`series-stat-btn${series === id ? ' active' : ''}`}
                    onClick={() => setSeries(series === id ? 'all' : id)}
                  >
                    <span className="series-stat-name">{seriesLabel(id)}</span>
                    <span className="series-stat-count">{count}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {visible.length === 0 && rows.length > 0 ? (
            <p className="empty-state">呢個舖頭篩選冇匹配嘅 SKU。</p>
          ) : view === 'table' ? (
            <ComparisonTable rows={visible} />
          ) : (
            <ComparisonGallery rows={visible} />
          )}
        </>
      )}
    </section>
  );
}
