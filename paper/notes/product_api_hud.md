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

### Implied trade-offs (orienteering adds scores)
- One ridge (5) is worth less than two Curiosity sites (6).
- Hollow + contact (8) ties ridge + Curiosity site (8); the E3/E4 cost breaks the tie.

## Results
- Blocked share of the box by the cell limit: 12.4 % at 30°, 29.6 % at 20° (`/layers/blocked`, from `slope_deg.tif`).
- Cost layer colour scale starts at 0.0941 Wh per cell = 338.75 J/m, the analytic c_min,h of E3 (`/layers/cost`; test `test_cost_layer_png_and_legend`).
- Fixed test route: Curiosity's 3,900.3 m trajectory falls on the valley floor of the orthophoto, entering at cell (row 30, col 1999) as in E2.

## Checks
- API tests with FastAPI's TestClient (`tests/api/test_api.py`): contract validation (422 on invalid budgets, margins, gravity, out-of-box points, duplicate ids, negative scores, unknown station types), PNG layers, blocked fractions, GeoPackage round trip in a temporary folder (scores follow the edited rubric, DEM CRS kept).
- Visual checks with headless Edge screenshots: ortho and slope align, north up, layers blend, route and stations drawn in place, rubric edits update labels and point sizes live.

## Limitations
- The planner is not connected yet: `/plan` returns a fixed route and never claims feasibility.
- The rubric's empirical base is thin: one drill sample per setting, LPSC 2026 abstracts and JPL releases, no peer-reviewed paper on the in-situ campaign, no published TMAH result. Revisit when they appear.
- Additive scores can stack near-duplicate stations; BASALT removed redundant locations. Not handled yet (options: minimum distance between stations of the same type, or one station per site with the maximum of its types).
- A contact station only makes sense if the 2 × 2 km box contains a real contact between units; to be checked on the map.
- Station placement is manual and subjective; the HUD makes it explicit and editable, it does not remove it.

## What other pieces can use
- **E5 (Diana):** `data/stations/stations_manual.gpkg` (layer `stations`, columns above). Proposed sensitivity analysis for the E5 results: rubrics S0 5/4/3/3, S1 5/4/4/3 (default), S2 all equal, S3 NASA-like 3/2/2/1, S4 contact first 4/4/5/3, S5 hollow = ridge 5/5/4/3, S6 wide 9/4/4/1, S7 ≥ 500 random rubrics in 1–5 that keep the order of S1; budgets 0.5–1.2 × nominal; metrics: Jaccard of the station set against S1, Kendall's τ of the visiting order, share of the maximum score. The key output is the budget above which the route stops depending on the rubric [Smith2004] [Broddrick2024]. A complementarity bonus for visiting a ridge and its neighbouring hollow (the sampling unit Curiosity used) is a possible extension.
- **E4 (Aaron):** `/plan` already carries `max_cell_slope_deg` for the planner; R(v) and the 30 min line will be drawn from `rv.tif`.
- **E8 (JB):** Curiosity measurement sites are the ground truth for the ridge/hollow maps.

## Reproduce
```
python -m pytest tests/api -q
python -m uvicorn api.main:app --port 8000      # then open http://localhost:8000/
```
Inputs: `data/base/` (base-grid-v2), `data/tiles/` (tiles-v2), `data/e2/` (e2-trajectory-v1).

## Outputs
- `data/stations/stations_manual.gpkg` and `stations_rubric.json` (written from the HUD; not in git).
- `docs/research/station_value_rubric.md` and `docs/research/station_value_notes/`.
