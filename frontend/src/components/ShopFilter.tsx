// frontend/src/components/ShopFilter.tsx
import { SHOP_CODES, type ShopFilterValue } from '../types';
import { SHOP_LABEL } from '../shops';

const OPTIONS: Array<{ value: ShopFilterValue; label: string }> = [
  { value: 'all', label: '全部' },
  ...SHOP_CODES.map((shop) => ({ value: shop, label: SHOP_LABEL[shop] })),
];

interface Props {
  value: ShopFilterValue;
  onChange: (value: ShopFilterValue) => void;
}

export function ShopFilter({ value, onChange }: Props) {
  return (
    <label className="shop-filter">
      <span className="shop-filter-label">有售舖頭</span>
      <select value={value} onChange={(e) => onChange(e.target.value as ShopFilterValue)}>
        {OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
