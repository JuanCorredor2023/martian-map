"""Directed 8-neighbour graph over the base grid (issue #7).

Node id = row * width + col (row 0 = north). Edge weights come from E3
(`edges_e3.npz`, Sebas): arrays of shape (8, rows, cols) where
weight[k, r, c] is the cost of moving from (r, c) to its neighbour k,
k following fisica.edge_cost.NEIGHBOURS (N, NE, E, SE, S, SW, W, NW).
NaN = no edge.

Units inside the engine: J (energy), s (time), m (length).

Shortest paths use scipy.sparse.csgraph.dijkstra (compiled), so one search
over the whole 4 M-node grid takes well under a second.
"""

import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components, dijkstra

WEIGHTS = ("energy_j", "time_s", "length_m")


class Graph:
    """Directed grid graph with one CSR matrix per weight, built lazily."""

    def __init__(self, edges, neighbours, transform=None, crs_wkt=None):
        """edges: dict weight name -> float array (8, rows, cols), NaN = no edge.
        neighbours: list of 8 (d_row, d_col).
        transform: affine (a, b, c, d, e, f) of the grid (rasterio order)."""
        neighbours = [tuple(int(v) for v in n) for n in neighbours]
        if len(neighbours) != 8:
            raise ValueError("expected 8 neighbours")
        self.neighbours = neighbours
        first = next(iter(edges.values()))
        self.shape = first.shape[1:]
        self.height, self.width = self.shape
        self.n = self.height * self.width
        self.transform = transform
        self.crs_wkt = crs_wkt

        # Length is implied by the topology of the edges that exist.
        valid = np.isfinite(first)
        lengths = np.array([np.sqrt(2.0) if dr and dc else 1.0 for dr, dc in neighbours])
        cell = abs(transform[0]) if transform is not None else 1.0
        edges = dict(edges)
        edges.setdefault("length_m", np.where(valid, (lengths * cell)[:, None, None], np.nan))
        for name, w in edges.items():
            if w.shape != first.shape:
                raise ValueError(f"{name}: shape {w.shape} != {first.shape}")
            if np.nanmin(w) < 0:
                raise ValueError(f"{name}: negative weights break Dijkstra")
        self._edges = edges
        self._csr = {}

    # ------------------------------------------------------------------ build
    @classmethod
    def from_npz(cls, npz_path, grid_json=None, crs_wkt=None):
        """Load the E3 contract file. grid_json gives the affine transform."""
        z = np.load(npz_path)
        edges = {k: z[k] for k in ("energy_j", "time_s") if k in z.files}
        transform = None
        if grid_json is not None:
            g = json.loads(Path(grid_json).read_text(encoding="utf-8"))
            transform = tuple(g["grid_1m"]["affine"])
        wkt = Path(crs_wkt).read_text(encoding="utf-8").strip() if crs_wkt else None
        return cls(edges, z["neighbours"], transform=transform, crs_wkt=wkt)

    @classmethod
    def from_base_dir(cls, base_dir):
        """Load data/base/edges_e3.npz + grid.json + crs.wkt."""
        base = Path(base_dir)
        return cls.from_npz(base / "edges_e3.npz", base / "grid.json", base / "crs.wkt")

    def _sources_targets(self, name):
        w = self._edges[name]
        idx = np.arange(self.n, dtype=np.int64).reshape(self.shape)
        src, dst, val = [], [], []
        for k, (dr, dc) in enumerate(self.neighbours):
            m = np.isfinite(w[k])
            s = idx[m]
            src.append(s)
            dst.append(s + dr * self.width + dc)
            val.append(w[k][m].astype(np.float64))
        return np.concatenate(src), np.concatenate(dst), np.concatenate(val)

    def csr(self, weight="energy_j", reverse=False):
        """CSR adjacency. reverse=True swaps every arc (u->v becomes v->u) and
        keeps the cost of the ORIGINAL arc: a search from the habitat on it gives
        the cost of going from each cell TO the habitat."""
        key = (weight, reverse)
        if key not in self._csr:
            s, d, v = self._sources_targets(weight)
            if reverse:
                s, d = d, s
            self._csr[key] = sparse.csr_matrix((v, (s, d)), shape=(self.n, self.n))
        return self._csr[key]

    # ------------------------------------------------------- cells and nodes
    def node(self, row, col):
        return np.asarray(row) * self.width + np.asarray(col)

    def cell(self, node):
        return np.divmod(np.asarray(node), self.width)

    def xy_to_cell(self, x, y):
        a, _, c, _, e, f = self.transform[:6]
        col = np.floor((np.asarray(x) - c) / a).astype(int)
        row = np.floor((np.asarray(y) - f) / e).astype(int)
        return row, col

    def cell_to_xy(self, row, col):
        """Centre of the cell, in CRS metres."""
        a, _, c, _, e, f = self.transform[:6]
        return c + (np.asarray(col) + 0.5) * a, f + (np.asarray(row) + 0.5) * e

    def out_degree(self):
        return np.diff(self.csr("energy_j").indptr)

    def components(self):
        """Strongly connected components: (labels, size of each label)."""
        _, labels = connected_components(self.csr("energy_j"), directed=True,
                                         connection="strong")
        return labels, np.bincount(labels)

    def snap(self, row, col, mask=None, max_radius=50):
        """Nearest cell (Chebyshev rings) with outgoing edges and inside `mask`
        (bool array over the grid, e.g. the largest component). Returns (row, col)."""
        ok = (self.out_degree() > 0).reshape(self.shape)
        if mask is not None:
            ok &= mask
        for r in range(max_radius + 1):
            r0, r1 = max(row - r, 0), min(row + r + 1, self.height)
            c0, c1 = max(col - r, 0), min(col + r + 1, self.width)
            rr, cc = np.nonzero(ok[r0:r1, c0:c1])
            if len(rr):
                rr, cc = rr + r0, cc + c0
                i = np.argmin((rr - row) ** 2 + (cc - col) ** 2)
                return int(rr[i]), int(cc[i])
        raise ValueError(f"no walkable cell within {max_radius} cells of ({row}, {col})")

    # --------------------------------------------------------- shortest paths
    def costs_from(self, source, weight="energy_j", limit=np.inf, predecessors=False):
        """Minimum cost from `source` (node id) to every node. inf = unreachable."""
        return dijkstra(self.csr(weight), indices=int(source), limit=limit,
                        return_predecessors=predecessors)

    def costs_to(self, target, weight="energy_j", limit=np.inf, predecessors=False):
        """Minimum cost from every node to `target`, on the reversed graph.
        With predecessors=True, pred[v] is the NEXT node from v towards target."""
        return dijkstra(self.csr(weight, reverse=True), indices=int(target), limit=limit,
                        return_predecessors=predecessors)

    def cost_matrix(self, nodes, weight="energy_j"):
        """Directed cost matrix between `nodes`: M[i, j] = min cost i -> j."""
        nodes = np.asarray(nodes, dtype=np.int64)
        d = dijkstra(self.csr(weight), indices=nodes)
        return d[:, nodes]

    def path_cost(self, path, weight="energy_j"):
        """Cumulative cost along a node path (array starting at 0)."""
        path = np.asarray(path, dtype=np.int64)
        m = self.csr(weight)
        step = np.asarray(m[path[:-1], path[1:]]).ravel()
        if np.any(step == 0):
            bad = int(np.argmax(step == 0))
            raise ValueError(f"no edge {path[bad]} -> {path[bad + 1]}")
        return np.concatenate([[0.0], np.cumsum(step)])


def follow(pred, start, end=None):
    """Walk a predecessor array from `start` until -9999 (scipy's 'no predecessor').

    For a forward search from s, call follow(pred, v) and reverse the result to get
    s -> v. For costs_to(t), follow(pred, v) already gives v -> t."""
    out = [int(start)]
    while pred[out[-1]] >= 0:
        out.append(int(pred[out[-1]]))
        if len(out) > len(pred):
            raise RuntimeError("cycle in predecessor array")
    if end is not None and out[-1] != end:
        raise ValueError("unreachable")
    return np.array(out, dtype=np.int64)
