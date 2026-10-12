// frontend/src/components/FreshnessBar.tsx
import type { Grade, ImportFreshness } from '../types';
import { SHOP_CODES } from '../types';
import { SHOP_LABEL } from '../shops';

const GRADE_LABEL: Record<Grade, string> = { hg: 'HG', mg: 'MG', rg: 'RG' };

const TIMESTAMP_FORMAT = new Intl.DateTimeFormat('zh-HK', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : TIMESTAMP_FORMAT.format(date);
}

interface Props {
  freshness: ImportFreshness | undefined;
  isLoading: boolean;
}

export function FreshnessBar({ freshness, isLoading }: Props) {
  if (isLoading) {
    return <p className="freshness">最後更新 · 載入中…</p>;
  }
  // Not loading and still undefined means the freshness query failed.
  if (freshness === undefined) {
    return <p className="freshness">最後更新 · 未能載入</p>;
  }
  if (freshness.overall === null) {
    return <p className="freshness">最後更新 · 呢個級別未有匯入紀錄</p>;
  }

  const grade = freshness.grade === null ? null : GRADE_LABEL[freshness.grade];
  return (
    <p className="freshness">
      <span className="freshness-label">最後更新{grade === null ? '' : ` · ${grade}`}</span>
      {SHOP_CODES.map((shop) => {
        const stamp = freshness.byShop[shop];
        return (
          <span key={shop} className="freshness-item">
            <span className="freshness-shop">{SHOP_LABEL[shop]}</span>
            {stamp === null ? (
              <span className="freshness-none">冇紀錄</span>
            ) : (
              <time className="freshness-time" dateTime={stamp}>
                {formatTimestamp(stamp)}
              </time>
            )}
          </span>
        );
      })}
    </p>
  );
}
