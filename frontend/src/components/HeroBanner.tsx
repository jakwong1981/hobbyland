// frontend/src/components/HeroBanner.tsx
import { useMemo } from 'react';
import { SHOP_CODES, type ComparisonRow, type Grade } from '../types';
import { SHOP_LABEL, SHOP_TONE } from '../shops';
import { summarizeComparisons } from '../utils/comparisonStats';
import { MobileSuitArt } from './MobileSuitArt';
import { ShopLogo } from './ShopLogo';
import { StatTile } from './StatTile';

interface Props {
  rows: ComparisonRow[];
  grade: Grade;
}

export function HeroBanner({ rows, grade }: Props) {
  const summary = useMemo(() => summarizeComparisons(rows), [rows]);

  return (
    <section className="hero" aria-label="格價戰況">
      <MobileSuitArt />
      <div className="hero-body">
        <p className="hero-kicker">
          <span className="hero-kicker-dot" aria-hidden="true" />
          OPERATION // PRICE RECON
        </p>
        <h2 className="hero-title">
          <span className="hero-grade" data-grade={grade}>
            {grade.toUpperCase()}
          </span>
          <span className="faction-copy faction-copy-federation">聯邦補給線 · 搵最平嘅高達</span>
          <span className="faction-copy faction-copy-zeon">自護軍需處 · 為了自護，搵最平！</span>
        </h2>
        <div className="stat-grid">
          <StatTile label="總 SKU" value={summary.total} tone="stat-total" />
          {SHOP_CODES.map((shop) => (
            <StatTile
              key={shop}
              value={summary.cheapestByShop[shop]}
              tone={`stat-shop ${SHOP_TONE[shop]}`}
              label={
                <>
                  <ShopLogo shop={shop} />
                  <span className="stat-shop-name">{SHOP_LABEL[shop]}</span>
                  <span className="stat-shop-suffix">最平</span>
                </>
              }
            />
          ))}
          <StatTile label="單一網店獨家" value={summary.exclusives} tone="stat-exclusive" />
        </div>
      </div>
    </section>
  );
}
