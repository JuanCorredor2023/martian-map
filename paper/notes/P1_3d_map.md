# P1 · 3D map of the boxwork box (terrain, route rehearsal)

Owner: Juan (`@JuanCorredor2023`) · Issue: #42 · PRs: #54 (block 1 of 6), #63 (block 2), this PR (block 3) · Status: in progress (terrain done; route, stations and habitat on the terrain done; route rehearsal at eye height done; rover photos, Mars sun and shadows to do) · Last update: 2026-11-14

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

### Rehearsing the route (`web/3d/rehearse_model.js`, `rehearse.js`, `card.js`)
"Rehearse the route" walks the planned route in first person before the EVA; "Exit" gives the free-flight view back as it was. The page still plans nothing: it plays the profile of the plan answer.

- **Time base.** The clock is the profile's `t_s` when the answer has one, so the walker moves at the planner's own pace (0.52 to 0.91 m/s on the E4 route). A stop is charged to the step that arrives at it: in the E4 answer `t_s` jumps 601.6 s over the last metre before the goal, which is 1.7 s of walking plus the 10 min of service. The model splits any step that is more than 5 times slower than the median pace, and more than 10 s longer than that, into a walk at the pace of the step before and a wait at its end; during the wait the walker stands on the vertex, energy and O₂ keep rising with the clock and the energy and time to return do not change. With no profile the time is distance at an assumed 1.0 m/s, and the screen says "assumed 1 m/s".
- **Profile values come from the true route**, linearly between its vertices, so at a vertex they are the answer's own numbers. The energy bar (used / needed to return / free of the usable budget) and its two lines of text repeat the arithmetic and the wording of the 2D planner's route profile.
- **Smoothed camera path, and why.** The planner moves cell to cell in eight directions, so the true path is a staircase that turns 45° at a vertex every metre or two: a camera walked along it shakes. The camera follows a copy of the route averaged along the path with a Gaussian of σ = 2.5 m (sampled every 0.5 m), pinned exactly at the route ends, at the stops and at the turn (the path is continued by its own mirror image through those points, so they do not move), and smoothed less wherever it would be more than 1.2 m from the true route, so it never cuts a corner by more than 1.5 m. Only the camera position and heading use this copy.
- **Heading** is the direction to the point 12 m further along the camera path (the 2D planner's heading arrow looks 12 vertices ahead), never beyond the next stop: looking past the point where the route turns back would spin the view. It is held over the last 3 m before a stop, and while the walker stands there it turns from the arrival to the departure direction. While playing, the view follows a change of heading with a time constant of 1/6 s.
- **Stops.** A stop is a vertex where the walker stands still, a vertex the answer lists (`stop_index` / `visit_order` of a tour), or the vertex nearest to a station that the answer marks as visited or as the goal, when it is within 3 m. Nothing assumes a single goal. Arriving at a stop while playing pauses and shows the station card (id, type label from `GET /stations/rubric`, score, service time, arrival time); play again runs the wait at the playback speed with the walker standing.
- **Camera.** Eye 1.7 m above the shown ground averaged over ±3 m of path (so it does not bob over every 2 m facet), never under 1.6 m above the ground right under it; vertical field of view 60°; near plane 0.3 m instead of the 2 m of free flight. Dragging looks around (offsets from the direction of travel, ±70° of pitch); double-click or "Recentre" looks forward. "Chase view" puts the camera 15 m behind the walker and 8 m above the ground it stands on, at least 2 m above the ground under the camera, with a 1.7 m marker for the walker.
- **True scale is forced, and why.** While rehearsing, the relief slider is locked at ×1 and says so; the previous value comes back on exit. The exaggeration is a reading aid from above. At eye height it would put a wall where there is a knoll, and the slopes the astronaut will walk are what the rehearsal is for.
- **Player.** Play / pause (also the space bar), ×1, ×30, ×60 (default) and ×180, a scrubber over the whole plan time, and "time of total · outbound or returning · metres". Frames are drawn only while playing, dragging or easing.
- **Walkback lines on pause.** As in the 2D planner, pausing asks `POST /walkback` for the 30 min return line (red) and the energy-safe boundary (cyan) from the walker's position with the energy left (usable − used, rounded as the 2D planner does), with the plan's own slope limit and habitat; the lines are draped on the mesh like the route and removed on play or exit. This request computes and answers only: `api/main.py` `walkback()` writes no file.
- **`flyTo`** (`controls.js`): an eased flight of about 1 s to a pose given as CRS position, eye height above the ground, heading, pitch and field of view. Clicking a pin in free flight shows the same card with "Fly here", which views the station from 60 m. A pose may be lower than 2 m and may look above the horizon (rover photo poses of a later block); the next gesture brings the free-flight limits back.

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

### Route rehearsal (block 3)
Plans used: the saved plan of this server on 2026-11-14, which is the E4 answer kept as `plan_e4.json` (1073 vertices, 1333.8 m, 2402.5 s, one stop: R0 at vertex 536), and `plan_fixed_route.json` (first 400 vertices of the fixed route, 332.2 m, no profile), given to the page with `viz3d.showPlan`. "Page" numbers come from `web/3d/checks.js` (`/3d/?check=rehearse`; for the fixed route the same function called from the console), high preset unless stated; "Node" numbers from `tests/viz3d/rehearse_model.test.mjs` (12 tests, `node --test`). Anything else was measured with `javascript` in the running page and is marked "manual".
- **Time base and stop** (Node). At every seventh vertex the state at `t_s[i]` is that vertex and the answer's own profile values (differences under 10⁻⁹). The stop is found at vertex 536 with station R0 (ridge, score 5, 10 min): arrival at 946.4 s, 599.9 s standing, during which the position and the energy to return are constant and the energy used rises to the answer's value. A hand-written tour gives its three stops, from `stop_index` or from the stations marked visited, and skips the station marked not visited; the fixed route gives none and a clock of distance / 1 m/s.
- **Walking the whole route** (page, real terrain, steps of 0.1 s of plan time: 24 027 for E4, 3324 for the fixed route).

| | E4 round trip | Fixed route (400 vertices) |
|---|---|---|
| Eye above the drawn ground under it | 1.600 to 1.897 m | 1.606 to 1.856 m |
| Largest camera move in one step | 0.090 m | 0.101 m |
| Fastest turn of the heading while walking | 3.98° per metre | 8.90° per metre |
| Camera path from the true route (every segment) | 0.81 m at most | 1.07 m at most |
| Chase camera above the ground under it | 3.1 m at least | 3.9 m at least |

  The same walk in Node (no terrain; made-up ground with ripples and a scarp for the eye) gives 3.98 and 8.90° per metre and 0.81 and 1.06 m, and asserts under 10° per metre, under 1.5 m, no camera move longer than the walker's own step and eye ≥ 1.6 m. At the E4 stop the view turns 180° on the spot, at most 0.25° per 0.1 s of plan time. Low preset (4 m mesh): eye 1.600 to 1.883 m, same turn and distance. A grid staircase 22° off the axes wobbles 0.22 m each way; its camera path wobbles under 0.02 m and its heading is within 1° of the true bearing; a right-angle corner is rounded by 0.99 m (Node).
- **Energy bar and texts** (Node). At vertices 0, 1, 250, 535, 536, 537, 800 and 1072 the three widths, "Energy used … · return needs … · free … of … Wh", "O₂ used … · back in … min" and "time of total · outbound/returning" equal the 2D planner's `showRouteIdx` formulas written out again on the raw answer.
- **Pause at the goal** (page, playback at ×60 through `update`): pauses at 946.4 s with the card "R0", and at the end, 2402.5 s. Manual, with the real frame loop: started 60 s of plan time before the stop, it paused there after 1.01 s; play again advanced 60 s of plan time in 1 s with the walker on the same spot.
- **Playback speed and frames** (manual, 1280 × 800 emulated viewport, high preset, real `requestAnimationFrame`): 181 frames in 3.01 s (60 fps, the display cap) for 180.9 s of plan time (×60.1). Paused in the rehearsal, and in free flight, no frame was drawn in 1 s.
- **Exit restores everything** (page): after entering and leaving twice the camera has moved 0 m and turned 0, and relief (×2), field of view (50°), near plane (2 m), slider, labels and the list of objects in the scene are equal to before. Manual, from a view that was not the opening one and relief ×3.5, leaving once with "Exit" and once with the panel button while playing: same result; 7 listeners added on the canvas and window per entry and 7 removed per exit; one more object in the scene while rehearsing (the walker) and none after; no geometry or texture left on the GPU; in free flight afterwards the space bar and a double-click change nothing and draw no frame, and a drag rotates as before. Reloading the plan while rehearsing also leaves the mode and restores the camera.
- **Looking around** (manual): a drag of 200 px right and 100 px down in an 800 px view turns the view 15° left and 7.5° up; huge drags stop at ±70°; double-click and "Recentre" return to forward. Rendered first-person frames at six times along the route have 31 to 42 % of sky and ground over the whole bottom quarter. In the chase view the pixel at the walker's projected position is the marker's colour in 38 of 40 samples along the route (in the other two it is behind the ground or a pin).
- **Fly here** (manual): 1.01 s; the camera ends 60.00 m from the station with the station 0.000° from the centre of the view, pitch 20°; 17, 55 and 90 % of the way at a quarter, half and three quarters of the time (eased). `flyTo` to an explicit pose (eye 1.9 m, looking 5.7° up, 35° field of view): position error 0 m, eye 1.900 m above the ground, heading, pitch and field of view as asked.
- **Walkback on pause** (manual): pausing at 721 s sent one `POST /walkback` with the walker's position and 832 Wh; two sets of lines were drawn (cyan 2.5 px, red 3 px), 37 148 segments, every end 0.300 m above the drawn ground; the server's return time from there is 671.4 s against the profile's 671.7 s, and its return energy 55.4 Wh against the profile's 54.3 Wh. Play removed the lines; an answer that arrived after leaving the rehearsal was dropped. The first answer took 8.4 s (the server computes the return fields once per base). No `POST /plan` was sent in any check; the saved plan file was not modified.
- **Plan states** (manual, page errors caught with `error` and `unhandledrejection` listeners): saved plan, button enabled ("40:03 of EVA, 1 stop"); no plan (stubbed 404), button disabled with "No route to rehearse: there is no plan." and entering refused; fixed route, button enabled with "assumed 1 m/s", no energy bar. No JavaScript error in any of them.
- **Small screen** (manual, 375 × 812 emulation, low preset): the player spans 8 to 367 px with nothing overflowing and one row of buttons; the card ends above it.
- **Earlier checks still hold**: `?check=shading` 0.940 / −0.506 and 0.946 / −0.409 at k = 3; `?check=route` 0.300 m at k = 1, 3 and 5, 1334.6 m drawn, 14 markers.

## Limitations
- The DEM does not resolve the boxwork ridges; neither the geometry nor the shading shows them. Only the photo does.
- The local relief is a smoothed field: at k > 1 small real features below about 6 m across are not exaggerated, and what is exaggerated is no longer to scale. Shading is exaggerated with it.
- The photo carries its own illumination (HiRISE images are taken in the mid-afternoon); the synthetic light is added on top.
- DEM mosaic seams are visible as straight lines in the raw local relief (fig. 1, top row); the smoothing attenuates them but does not remove them.
- At eye height the ground looks blurred: the photo has 0.25 m pixels and the eye is 1.7 m from it, and the 2 m facets of the mesh show. The rehearsal gives the lie of the land (slopes, horizon, where the route goes), not the surface underfoot; real Curiosity images (P3) address that.
- The walker's position is simulated: it is the plan played back on its own clock, not a position of the astronaut. With no profile even the pace is an assumption (1 m/s).
- The camera does not walk the planner's cells: its path is up to 0.8 m (E4 route) or 1.1 m (fixed route) from the true route, and nothing checks that the smoothed path avoids a blocked cell the route went around. Times, distances and energy are those of the true route.
- A stop's waiting time is inferred from the profile (a step far slower than its neighbours); a real step that slow would be shown as a short walk and a wait. At a stop with no waiting time the heading changes at once and only the on-screen easing softens it.
- Several stops were tested only with a hand-written tour (E5 is not in this checkout), and the fixed route only with its first 400 vertices: getting the whole route needs a `POST /plan`, which would replace the saved plan.
- The walkback lines come from `POST /walkback`, whose return energy differed by 2 % from the plan's own `rv_wh` at the point tested; the first request for a habitat takes several seconds. The radiation dose that the 2D profile text adds is not shown here.
- With the near plane at 0.3 m the depth buffer is coarser far away; whether the route line flickers against the ground at long range from eye height was not measured.
- The look of the first-person and chase views was judged from numbers (sky fraction, marker pixel) and one small capture, not from a careful visual review. Frames per second are from one laptop in an emulated viewport.
- After a `flyTo` pose that looks above the horizon, the first gesture tilts the view down to the free-flight limit (2°) and lifts the camera to 2 m.
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
- `web/3d/rehearse_model.js` (no dependencies): the state of a walker at any time of a plan (position, heading, stops, interpolated profile) and the split of a stop into walk and wait (guide screen, Sebas). `web/3d/card.js`: `showCard({title, subtitle, rows, note, media, actions})` and `controls.flyTo({x, y, eyeHeight, heading, pitch, fov})` for rover photo poses (P3).

## Reproduce
From the repo root, with `data/base/` in place (`base-grid-v2`):
```
python src/viz3d/build_terrain_assets.py      # writes data/tiles/3d/ (about 4 s)
python -m pytest tests/viz3d -q
node --test tests/viz3d/                      # camera maths, plan model and rehearsal model (Node 26; nothing to install)
python src/viz3d/paper_figures.py             # paper/figures/p1_fig1_relief_exaggeration.jpg
python -m uvicorn api.main:app --port 8000    # then open http://localhost:8000/3d/
```
Checks in the page: `/3d/?check=shading`, `/3d/?check=route`, `/3d/?check=rehearse` (add `&q=low` for the low preset); each shows its result as JSON.
`MARTIAN_DATA` selects another data folder, as in `api/main.py`. **`data/tiles/3d/` is not in the `tiles-v2` release:** if `data/tiles/` is downloaded or unzipped again, run the first command again. Without it the page shows that command.

## Outputs
- `data/tiles/3d/` (not in git, not in a release: rebuilt by the script).
- `paper/figures/p1_fig1_relief_exaggeration.jpg`.
