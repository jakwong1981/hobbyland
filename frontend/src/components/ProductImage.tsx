// frontend/src/components/ProductImage.tsx
import { useState } from 'react';
import type { ComparisonRow } from '../types';
import { productImageUrl } from '../utils/productImage';

interface Props {
  row: ComparisonRow;
  className: string;
}

export function ProductImage({ row, className }: Props) {
  const imageUrl = productImageUrl(row);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  if (imageUrl !== null && imageUrl !== failedSrc) {
    return (
      <img
        className={`product-thumb ${className}`}
        src={imageUrl}
        alt=""
        // Every usage renders square (table 88px/60px, gallery 1:1); declaring
        // the size lets the browser reserve the box before the image loads.
        width={88}
        height={88}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setFailedSrc(imageUrl)}
      />
    );
  }
  return (
    <span
      className={`product-thumb product-thumb-fallback ${className}`}
      data-grade={row.grade}
      aria-hidden="true"
    >
      {row.grade.toUpperCase()}
    </span>
  );
}
