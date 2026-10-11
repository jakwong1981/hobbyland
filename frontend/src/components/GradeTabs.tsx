// frontend/src/components/GradeTabs.tsx
import type { Grade } from '../types';

const GRADES: Array<{ value: Grade; label: string }> = [
  { value: 'hg', label: 'HG' },
  { value: 'mg', label: 'MG' },
  { value: 'rg', label: 'RG' },
];

interface Props {
  value: Grade;
  onChange: (grade: Grade) => void;
}

export function GradeTabs({ value, onChange }: Props) {
  return (
    <div className="grade-tabs" role="tablist" aria-label="Grade">
      {GRADES.map((g) => (
        <button
          key={g.value}
          role="tab"
          aria-selected={value === g.value}
          className={value === g.value ? 'tab active' : 'tab'}
          onClick={() => onChange(g.value)}
        >
          {g.label}
        </button>
      ))}
    </div>
  );
}
