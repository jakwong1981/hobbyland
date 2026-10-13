// frontend/src/components/FactionCrest.tsx
import type { Faction } from '../types';

function FederationMark() {
  return (
    <g className="crest-mark">
      <path d="M16 6 L20.5 15 L16 13 L11.5 15 Z" />
      <path d="M5 13 Q10 15 13.5 19 L16 24 L18.5 19 Q22 15 27 13 Q22 19 16 26 Q10 19 5 13 Z" />
    </g>
  );
}

function ZeonMark() {
  return (
    <g className="crest-mark">
      <path d="M16 5 L18 13 L27 9 L20 16 L27 23 L18 19 L16 27 L14 19 L5 23 L12 16 L5 9 L14 13 Z" />
      <circle className="crest-core" cx="16" cy="16" r="2.4" />
    </g>
  );
}

export function FactionCrest({ faction }: { faction: Faction }) {
  return (
    <svg className="crest" data-crest={faction} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <polygon className="crest-frame" points="16,1 31,9 31,23 16,31 1,23 1,9" />
      {faction === 'federation' ? <FederationMark /> : <ZeonMark />}
    </svg>
  );
}
