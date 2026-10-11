// frontend/src/pages/DashboardPage.tsx
import { useMemo, useState } from 'react';
import { GradeTabs } from '../components/GradeTabs';
import { SearchBar } from '../components/SearchBar';
import { ShopFilter } from '../components/ShopFilter';
import { FreshnessBar } from '../components/FreshnessBar';
import { ComparisonTable } from '../components/ComparisonTable';
import { useComparisons } from '../hooks/useComparisons';
import { useImportFreshness } from '../hooks/useImportFreshness';
import type { Grade, ShopFilterValue } from '../types';

export function DashboardPage() {
  const [grade, setGrade] = useState<Grade>('hg');
  const [q, setQ] = useState('');
  const [shop, setShop] = useState<ShopFilterValue>('all');
  const { data, isLoading, isError, error } = useComparisons({
    grade,
    ...(q.trim() ? { q: q.trim() } : {}),
  });
  const { data: freshness, isLoading: isFreshnessLoading } = useImportFreshness(grade);

  const visible = useMemo(() => {
    const rows = data ?? [];
    return shop === 'all' ? rows : rows.filter((r) => r.offers.some((o) => o.shop === shop));
  }, [data, shop]);

  return (
    <section>
      <div className="toolbar">
        <GradeTabs value={grade} onChange={setGrade} />
        <ShopFilter value={shop} onChange={setShop} />
        <SearchBar value={q} onChange={setQ} />
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
          ) : (
            <ComparisonTable rows={visible} />
          )}
        </>
      )}
    </section>
  );
}
