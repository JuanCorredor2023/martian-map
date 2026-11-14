# src/ml · E2 and E1 (Juan)

Requires the `martian` environment (`environment.yml`) and JB's base grid in `data/base/`, downloaded from the `base-grid-v2` release (see the board). PLACES is looked up in `data/`, `data/raw/` or `../data`; if it lives elsewhere, set `MARTIAN_DATA`.

## Minimal E2: Curiosity's trajectory on the grid (#4)

```bash
python src/ml/trajectory_to_grid.py
python src/ml/plot_trajectory.py       # review image (optional)
```

Outputs in `data/e2/` (not tracked by git):

| File | Contents |
|---|---|
| `trajectory.gpkg` | Layers `route` (line) and `poses` (points), in the DEM CRS. This is the file to open in QGIS. |
| `trajectory.geojson` | The route as a `LineString`, one segment per entry into the box. Properties: `sol_start`, `sol_end`, `n_poses`, `length_m`. |
| `trajectory_poses.geojson` | One point per pose, with `site`, `drive`, `pose`, `sol`, `sclk`, `row`, `col`, `elev_places`, `elev_dem`, `dz` and `in_boxwork`. |
| `trajectory_cells.csv` | One row per cell the rover went through, including cells crossed by the line between poses. Columns: `row`, `col`, `x`, `y` (cell centre), `n_steps`, `first_step`, `sol_min`, `sol_max`, `n_poses`, `has_pose`. |
| `cell_sequence.csv` | The same cells in traversal order, without consecutive repeats. Every step moves to one of the 8 neighbours. This is the input for E1. |
| `summary.json` | DEM used, counts and checks. |

Conventions: `col = floor(E − XMIN)` and `row = floor(YMAX − N)` in metres, with row 0 at the top (north). This matches `rasterio.transform.rowcol` with the `dem_1m.tif` transform. The GeoJSON files are in metres, with the contract CRS in the `crs` member; GDAL reads it, but use the `.gpkg` in QGIS (format agreed in #2). `in_boxwork` flags sols 4541–4848, a provisional range the team still has to confirm.

## E2 hours 4–12: cell × feature table and logistic baseline (#4)

```bash
python src/ml/cell_features.py        # after trajectory_to_grid.py
python src/ml/logistic_baseline.py
```

The question: within reach of the route, do the terrain features tell where Curiosity drove? This baseline is the bar E1 has to beat.

- **Compared cells:** the visited cells against the not visited cells within 25, 50 (main) and 100 m of the route, plus the whole box as a reference. Cells closer than 2 m to the route are left out, because the rover is about 3 m wide.
- **Features:** `slope_deg`, `roughness`, `tpi`, and the mean slope in 5 × 5 and 15 × 15 m windows. There is no position, elevation or distance, so the model cannot guess by location.
- **Validation:** the route is split into 5 consecutive blocks by route order. Each block is scored by a model trained on the other four, and every cell inherits the block of its nearest visited cell.
- **Model:** a logistic regression on standardized features, with class-balanced weights, plus a slope-only model for comparison.

Outputs in `data/e2/`:

| File | Contents |
|---|---|
| `cell_features.parquet` | One row per cell (visited, or not visited 2–100 m from the route): `row`, `col`, `x`, `y`, the five features, `visited`, `dist_to_route_m`, `route_pos` and `sol` of the nearest visited cell, and `block`. |
| `logistic_baseline.json` | AUC per block, mean and pooled out-of-block AUC for every comparison set and model, the main model's standardized coefficients and feature medians. |
| `logistic_roc.png` | ROC curves for the 50 m corridor (out-of-block predictions). |
| `visit_probability.tif` | The main model applied to every cell, on the base grid. It is a relative 0–1 score of how route-like the terrain is, not a calibrated probability. |

Notes on PLACES:

- We use `localized_interp.csv`, not the `_demv2` variant: that one is tied to another DEM version, about +56 m in height and up to 22 m of horizontal shift against DEM v3.
- Only `ROVER` rows are used. `SITE` rows (`drive = -1`) are site-frame origins, not poses; each one repeats an existing `ROVER` pose and has no orientation. That is why there are 5,247 poses here and 5,257 points in the trajectory layer of JB's base grid package, which also includes the 10 `SITE` rows.
