// frontend/src/components/ViewToggle.tsx
import type { DashboardView } from '../types';

const VIEWS: Array<{ value: DashboardView; label: string; glyph: string }> = [
  { value: 'table', label: '表格', glyph: '☰' },
  { value: 'gallery', label: '圖鑑', glyph: '▦' },
];

interface Props {
  value: DashboardView;
  onChange: (view: DashboardView) => void;
}

export function ViewToggle({ value, onChange }: Props) {
  return (
    <div className="view-toggle" role="radiogroup" aria-label="顯示方式">
      {VIEWS.map((v) => (
        <button
          key={v.value}
          type="button"
          role="radio"
          aria-checked={value === v.value}
          className={value === v.value ? 'view-btn active' : 'view-btn'}
          onClick={() => onChange(v.value)}
        >
          <span className="view-glyph" aria-hidden="true">
            {v.glyph}
          </span>
          {v.label}
        </button>
      ))}
    </div>
  );
}
