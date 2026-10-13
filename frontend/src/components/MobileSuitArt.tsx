// frontend/src/components/MobileSuitArt.tsx
// Original line art, not traced from any official artwork. Both heads are always
// rendered and CSS shows the one matching html[data-faction], so switching faction
// cross-fades instead of remounting.

function FederationHead() {
  return (
    <svg className="ms-art ms-art-federation" viewBox="0 0 200 200" aria-hidden="true" focusable="false">
      <path className="ms-vfin" d="M100 92 L38 22 L52 20 L100 74 L148 20 L162 22 Z" />
      <path className="ms-vfin-glint" d="M100 92 L38 22 L52 20 L100 74 L148 20 L162 22 Z" />
      <circle className="ms-crest-gem" cx="100" cy="80" r="6" />
      <path className="ms-helmet" d="M58 96 Q60 64 100 60 Q140 64 142 96 L146 136 L126 150 L74 150 L54 136 Z" />
      <path className="ms-face" d="M76 104 L124 104 L118 128 L82 128 Z" />
      <path className="ms-eye ms-eye-left" d="M78 108 L96 112 L94 118 L80 115 Z" />
      <path className="ms-eye ms-eye-right" d="M122 108 L104 112 L106 118 L120 115 Z" />
      <path className="ms-mouthplate" d="M84 130 L116 130 L112 140 L88 140 Z" />
      <path className="ms-chin" d="M92 141 L108 141 L104 150 L96 150 Z" />
      <path className="ms-vent" d="M64 120 L72 120 L72 138 L64 134 Z M136 120 L128 120 L128 138 L136 134 Z" />
      <path className="ms-collar" d="M44 152 L156 152 L170 176 L30 176 Z" />
    </svg>
  );
}

function ZeonHead() {
  return (
    <svg className="ms-art ms-art-zeon" viewBox="0 0 200 200" aria-hidden="true" focusable="false">
      <path className="ms-horn" d="M100 34 L108 70 L92 70 Z" />
      <path className="ms-helmet" d="M50 112 Q50 58 100 54 Q150 58 150 112 L144 140 L56 140 Z" />
      <rect className="ms-rail" x="62" y="96" width="76" height="18" rx="9" />
      <circle className="ms-monoeye" cx="100" cy="105" r="7" />
      <path className="ms-mouth" d="M78 124 L122 124 L116 156 L84 156 Z" />
      <path className="ms-pipe ms-pipe-left" d="M80 136 Q52 150 48 178" />
      <path className="ms-pipe ms-pipe-right" d="M120 136 Q148 150 152 178" />
      <path className="ms-collar" d="M40 160 L160 160 L172 182 L28 182 Z" />
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
