// frontend/src/components/ComparisonGallery.tsx
import { memo, type CSSProperties } from 'react';
import { SHOP_CODES, type ComparisonRow, type ShopCode } from '../types';
import { SHOP_LABEL, SHOP_TONE } from '../shops';
import { CheaperBadge } from './CheaperBadge';
import { GradeEmblem } from './GradeEmblem';
import { ProductImage } from './ProductImage';
import { ShopLogo } from './ShopLogo';
import { skuLabel } from '../utils/skuLabel';

const STAGGER_CAP = 20;

function OfferLine({ row, shop }: { row: ComparisonRow; shop: ShopCode }) {
  const offer = row.offers.find((o) => o.shop === shop);
  const isWinner = row.exclusiveShop === null && row.cheapestShop === shop;
  return (
    <li className={`gallery-offer ${SHOP_TONE[shop]}${isWinner ? ' winner' : ''}`}>
      <ShopLogo shop={shop} />
      <span className="gallery-offer-shop">{SHOP_LABEL[shop]}</span>
      {offer ? (
        <a href={offer.url} target="_blank" rel="noreferrer" className="gallery-offer-price">
          HK${offer.price.toFixed(0)}
        </a>
      ) : (
        <span className="gallery-offer-price empty">—</span>
      )}
    </li>
  );
}

const GalleryCard = memo(function GalleryCard({ row, index }: { row: ComparisonRow; index: number }) {
  const style = { '--i': Math.min(index, STAGGER_CAP) } as CSSProperties;
  return (
    <article className="gallery-card" style={style}>
      <div className="gallery-media">
        <ProductImage row={row} className="gallery-image" />
        <span className="gallery-grade" data-grade={row.grade}>
          <GradeEmblem grade={row.grade} />
        </span>
      </div>
      <div className="gallery-body">
        <h3 className="product-title">{row.title}</h3>
        <span className="sku">{skuLabel(row.sku)}</span>
        <ul className="gallery-offers">
          {SHOP_CODES.map((shop) => (
            <OfferLine key={shop} row={row} shop={shop} />
          ))}
        </ul>
        <CheaperBadge cheapestShop={row.cheapestShop} exclusiveShop={row.exclusiveShop} />
      </div>
    </article>
  );
});

export function ComparisonGallery({ rows }: { rows: ComparisonRow[] }) {
  if (rows.length === 0) {
    return <p className="empty-state">冇資料 — 請先匯入 CSV。</p>;
  }
  return (
    <div className="gallery-grid">
      {rows.map((row, index) => (
        <GalleryCard key={`${row.grade}-${row.sku}`} row={row} index={index} />
      ))}
    </div>
  );
}
