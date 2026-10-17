// frontend/src/components/PbandaiCard.tsx
import { memo, useState, type CSSProperties } from 'react';
import type { PbandaiItem } from '../types';

interface Props {
  item: PbandaiItem;
  index: number;
}

const STAGGER_CAP = 20;

function CardImage({ item }: { item: PbandaiItem }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  if (item.imageUrl !== null && item.imageUrl !== failedSrc) {
    return (
      <img
        className="gallery-image pbandai-image"
        src={item.imageUrl}
        alt=""
        // Square media box mirrors the gallery grid; declaring the size lets
        // the browser reserve the box before the image loads.
        width={220}
        height={220}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setFailedSrc(item.imageUrl)}
      />
    );
  }
  return (
    <span className="gallery-image pbandai-image pbandai-thumb-fallback" aria-hidden="true">
      PB
    </span>
  );
}

export const PbandaiCard = memo(function PbandaiCard({ item, index }: Props) {
  const style = { '--i': Math.min(index, STAGGER_CAP) } as CSSProperties;
  return (
    <article className="gallery-card pbandai-card" style={style}>
      <a href={item.url} target="_blank" rel="noreferrer" className="pbandai-link">
        <div className="gallery-media">
          <CardImage item={item} />
          {item.status !== null && <span className="pbandai-status">{item.status}</span>}
        </div>
        <div className="gallery-body">
          <h3 className="product-title">{item.tcName ?? item.name}</h3>
          {item.tcName !== null && <p className="pbandai-subtitle">{item.name}</p>}
          {item.price !== null && (
            <span className="pbandai-price">HK${item.price.toFixed(0)}</span>
          )}
        </div>
      </a>
    </article>
  );
});
