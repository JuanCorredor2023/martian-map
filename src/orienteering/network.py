"""
E5 on top of the E4 grid graph (grafos, Aaron): loading, habitat placement,
station-to-station matrix and the cell path of each leg.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grafos.graph import Graph, follow  # noqa: E402

from orienteering.data_io import BASE_DIR  # noqa: E402


"""
Loads the E4 graph from data/base (edges_e3.npz, grid.json, crs.wkt) and the mask
of its largest strongly connected component (the cells you can go to and come back
from), from Graph.main_component (cached in the graph).
Returns (graph, main_cc) with main_cc a bool array of the grid's shape.
"""
def load_graph(base_dir=BASE_DIR):
    graph = Graph.from_base_dir(base_dir)
    return graph, graph.main_component()


"""
Places the habitat exactly as E4 and /plan do (Graph.place): if its cell is blocked
or outside the main component it moves to the nearest valid cell.
Returns (row, col, moved_m); use graph.cell_to_xy(row, col) for the coordinates shared
with E4 and E12. Raises ValueError if xy is outside the grid.
"""
def place_habitat(graph, xy):
    return graph.place(*xy, label="habitat")


"""
Tells which stations sit inside the main component, i.e. can be reached from
the habitat and can return to it.
"""
def reachable_stations(main_cc, stations):
    return main_cc[stations.row, stations.col]


"""
Directed cost matrix between stations: dis[i][j] is the minimum cost from station i
to station j (one Dijkstra per station, grafos Graph.cost_matrix).
weight: "energy_j" (J) or "time_s" (s). It is not symmetric.
"""
def station_matrix(graph, stations, weight="energy_j"):
    return graph.cost_matrix(graph.node(stations.row, stations.col), weight)


"""
Energy and time matrices between stations, both measured along the same legs:
energy[i][j] is the minimum energy from station i to station j, and time[i][j] is
the walking time along that minimum-energy leg (not the fastest leg), so the
solver's times match the route that is actually walked. One Dijkstra per station.
Unreachable pairs are np.inf in both.
"""
def station_matrices(graph, stations):
    ids = graph.node(stations.row, stations.col)
    n = len(ids)
    energy = np.full((n, n), np.inf)
    time = np.full((n, n), np.inf)

    for i, src in enumerate(ids):
        dist, pred = graph.costs_from(int(src), "energy_j", predecessors=True)
        energy[i] = dist[ids]
        for j, dst in enumerate(ids):
            if i == j:
                time[i, j] = 0.0
            elif np.isfinite(energy[i, j]):
                leg = follow(pred, int(dst), end=int(src))[::-1]
                time[i, j] = graph.path_cost(leg, "time_s")[-1]
    return energy, time


"""
Node path (cell ids) of the cheapest leg from node a to node b.
limit: known cost of the leg (e.g. from station_matrix); the search stops there,
which is much faster than a search over the whole grid.
Raises ValueError if b is unreachable from a.
"""
def leg_path(graph, a, b, weight="energy_j", limit=np.inf):
    if a == b:
        return np.array([a], dtype=np.int64)
    limit = limit * (1 + 1e-9) + 1e-6 if np.isfinite(limit) else np.inf
    _, pred = graph.costs_from(a, weight, limit=limit, predecessors=True)
    return follow(pred, b, end=a)[::-1]


"""
Full cell path of a tour (station indices, from start to end).
    dis : station matrix used by the solver, to bound each leg's search
Returns (path, stop_index): path is the node id of every cell visited, in order;
stop_index[k] is the position in path of the k-th stop of the tour.
"""
def route_path(graph, stations, route, dis=None, weight="energy_j"):
    nodes = graph.node(stations.row, stations.col)
    path, stop_index = [int(nodes[route[0]])], [0]

    for a, b in zip(route, route[1:]):
        limit = dis[a][b] if dis is not None else np.inf
        leg = leg_path(graph, int(nodes[a]), int(nodes[b]), weight, limit)
        path.extend(int(v) for v in leg[1:])
        stop_index.append(len(path) - 1)

    return np.array(path, dtype=np.int64), stop_index
