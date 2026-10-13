// frontend/src/components/StatTile.tsx
import type { ReactNode } from 'react';
import { useCountUp } from '../hooks/useCountUp';

interface Props {
  label: ReactNode;
  value: number;
  tone: string;
  note?: ReactNode;
}

export function StatTile({ label, value, tone, note }: Props) {
  const shown = useCountUp(value);
  return (
    <div className={`stat-tile ${tone}`}>
      <span className="stat-value" data-value={value}>
        {shown}
      </span>
      <span className="stat-label">{label}</span>
      {note !== undefined && <span className="stat-note">{note}</span>}
    </div>
  );
}
