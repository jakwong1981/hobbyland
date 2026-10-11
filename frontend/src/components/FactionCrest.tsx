// frontend/src/components/FactionCrest.tsx
import type { Faction } from '../types';

const MARK_POINTS: Record<Faction, string> = {
  federation: '16,7 25,22 20,22 16,15 12,22 7,22',
  zeon: '9,8 24,8 17,16 24,24 9,24 16,16',
};

export function FactionCrest({ faction }: { faction: Faction }) {
  return (
    <svg className="crest" data-crest={faction} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <polygon className="crest-frame" points="16,1 31,9 31,23 16,31 1,23 1,9" />
      <polygon className="crest-mark" points={MARK_POINTS[faction]} />
    </svg>
  );
}
