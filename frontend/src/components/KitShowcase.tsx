// frontend/src/components/KitShowcase.tsx
import { memo, useMemo, useState } from 'react';
import type { ComparisonRow } from '../types';
import { SHOP_LABEL } from '../shops';
import { selectShowcaseKits, type ShowcaseKit } from '../utils/showcase';
import { ShopLogo } from './ShopLogo';

interface ItemProps {
  kit: ShowcaseKit;
  isClone: boolean;
  onImageError: (key: string) => void;
}

function ShowcaseItem({ kit, isClone, onImageError }: ItemProps) {
  const price = `HK$${kit.bestOffer.price.toFixed(0)}`;
  return (
    <li className={isClone ? 'showcase-item showcase-clone' : 'showcase-item'} aria-hidden={isClone || undefined}>
      <a
        href={kit.bestOffer.url}
        target="_blank"
        rel="noreferrer"
        className="showcase-link"
        title={kit.title}
        aria-label={`${kit.title} — ${SHOP_LABEL[kit.bestOffer.shop]} ${price}`}
        tabIndex={isClone ? -1 : undefined}
      >
        <img
          src={kit.imageUrl}
          alt=""
          // Matches the square .showcase-link box (132px, 156px on >=720px).
          width={132}
          height={132}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => onImageError(kit.key)}
        />
        <span className="showcase-price">
          <ShopLogo shop={kit.bestOffer.shop} />
          {price}
        </span>
      </a>
    </li>
  );
}

// The list is rendered twice so a translateX(-50%) loop scrolls seamlessly; the
// clone is hidden from assistive tech and the tab order.
export const KitShowcase = memo(function KitShowcase({ rows }: { rows: ComparisonRow[] }) {
  const [failed, setFailed] = useState<ReadonlySet<string>>(new Set());
  const kits = useMemo(
    () => selectShowcaseKits(rows).filter((kit) => !failed.has(kit.key)),
    [rows, failed],
  );

  if (kits.length === 0) return null;

  const markFailed = (key: string) => setFailed((prev) => new Set(prev).add(key));

  return (
    <section className="showcase" aria-label="精選模型">
      <div className="showcase-viewport">
        <ul className="showcase-track" style={{ animationDuration: `${kits.length * 4}s` }}>
          {kits.map((kit) => (
            <ShowcaseItem key={kit.key} kit={kit} isClone={false} onImageError={markFailed} />
          ))}
          {kits.map((kit) => (
            <ShowcaseItem key={`clone-${kit.key}`} kit={kit} isClone onImageError={markFailed} />
          ))}
        </ul>
      </div>
    </section>
  );
});
