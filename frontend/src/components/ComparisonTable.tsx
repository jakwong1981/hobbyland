// frontend/src/components/ComparisonTable.tsx
import { useState } from 'react';
import {
  SHOP_CODES,
  type ComparisonRow,
  type Offer,
  type ShopCode,
  type SortKey,
  type SortState,
} from '../types';
import { SHOP_LABEL, SHOP_TONE } from '../shops';
import { useComparisonSort } from '../hooks/useComparisonSort';
import { CheaperBadge } from './CheaperBadge';

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
  code: string;
  sortKey: SortKey;
  sort: SortState | null;
  onSort: (key: SortKey) => void;
  className: string;
}

function SortableHeader({ label, code, sortKey, sort, onSort, className }: SortableHeaderProps) {
  const direction = activeDirection(sort, sortKey);
  return (
    <th scope="col" className={className} aria-sort={ariaSort(direction)}>
      <button type="button" className="sort-btn" onClick={() => onSort(sortKey)}>
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

function rowImageUrl(row: ComparisonRow): string | null {
  // SHOP_CODES order doubles as the preference order: the first shop that has a
  // photo for this kit supplies the thumbnail.
  for (const shop of SHOP_CODES) {
    const imageUrl = row.offers.find((o) => o.shop === shop)?.imageUrl;
    if (imageUrl) return imageUrl;
  }
  return null;
}

function findOffer(row: ComparisonRow, shop: ShopCode): Offer | undefined {
  return row.offers.find((o) => o.shop === shop);
}

function ProductThumb({ row }: { row: ComparisonRow }) {
  const imageUrl = rowImageUrl(row);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  if (imageUrl !== null && imageUrl !== failedSrc) {
    return (
      <img
        className="product-thumb"
        src={imageUrl}
        alt=""
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setFailedSrc(imageUrl)}
      />
    );
  }
  return (
    <span className="product-thumb product-thumb-fallback" aria-hidden="true">
      {row.grade.toUpperCase()}
    </span>
  );
}

function TitleCell({ row }: { row: ComparisonRow }) {
  return (
    <td className="title-cell">
      <div className="title-inner">
        <ProductThumb row={row} />
        <div className="product-info">
          <span className="product-title">{row.title}</span>
          <span className="sku">{row.sku}</span>
        </div>
      </div>
    </td>
  );
}

export function ComparisonTable({ rows }: { rows: ComparisonRow[] }) {
  const { sorted, sort, toggleSort } = useComparisonSort(rows);

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
            {SHOP_CODES.map((shop, index) => (
              <SortableHeader
                key={shop}
                label={SHOP_LABEL[shop]}
                code={`SHOP-${String(index + 1).padStart(2, '0')} · 價錢`}
                sortKey={shop}
                sort={sort}
                onSort={toggleSort}
                className={`shop-head ${SHOP_TONE[shop]}`}
              />
            ))}
            <th scope="col" className="verdict-head">
              判定<span className="th-code">VERDICT</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={`${row.grade}-${row.sku}`}>
              <TitleCell row={row} />
              {SHOP_CODES.map((shop) => (
                <OfferCell key={shop} offer={findOffer(row, shop)} shop={shop} />
              ))}
              <td className="badge-cell">
                <CheaperBadge
                  cheapestShop={row.cheapestShop}
                  saving={row.saving}
                  exclusiveShop={row.exclusiveShop}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
