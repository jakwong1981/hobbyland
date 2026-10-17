// frontend/src/pages/PbandaiPage.tsx
import { useMemo, useState } from 'react';
import { SearchBar } from '../components/SearchBar';
import { PbandaiGallery } from '../components/PbandaiGallery';
import { usePbandai } from '../hooks/usePbandai';
import pbandaiHeroArt from '../assets/pbandai-hero.jpg';
import type { PbandaiItem } from '../types';

const NO_ITEMS: PbandaiItem[] = [];
const ALL_STATUSES = 'all';

const TIMESTAMP_FORMAT = new Intl.DateTimeFormat('zh-HK', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

function lastUpdated(items: PbandaiItem[]): string | null {
  // ISO-8601 timestamps sort lexicographically in chronological order.
  const latest = items.map((i) => i.importedAt).sort().at(-1);
  if (latest === undefined) return null;
  const date = new Date(latest);
  return Number.isNaN(date.getTime()) ? latest : TIMESTAMP_FORMAT.format(date);
}

export function PbandaiPage() {
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<string>(ALL_STATUSES);
  const { data, isLoading, isError, error } = usePbandai();
  const items = data ?? NO_ITEMS;

  // Chips derive from the unfiltered snapshot so filtering never shrinks them.
  const statuses = useMemo(
    () => [...new Set(items.map((i) => i.status).filter((s): s is string => s !== null))],
    [items],
  );

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return items.filter(
      (i) =>
        (status === ALL_STATUSES || i.status === status) &&
        (needle === '' ||
          i.name.toLowerCase().includes(needle) ||
          (i.tcName ?? '').toLowerCase().includes(needle)),
    );
  }, [items, q, status]);

  const filtering = q.trim() !== '' || status !== ALL_STATUSES;

  return (
    <section className="dashboard pbandai-page">
      <div className="pbandai-hero">
        <span className="pbandai-mark" aria-hidden="true">
          PB
        </span>
        <div className="pbandai-hero-text">
          <h2>P-Bandai HK 最新預訂</h2>
          <p className="pbandai-hero-sub">香港官方網店一覽 · 只作展示，唔參與格價</p>
        </div>
        {/* Decorative booth shot; the heading already names the page. */}
        <img className="pbandai-hero-art" src={pbandaiHeroArt} alt="" decoding="async" />
      </div>
      <div className="toolbar">
        <SearchBar value={q} onChange={setQ} />
        {statuses.length > 0 && (
          <div className="status-chips" role="group" aria-label="狀態篩選">
            <button
              type="button"
              className={`status-chip${status === ALL_STATUSES ? ' active' : ''}`}
              onClick={() => setStatus(ALL_STATUSES)}
            >
              全部
            </button>
            {statuses.map((s) => (
              <button
                key={s}
                type="button"
                className={`status-chip${status === s ? ' active' : ''}`}
                onClick={() => setStatus(status === s ? ALL_STATUSES : s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="status-row">
        {isLoading && <p className="status">載入中…</p>}
        {isError && <p className="status error">載入失敗：{error.message}</p>}
        {data && data.length > 0 && (
          <p className="freshness">
            <span className="live-dot" aria-hidden="true" />
            最後更新 · {lastUpdated(data)}
          </p>
        )}
      </div>
      {data && data.length > 0 && (
        <>
          <p className="result-count">
            {filtering ? `${visible.length} / ${items.length} 件` : `${items.length} 件`}
          </p>
          {visible.length === 0 ? (
            <p className="empty-state">呢個篩選冇匹配嘅商品。</p>
          ) : (
            <PbandaiGallery items={visible} />
          )}
        </>
      )}
      {data && data.length === 0 && (
        <p className="empty-state">冇資料 — 請先撳更新或匯入 pbandai_products.csv。</p>
      )}
    </section>
  );
}
