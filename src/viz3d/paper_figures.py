"""Figures for the P1 paper note (paper/notes/P1_3d_map.md).

Run from the repo root:
    python src/viz3d/paper_figures.py [--data-dir data]

Writes paper/figures/p1_fig1_relief_exaggeration.jpg: the local relief of a
600 x 600 m window shaded from the west, exaggerated 1, 3, 5 and 10 times, from the
raw 1 m DEM (top) and after the 3 m Gaussian used by the 3D map (bottom), next to
the orthophoto of the same window. It is the evidence for two choices of
build_terrain_assets.py: smoothing the local relief and capping the slider at x5.
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from viz3d.build_terrain_assets import DETAIL_SIGMA_M, LOW_SIGMA_M, slopes  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FIG = REPO / "paper" / "figures"
WINDOW = (900, 700, 600)            # row, col, side (m): knolls, a scarp and boxwork
LIGHT_AZ_EL = (270.0, 35.0)         # from the west, 35 degrees above the horizon
KS = (1, 3, 5, 10)


def shade(d_east, d_north, k):
    """Lambert shading of a surface whose slopes are k times the given ones."""
    az, el = np.radians(LIGHT_AZ_EL)
    light = (np.sin(az) * np.cos(el), np.cos(az) * np.cos(el), np.sin(el))   # east, north, up
    nx, ny = -k * d_east, -k * d_north
    return np.clip((nx * light[0] + ny * light[1] + light[2]) / np.sqrt(nx * nx + ny * ny + 1), 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.environ.get("MARTIAN_DATA", str(REPO / "data")))
    base = Path(ap.parse_args().data_dir) / "base"
    r0, c0, n = WINDOW
    with rasterio.open(base / "dem_1m.tif") as src:
        dem = src.read(1).astype(np.float64)
    with rasterio.open(base / "ortho_color_025.tif") as src:
        ortho = np.transpose(src.read(window=((r0 * 4, (r0 + n) * 4), (c0 * 4, (c0 + n) * 4)),
                                      out_shape=(3, n, n)), (1, 2, 0))
    raw = dem - ndi.gaussian_filter(dem, LOW_SIGMA_M, mode="reflect")
    smooth = ndi.gaussian_filter(raw, DETAIL_SIGMA_M, mode="reflect")
    win = (slice(r0, r0 + n), slice(c0, c0 + n))

    fig, axes = plt.subplots(2, len(KS) + 1, figsize=(15, 6.3), dpi=110)
    rows = ((f"1 m DEM minus hillside (raw)", raw),
            (f"same, Gaussian {DETAIL_SIGMA_M:g} m (used)", smooth))
    for r, (label, field) in enumerate(rows):
        d_east, d_north = slopes(field)
        for c, k in enumerate(KS):
            ax = axes[r, c]
            ax.imshow(shade(d_east[win], d_north[win], k), cmap="gray", vmin=0, vmax=1)
            ax.set_title(f"local relief ×{k}" + (" (not offered)" if k > 5 else ""), fontsize=10)
            if c == 0:
                ax.set_ylabel(label, fontsize=10)
    axes[0, -1].imshow(ortho)
    axes[0, -1].set_title("HiRISE orthophoto, same window", fontsize=10)
    axes[1, -1].axis("off")
    axes[1, -1].text(0.0, 0.95, f"Window {n} × {n} m, north up.\nLight from the west, "
                     f"{LIGHT_AZ_EL[1]:g}° high.\nHillside = Gaussian {LOW_SIGMA_M:g} m of the DEM.",
                     va="top", fontsize=10, transform=axes[1, -1].transAxes)
    for ax in axes.flat:
        ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    out = FIG / "p1_fig1_relief_exaggeration.jpg"
    fig.savefig(out, pil_kwargs={"quality": 82})
    print(out, f"{out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
