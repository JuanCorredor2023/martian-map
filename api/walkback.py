"""Return fields and walkback boundaries for the HUD (guide REV3, sections 20 and 34.3).

PROVISIONAL: E4 (Aaron) owns R(v). Until his rv.tif is delivered, the HUD uses
these fields, computed with the same E3 directed costs; swap the source when it
arrives.

- R_T(v): minimum TIME from v back to the base (s). The red line is R_T = 1800 s,
  the 30 min emergency-oxygen contingency. Cached per base.
- R_E(v): minimum ENERGY from v back to the base (J). Cached per base.
- F_E(p, v): minimum energy from the current position p to v (J), per request.
- Energy-safe region: F_E(p, v) + R_E(v) <= E_remaining (go to v and still get back).

R_T and R_E are Dijkstra runs from the base on the REVERSED graph, keeping the
cost of each original arc, so going down and coming back up are not mixed.
"""

import sys
from functools import lru_cache
from pathlib import Path

import contourpy
import numpy as np
import rasterio
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fisica.edge_cost import NEIGHBOURS, edge_costs  # noqa: E402


class Grid:
    """Base grid, its directed E3 costs and the two sparse graphs (time, energy)."""

    def __init__(self, base_dir, max_cell_slope_deg):
        with rasterio.open(f"{base_dir}/dem_1m.tif") as src:
            dem = src.read(1)
            self.transform = src.transform
        with rasterio.open(f"{base_dir}/slope_deg.tif") as src:
            slope = src.read(1)
        self.shape = dem.shape
        time_s, energy_j, _ = edge_costs(dem, cell_size_m=abs(self.transform.a),
                                         cell_slope_deg=slope,
                                         max_cell_slope_deg=max_cell_slope_deg)
        self.time = self._graph(time_s)
        self.energy = self._graph(energy_j)
        self.time_rev = self.time.T.tocsr()
        self.energy_rev = self.energy.T.tocsr()

    def _graph(self, weights):
        rows, cols = self.shape
        idx = np.arange(rows * cols).reshape(rows, cols)
        src, dst, data = [], [], []
        for k, (dr, dc) in enumerate(NEIGHBOURS):
            ok = np.isfinite(weights[k])
            r, c = np.nonzero(ok)
            src.append(idx[r, c])
            dst.append(idx[r + dr, c + dc])
            data.append(weights[k][ok].astype(np.float64))
        n = rows * cols
        return csr_matrix((np.concatenate(data), (np.concatenate(src), np.concatenate(dst))),
                          shape=(n, n))

    def cell(self, x, y):
        row, col = rasterio.transform.rowcol(self.transform, x, y)
        if not (0 <= row < self.shape[0] and 0 <= col < self.shape[1]):
            raise ValueError("point is outside the study box")
        return row, col

    def node(self, x, y):
        row, col = self.cell(x, y)
        return row * self.shape[1] + col

    def contour(self, field, level):
        """MultiLineString coordinates (metres, DEM CRS) of field == level."""
        f = np.where(np.isfinite(field), field, np.nan)
        lines = contourpy.contour_generator(z=f, line_type="Separate").lines(level)
        a, e, c, b, d, fy = (self.transform.a, self.transform.e, self.transform.c,
                             self.transform.b, self.transform.d, self.transform.f)
        out = []
        for line in lines:
            cols, rows = line[:, 0] + 0.5, line[:, 1] + 0.5     # cell centres
            xs = c + cols * a + rows * b
            ys = fy + cols * d + rows * e
            out.append(np.round(np.column_stack([xs, ys]), 2).tolist())
        return out


@lru_cache(maxsize=2)
def grid(base_dir, max_cell_slope_deg):
    return Grid(base_dir, max_cell_slope_deg)


@lru_cache(maxsize=8)
def return_fields(base_dir, max_cell_slope_deg, base_node):
    """(R_T in s, R_E in J) as 2-D arrays; inf where the base cannot be reached."""
    g = grid(base_dir, max_cell_slope_deg)
    r_t = dijkstra(g.time_rev, directed=True, indices=base_node).reshape(g.shape)
    r_e = dijkstra(g.energy_rev, directed=True, indices=base_node).reshape(g.shape)
    return r_t, r_e


def forward_energy(base_dir, max_cell_slope_deg, start_node, limit_j):
    g = grid(base_dir, max_cell_slope_deg)
    return dijkstra(g.energy, directed=True, indices=start_node, limit=limit_j).reshape(g.shape)
