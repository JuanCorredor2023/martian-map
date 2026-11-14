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

Notes on PLACES:

- We use `localized_interp.csv`, not the `_demv2` variant: that one is tied to another DEM version, about +56 m in height and up to 22 m of horizontal shift against DEM v3.
- Only `ROVER` rows are used. `SITE` rows (`drive = -1`) are site-frame origins, not poses; each one repeats an existing `ROVER` pose and has no orientation. That is why there are 5,247 poses here and 5,257 points in the trajectory layer of JB's base grid package, which also includes the 10 `SITE` rows.
