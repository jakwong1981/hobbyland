// frontend/src/components/ShopFilter.tsx
import type { ShopFilterValue } from '../types';

const OPTIONS: Array<{ value: ShopFilterValue; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'hobbyland', label: 'Hobbyland' },
  { value: 'animes-pro', label: 'Animes-Pro' },
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
