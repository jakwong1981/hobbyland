// frontend/src/components/ShopLogo.tsx
import type { ReactElement } from 'react';
import type { ShopCode } from '../types';
import { SHOP_MONOGRAM, SHOP_TONE } from '../shops';

const SHAPE: Record<ShopCode, ReactElement> = {
  'hobbyland': <polygon className="shop-logo-shape" points="12,1 22,6.5 22,17.5 12,23 2,17.5 2,6.5" />,
  'animes-pro': <circle className="shop-logo-shape" cx="12" cy="12" r="10.5" />,
  'hobbydigi': <polygon className="shop-logo-shape" points="12,1 23,12 12,23 1,12" />,
  'fookle': <rect className="shop-logo-shape" x="2" y="2" width="20" height="20" rx="5.5" />,
};

export function ShopLogo({ shop }: { shop: ShopCode }) {
  return (
    <svg
      className={`shop-logo ${SHOP_TONE[shop]}`}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      {SHAPE[shop]}
      <text className="shop-logo-text" x="12" y="12.5" textAnchor="middle" dominantBaseline="middle">
        {SHOP_MONOGRAM[shop]}
      </text>
    </svg>
  );
}
