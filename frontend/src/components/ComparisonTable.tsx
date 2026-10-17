// frontend/src/components/ComparisonTable.tsx
import type { CSSProperties } from 'react';
import {
  type ComparisonRow,
  type Offer,
  type ShopCode,
  type SortKey,
  type SortState,
} from '../types';
import { SHOP_LABEL, SHOP_TONE, DASHBOARD_SHOPS } from '../shops';
import { seriesLabel } from '../series';
import { useComparisonSort } from '../hooks/useComparisonSort';
import { useProgressiveRows } from '../hooks/useProgressiveRows';
import { CheaperBadge } from './CheaperBadge';
import { ProductImage } from './ProductImage';
import { ShopLogo } from './ShopLogo';
import { skuLabel } from '../utils/skuLabel';

const STAGGER_CAP = 20;

const SORT_GLYPH = { none: '◇', asc: '▲', desc: '▼' } as const;

function activeDirection(sort: SortState | null, key: SortKey): 'asc' | 'desc' | 'none' {
  if (sort === null || sort.key !== key) return 'none';
  return sort.direction;
}

function ariaSort(direction: 'asc' | 'desc' | 'none'): 'ascending' | 'descending' | 'none' {
  if (direction === 'asc') return 'ascending';
  return direction === 'desc' ? 'descending' : 'none';
}

interface SortableHeaderProps {
  label: string;
  shop?: ShopCode;
  code: string;
  sortKey: SortKey;
  sort: SortState | null;
  onSort: (key: SortKey) => void;
  className: string;
}

function SortableHeader({ label, shop, code, sortKey, sort, onSort, className }: SortableHeaderProps) {
  const direction = activeDirection(sort, sortKey);
  return (
    <th scope="col" className={className} aria-sort={ariaSort(direction)}>
      <button type="button" className="sort-btn" onClick={() => onSort(sortKey)}>
        {shop && <ShopLogo shop={shop} />}
        <span className="sort-text">
          <span className="sort-label">{label}</span>
          <span className="th-code">{code}</span>
        </span>
        <span className="sort-indicator" aria-hidden="true">
          {SORT_GLYPH[direction]}
        </span>
      </button>
    </th>
  );
}

function OfferCell({ offer, shop }: { offer: Offer | undefined; shop: ShopCode }) {
  const tone = SHOP_TONE[shop];
  if (!offer) return <td className={`price-cell empty ${tone}`}>—</td>;
  return (
    <td className={`price-cell ${tone}`}>
      <a href={offer.url} target="_blank" rel="noreferrer" className="price-link">
        HK${offer.price.toFixed(0)}
        <span className="external-icon" aria-hidden="true">↗</span>
      </a>
      {offer.regularPrice !== null && offer.regularPrice > offer.price && (
        <span className="regular-price">HK${offer.regularPrice.toFixed(0)}</span>
      )}
      <span className={offer.sellType === '預訂' ? 'stock-note preorder' : 'stock-note'}>
        {offer.stock ? `存貨 ${offer.stock}` : (offer.sellType ?? '')}
      </span>
    </td>
  );
}

function findOffer(row: ComparisonRow, shop: ShopCode): Offer | undefined {
  return row.offers.find((o) => o.shop === shop);
}

// The verdict rides under the thumbnail instead of owning a column: it is a
// property of the kit, not a comparable field, and a whole column of one-chip
// cells cost more width than it carried meaning.
function TitleCell({ row }: { row: ComparisonRow }) {
  return (
    <td className="title-cell">
      <div className="title-inner">
        <div className="thumb-stack">
          <ProductImage row={row} className="table-thumb" />
          <CheaperBadge cheapestShop={row.cheapestShop} exclusiveShop={row.exclusiveShop} />
        </div>
        <div className="product-info">
          <span className="product-title">{row.title}</span>
          <span className="sku">{skuLabel(row.sku)}</span>
          <span className="series-tag" data-series={row.series ?? 'none'}>
            {seriesLabel(row.series)}
          </span>
        </div>
      </div>
    </td>
  );
}

export function ComparisonTable({ rows }: { rows: ComparisonRow[] }) {
  const { sorted, sort, toggleSort } = useComparisonSort(rows);
  const { shown, sentinelRef, hasMore, remaining } = useProgressiveRows(sorted);

  if (rows.length === 0) {
    return <p className="empty-state">冇資料 — 請先匯入 CSV。</p>;
  }

  return (
    <div className="table-wrapper">
      <table className="comparison-table">
        <thead>
          <tr>
            <SortableHeader
              label="產品"
              code="UNIT / SKU"
              sortKey="title"
              sort={sort}
              onSort={toggleSort}
              className="title-head"
            />
            {DASHBOARD_SHOPS.map((shop, index) => (
              <SortableHeader
                key={shop}
                label={SHOP_LABEL[shop]}
                shop={shop}
                code={`SHOP-${String(index + 1).padStart(2, '0')} · 價錢`}
                sortKey={shop}
                sort={sort}
                onSort={toggleSort}
                className={`shop-head ${SHOP_TONE[shop]}`}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, index) => (
            <tr
              key={`${row.grade}-${row.sku}`}
              style={{ '--i': Math.min(index, STAGGER_CAP) } as CSSProperties}
            >
              <TitleCell row={row} />
              {DASHBOARD_SHOPS.map((shop) => (
                <OfferCell key={shop} offer={findOffer(row, shop)} shop={shop} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div ref={sentinelRef} aria-hidden="true" />
      {hasMore && <p className="status">下拉載入其餘 {remaining} 個 SKU…</p>}
    </div>
  );
}
