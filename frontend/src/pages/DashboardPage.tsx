// frontend/src/pages/DashboardPage.tsx
import { useMemo, useState } from 'react';
import { GradeTabs } from '../components/GradeTabs';
import { SearchBar } from '../components/SearchBar';
import { ShopFilter } from '../components/ShopFilter';
import { FreshnessBar } from '../components/FreshnessBar';
import { ComparisonTable } from '../components/ComparisonTable';
import { ComparisonGallery } from '../components/ComparisonGallery';
import { HeroBanner } from '../components/HeroBanner';
import { KitShowcase } from '../components/KitShowcase';
import { ViewToggle } from '../components/ViewToggle';
import { useComparisons } from '../hooks/useComparisons';
import { useImportFreshness } from '../hooks/useImportFreshness';
import type { ComparisonRow, DashboardView, Grade, ShopFilterValue } from '../types';

const NO_ROWS: ComparisonRow[] = [];

export function DashboardPage() {
  const [grade, setGrade] = useState<Grade>('hg');
  const [q, setQ] = useState('');
  const [shop, setShop] = useState<ShopFilterValue>('all');
  const [view, setView] = useState<DashboardView>('table');
  const { data, isLoading, isError, error } = useComparisons({
    grade,
    ...(q.trim() ? { q: q.trim() } : {}),
  });
  const { data: freshness, isLoading: isFreshnessLoading } = useImportFreshness(grade);
  const rows = data ?? NO_ROWS;

  const visible = useMemo(
    () => (shop === 'all' ? rows : rows.filter((r) => r.offers.some((o) => o.shop === shop))),
    [rows, shop],
  );

  return (
    <section className="dashboard">
      <HeroBanner rows={rows} grade={grade} />
      <KitShowcase rows={rows} />
      <div className="toolbar">
        <GradeTabs value={grade} onChange={setGrade} />
        <ShopFilter value={shop} onChange={setShop} />
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
            {shop === 'all'
              ? `${data.length} 個 SKU`
              : `${visible.length} / ${data.length} 個 SKU`}
          </p>
          {visible.length === 0 && data.length > 0 ? (
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
