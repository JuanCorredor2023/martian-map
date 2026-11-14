# Product · API, HUD and manual science stations

Owner: Sebas (`@Seredial0326`) · Issue: #10 · PRs: #24, #26, this PR · Status: in progress (planner, R(v) and walkback layers still to connect) · Last update: 2026-11-14

## Question
How does the planner reach the jury: which service exposes the terrain, the cost and the plans, how the HUD shows them in Mars coordinates, and how the science stations that E5 optimises get a value that can be defended?

## Data
- JB's base grid (`base-grid-v2`) and map tiles (`tiles-v2`): ortho z 0–5, slope and hillshade z 0–3, gdal2tiles raster profile, tile z = 0 spans 2048 m [Parker2016] [HiRISE-Gale].
- Curiosity's trajectory from E2 (`data/e2/trajectory.geojson`) as a fixed test route [PLACES].
- E3 directed costs (`src/fisica/edge_cost.py`) and `slope_deg.tif`.
- Station rubric: literature review in `docs/research/station_value_rubric.md` (notes per source in `docs/research/station_value_notes/`).

## Method

### API (`api/`, FastAPI)
- `GET /health`, `GET /layers` (CRS WKT, `grid.json`, `tiles.json`). Everything is served from one origin, so no CORS setup [Guide-REV3, sections 33–38].
- `POST /plan` with a Pydantic contract: budget in Wh (> 0), gravity in m/s² (> 0, never a 0.38 factor), margin in [0, 1), unique station ids, scores ≥ 0, points inside the box, `max_cell_slope_deg` (null disables the cell block). Until E4/E5 are connected it returns Curiosity's trajectory as a **fixed test route**, with `feasible = null` and warnings; this tests the whole pipeline first (guide section 38). Responses are GeoJSON FeatureCollections in metres of the DEM CRS, never WGS84.
- `GET /layers/cost.png` (+ legend): E3 mean Wh per cell, computed once without the cell block. `GET /layers/blocked.png?max_cell_slope_deg=N` (+ blocked fraction): cheap, so the HUD slider requests it live.
- Stations: `GET /stations/rubric`, `GET/POST /stations`, `GET /stations/stations_manual.gpkg`.

### HUD (`web/index.html`, deck.gl 9.1.14 from CDN)
- `OrthographicView` (a plane in metres, the equivalent of Leaflet's `L.CRS.Simple`). One world unit = `tile_z0_m / 256` = 8 m, so deck.gl tile indices equal gdal2tiles indices with no offset.
- Layers: ortho, hillshade, slope (opacity slider made linear: deck.gl applies `opacity^(1/2.2)`, compensated by raising the slider value to 2.2), E3 cost with legend, steep-cell block with on/off and a 15–60° slider, route, start and stations. Cursor readout in Mars metres and grid cell.

### Walkback: the red line and the energy-safe area (`api/walkback.py`, `POST /walkback`)
**Provisional:** E4 (Aaron) owns R(v); until his `rv.tif` arrives, the HUD computes the fields itself from the same E3 directed costs.
- R_T(v) and R_E(v): minimum time and energy from v back to the base, from Dijkstra runs from the base on the **reversed** graph that keep each original arc's cost (guide section 20). Cached per base and cell-block limit. Run time is under 1 s per field on the 4 M-node, 25 M-edge graph (`scipy.sparse.csgraph.dijkstra`).
- Red line: contour R_T = 1800 s, the 30 min emergency-oxygen contingency (guide section 20.4). It depends only on the base.
- Energy-safe boundary: contour of F_E(p, v) + R_E(v) = E_remaining, with F_E from a forward Dijkstra limited to E_remaining (guide section 20.3). It is recomputed for each position and energy, about 0.3 s.
- Boundaries are drawn from the **region**, not from raw contours. The cells inside the limit that are connected to the base (red line) or to the astronaut (cyan line) form the region. Blocked and unreachable cells count as outside, and small holes are filled. A morphological closing and opening of about 2 m smooth it, and it is traced with `contourpy` on a one-cell padded grid so it closes along scarps and the box edge. The result is simplified to 2 m. A first version contoured the raw fields with NaN at blocked cells. It produced over 3,000 broken fragments (the line stopped at every blocked cell) and never closed the region; this is now covered by a test.
- The HUD places the astronaut and the base by clicking. It shows the return time against the 30 min limit, the return energy and the energy left after returning.

### Radiation in the HUD (`api/radiation.py`, `GET /radiation`)
- Reads E12's outputs (Juan, `data/e12/`): background rate, the real 2025-11-11 SEP event, the alarm rule and the dose along the provisional EVA. Radiation is shown as a **dose budget along the EVA timeline**, never as a per-pixel map, because the cosmic background barely changes across a few km [Guide-REV3, section 43] [Hassler2014].
- HUD panel:
  - background rate and EVA dose;
  - a one-series chart of accumulated dose against EVA time, with a crosshair tooltip;
  - an **SEP alert simulation** at the astronaut's position: dose on the way back = R_T(p) × storm rate.
- Storm options are the real event peak and E12's hypothetical ×10 and ×50 scalings of its excess over the baseline.
- With the real storm the return dose is tiny. For an astronaut about 520 m from the base, R_T is 12.1 min, so the dose on the way back is 58.8 µGy at ×50 against 1.3 µGy without a storm. So radiation only changes the plan through the SEP return, as E12 concludes.

### Manual science stations and their rubric
- Stations are placed by clicking on the 0.25 m orthophoto, where ridges and hollows are visible; the 1 m DEM does not resolve them (base grid note).
- A station's score is **the rubric score of its type**, never typed per station, so each value traces back to a written rule [Guide-REV3, section 24]. The rubric is editable live in the HUD and saved with the stations.
- Output for E5: `data/stations/stations_manual.gpkg`, layer `stations`, DEM CRS, columns `id, type, score, service_time_min, note`, plus `stations_rubric.json` (scores, default version, sources).

**Default rubric (version 2026-11-14):**

| Type | Score | Why (short) | Sources |
|---|---|---|---|
| Boxwork ridge | 5 | Groundwater cement; drilled ridge has clays + Fe oxides; chosen for the last SAM TMAH organics run | [Siebach2014] [Hausrath2026] [JPL2026] |
| Hollow between ridges | 4 | Siderite-rich, clay-free, less altered bedrock (reduced end-member); sand hazard is costed in E3/E4, not here | [Hausrath2026] [Siebach2026] |
| Contact between units | 4 | Brackets environmental change and timing; final-phase target of the boxwork campaign | [NASA-blog-4804] [Herd2025] [Siebach2026] |
| Curiosity measurement site | 3 | Ground truth and calibration for E8; little new science | [MSR-STM2025] [Brady2019] |

**Why integers, and why these.**
- No EVA analog published a numeric score per station. Apollo used priority orders, prime and alternate stations and a deletion order; BASALT/Minerva ranked candidates on an ordinal "leaderboard" by expert consensus against a Science Traceability Matrix [Brady2019] [Marquez2019] [Stevens2019]. MIT SEXTANT leaves site value to the user [Johnson2010].
- The closest numeric precedent is NASA's lunar "Science Yield" prototype, which scores relevance and objective priority 3/2/1 and lets the science team adjust the weights [Broddrick2024]. Orienteering surveys treat scores as given inputs [Vansteenwegen2011] [Gunawan2016]; Smith models rover science planning as orienteering with given rewards [Smith2004].
- So 5/4/4/3 is presented as our cardinal encoding of an expert order, with a sensitivity analysis, not as a measured quantity.
- Contact was raised from 3 to 4 after the review: stratigraphic transitions drove the choice of Gale and Mars 2020 sampling [Herd2025], and Curiosity spent the final phase of the boxwork campaign on contacts.
- Astrobiology frameworks group clays and carbonates as preservation-capable minerals, with sulfates less stable; they give no explicit ranking (MEPAG Goals, Mars 2020 SDT, iMOST). The ridge stays above the hollow because of context (early cement, the TMAH choice), not the mineral label.

### Suggested stations (`api/candidates.py` → `data/stations/candidates.json`)
The HUD can load suggestions **unsaved**; a person reviews them on the orthophoto and only saved stations reach E5.
- **Curiosity's own targets (NASA science team choices).** No public NASA layer of drill sites exists, so drill sites are found by crossing the PLACES drill-mechanism log (`mech_drill.csv`, site/drive with drill activity) with the rover poses [PLACES]: Altadena (site 116, drive 1944, arrival sol 4560), Valle de la Luna hollow (119/1722, sol 4687) and Nevado Sajama ridge (120/82, sol 4711; re-drilled at 120/574, sol 4789). Check: the drilled ridge lies 10.2 m from the drilled hollow and 2.5 m higher in the DEM (PLACES elevations agree within 0.5 m), matching NASA's "about 10 m and 2 m". Nevado Sajama is counted once, as a ridge. Two contacts are the rover positions on the sols it crossed them (4534 and 4848), so they are approximate.
- **Extra ridge/hollow candidates.** Calibrated on the drilled pair: in a 21 m window the ridge stands +0.5 m above its surroundings and is lighter; the hollow is lower and darker (JB's `tpi.tif` gives the same +0.52 / −0.08 m). Candidates need both signals to agree (ridge relief > +0.3 m and lighter; hollow < −0.1 m and darker), slope ≤ 25°, at least 40 m apart, inside the visible polygon network. Relief above 1.5 m is flagged low confidence (likely a scarp, not a boxwork ridge). The signal is weak because the 1 m DEM barely resolves the boxwork, so these are suggestions, not detections; E8 will replace them.

### Implied trade-offs (orienteering adds scores)
- One ridge (5) is worth less than two Curiosity sites (6).
- Hollow + contact (8) ties ridge + Curiosity site (8); the E3/E4 cost breaks the tie.

## Results
- Blocked share of the box by the cell limit: 12.4 % at 30°, 29.6 % at 20° (`/layers/blocked`, from `slope_deg.tif`).
- Cost layer colour scale starts at 0.0941 Wh per cell = 338.75 J/m, the analytic c_min,h of E3 (`/layers/cost`; test `test_cost_layer_png_and_legend`).
- Fixed test route: Curiosity's 3,900.3 m trajectory falls on the valley floor of the orthophoto, entering at cell (row 30, col 1999) as in E2.

### Walkback on the real grid (base at the box centre)
Source: `api/walkback.py` fields, computed in the session that produced this note.

| Configuration | Cells that can reach the base | Within 30 min (R_T ≤ 1800 s) | Costliest return |
|---|---|---|---|
| Edge limit 20° + cell block 30° (default) | 84.4 % | 63.4 % of the box | 2600 s, 285.5 Wh |
| Edge limit 20° only | 99.1 % | 92.4 % of the box | 2324 s, 267.3 Wh |

- The 84.4 % equals the largest strongly connected component that Aaron found independently for E4, a cross-check that both pieces use the same graph.
- The cell block shrinks the 30 min zone from 92 % to 63 % of the box: detours around scarps lengthen the way back.
- The costliest return (286 Wh) is about 10 % of the xEMU budget (2813 Wh). So inside this box the binding limit is the 30 min time contingency, not energy, as the guide anticipates (section 15).

## Checks
- API tests with FastAPI's TestClient (`tests/api/test_api.py`): contract validation (422 on invalid budgets, margins, gravity, out-of-box points, duplicate ids, negative scores, unknown station types), PNG layers, walkback (return time and energy of a point 300 m from the base within physical bounds, R_T = R_E = 0 at the base, forward and return energies differ, invalid requests rejected), blocked fractions, GeoPackage round trip in a temporary folder (scores follow the edited rubric, DEM CRS kept).
- Visual checks with headless Edge screenshots: ortho and slope align, north up, layers blend, route and stations drawn in place, rubric edits update labels and point sizes live.

## Limitations
- The planner is not connected yet: `/plan` returns a fixed route and never claims feasibility.
- The walkback fields are provisional (computed here, not E4's `rv.tif`) and the base defaults to the box centre, which is illustrative; the habitat location is not fixed by the team yet.
- The rubric's empirical base is thin: one drill sample per setting, LPSC 2026 abstracts and JPL releases, no peer-reviewed paper on the in-situ campaign, no published TMAH result. Revisit when they appear.
- Additive scores can stack near-duplicate stations; BASALT removed redundant locations. Not handled yet (options: minimum distance between stations of the same type, or one station per site with the maximum of its types).
- A contact station only makes sense if the 2 × 2 km box contains a real contact between units; to be checked on the map.
- Station placement is manual and subjective; the HUD makes it explicit and editable, it does not remove it.

## What other pieces can use
- **E5 (Diana):** `data/stations/stations_manual.gpkg` (layer `stations`, columns above). Proposed sensitivity analysis for the E5 results: rubrics S0 5/4/3/3, S1 5/4/4/3 (default), S2 all equal, S3 NASA-like 3/2/2/1, S4 contact first 4/4/5/3, S5 hollow = ridge 5/5/4/3, S6 wide 9/4/4/1, S7 ≥ 500 random rubrics in 1–5 that keep the order of S1; budgets 0.5–1.2 × nominal; metrics: Jaccard of the station set against S1, Kendall's τ of the visiting order, share of the maximum score. The key output is the budget above which the route stops depending on the rubric [Smith2004] [Broddrick2024]. A complementarity bonus for visiting a ridge and its neighbouring hollow (the sampling unit Curiosity used) is a possible extension.
- **E4 (Aaron):** `/plan` already carries `max_cell_slope_deg` for the planner; R(v) and the 30 min line will be drawn from `rv.tif`.
- **E8 (JB):** Curiosity measurement sites are the ground truth for the ridge/hollow maps.
- **E12 (Juan):** the HUD reads `data/e12/` from his release `e12-dose-v1` (produced by `src/radiation/`); the walkback R_T at the astronaut is the same return time his alert uses (they agree within 0.0002 s).

## Reproduce
```
python -m pytest tests/api -q
python -m uvicorn api.main:app --port 8000      # then open http://localhost:8000/
```
Inputs: `data/base/` (base-grid-v2), `data/tiles/` (tiles-v2), `data/e2/` (e2-trajectory-v1).

## Outputs
- `data/stations/stations_manual.gpkg` and `stations_rubric.json` (written from the HUD; not in git).
- `docs/research/station_value_rubric.md` and `docs/research/station_value_notes/`.
