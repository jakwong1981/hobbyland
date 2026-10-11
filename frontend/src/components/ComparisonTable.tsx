// frontend/src/components/ComparisonTable.tsx
import { useState } from 'react';
import type { ComparisonRow, Offer, ShopCode, SortKey, SortState } from '../types';
import { useComparisonSort } from '../hooks/useComparisonSort';
import { CheaperBadge } from './CheaperBadge';

const SHOP_TONE: Record<ShopCode, string> = {
  'hobbyland': 'shop-a',
  'animes-pro': 'shop-b',
};

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
  const hobbyland = row.offers.find((o) => o.shop === 'hobbyland' && o.imageUrl);
  return hobbyland?.imageUrl ?? row.offers.find((o) => o.imageUrl)?.imageUrl ?? null;
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
            <SortableHeader
              label="Hobbyland"
              code="SHOP-01 · 價錢"
              sortKey="hobbyland"
              sort={sort}
              onSort={toggleSort}
              className={`shop-head ${SHOP_TONE['hobbyland']}`}
            />
            <SortableHeader
              label="Animes-Pro"
              code="SHOP-02 · 價錢"
              sortKey="animes-pro"
              sort={sort}
              onSort={toggleSort}
              className={`shop-head ${SHOP_TONE['animes-pro']}`}
            />
            <th scope="col" className="verdict-head">
              判定<span className="th-code">VERDICT</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={`${row.grade}-${row.sku}`}>
              <TitleCell row={row} />
              <OfferCell offer={findOffer(row, 'hobbyland')} shop="hobbyland" />
              <OfferCell offer={findOffer(row, 'animes-pro')} shop="animes-pro" />
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
