// frontend/src/components/FactionWipe.tsx
import { useEffect, useRef, useState } from 'react';
import type { Faction } from '../types';

// Plays only on a real switch: the first render is the restored faction, not a change.
export function FactionWipe({ faction }: { faction: Faction }) {
  const initial = useRef(faction);
  const [hasSwitched, setHasSwitched] = useState(false);

  useEffect(() => {
    if (faction !== initial.current) setHasSwitched(true);
  }, [faction]);

  if (!hasSwitched) return null;
  return <div key={faction} className="faction-wipe" data-wipe={faction} aria-hidden="true" />;
}
