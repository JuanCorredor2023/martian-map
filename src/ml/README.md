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

## E1: terrain cost learned from the route with MaxEnt IRL (#5)

The question: under which terrain prices is Curiosity's real route the most likely one? Maximum-entropy inverse reinforcement learning [Ziebart 2008]: a route is more likely the cheaper it is, `P(route) ∝ exp(−cost)`, and the prices are fitted so that the real route is as likely as possible. Every demonstration gets its start and goal, so the model learns *how* the rover went, not *where*.

```bash
python -m pytest tests/ml -q
python src/ml/irl_toy_check.py                          # synthetic check: recovers hidden prices
python src/ml/fit_irl.py                                # one demonstration per sol, 1 m, 50 m margin
python src/ml/validate_irl.py                           # leave-one-block-out (E2's 5 blocks)
python src/ml/fit_irl.py --piece-m 250 --cell 5 --whole-box
python src/ml/validate_irl.py --piece-m 250 --cell 5 --whole-box
python src/ml/irl_paper_figures.py                      # after every scale in its SCALES list
python src/ml/export_e1_weights.py                      # hand-off to E3 (data/e1/e1_weights.json)
```

| Script | What it does |
|---|---|
| `maxent_irl.py` | The method: move costs on the 8-neighbour grid (same `NEIGHBOURS` order as `src/fisica/edge_cost.py`), soft value iteration (backward pass), expected visits (forward pass), NLL and its gradient, L-BFGS-B fit with every weight ≥ 0. Runs on the GPU with PyTorch if there is one. |
| `irl_data.py` | Demonstrations from `data/e2/cell_sequence.csv`: one per sol (≥ 10 m) or route pieces of a given length, each in a window around it (or the whole box), with the E2 validation block. Features ≥ 0: `metre` (constant), `slope_deg`, `roughness`, `tpi_ridge`, `tpi_hollow` (TPI split by sign), `slope_mean_5m`, `slope_mean_15m`, each divided by its 99th percentile over the box. `--cell 5` averages them over 5 × 5 m cells. |
| `irl_toy_check.py` | Invented terrain with hidden prices: the fit must recover them, and the gradient must match PyTorch autograd and finite differences. |
| `fit_irl.py` | Fits the terrain model and the distance-only control (only the price of a metre) on every demonstration. |
| `validate_irl.py` | Fits on four E2 blocks and tests on the fifth: NLL per metre, Hausdorff and within-5/10 m of the cheapest predicted route, and the AUC of the learned cost on E2's comparison sets. |
| `irl_paper_figures.py` | `data/e1/e1_summary.json` and the figures `paper/figures/e1_fig2`–`e1_fig4`. |
| `export_e1_weights.py` | Hand-off to E3: `data/e1/e1_weights.json` in the format agreed in #2 (read by `fisica.human_cost`). Weights are handed over only if the terrain model beats the distance-only control on held-out blocks; otherwise they are 0 and the fitted values stay in `fitted_weight`. |

Outputs in `data/e1/` (not tracked by git), `<tag>` = demonstrations, cell size and window (for example `per_sol_cell1m_margin50m`, `piece250m_cell5m_box`):

| File | Contents |
|---|---|
| `toy_check.json` | Hidden and recovered prices (5 repeats), gradient check, NLL per metre of the fit, the hidden prices and the control. |
| `irl_fit_<tag>.json` | Weights of both models, NLL per metre, real vs expected feature counts, the preference check at the control's fit, and per-demonstration NLL. |
| `validation_<tag>.json` | Held-out metrics per block and overall, weights fitted without each block, AUC of the learned cost next to E2's. |
| `e1_summary.json` | The numbers quoted in the E1 note, gathered from the files above. |
| `e1_weights.json` | Weights for `fisica.human_cost` (E3 × terrain factor): per feature `weight`, `fitted_weight`, `raster`, `min`/`max`, `transform`, `slope`; plus `distance_weight`, `validated` and the held-out NLL. |

Prices are per cell length (1 m or 5 m of route); compare scales with `w_relative_to_metre`.

## Paper

`python src/ml/paper_figures.py` writes the E2 figures to `paper/figures/` (run it after the scripts above). The write-up of E2 is in `paper/notes/E2_curiosity_traverse.md`. E1: `python src/ml/irl_paper_figures.py` and `paper/notes/E1_maxent_irl.md`.

Notes on PLACES:

- We use `localized_interp.csv`, not the `_demv2` variant: that one is tied to another DEM version, about +56 m in height and up to 22 m of horizontal shift against DEM v3.
- Only `ROVER` rows are used. `SITE` rows (`drive = -1`) are site-frame origins, not poses; each one repeats an existing `ROVER` pose and has no orientation. That is why there are 5,247 poses here and 5,257 points in the trajectory layer of JB's base grid package, which also includes the 10 `SITE` rows.
