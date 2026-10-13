<!-- docs/plans/enhancement3-layout-plan.md -->
# Enhancement 3 — Dynamic, Colourful, Faction-Heavy Layout (Plan)

## 1. Request (ehancement3.md)
> 修改版面設計，想多一點動態，自護聯邦風格再出一點，如多點 logo，可以加一些模型圖片；多一點動態令色彩豐富點

Interpretation:
| Ask | Design answer |
|---|---|
| 多一點動態 (more motion) | Animated hero, count-up stats, auto-scrolling kit showcase, staggered row entrance, badge shine, faction-switch wipe, drifting "Minovsky particle" background |
| 自護 / 聯邦風格再出一點 (stronger Zeon / Federation identity) | Large faction emblem + original mobile-suit line art per faction (V-fin head for 聯邦, mono-eye head with sweeping eye for 自護), tri-colour/faction stripes, faction-specific copy |
| 多點 logo | Shop logo chips (SVG monograms), grade emblems (HG/MG/RG), bigger animated faction crest |
| 加一些模型圖片 | Kit photos from scraped `imageUrl` (already in all 9 CSVs): hero showcase marquee + new Gallery (圖鑑) view with large photos |
| 色彩豐富 | Multi-tone palette per faction (not one accent), coloured grade emblems, coloured shop chips |

Scope: **frontend only** (`frontend/`). No backend/API change — stats are derived client-side from `ComparisonRow[]` already fetched. No bundled Bandai artwork: kit photos are hot-linked from shop data (same as today), mobile-suit art is original SVG line drawing.

## 2. New Layout (wireframe)

```
┌─ HEADER ───────────────────────────────────────────────────────────────┐
│ [animated crest] Gunpla 格價            [聯邦 | 自護]  [格價表] [匯入]   │
│ ═══ faction stripe (聯邦: white/blue/red/yellow · 自護: green/red/gold) ═ │
├─ HERO (DashboardPage only) ────────────────────────────────────────────┤
│  MS line-art head (animated)  │  "OPERATION // PRICE RECON"            │
│  聯邦: V-fin glint            │  STAT TILES (count-up):                 │
│  自護: mono-eye sweep          │  [總 SKU 312] [HL最平 120] [AP最平 98]  │
│                               │  [HD最平 14] [獨家 80]                   │
├─ KIT SHOWCASE (marquee, auto-scroll, pause on hover) ──────────────────┤
│  [img][img][img][img][img][img] ... (top-saving kits, link to cheapest) │
├─ TOOLBAR ──────────────────────────────────────────────────────────────┤
│ [HG◆][MG◆][RG◆] emblem tabs | 有售舖頭 ▼ | 🔍 search | [表格|圖鑑]       │
├─ STATUS / FRESHNESS (shop logo chips + pulsing LIVE dot) ──────────────┤
├─ CONTENT ──────────────────────────────────────────────────────────────┤
│ 表格 view: existing table + shop logos in headers, row stagger-in,      │
│            thumbnail zoom on hover, shining 最平 badge                  │
│ 圖鑑 view: responsive card grid (1/2/3/4 cols), big photo, grade        │
│            emblem corner, per-shop price rows, verdict ribbon           │
└────────────────────────────────────────────────────────────────────────┘
```
Mobile (<640px): hero stacks (art above stats, stats 2-col grid), showcase stays a swipeable strip, Gallery is the more readable view (table still available).

## 3. Visual System

### 3.1 Palette (CSS custom properties, `html[data-faction]`)
| Token | 聯邦 federation | 自護 zeon |
|---|---|---|
| `--accent` | `#2f7de1` (RX blue) | `#d23b2f` (Char red) |
| `--accent-2` | `#e03a3e` (chest red) | `#5d8a3c` (Zaku green) |
| `--accent-3` | `#f5c518` (V-fin yellow) | `#c9a43a` (Zeon gold) |
| `--accent-4` | `#f4f7fb` (armour white) | `#ff3d7f` (mono-eye pink) |
| `--glow` / `--glow-2` | blue / yellow rgba | red / pink rgba |
| `--bg` tint | deep navy `#050a14` | deep olive-black `#0a0c07` |

- Grade colours (faction-independent): HG `#3fb6ff`, MG `#f5a623`, RG `#ff4d6d`.
- Shop chip colours (logo only; price text stays neutral so the accent keeps meaning "winner"): Hobbyland `#4dd0e1`, Animes-Pro `#b388ff`, HobbyDigi `#69f0ae`. Update the comment in `shops.ts`/`styles.css` that previously forbade shop colour.
- Optional display font: self-hosted `@fontsource/rajdhani` (pinned) for headings/stat numbers only; fallback to existing mono stack.

### 3.2 Motion (all disabled under `prefers-reduced-motion: reduce`)
| Element | Animation |
|---|---|
| Background | 2-layer drifting particle dots (CSS `background-position` keyframes, 60–90s) + slow grid pan |
| Header crest | slow rotate of outer hex frame, mark pulse glow |
| Header stripe | gradient sweep (`::after` light bar every 6s) |
| Hero art | 聯邦: V-fin glint sweep + eye glow pulse; 自護: mono-eye travels left↔right on rail |
| Stat tiles | count-up 0→value over 900ms (`useCountUp`, rAF, cleanup on unmount) + fade-up stagger |
| Showcase | infinite CSS marquee (`translateX(-50%)` on a duplicated list), pauses on hover/focus |
| Table rows | fade/slide-in stagger via `style={{'--i': index}}`, delay capped at 20 rows |
| Thumbnails | scale 1.08 + glow on row hover |
| 最平 badge | diagonal shine sweep every 4s |
| Grade tab | active emblem bounce-in; underline bar slides |
| Faction switch | full-screen diagonal colour wipe (`<div key={faction} className="faction-wipe">`, mounted only after the first change) |

## 4. Implementation

### 4.1 New files (`frontend/src/`)
| File | Responsibility |
|---|---|
| `components/ShopLogo.tsx` | SVG monogram chip per shop (`HL` hexagon, `AP` circle, `HD` diamond), `aria-hidden`, colour from `SHOP_COLOR` |
| `components/GradeEmblem.tsx` | SVG shield with `HG/MG/RG` text in grade colour; used in tabs, gallery, thumb fallback |
| `components/MobileSuitArt.tsx` | Original SVG line art: `faction="federation"` V-fin head, `"zeon"` mono-eye head; animated parts have classes for CSS |
| `components/HeroBanner.tsx` | Props `{ rows: ComparisonRow[]; faction: Faction; grade: Grade }`; art + headline + `StatTile`s |
| `components/StatTile.tsx` | Label + `useCountUp(value)` number; plain `<div>` (NOT a button) |
| `components/KitShowcase.tsx` | Props `{ rows }`; picks up to 16 rows with image, ordered by `saving` desc; duplicates list for marquee; each item `<a aria-label={title}>` with `<img alt="">` + price chip; returns `null` when no images |
| `components/ViewToggle.tsx` | `role="radiogroup"` 表格 / 圖鑑 (value `'table' \| 'gallery'`) |
| `components/ComparisonGallery.tsx` | Card grid; reuses `CheaperBadge`, `GradeEmblem`, `ShopLogo`, `productImageUrl` |
| `components/FactionWipe.tsx` | Transition overlay keyed on faction; skip initial mount via `useRef` |
| `hooks/useCountUp.ts` | rAF tween; returns final value immediately when reduced motion; cancels frame on unmount/value change |
| `hooks/usePrefersReducedMotion.ts` | `matchMedia('(prefers-reduced-motion: reduce)')` + change listener cleanup |
| `utils/comparisonStats.ts` | Pure `summarizeComparisons(rows) → { total, cheapestByShop: Record<ShopCode, number>, ties, exclusives }` |
| `utils/productImage.ts` | Move `rowImageUrl` out of `ComparisonTable.tsx` → `productImageUrl(row)` (shared by table, gallery, showcase) |
| `styles/` | Split the 897-line `styles.css` into `tokens.css`, `base.css`, `header.css`, `hero.css`, `showcase.css`, `toolbar.css`, `table.css`, `gallery.css`, `motion.css`, `import.css`, `index.css` (imports all); `main.tsx` imports `./styles/index.css` |
| `types/index.ts` (edit) | add `export type DashboardView = 'table' \| 'gallery'` |

### 4.2 Modified files
- `App.tsx` — add `<FactionWipe faction>`; header gets stripe element; nav buttons keep text 格價表/匯入.
- `pages/DashboardPage.tsx` — render `HeroBanner` + `KitShowcase` above toolbar (from `data`), add `ViewToggle` to toolbar, switch `ComparisonTable` / `ComparisonGallery`; pass `faction` down (lift `useFaction` value via prop from `App`).
- `components/FactionCrest.tsx` — richer emblem (federation: wings/globe-arc mark; zeon: stylised eagle-burst), keep `data-crest` + `className="crest"`.
- `components/GradeTabs.tsx` — prepend `<GradeEmblem>` (aria-hidden) inside each tab; tab accessible name must remain exactly `HG`/`MG`/`RG`.
- `components/ComparisonTable.tsx` — import `productImageUrl`; `ShopLogo` in shop headers; `style={{'--i': i}}` on rows; fallback thumb uses `GradeEmblem`.
- `components/CheaperBadge.tsx` — prepend `ShopLogo` (svg only, no text nodes → existing `getByText('Hobbyland 最平')` still passes); add `badge-shine` class for cheaper.
- `components/FreshnessBar.tsx` — `ShopLogo` before shop name; pulsing live dot.
- `shops.ts` — add `SHOP_COLOR` and `SHOP_MONOGRAM` maps.
- `index.html` — `theme-color` per faction kept dark; no external fonts.
- `tests/setup.ts` — stub `window.matchMedia` (jsdom lacks it).

### 4.3 Test-compatibility constraints (existing suites must stay green)
- Showcase / hero must **not render product titles as text** (dashboard test uses `findByText('HG Gundam')`) → titles only via `aria-label`/`title`.
- Hero must not render `"N 個 SKU"` text (collides with `result-count` assertions) → label 「總 SKU」 + number.
- No new `button`s whose name contains shop names (`getByRole('button', {name: /Hobbyland/})` in sort tests); stat tiles are divs, showcase items are links.
- Keep `combobox` 有售舖頭, `columnheader` names, `radio` 聯邦/自護, tab names.

### 4.4 Rules followed
Strict TS, no `any`, no new runtime deps except optional pinned `@fontsource/rajdhani`; timers/rAF/matchMedia listeners cleaned up in `useEffect` returns; `React.memo` on `KitShowcase` and gallery cards; mobile-first CSS.

## 5. Steps
1. Extract `productImageUrl`, add `comparisonStats.ts` + unit tests.
2. Split CSS into `styles/`, introduce new palette tokens (pure refactor; screenshot-check unchanged layout).
3. `ShopLogo`, `GradeEmblem`, richer `FactionCrest`, `MobileSuitArt`.
4. `usePrefersReducedMotion`, `useCountUp`, `StatTile`, `HeroBanner`.
5. `KitShowcase` marquee.
6. `ViewToggle` + `ComparisonGallery`; wire into `DashboardPage`.
7. Motion layer (`motion.css`), `FactionWipe`, badge shine, row stagger.
8. Tests + docs update.

## 6. Tests to add (Vitest + RTL, AAA)
| File | Cases |
|---|---|
| `tests/comparison-stats.test.ts` | counts per shop, ties, exclusives, empty rows |
| `tests/count-up.test.tsx` | reduced motion → final value immediately; animates to target with fake rAF; cancels on unmount |
| `tests/hero.test.tsx` | renders stat numbers for fixture rows; shows 聯邦 vs 自護 art via `data-faction` |
| `tests/showcase.test.tsx` | renders only rows with images, sorted by saving, max 16, links to cheapest offer URL; returns nothing when no images |
| `tests/gallery.test.tsx` | ViewToggle switches to gallery; card shows prices per shop & verdict; empty-state |
| existing 4 suites | must pass unchanged |

## 7. Docs to update
`docs/PROGRAM_SPEC.md` (new components/hooks, file map), `docs/FUNCTION_SPEC.md` (hero stats semantics, showcase selection rule, view toggle, reduced-motion), `docs/ARCHITECTURE.md` (component hierarchy Mermaid), `docs/TESTING.md` (new test matrix rows).

## 8. Verification
1. `pnpm --filter frontend test` — all suites green.
2. `pnpm --filter frontend build` — strict tsc passes.
3. `pnpm dev` with backend running → check in browser (agent-browser screenshots) at 375px / 768px / 1280px, both factions: hero counts animate, marquee scrolls & pauses on hover, faction wipe plays on toggle, gallery view renders photos, broken image falls back to grade emblem.
4. Toggle OS "Reduce motion" → no animations, counts show final values.
