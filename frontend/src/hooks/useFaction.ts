// frontend/src/hooks/useFaction.ts
import { useEffect, useState } from 'react';
import type { Faction } from '../types';

export const FACTION_STORAGE_KEY = 'hobbyland:faction';

function readStoredFaction(): Faction {
  return window.localStorage.getItem(FACTION_STORAGE_KEY) === 'zeon' ? 'zeon' : 'federation';
}

export function useFaction(): [Faction, (faction: Faction) => void] {
  const [faction, setFaction] = useState<Faction>(readStoredFaction);

  useEffect(() => {
    document.documentElement.dataset.faction = faction;
    window.localStorage.setItem(FACTION_STORAGE_KEY, faction);
  }, [faction]);

  return [faction, setFaction];
}
