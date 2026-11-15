# E11 · Pair EVA and radio line of sight to the habitat

Owner: JB (`@JavierBonilla2004`) · Issue: #45 (P6), #76 (integration) · PRs: #75 (library, note, figure), API PR (this) · Status: library and API done; HUD and walk by Sebas after #73 · Last update: 2026-11-15

## Question
Along a planned EVA route, where does the astronaut lose direct radio contact with the habitat, and how much of it does a partner walking behind on the same route recover as a relay?

## Data
- `dem_1m.tif` from `base-grid-v2` (see `base_grid.md`); 1 m posting, effective resolution coarser.
- Demo route: E4's live round trip (`api.planner.plan`) from the box centre with the saved stations (`stations-v1`), 1000 Wh, 10 % margin, 120 min, cells > 30° blocked, human cost when `e1-sand-v1` is present. The planner picked station R0 (single-goal round trip; E5's tour was not in `main` when this ran).

## Method
1. **Habitat coverage.** GDAL `ViewshedGenerate` on the DEM, observer at the habitat cell with the antenna 3 m above the ground, target an astronaut radio 1.7 m above each cell. The curvature coefficient is 1.0 (no refraction: Mars' atmosphere is too thin to bend the radio path noticeably). GDAL takes the radius from the DEM's CRS (Mars sphere, 3,396,190 m). Computed in memory, about 0.1 s per habitat, cached per habitat cell (`src/gis/comms.py: line_of_sight`).
2. **Astronaut to astronaut.** An exact profile between the two positions: bilinear DEM samples every 0.5 m, with the same curvature bulge s (D − s) / 2R (`profile_los`).
3. **One astronaut** (`check_route`): each route vertex has radio if its cell is in the viewshed. A step between two vertices counts as "no radio" if either end lacks it (conservative, ≤ 1 m per transition). Times come from E4's per-vertex `t_s`.
4. **Pair** (`check_pair`): B walks `gap` metres behind A along the route. B waits at the habitat until A is `gap` m out, and A waits at the habitat at the end until B arrives. Every 1 m of progress the pair is **linked** if both see the habitat, or one sees it and the two see each other within the 100 m separation limit (relay).

## Results
Source: `src/gis/comms_figures.py` → `data/comms/summary.json`, figure [e11_fig1_radio.png](../figures/e11_fig1_radio.png).

- **Coverage.** From the box centre, 22.6 % of the box can talk to the habitat directly. Across 20 random habitats (seed 0) the mean is 13.0 % (range 4.3–27.6 %). The scarps and knobs of the boxwork confine a 3 m mast to its own valley.
- **Demo route (one astronaut).** Of 1,331 m (40.0 min), 604 m (45 %, 13.5 min) are without radio, in 3 stretches. The longest is 315 m (6.9 min), on the way back. The two long stretches are the same ridge crossed out and back (fig. a).
- **Pair.** No-link length by gap (m): 0 → 604, 10 → 581, 20 → 564, 50 → 537, 100 → 558. Beyond 100 m the relay is not allowed and the length jumps to 854 m (125 m gap) and 907 m (150 m gap) (fig. b). The relay covers 87 m at 20 m and 263 m at 100 m. Most of the shadow remains, because both astronauts end up on the same side of the ridge.
- **Longest silent stretch** drops from 315 m alone to 295 m at 20 m and 215 m at 100 m.

## Checks
- **GDAL viewshed vs exact profile:** 99.6 % agreement on 5,000 random cells from the centre habitat (`checks.viewshed_vs_profile_agreement`). The rest are cells where the line grazes the ground.
- **Mars radius in GDAL:** on a flat DEM in the team CRS with both ends 0.1 m high, the last visible cell is at 1,648 m. The Mars horizon 2√(2Rh) is 1,648.3 m; with Earth's radius it would be 2,258.9 m (`checks.horizon`).
- Synthetic tests (`tests/gis/test_comms.py`): flat ground is fully visible, a wall hides what is behind it, and a partner 20 m behind delays the loss of link by 20 m (±2 m).

## Limitations
- **Pure line of sight.** No diffraction, link budget, multipath or antenna pattern. Real UHF suit radios get some signal past a ridge crest, so this is a conservative coverage map.
- The DEM misses the 1–3 m boxwork ridges (`base_grid.md`). Boulders and the ridges themselves can block a 1.7 m radio that the DEM says is clear. E9 (Aaron, #12, in progress) finds about 8,400 boulders in the box (median diameter 1.7 m, top 5 % above 3.8 m). The largest can block the line of sight at short range; `rocas.tif` could be added to the DEM once it lands.
- The pair model is fixed-gap on the same route. Real partners move apart at stations, and the gap changes with speed. With one route and a gap ≤ 100 m, the separation limit never binds (the straight-line distance is at most the gap).
- One demo route and one habitat for the pair numbers. They show the mechanism, not a general rate.

## What other pieces can use
- **HUD / walk / 3D (Sebas, Juan):** the API (#76) serves it.
  - `POST /comms/check` takes a route, or uses the last plan. It returns `radio_ok` and `pair_state` (`direct` / `relay` / `none`) per route vertex, aligned like `rv_wh`. It also returns the `no_radio` and `pair_unlinked` stretches with m, min and `t_s`.
  - `GET /layers/comms.png` and `/layers/comms` give the habitat's coverage.
- **E4 / E5 (Aaron, Diana):** the viewshed is a boolean raster per habitat. It could become a planning cost or constraint (for example a maximum silent time).
- **Pitch:** with a mast at the habitat, almost half of the demo route is silent. That is an argument for a relay (a partner, a rover or a mast on a crest) and for planning with the tablet offline.

## Reproduce
From the repo root, with `data/base`, `data/stations` (and optionally `data/e1`):
```bash
python src/gis/comms_figures.py
python -m pytest tests/gis -q
```

## Outputs
`data/comms/summary.json` (local, not released); `paper/figures/e11_fig1_radio.png`.
