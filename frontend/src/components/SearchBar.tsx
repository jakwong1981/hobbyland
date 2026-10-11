// frontend/src/components/SearchBar.tsx
interface Props {
  value: string;
  onChange: (value: string) => void;
}

export function SearchBar({ value, onChange }: Props) {
  return (
    <input
      className="search-bar"
      type="search"
      placeholder="搜尋產品名稱或 SKU…"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="搜尋產品"
    />
  );
}
