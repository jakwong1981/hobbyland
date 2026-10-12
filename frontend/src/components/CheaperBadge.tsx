// frontend/src/components/CheaperBadge.tsx
import type { CheapestShop, ShopCode } from '../types';
import { SHOP_SHORT_LABEL } from '../shops';

interface Props {
  cheapestShop: CheapestShop;
  saving: number | null;
  exclusiveShop: ShopCode | null;
}

export function CheaperBadge({ cheapestShop, saving, exclusiveShop }: Props) {
  if (exclusiveShop !== null) {
    return <span className="badge badge-exclusive">只有 {SHOP_SHORT_LABEL[exclusiveShop]} 有貨</span>;
  }
  if (cheapestShop === 'tie') {
    return <span className="badge badge-tie">同價</span>;
  }
  if (cheapestShop === null) {
    return <span className="badge badge-none">—</span>;
  }
  return (
    <span className="badge badge-cheaper">
      {SHOP_SHORT_LABEL[cheapestShop]} 平{saving !== null && saving > 0 ? ` HK$${saving.toFixed(0)}` : ''}
    </span>
  );
}
