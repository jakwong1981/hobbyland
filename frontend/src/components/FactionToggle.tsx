// frontend/src/components/FactionToggle.tsx
import type { Faction } from '../types';
import { FactionCrest } from './FactionCrest';

const FACTIONS: Array<{ value: Faction; label: string; code: string }> = [
  { value: 'federation', label: '聯邦', code: 'E.F.S.F.' },
  { value: 'zeon', label: '自護', code: 'ZEON' },
];

interface Props {
  value: Faction;
  onChange: (faction: Faction) => void;
}

export function FactionToggle({ value, onChange }: Props) {
  return (
    <div className="faction-toggle" role="radiogroup" aria-label="主題陣營">
      {FACTIONS.map((f) => (
        <button
          key={f.value}
          type="button"
          role="radio"
          aria-checked={value === f.value}
          className={value === f.value ? 'faction-btn active' : 'faction-btn'}
          onClick={() => onChange(f.value)}
        >
          <FactionCrest faction={f.value} />
          <span className="faction-text">
            <span className="faction-label">{f.label}</span>
            <span className="faction-sub">{f.code}</span>
          </span>
        </button>
      ))}
    </div>
  );
}
