"""Build the E3 cost layers from a DEM GeoTIFF on the base grid.

Usage:
    python src/fisica/build_cost_layers.py DEM.tif OUT_DIR [--max-slope 20]

Writes to OUT_DIR:
    costo_e3.tif   display layer (contract: float32, Wh, same grid as the DEM):
                   mean energy to cross one cell (1 m horizontal), averaged over
                   the cell's valid outgoing edges. NaN = no valid edge.
    edges_e3.npz   the directed costs the planner must use (time_s, energy_j,
                   alpha_deg with shape (8, rows, cols), plus the NEIGHBOURS order).

The raster is only a summary for the HUD: planning must use the directed
edges, because cost(u -> v) != cost(v -> u).
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fisica.edge_cost import DEFAULT_MAX_SLOPE_DEG, NEIGHBOURS, edge_costs  # noqa: E402
from fisica.metabolico import J_PER_WH  # noqa: E402


def cell_cost_wh(energy_j, cell_size_m):
    """Mean Wh per metre-of-cell over valid outgoing edges, NaN if none."""
    lengths = np.array([cell_size_m * (np.sqrt(2) if dr and dc else 1.0)
                        for dr, dc in NEIGHBOURS], dtype=np.float32)
    per_metre = energy_j / lengths[:, None, None]      # NaN edges stay NaN
    mean_j = np.nanmean(per_metre, axis=0)
    return (mean_j * cell_size_m / J_PER_WH).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dem")
    ap.add_argument("out_dir")
    ap.add_argument("--max-slope", type=float, default=DEFAULT_MAX_SLOPE_DEG)
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.dem) as src:
        dem = src.read(1).astype(np.float64)
        if src.nodata is not None:
            dem[dem == src.nodata] = np.nan
        cell = abs(src.res[0])
        profile = src.profile.copy()

    time_s, energy_j, alpha = edge_costs(dem, cell_size_m=cell, max_slope_deg=args.max_slope)

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN cells -> NaN
        layer = cell_cost_wh(energy_j, cell)

    profile.update(dtype="float32", count=1, nodata=np.nan, compress="deflate")
    with rasterio.open(out / "costo_e3.tif", "w", **profile) as dst:
        dst.write(layer, 1)
    np.savez_compressed(out / "edges_e3.npz", time_s=time_s, energy_j=energy_j,
                        alpha_deg=alpha, neighbours=np.array(NEIGHBOURS),
                        max_slope_deg=args.max_slope)
    print(f"costo_e3.tif: Wh/cell min {np.nanmin(layer):.4f} median {np.nanmedian(layer):.4f} "
          f"max {np.nanmax(layer):.4f}, NaN {np.isnan(layer).mean() * 100:.1f}%")


if __name__ == "__main__":
    main()
