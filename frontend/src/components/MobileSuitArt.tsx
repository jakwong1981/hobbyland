// frontend/src/components/MobileSuitArt.tsx
// Original line art, not traced from any official artwork. Both heads are always
// rendered and CSS shows the one matching html[data-faction], so switching faction
// cross-fades instead of remounting.

function FederationHead() {
  return (
    <svg className="ms-art ms-art-federation" viewBox="0 0 200 200" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="ms-fed-helmet" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#aebfd6" />
          <stop offset="0.3" stopColor="#ffffff" />
          <stop offset="0.7" stopColor="#f1f5fb" />
          <stop offset="1" stopColor="#9fb2cb" />
        </linearGradient>
        <linearGradient id="ms-fed-fin" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff3a0" />
          <stop offset="1" stopColor="#e3a800" />
        </linearGradient>
        <linearGradient id="ms-fed-chin" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f2545c" />
          <stop offset="1" stopColor="#b3202a" />
        </linearGradient>
        <linearGradient id="ms-fed-collar" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#4aa0ff" />
          <stop offset="1" stopColor="#1c58b8" />
        </linearGradient>
      </defs>
      <path className="ms-vfin" d="M97 76 L40 14 L50 12 L99 54 Z M103 76 L160 14 L150 12 L101 54 Z" />
      <path className="ms-vfin-core" d="M100 46 L108 62 L103 78 L97 78 L92 62 Z" />
      <path className="ms-vfin-glint" d="M97 76 L40 14 L50 12 L99 54 Z M103 76 L160 14 L150 12 L101 54 Z" />
      <path className="ms-collar" d="M42 156 L158 156 L172 182 L28 182 Z" />
      <path className="ms-detail" d="M62 158 L58 180 M138 158 L142 180 M100 158 L100 180" />
      <path className="ms-helmet" d="M56 100 Q54 64 100 58 Q146 64 144 100 L148 132 L128 152 L72 152 L52 132 Z" />
      <path className="ms-ear" d="M50 98 L40 104 L42 134 L54 138 Z M150 98 L160 104 L158 134 L146 138 Z" />
      <path className="ms-detail" d="M80 66 L84 90 M120 66 L116 90 M100 60 L100 74" />
      <path className="ms-crest" d="M93 72 L107 72 L104 88 L96 88 Z" />
      <circle className="ms-vulcan" cx="78" cy="74" r="3.5" />
      <circle className="ms-vulcan" cx="122" cy="74" r="3.5" />
      <path className="ms-brow" d="M66 92 L134 92 L130 100 L70 100 Z" />
      <path className="ms-face" d="M72 100 L128 100 L122 132 L78 132 Z" />
      <path className="ms-eye ms-eye-left" d="M76 104 L97 108 L95 116 L79 113 Z" />
      <path className="ms-eye ms-eye-right" d="M124 104 L103 108 L105 116 L121 113 Z" />
      <path className="ms-cheek" d="M64 104 L72 104 L78 132 L66 128 Z M136 104 L128 104 L122 132 L134 128 Z" />
      <path className="ms-mouthplate" d="M82 128 L118 128 L113 142 L87 142 Z" />
      <path className="ms-detail" d="M91 130 L92 141 M96 130 L96 141 M100 130 L100 141 M104 130 L104 141 M109 130 L108 141" />
      <path className="ms-chin" d="M88 142 L112 142 L106 154 L94 154 Z" />
      <path className="ms-hl" d="M70 80 Q74 68 92 64" />
    </svg>
  );
}

function ZeonHead() {
  return (
    <svg className="ms-art ms-art-zeon" viewBox="0 0 200 200" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="ms-zeon-helmet" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#3f6a26" />
          <stop offset="0.35" stopColor="#8cc063" />
          <stop offset="0.75" stopColor="#5f9140" />
          <stop offset="1" stopColor="#365a22" />
        </linearGradient>
        <radialGradient id="ms-zeon-eye" cx="0.4" cy="0.4" r="0.7">
          <stop offset="0" stopColor="#ffd0e0" />
          <stop offset="0.45" stopColor="#ff3d7f" />
          <stop offset="1" stopColor="#8a0f3c" />
        </radialGradient>
      </defs>
      <path className="ms-pipe ms-pipe-left" d="M82 140 Q46 150 40 184" />
      <path className="ms-pipe ms-pipe-right" d="M118 140 Q154 150 160 184" />
      <path className="ms-collar" d="M36 164 L164 164 L176 186 L24 186 Z" />
      <path className="ms-horn" d="M100 28 L106 60 L94 60 Z" />
      <path className="ms-helmet" d="M46 118 Q42 56 100 50 Q158 56 154 118 L146 148 L54 148 Z" />
      <path className="ms-detail" d="M62 66 Q100 54 138 66 M100 52 L100 90 M54 110 L66 144 M146 110 L134 144" />
      <path className="ms-cheek" d="M46 118 L62 126 L66 148 L54 148 Z M154 118 L138 126 L134 148 L146 148 Z" />
      <path className="ms-visor" d="M58 92 L142 92 L146 118 L54 118 Z" />
      <rect className="ms-rail" x="64" y="98" width="72" height="14" rx="7" />
      <circle className="ms-monoeye" cx="100" cy="105" r="8" />
      <circle className="ms-eye-glint" cx="97" cy="102" r="2" />
      <path className="ms-mouth" d="M74 126 L126 126 L118 158 L82 158 Z" />
      <path className="ms-grille" d="M86 130 L88 156 M93 130 L94 156 M100 130 L100 156 M107 130 L106 156 M114 130 L112 156" />
      <path className="ms-hl" d="M60 84 Q70 62 94 56" />
    </svg>
  );
}

export function MobileSuitArt() {
  return (
    <div className="ms-art-stage">
      <span className="ms-art-halo" aria-hidden="true" />
      <FederationHead />
      <ZeonHead />
    </div>
  );
}
