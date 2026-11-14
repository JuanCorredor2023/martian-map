"""
Directed graph of the base grid and station-to-station costs with Dijkstra.
"""
import numpy as np
from scipy.sparse import csgraph, csr_matrix


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
