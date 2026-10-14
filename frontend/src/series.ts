// frontend/src/series.ts
// Mirrors the SERIES table in scripts/jev_series.py by hand — the backend
// stores the series id, the dashboard shows the display name.
export const SERIES_IDS = [
  'gundam_0079',
  'the_08th_ms_team',
  'gundam_0080',
  'gundam_0083',
  'zeta',
  'zz',
  'chars_counterattack',
  'unicorn',
  'hathaways_flash',
  'f91',
  'victory',
  'seed',
  'seed_destiny',
  'seed_freedom',
  'gundam_00',
  'iron_blooded_orphans',
  'witch_from_mercury',
  'g_gundam',
  'gundam_wing',
  'gundam_x',
  'turn_a',
  'build_fighters',
  'gquuuuuux',
  'unknown',
] as const;

export type SeriesId = (typeof SERIES_IDS)[number];

export const SERIES_LABEL: Record<string, string> = {
  gundam_0079: '初代(0079)',
  the_08th_ms_team: '08MS小隊',
  gundam_0080: '0080',
  gundam_0083: '0083',
  zeta: 'Z',
  zz: 'ZZ',
  chars_counterattack: '馬沙之反擊',
  unicorn: '獨角獸',
  hathaways_flash: '閃光凱薩衛',
  f91: 'F91',
  victory: 'V高達',
  seed: 'SEED',
  seed_destiny: 'SEED Destiny',
  seed_freedom: 'SEED Freedom',
  gundam_00: '高達00',
  iron_blooded_orphans: '鐵血的孤兒',
  witch_from_mercury: '水星的魔女',
  g_gundam: '機動武鬥傳 G高達',
  gundam_wing: '新機動戰記 高達W',
  gundam_x: '機動新世紀 高達X',
  turn_a: '(Turn A) 高達',
  build_fighters: '創戰者',
  gquuuuuux: 'GQUUUUUX',
  unknown: '無法確定',
};

export function seriesLabel(series: string | null): string {
  if (series === null) return '—';
  return SERIES_LABEL[series] ?? series;
}
