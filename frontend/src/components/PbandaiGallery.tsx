// frontend/src/components/PbandaiGallery.tsx
import type { PbandaiItem } from '../types';
import { useProgressiveRows } from '../hooks/useProgressiveRows';
import { PbandaiCard } from './PbandaiCard';

export function PbandaiGallery({ items }: { items: PbandaiItem[] }) {
  const { shown, sentinelRef, hasMore, remaining } = useProgressiveRows(items);

  if (items.length === 0) {
    return <p className="empty-state">冇資料 — 請先撳更新或匯入 pbandai_products.csv。</p>;
  }
  return (
    <>
      <div className="gallery-grid pbandai-grid">
        {shown.map((item, index) => (
          <PbandaiCard key={item.id} item={item} index={index} />
        ))}
      </div>
      <div ref={sentinelRef} aria-hidden="true" />
      {hasMore && <p className="status">下拉載入其餘 {remaining} 件…</p>}
    </>
  );
}
