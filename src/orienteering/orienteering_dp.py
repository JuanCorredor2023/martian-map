"""
DP de orienteering con máscara de bits sobre 10–12 estaciones sintéticas; 
lector del GeoPackage de estaciones del contrato
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from scipy.sparse import csgraph, csr_matrix

BASE_DIR = Path(__file__).resolve().parents[2] / "data" / "base"
GPKG_PATH = BASE_DIR / "trayecto_caja.gpkg"
NPZ_PATH = BASE_DIR / "edges_e3.npz"
GRID_PATH = BASE_DIR / "grid.json"

"""
Reads the 1 m base grid description (grid.json): origin of the top-left corner,
cell size and shape. Row 0 is the north edge.
"""
def read_grid(path=GRID_PATH):
    with open(path, encoding="utf-8") as file:
        g = json.load(file)["grid_1m"]
    return g["origin_x"], g["origin_y"], g["cell_size_m"], g["height"], g["width"]


"""
Reads a point layer from a GeoPackage and places every point on the base grid.
Returns five arrays, one entry per station:
    x, y: coordinates in the layer's CRS (Mars equirectangular metres)
    row, col: cell of the base grid that contains the point (index into the npz costs)
    p: prize of the point
Points outside the grid are dropped. Points falling in an already used cell are
dropped too (the first one is kept), so every station is a distinct graph node.
If the layer has a "tipo" column, "habitat" points are placed first, so the
habitat is station 0.
If prize_col is not a column of the layer, every point gets prize 1.
"""
def read_gpkg(path=GPKG_PATH, layer=None, prize_col="valor", grid_path=GRID_PATH):
    gdf = gpd.read_file(path, layer=layer)

    if "tipo" in gdf.columns:
        gdf = gdf.sort_values("tipo", key=lambda s: s != "habitat", kind="stable")
    gdf = gdf.reset_index(drop=True)

    x = gdf.geometry.x.to_numpy()
    y = gdf.geometry.y.to_numpy()
    if prize_col in gdf.columns:
        p = gdf[prize_col].to_numpy(dtype=float)
    else:
        p = np.ones(len(gdf))

    origin_x, origin_y, cell, height, width = read_grid(grid_path)
    col = np.floor((x - origin_x) / cell).astype(np.int64)
    row = np.floor((origin_y - y) / cell).astype(np.int64)

    inside = (row >= 0) & (row < height) & (col >= 0) & (col < width)
    x, y, row, col, p = x[inside], y[inside], row[inside], col[inside], p[inside]

    _, first = np.unique(row * width + col, return_index=True)
    keep = np.sort(first)

    return x[keep], y[keep], row[keep], col[keep], p[keep]

"""
Reads the directed edge costs of E3 (edges_e3.npz) and returns:
    cost: float array (8, rows, cols); cost[k, r, c] is the cost of moving from
          cell (r, c) to its neighbour k. Missing edges (off-grid, nodata,
          too steep) are np.inf instead of NaN.
    neighbours: int array (8, 2) with the (d_row, d_col) of each k
                (N, NE, E, SE, S, SW, W, NW; rows grow southwards).
kind selects the cost: "energy_j" (joules) or "time_s" (seconds).
"""
def read_npz(path=NPZ_PATH, kind="energy_j"):
    if kind not in ("energy_j", "time_s"):
        raise ValueError(f"kind must be 'energy_j' or 'time_s', not {kind!r}")

    with np.load(path) as data:
        cost = data[kind].astype(np.float64)
        neighbours = data["neighbours"].astype(np.int64)

    cost[~np.isfinite(cost)] = np.inf
    return cost, neighbours


"""
Tells which stations sit on a cell with no usable outgoing edge (blocked
or nodata), so they can't be reached or left on the cost graph.
"""
def blocked_stations(cost, row, col):
    return ~np.isfinite(cost[:, row, col]).any(axis=0)


"""
Flat node id of a grid cell: id = row * width + col.
"""
def cell_id(row, col, width):
    return np.asarray(row, dtype=np.int64) * width + np.asarray(col, dtype=np.int64)


"""
Builds the directed graph of the grid as a sparse CSR matrix (N x N, N = rows * cols).
graph[u, v] is the cost of moving from cell u to cell v; only finite edges are stored.
Built once and reused for every Dijkstra run.
"""
def build_graph(cost, neighbours):
    _, rows, cols = cost.shape
    r, c = np.indices((rows, cols))
    src_all, dst_all, w_all = [], [], []

    for k, (dr, dc) in enumerate(neighbours):
        nr, nc = r + dr, c + dc
        ok = np.isfinite(cost[k]) & (nr >= 0) & (nr < rows) & (nc >= 0) & (nc < cols)
        src_all.append((r[ok] * cols + c[ok]).astype(np.int32))
        dst_all.append((nr[ok] * cols + nc[ok]).astype(np.int32))
        w_all.append(cost[k][ok])

    n = rows * cols
    return csr_matrix((np.concatenate(w_all), (np.concatenate(src_all), np.concatenate(dst_all))),
                      shape=(n, n))


"""
Runs Dijkstra (scipy.sparse.csgraph, in C) on the directed grid graph:
    graph : CSR matrix from build_graph
    src : flat id of the starting cell (or a list of ids)
    return_predecessors : also return the predecessor of each cell, to rebuild routes
Returns the minimum cost from src to every cell (np.inf if unreachable).
"""
def dijkstra(graph, src, return_predecessors=False):
    return csgraph.dijkstra(graph, directed=True, indices=src,
                            return_predecessors=return_predecessors)


"""
Runs Dijkstra from every station and keeps only the costs to the other stations.
    graph : CSR matrix from build_graph
    row, col : grid cells of the stations
    width : number of columns of the grid
Returns an (n, n) matrix: dis[i][j] is the minimum cost from station i to station j.
It is not symmetric (going uphill costs more than going down).
"""
def calculate_distances(graph, row, col, width):
    ids = cell_id(row, col, width)
    dis = np.empty((len(ids), len(ids)))

    for i, node in enumerate(ids):
        dis[i] = dijkstra(graph, node)[ids]
    return dis


"""
Rebuilds the cell route from src to dst with the predecessors returned by
dijkstra(graph, src, return_predecessors=True). Returns (rows, cols) arrays,
or None if dst is unreachable.
"""
def path_cells(predecessors, src, dst, width):
    if src != dst and predecessors[dst] < 0:
        return None
    path = [dst]
    while path[-1] != src:
        path.append(predecessors[path[-1]])
    path = np.array(path[::-1])
    return path // width, path % width


"""
Bitmask DP to solve small instances of the orienteering problem (18-20 nodes).
By default it will trace a path starting and ending in node 0, this can be 
changed with parameters.
"""
def solve(dis, prize, cost, start=0, end=0):
    n = len(dis)
    if n > 20:
        return

    INF = float('inf')
    # n+1 columns, 2^n-1 rows
    dp = [[INF] * (n+1) for _ in range(1 << n)] 
    best, best_state  = 0, None

    for mask in range (1, 1 << n):
        for i in range(1, n+1):
            c = dp[mask][i]

            # If node is unreachable or the distance to go to that node would exceed cost, skip it
            if c == INF or c + dis[i][0] > cost:
                continue 

            # If its prize would be better, update it 
            if prize[mask] > best:
                best, best_state = prize[mask], (mask, i)

            # Update dp values for each submask in the mask 
            for j in range(1, n+1):
                bit = 1 << (j-1)
                if not mask & bit and c + dis[i][j] < dp[mask | bit][j]:
                    dp[mask  | bit][j] = c + dis[i][j]

    return best, best_state

def build_gpkg():
    pass

#if __name__ == "__main__":
    