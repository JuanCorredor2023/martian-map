"""
Inputs of E5: stations (GeoPackage, CRS of the DEM) placed on the E4 grid graph.
The grid, the E3 costs and the habitat placement come from grafos (E4, Aaron).
"""
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Point

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BASE_DIR = DATA_DIR / "base"
ROUTE_PATH = DATA_DIR / "e5" / "e5_route.gpkg"
STATIONS_PATH = DATA_DIR / "stations" / "stations_manual.gpkg"
STATIONS_LAYER = "stations"
TRAJECTORY_PATH = DATA_DIR / "e2" / "trajectory.gpkg"
TRAJECTORY_LAYER = "poses"


"""
Stations placed on the base grid, one entry per station:
    id, type: identifier and kind of the station (ridge, hollow, contact, curiosity, habitat)
    x, y: coordinates in the CRS of the DEM (Mars equirectangular metres)
    row, col: cell of the base grid that contains the point
    prize: prize of the station (score of the rubric)
    service_s: service time at the station in s
"""
@dataclass
class Stations:
    id: np.ndarray
    type: np.ndarray
    x: np.ndarray
    y: np.ndarray
    row: np.ndarray
    col: np.ndarray
    prize: np.ndarray
    service_s: np.ndarray

    def __len__(self):
        return len(self.row)

    """
    Stations selected by a boolean mask or an index array.
    """
    def subset(self, keep):
        return Stations(self.id[keep], self.type[keep], self.x[keep], self.y[keep],
                        self.row[keep], self.col[keep], self.prize[keep], self.service_s[keep])

    """
    Stations with a new one inserted first (the habitat as station 0).
    """
    def prepend(self, id, type, x, y, row, col, prize=0.0, service_s=0.0):
        return Stations(np.r_[[id], self.id], np.r_[[type], self.type],
                        np.r_[x, self.x], np.r_[y, self.y], np.r_[row, self.row],
                        np.r_[col, self.col], np.r_[prize, self.prize],
                        np.r_[service_s, self.service_s])


"""
Reads a point layer from a GeoPackage and places every point on the grid of `graph`
(grafos.graph.Graph). Columns of stations_manual.gpkg (Sebas, release stations-v1):
    id, type, score (prize_col), service_time_min
Missing columns get defaults: id = row number, type = "", prize = 1, service = 0.
Points outside the grid are dropped. Points falling in an already used cell are
dropped too (the first one is kept), so every station is a distinct graph node.
The habitat is not read from the file: it is a user input (see run.py).
"""
def read_stations(graph, path=STATIONS_PATH, layer=STATIONS_LAYER, prize_col="score"):
    gdf = gpd.read_file(path, layer=layer).reset_index(drop=True)
    n = len(gdf)

    x = gdf.geometry.x.to_numpy()
    y = gdf.geometry.y.to_numpy()
    ids = gdf["id"].astype(str).to_numpy() if "id" in gdf.columns else np.arange(n).astype(str)
    types = gdf["type"].astype(str).to_numpy() if "type" in gdf.columns else np.full(n, "")
    prize = gdf[prize_col].to_numpy(dtype=float) if prize_col in gdf.columns else np.ones(n)
    if "service_time_min" in gdf.columns:
        service_s = gdf["service_time_min"].to_numpy(dtype=float) * 60.0
    else:
        service_s = np.zeros(n)

    row, col = graph.xy_to_cell(x, y)
    inside = (row >= 0) & (row < graph.height) & (col >= 0) & (col < graph.width)
    stations = Stations(ids, types, x, y, row, col, prize, service_s).subset(inside)

    _, first = np.unique(graph.node(stations.row, stations.col), return_index=True)
    return stations.subset(np.sort(first))


"""
Writes the E5 route to a GeoPackage in the CRS of the DEM (contract #2), two layers:
    route : one LineString through the centre of every cell of the tour, with
            solver, prize, energy_wh, travel_time_s, length_m, usable_wh and the
            visiting order (station ids separated by ">")
    stops : one Point per stop in visiting order (habitat first and last) with
            order, id, type, score, service_time_min, and the cumulative energy_wh,
            travel_time_s and length_m on arrival, plus the energy of the leg into it
    graph : grafos Graph (cell centres, CRS and leg costs)
    path, stop_index : from network.route_path
    usable_j : energy budget the solver used, in J
Travel time is walking time only; service time at the stations is not included.
Returns the path of the file.
"""
def write_route_gpkg(out_path, graph, stations, solution, path, stop_index, usable_j):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    energy = graph.path_cost(path, "energy_j") if len(path) > 1 else np.zeros(1)
    time_s = graph.path_cost(path, "time_s") if len(path) > 1 else np.zeros(1)
    length = graph.path_cost(path, "length_m") if len(path) > 1 else np.zeros(1)

    rows, cols = graph.cell(path)
    xs, ys = graph.cell_to_xy(rows, cols)
    coords = list(zip(xs.tolist(), ys.tolist()))
    if len(coords) == 1:
        coords = coords * 2

    route_ids = [str(stations.id[k]) for k in solution.route]
    route = gpd.GeoDataFrame({
        "solver": [solution.solver],
        "prize": [float(solution.prize)],
        "energy_wh": [float(energy[-1]) / 3600.0],
        "travel_time_s": [float(time_s[-1])],
        "length_m": [float(length[-1])],
        "usable_wh": [float(usable_j) / 3600.0],
        "n_stops": [len(route_ids)],
        "order": [">".join(route_ids)],
    }, geometry=[LineString(coords)], crs=graph.crs_wkt)

    at = np.asarray(stop_index)
    previous = np.r_[0, at[:-1]]
    stops = gpd.GeoDataFrame({
        "order": np.arange(len(route_ids)),
        "id": route_ids,
        "type": [str(stations.type[k]) for k in solution.route],
        "score": [float(stations.prize[k]) for k in solution.route],
        "service_time_min": [float(stations.service_s[k]) / 60.0 for k in solution.route],
        "energy_wh": energy[at] / 3600.0,
        "leg_energy_wh": (energy[at] - energy[previous]) / 3600.0,
        "travel_time_s": time_s[at],
        "length_m": length[at],
    }, geometry=[Point(stations.x[k], stations.y[k]) for k in solution.route], crs=graph.crs_wkt)

    if out_path.exists():
        out_path.unlink()
    route.to_file(out_path, layer="route", driver="GPKG")
    stops.to_file(out_path, layer="stops", driver="GPKG")
    return out_path
