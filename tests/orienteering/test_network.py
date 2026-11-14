"""E5 on the E4 grid graph: stations, habitat, matrix and legs on small synthetic grids."""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from grafos.graph import Graph

from orienteering.data_io import read_stations
from orienteering.network import (leg_path, main_component, place_habitat,
                                  reachable_stations, station_matrix)

NEIGHBOURS = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
E, W = 2, 6


def grid_graph(rows, cols, blocked=(), east_cost=1.0):
    """Unit costs on a rows x cols grid, east moves cost east_cost, blocked cells have no edges.
    Cell (r, c) covers x in [c, c+1) and y in (rows-r-1, rows-r]."""
    energy = np.full((8, rows, cols), 1.0)
    r, c = np.indices((rows, cols))
    for k, (dr, dc) in enumerate(NEIGHBOURS):
        nr, nc = r + dr, c + dc
        off = (nr < 0) | (nr >= rows) | (nc < 0) | (nc >= cols)
        for br, bc in blocked:
            off |= ((r == br) & (c == bc)) | ((nr == br) & (nc == bc))
        energy[k][off] = np.nan
    energy[E] = np.where(np.isfinite(energy[E]), east_cost, np.nan)
    return Graph({"energy_j": energy, "time_s": energy.copy()}, NEIGHBOURS,
                 transform=(1.0, 0.0, 0.0, 0.0, -1.0, float(rows)))


def stations_at(graph, cells, **cols):
    pts = [Point(*(float(v) for v in graph.cell_to_xy(r, c))) for r, c in cells]
    return gpd.GeoDataFrame(cols, geometry=pts)


def test_read_stations_uses_contract_columns(tmp_path):
    graph = grid_graph(3, 4)
    gdf = stations_at(graph, [(0, 0), (1, 2), (1, 2), (2, 3)],
                      id=["R0", "H0", "dup", "C1"], type=["ridge", "hollow", "hollow", "contact"],
                      score=[5.0, 4.0, 4.0, 4.0], service_time_min=[10.0, 5.0, 5.0, 0.0])
    path = tmp_path / "stations.gpkg"
    gdf.to_file(path, layer="stations")

    s = read_stations(graph, path, layer="stations")

    assert s.id.tolist() == ["R0", "H0", "C1"]
    assert s.type.tolist() == ["ridge", "hollow", "contact"]
    assert s.prize.tolist() == [5.0, 4.0, 4.0]
    assert s.service_s.tolist() == [600.0, 300.0, 0.0]
    assert list(zip(s.row.tolist(), s.col.tolist())) == [(0, 0), (1, 2), (2, 3)]


def test_read_stations_defaults_without_columns(tmp_path):
    graph = grid_graph(2, 2)
    path = tmp_path / "poses.gpkg"
    stations_at(graph, [(0, 0), (1, 1)]).to_file(path, layer="poses")

    s = read_stations(graph, path, layer="poses")

    assert s.prize.tolist() == [1.0, 1.0] and s.service_s.tolist() == [0.0, 0.0]


def test_matrix_is_directed():
    graph = grid_graph(1, 3, east_cost=2.0)
    stations = type("S", (), {"row": np.array([0, 0]), "col": np.array([0, 2])})
    dis = station_matrix(graph, stations)
    assert dis[0, 1] == 4.0 and dis[1, 0] == 2.0


def test_habitat_snaps_and_blocked_station_is_unreachable():
    graph = grid_graph(3, 3, blocked=[(1, 1)])
    main_cc = main_component(graph)

    assert place_habitat(graph, main_cc, graph.cell_to_xy(1, 1)) != (1, 1)
    stations = type("S", (), {"row": np.array([0, 1]), "col": np.array([0, 1])})
    assert reachable_stations(main_cc, stations).tolist() == [True, False]


def test_leg_path_detours_blocked_cell():
    graph = grid_graph(3, 3, blocked=[(1, 1)])
    a, b = int(graph.node(1, 0)), int(graph.node(1, 2))
    path = leg_path(graph, a, b)
    cells = [tuple(int(v) for v in graph.cell(n)) for n in path]
    assert cells[0] == (1, 0) and cells[-1] == (1, 2) and (1, 1) not in cells
