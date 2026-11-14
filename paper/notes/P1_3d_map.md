# P1 · 3D map of the boxwork box (terrain, route rehearsal)

Owner: Juan (`@JuanCorredor2023`) · Issue: #42 · PRs: this PR (block 1 of 6) · Status: in progress (terrain done; route, rehearsal camera, Mars sun and shadows to do) · Last update: 2026-11-14

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
- A separate page at `/3d/`, served by the existing static mount; three.js is vendored (`web/3d/vendor/`, 10 files, MIT) so the page needs no internet.
- three.js instead of deck.gl's `TerrainLayer` inside the HUD: shadows and terrain draping are experimental in deck.gl 9.1, live exaggeration reloads the mesh there, and a separate page does not collide with the HUD work.
- Scene axes: X east, Y up, Z south, origin at the box centre. CRS coordinates (about 8.1 × 10⁶ m) are shifted in JavaScript (64-bit) before reaching the GPU (32-bit).
- No custom shaders: `MeshStandardMaterial` with the photo and the normal map. In the high preset the four photo tiles share one UV set through per-texture transforms.
- Rendering on demand (only when the camera moves), map-style controls, a compass, and a readout of CRS position and elevation.

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
- **Low preset shades like the high preset:** the same check gives the same numbers for `q=low` and `q=high` (k = 3: 0.939 / 0.946 against 0.940 / 0.946; mean brightness equal to 0.01 on a 0–255 scale).

## Limitations
- The DEM does not resolve the boxwork ridges; neither the geometry nor the shading shows them. Only the photo does.
- The local relief is a smoothed field: at k > 1 small real features below about 6 m across are not exaggerated, and what is exaggerated is no longer to scale. Shading is exaggerated with it.
- The photo carries its own illumination (HiRISE images are taken in the mid-afternoon); the synthetic light is added on top.
- DEM mosaic seams are visible as straight lines in the raw local relief (fig. 1, top row); the smoothing attenuates them but does not remove them.
- At eye height the ground will look blurred: the photo has 0.25 m pixels. This matters for the rehearsal camera (later block) and is what P3 (real Curiosity images) addresses.
- Performance is measured on one laptop; no tablet was available.

## What other pieces can use
- `data/tiles/3d/terrain.json` and the three height grids: a ready 2 m DEM, its smooth hillside and its local relief (any browser view; P3, Juan).
- The hillside / local relief split (σ = 25 m and 3 m) and fig. 1 as evidence of the DEM's pixel-scale noise (E8, JB; E3 slope-scale discussion, Sebas).
- `web/3d/terrain.js`: `toLocal`/`toMars` and `heightAt` for anything drawn on the terrain (P3).

## Reproduce
From the repo root, with `data/base/` in place (`base-grid-v2`):
```
python src/viz3d/build_terrain_assets.py      # writes data/tiles/3d/ (about 4 s)
python -m pytest tests/viz3d -q
python src/viz3d/paper_figures.py             # paper/figures/p1_fig1_relief_exaggeration.jpg
python -m uvicorn api.main:app --port 8000    # then open http://localhost:8000/3d/
```
`MARTIAN_DATA` selects another data folder, as in `api/main.py`. **`data/tiles/3d/` is not in the `tiles-v2` release:** if `data/tiles/` is downloaded or unzipped again, run the first command again. Without it the page shows that command.

## Outputs
- `data/tiles/3d/` (not in git, not in a release: rebuilt by the script).
- `paper/figures/p1_fig1_relief_exaggeration.jpg`.
