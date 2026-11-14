# P1 · 3D map of the boxwork box (terrain, route rehearsal)

Owner: Juan (`@JuanCorredor2023`) · Issue: #42 · PRs: #54 (block 1 of 6), this PR (block 2) · Status: in progress (terrain done; route, stations and habitat on the terrain done; rehearsal camera, Mars sun and shadows to do) · Last update: 2026-11-14

## Question
What does the astronaut gain from seeing the planned EVA in 3D before leaving the habitat: the relief of the 2 × 2 km box, the planned route on the ground and a walk-through at eye height? This block answers the first part: how to show a 475 m hillside whose features of interest are 1–2 m high, in a browser, without overselling what the DEM contains.

## Data
- Base grid (JB, `base-grid-v2`): `dem_1m.tif` (2000 × 2000, 1 m) [Parker2016] and `ortho_color_025.tif` (8000 × 8000, 0.25 m) [HiRISE-Gale]. No cell is NaN in the box.
- Nothing is filtered out. The orthophoto is only resized (low preset) or cropped (high preset).

## Method

### Assets for the browser (`src/viz3d/build_terrain_assets.py` → `data/tiles/3d/`)
The output lives inside `data/tiles/` because the API already serves that folder at `/tiles/`: the 3D page needs no change in `api/`. It is **not** part of the `tiles-v2` release (see Reproduce).

| File | Content |
|---|---|
| `height_2m.bin` | DEM, mean of each 2 × 2 m block, 1000 × 1000 uint16 (step 7.2 mm) |
| `height_low_2m.bin` | "hillside": DEM smoothed with a Gaussian of σ = 25 m, same grid |
| `detail_2m.bin` | "local relief": Gaussian σ = 3 m of (DEM − hillside), same grid |
| `normal_detail.png` | tangent-space normal map of the local relief, 1000 × 1000 |
| `ortho_4096.jpg` | orthophoto of the whole box at 4096 px (0.49 m/px), low preset |
| `ortho_hi_<r><c>.jpg` | four 4096 px tiles at the native 0.25 m, overlapping 48 m, high preset |
| `terrain.json` | grid, encodings and the numbers quoted below |

- **Heights as numbers, not as an image.** A raw uint16 file is read exactly with one `fetch`; a height PNG would have to hide the value in colour channels, which browsers may alter (colour management, premultiplied alpha).
- **Two presets from the same files.** High: 2 m mesh, 2.0 M triangles, photo at 0.25 m. Low: the 2 m grid averaged to 4 m in the browser, 0.5 M triangles, one 4096 px photo.

### Exaggerating only the local relief
The box is a hillside: elevations span 475 m (−3876 to −3401 m) while knolls and scarps are metres high. A uniform vertical exaggeration would turn the hillside into a wall. The page draws

`shown = height + (k − 1) · detail`

so k = 1 is the DEM itself and k > 1 amplifies only the smoothed local relief. Whenever k ≠ 1 the screen says "Local relief ×k (exaggerated)".

**Why the local relief is smoothed, and why the slider stops at ×5.** At 1 m the DEM minus the hillside is dominated by a pebbly texture and by mosaic seams, not by landforms ([p1_fig1](../figures/p1_fig1_relief_exaggeration.jpg), top row). This agrees with the base grid note: the effective DEM resolution is coarser than 1 m. Exaggerating it exaggerates noise. A 3 m Gaussian keeps knolls, scarps and the lineated outcrop and removes most of the texture (bottom row). Even so, at ×10 half of the box would be shaded as steeper than 39°, so the page offers at most ×5 (`max_exaggeration` in `terrain.json`). Because the exaggeration term uses the smoothed field, the noise itself is never amplified: it stays at ×1 in the geometry.

### Shading: hillside normals plus a normal map
Vertex normals come from the hillside, and the local relief is shaded by a normal map with strength k. Consequences:
- Both presets shade the same, because the normal map does not depend on the mesh spacing.
- Moving the slider only rewrites vertex heights; no normals are recomputed.
- Slopes are stored multiplied by a gain of 4 so that small slopes survive 8 bits (decoding error < 0.02 in slope, test `test_normal_map_decodes_back_to_the_slopes`).

**What the shading shows.** Hillside, knolls and scarps. It does **not** show the boxwork ridges: they are 1–3 m wide and the DEM does not resolve them. In the 3D view the boxwork network is recognised by the HiRISE photo draped on the terrain. The page says so on screen.

### Page (`web/3d/`, three.js r187 [threejs], WebGL)
- A separate page at `/3d/`, served by the existing static mount; three.js is vendored (`web/3d/vendor/`, 8 files, MIT) so the page needs no internet.
- three.js instead of deck.gl's `TerrainLayer` inside the HUD: shadows and terrain draping are experimental in deck.gl 9.1, live exaggeration reloads the mesh there, and a separate page does not collide with the HUD work.
- Scene axes: X east, Y up, Z south, origin at the box centre. CRS coordinates (about 8.1 × 10⁶ m) are shifted in JavaScript (64-bit) before reaching the GPU (32-bit).
- No custom shaders: `MeshStandardMaterial` with the photo and the normal map. In the high preset the four photo tiles share one UV set through per-texture transforms.
- Rendering on demand (only when the camera moves), a compass, and a readout of CRS position and elevation.

### Camera: an arcball on the terrain (`web/3d/controls.js`, `web/3d/camera_math.js`)
three.js' stock map controls orbit around a target that drifts away from what the user is looking at, so they were replaced. Every gesture acts on the **terrain point under the cursor**, found by casting a ray against the height grid (step proportional to the height above ground, then bisection):
- **Rotate** (drag, or one finger): the view turns around that point, which stays fixed on screen. The camera has a heading and a tilt but never rolls, so the horizon stays level. A ring marks the point while rotating.
- **Move** (right-drag, Shift + drag, or two fingers): the grabbed point follows the cursor and the camera keeps its altitude.
- **Zoom** (wheel or pinch): towards that point, which stays under the cursor; two-finger twist turns the heading.
- If the cursor is off the terrain, rotation and zoom use the terrain at the centre of the screen (or the box centre), never a point in empty space. The camera stays at least 2 m above the ground. `?drag=pan` swaps the two mouse drags (map style).

### Route, stations and habitat on the terrain (`web/3d/plan_model.js`, `api.js`, `overlays.js`, `markers.js`)
Rule: the page draws what the plan answer contains, as is. It does not plan and does not assume where the route came from; every optional field (profile, turn, goal, totals) may be missing.

- **Where the plan comes from.** The page only reads: `GET /plan/last`, the last plan made in the 2D planner (the server answers `{request, plan}`; the page uses `plan`). **It never plans by itself.** The reason: the server saves every plan it makes as the last plan, and the guide screen on the arm tablet loads that one, so a page that planned on opening would silently replace the astronaut's plan. With no saved plan the page shows the terrain alone and says "No plan yet: plan an EVA in the 2D planner, then press Reload plan". A second button, "Plan with default settings" (or `?plan=default` in the address), sends the 2D planner's own default request when the user asks for it, and says that the result becomes the last plan: the saved stations scored by the rubric, 1000 Wh with a 10 % margin, 120 min, cells over 30° blocked, start at the box centre. If a request fails the terrain still works and the panel gives the server's reason. The panel shows the source, length, time, energy, the answer's warnings and a "Reload plan" button.
- **Plan model (no three.js, tested in Node).** The GeoJSON becomes routes, points and an optional per-vertex profile; a profile array is kept only if it has one value per vertex, and a bad field is listed as ignored instead of breaking the page. Each route is split so that no step is longer than 1 m; every new vertex keeps its fractional index into the original vertices and its cumulative 2D length, which is what the rehearsal (next block) needs to interpolate the profile and walk the route by time or by distance. The route is cut into outbound and return at `turn_index` when the answer has one.
- **Line draped on the mesh.** The route is drawn with fat lines (`Line2`, 4 px wide at any distance). Besides its own vertices the line gets a vertex wherever it crosses an edge of a terrain triangle (mesh column, row or cell diagonal), and every vertex is placed on the drawn triangles (`Terrain.surfaceAt`) plus 0.3 m. Between two consecutive vertices the ground is a plane, so the whole line, not only its vertices, is 0.3 m above the ground. Heights are recomputed when the relief slider moves.
- **Two legs, two passes.** Outbound in the 2D planner's cyan; the return leg in pink and shifted 0.8 m to the right of the direction of travel (direction taken over ±3 m, shift fading to zero over 4 m at both ends), because an E4 round trip returns along almost the same cells and one leg would hide the other. Each leg is drawn twice: solid with the depth test, and at 30 % opacity without it, so the route can be followed behind a knoll. The 1 m segments overlap on screen, so the faint pass uses the stencil buffer to paint each pixel once; without it the "faint" line adds up to a solid one (numbers in Checks).
- **Markers.** A generic layer takes `{id, x, y, kind, label, color, data}` in CRS metres and draws a pin (label, thin pole, ground dot) as a sprite of constant size on screen, never hidden by the terrain, like a map label. Stations take the 2D planner's colours by type (type from the answer, else from `GET /stations`, else grey); the station the route goes to is highlighted (filled label, taller pole); a station that a tour skipped (`visited: false`) is dimmed. The habitat is also a white dome 8 m across standing on the lowest ground under its rim. `pick()` returns the marker under a screen point using the painted pixels of the pin, and a click calls `onSelect` (hook for the station card and the rover photos of later blocks).
- **Relief slider** from ×1 to ×5 in steps of 0.5; the page now opens at ×2 (`?k=` changes it). Terrain, route, markers and the camera's floor follow it, at most once per frame.

## Results
Source of every number: `src/viz3d/build_terrain_assets.py` → `data/tiles/3d/terrain.json`, unless stated.

**Mesh error against the 1 m DEM** (`mesh_error_m`; block means, bilinear in between):

| Mesh spacing | Triangles | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| 2 m (high) | 1,996,002 | 0.03 m | 0.18 m | 0.29 m | 2.6 m |
| 4 m (low) | 498,002 | 0.09 m | 0.42 m | 0.67 m | 7.2 m |
| 8 m (fallback) | 124,002 | 0.17 m | 0.76 m | 1.24 m | 13.6 m |

The maxima are at scarps.

**Slope of the local relief once exaggerated** (`exaggeration_check_deg`, median / 90th percentile over the box):

| k | Smoothed 3 m (used) | Raw 1 m |
|---|---|---|
| 1 | 4.6° / 12.6° | 8.4° / 21.5° |
| 3 | 13.5° / 33.8° | 23.9° / 49.7° |
| 5 | 21.8° / 48.1° | 36.4° / 63.0° |
| 10 | 38.7° / 65.8° | 55.9° / 75.7° |

Local relief (smoothed): 1st to 99th percentile −3.9 to +6.9 m (`relief`).

**Size and speed.** Assets: 39 MB in total; the low preset downloads 15 MB. Build time 4 s. On the development laptop (NVIDIA T1000, Chromium) both presets run at the 60 fps display cap while the camera orbits: high at 1280 × 800, low in the browser's device emulation at 768 × 1024 and at 375 × 812 with pixel ratio 1.5 (`/3d/?q=low&fps=1&spin=1`, on-screen counter). Device emulation imitates the screen and touch, not a tablet's GPU: this is "the low preset on this laptop", not a measurement on a tablet.

## Checks
- **Assets against the DEM** (`tests/viz3d/test_terrain_assets.py`, 10 tests): stored heights equal the 2 × 2 m block means of the DEM within 2 cm everywhere; the north-west corner is the lowest and the south-east the highest, as in the DEM; slopes and normal map follow east and north with row 0 = north; a plane is reproduced with zero mesh error.
- **Orientation in the browser:** the four corners read from the running page are −3850.4 (NW), −3726.0 (NE), −3573.8 (SW) and −3401.3 m (SE), the DEM's values, and NW projects to the far left of a north-looking view.
- **Light from the right side** (`web/3d/checks.js`, `/3d/?check=shading`): the terrain without the photo is rendered from above lit from the north, south, east and west. The north-minus-south image correlates 0.94 with the north-facing slope of the shaded surface (hillside + k · detail) at k = 3; with the detail mirrored the correlation is −0.51, so a flipped normal map would be caught. East minus west: 0.95 against −0.41. At k = 1: 0.99 in both directions.
- **Camera maths** (`tests/viz3d/camera_math.test.mjs`, 11 tests, `node --test`): the rotation pivot keeps its screen position and its distance; a pan puts the grabbed point back under the cursor at the same altitude; picking hits a floor, a ramp and the near face of a wall, and misses outside the block. In the running page, with synthetic pointer events: after a 240 px rotation drag the pivot is at the same pixel (700, 450); after a pan the grabbed point is exactly under the cursor; after a wheel zoom the point under the cursor has not moved; a two-finger gesture that doubles the spread and twists 45° halves the distance and turns the heading 45° with the midpoint fixed.
- **Low preset shades like the high preset:** the same check gives the same numbers for `q=low` and `q=high` (k = 3: 0.939 / 0.946 against 0.940 / 0.946; mean brightness equal to 0.01 on a 0–255 scale).

### Route and markers (block 2)
Plan used: the answer of `POST /plan` of this server on 2026-11-14 to the default request (13 saved stations), kept whole as `tests/viz3d/fixtures/plan_e4.json`: an E4 round trip from the box centre to station R0, 1073 vertices, turn at vertex 536, 1333.8 m, 40 min, 196.9 Wh of 900 Wh usable. Second case: the answer to `stations: []`, the fixed test route with no profile (5247 vertices, 3900.3 m; its first 400 vertices are `plan_fixed_route.json`). Numbers below come from `web/3d/checks.js` run in the page (`/3d/?check=route`, also with `q=low`), unless stated.
- **Plan model** (`tests/viz3d/plan_model.test.mjs`, 14 tests, `node --test`): on both fixtures no step is longer than 1 m, all original vertices are kept, and the fractional index gives every new vertex back from the original ones to 10⁻⁶ m; the 2D length of the E4 vertices equals the answer's `length_m` (1333.8 m, given to 0.1 m); the turn vertex is the goal point; profile arrays are aligned with the vertices; the no-profile route, a tour written as `api/tour.py` writes it (several stops, no goal point) and malformed fields are all read without assuming a single goal; with a saved plan or with a 404, loading the plan sends no `POST` at all, and the default request is exactly one `POST /plan`.
- **Route above the ground.** For k = 1, 3 and 5, minimum height of the drawn line above the drawn terrain, at every vertex and at three points inside every segment: 0.300 m in all cases (E4 route: 2362 drawn vertices on the 2 m mesh, 2030 on the 4 m mesh; fixed route: 10 037 and 8049). Before the line was cut at the triangle edges the vertices were at 0.300 m but the inside of the segments went down to 0.21, 0.17 and 0.13 m (E4 route, 2 m mesh, k = 1, 3, 5) and to −0.03 m, under the ground, for the fixed route on the 4 m mesh at k = 5. `surfaceAt` against vertical rays cast on the real triangles at 42 route vertices per k: largest difference 10⁻⁶ m.
- **Length.** The drawn E4 route measures 1334.6 m in 2D against 1333.8 m declared (+0.06 %; the excess is the sideways shift of the return leg). Fixed route: 3900.3 m against 3900.3 m.
- **Markers.** 14 markers (habitat and 13 stations, R0 as the goal). Scene position converted back to CRS metres against the marker's coordinates: 0 to 10⁻⁶ m for all 14; Q1, R0 and C2 compared with `GET /stations`: same coordinates, colours of curiosity, ridge and contact. All station pins stand on the ground (0 m off `surfaceAt`) at k = 1, 3.5 and 5. Synthetic clicks on the labels of C1, C2, on Q1's ground dot and on the habitat select those markers; a 30 px drag ending on a label selects nothing and a point beside a pin picks nothing. (Measured with `javascript` in the running page, not in `checks.js`.)
- **Faint pass.** Opacity of the see-through pass alone, measured on every pixel it touches (rendered with and without it, 1280 × 800): with the stencil test mean 0.27 and maximum 0.30 from the opening view (2500 m), 0.26 and 0.31 from 500 m; without it mean 0.84–0.88 and maximum 1.00 from 2500 m. Same manual measurement: from 800, 2500, 3000 and 6000 m with nothing in between, 99.9–100 % of 1181 sampled route vertices show the solid pass (396 × 346 view), so the 0.3 m lift is enough for the depth buffer at those distances.
- **Relief slider and camera.** Moving the slider to 1, 3.5 and 5 updates the label, the route (0.300 m above the ground at a sampled vertex each time) and the pins in the next frame. With the camera 2 m above a spot whose local relief is +12.9 m at k = 1, going to k = 5 lifts the ground 51.6 m and leaves the camera 2.00 m above it.
- **Plan states in the page** (requests counted by wrapping `fetch` in the running page; "no plan" is a stubbed 404, the saved file was not touched). Saved plan present: route and 14 markers, no `POST`. No saved plan: nothing drawn, the "No plan yet" text and the default button appear, no `POST`. Default button pressed: one `POST /plan`, the route is drawn and the button goes away. With no saved stations the default request carries `stations: []` and the fixed route is drawn (one leg, no return, habitat only, both warnings shown). With no answer at all, or a 422, nothing is drawn, the panel gives the reason and the relief slider still works. No JavaScript error in any case; when there really is no saved plan the browser itself logs the 404 of `GET /plan/last`.
- **Earlier checks still hold.** The shading check hides route and markers while it measures and gives the same numbers as in block 1 (k = 3: 0.940 / −0.506 and 0.946 / −0.409). 60 fps at the display cap with route and markers, high preset, 1280 × 800 (`/3d/?fps=1&spin=1`).

## Limitations
- The DEM does not resolve the boxwork ridges; neither the geometry nor the shading shows them. Only the photo does.
- The local relief is a smoothed field: at k > 1 small real features below about 6 m across are not exaggerated, and what is exaggerated is no longer to scale. Shading is exaggerated with it.
- The photo carries its own illumination (HiRISE images are taken in the mid-afternoon); the synthetic light is added on top.
- DEM mosaic seams are visible as straight lines in the raw local relief (fig. 1, top row); the smoothing attenuates them but does not remove them.
- At eye height the ground will look blurred: the photo has 0.25 m pixels. This matters for the rehearsal camera (later block) and is what P3 (real Curiosity images) addresses.
- Performance is measured on one laptop; no tablet was available.
- The route shown is the planner's path on the 1 m grid, drawn as is: its steps in eight directions look like a zigzag from close up. The 0.8 m shift of the return leg is a drawing aid, not where the astronaut would walk, and beyond roughly 700 m (in a view 800 px high) it is under one pixel, so the two legs merge.
- Pins have the same size at any distance and are never hidden by the terrain: they give no cue of distance, and labels of stations a few metres apart (R0 and H0 are 10 m apart) overlap until the camera is close.
- "Plan with default settings" makes the server save its answer as the last plan (`data/plans/last_plan.json`): the guide screen will load it, and the next visit shows it as "last plan from the planner". The button says so, and the page never does it unasked.
- The multi-station tour (E5) was not in this checkout (`api/tour.py` reports it unavailable), so that answer was only tested with a hand-written example of the shape the code produces. The default request sends all saved stations; a tour solver with a station limit may refuse it, and the page then shows the reason and the terrain only.

## What other pieces can use
- `data/tiles/3d/terrain.json` and the three height grids: a ready 2 m DEM, its smooth hillside and its local relief (any browser view; P3, Juan).
- The hillside / local relief split (σ = 25 m and 3 m) and fig. 1 as evidence of the DEM's pixel-scale noise (E8, JB; E3 slope-scale discussion, Sebas).
- `web/3d/terrain.js`: `toLocal`/`toMars` and `heightAt` for anything drawn on the terrain (P3).
- `web/3d/plan_model.js` (no dependencies): reads any `/plan` answer, densifies the route to 1 m keeping the index into the profile. `web/3d/markers.js`: any list of points as pins, with `pick()` and `onSelect` (P3 rover photos).

## Reproduce
From the repo root, with `data/base/` in place (`base-grid-v2`):
```
python src/viz3d/build_terrain_assets.py      # writes data/tiles/3d/ (about 4 s)
python -m pytest tests/viz3d -q
node --test tests/viz3d/                      # camera maths and plan model (run with Node 26; nothing to install)
python src/viz3d/paper_figures.py             # paper/figures/p1_fig1_relief_exaggeration.jpg
python -m uvicorn api.main:app --port 8000    # then open http://localhost:8000/3d/
```
`MARTIAN_DATA` selects another data folder, as in `api/main.py`. **`data/tiles/3d/` is not in the `tiles-v2` release:** if `data/tiles/` is downloaded or unzipped again, run the first command again. Without it the page shows that command.

## Outputs
- `data/tiles/3d/` (not in git, not in a release: rebuilt by the script).
- `paper/figures/p1_fig1_relief_exaggeration.jpg`.
