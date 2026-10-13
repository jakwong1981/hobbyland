// frontend/src/components/CheaperBadge.tsx
import type { CheapestShop, ShopCode } from '../types';
import { SHOP_SHORT_LABEL } from '../shops';
import { ShopLogo } from './ShopLogo';

interface Props {
  cheapestShop: CheapestShop;
  exclusiveShop: ShopCode | null;
}

export function CheaperBadge({ cheapestShop, exclusiveShop }: Props) {
  if (exclusiveShop !== null) {
    return (
      <span className="badge badge-exclusive">
        <ShopLogo shop={exclusiveShop} />只有 {SHOP_SHORT_LABEL[exclusiveShop]} 有貨
      </span>
    );
  }
  if (cheapestShop === 'tie') {
    return <span className="badge badge-tie">同價</span>;
  }
  if (cheapestShop === null) {
    return <span className="badge badge-none">—</span>;
  }
  return (
    <span className="badge badge-cheaper">
      <ShopLogo shop={cheapestShop} />
      {SHOP_SHORT_LABEL[cheapestShop]} 最平
    </span>
  );
}
