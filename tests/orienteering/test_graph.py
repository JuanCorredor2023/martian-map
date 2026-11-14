"""Grid graph and station-to-station costs on small synthetic cost grids."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from orienteering.graph import (blocked_stations, build_graph, calculate_distances,
                                cell_id, dijkstra, path_cells)

NEIGHBOURS = np.array([(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)])
N, E, S, W = 0, 2, 4, 6


def uniform_cost(rows, cols, value=1.0):
    cost = np.full((8, rows, cols), value)
    for k, (dr, dc) in enumerate(NEIGHBOURS):
        r, c = np.indices((rows, cols))
        off = (r + dr < 0) | (r + dr >= rows) | (c + dc < 0) | (c + dc >= cols)
        cost[k][off] = np.inf
    return cost


def test_straight_line_cost():
    cost = uniform_cost(1, 5)
    graph = build_graph(cost, NEIGHBOURS)
    dis = calculate_distances(graph, np.array([0, 0]), np.array([0, 4]), 5)
    assert dis[0, 1] == 4.0 and dis[1, 0] == 4.0 and dis[0, 0] == 0.0


def test_directed_costs_are_kept():
    cost = uniform_cost(1, 3)
    cost[E] = np.where(np.isfinite(cost[E]), 2.0, np.inf)
    graph = build_graph(cost, NEIGHBOURS)
    dis = calculate_distances(graph, np.array([0, 0]), np.array([0, 2]), 3)
    assert dis[0, 1] == 4.0 and dis[1, 0] == 2.0


def test_blocked_cell_is_detoured_and_flagged():
    cost = uniform_cost(3, 3)
    middle = (1, 1)
    cost[:, middle[0], middle[1]] = np.inf
    for k, (dr, dc) in enumerate(NEIGHBOURS):
        r, c = middle[0] - dr, middle[1] - dc
        if 0 <= r < 3 and 0 <= c < 3:
            cost[k, r, c] = np.inf
    graph = build_graph(cost, NEIGHBOURS)

    assert blocked_stations(cost, np.array([1, 0]), np.array([1, 0])).tolist() == [True, False]
    dis = calculate_distances(graph, np.array([1, 1]), np.array([0, 2]), 3)
    assert dis[0, 1] == 2.0

    src, dst = cell_id(1, 0, 3), cell_id(1, 2, 3)
    _, pred = dijkstra(graph, int(src), return_predecessors=True)
    rows, cols = path_cells(pred, int(src), int(dst), 3)
    assert (1, 1) not in set(zip(rows.tolist(), cols.tolist()))
    assert (rows[0], cols[0]) == (1, 0) and (rows[-1], cols[-1]) == (1, 2)
