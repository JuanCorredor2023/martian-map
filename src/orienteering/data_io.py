"""
Inputs of E5: base grid, stations and E3 edge costs.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BASE_DIR = DATA_DIR / "base"
GPKG_PATH = BASE_DIR / "trayecto_caja.gpkg"
STATIONS_PATH = DATA_DIR / "stations" / "stations_manual.gpkg"
NPZ_PATH = BASE_DIR / "edges_e3.npz"
GRID_PATH = BASE_DIR / "grid.json"


"""
Stations placed on the base grid, one entry per station:
    x, y: coordinates in the CRS of the DEM (Mars equirectangular metres)
    row, col: cell of the base grid that contains the point (index into the npz costs)
    prize: prize of the station
"""
@dataclass
class Stations:
    x: np.ndarray
    y: np.ndarray
    row: np.ndarray
    col: np.ndarray
    prize: np.ndarray

    def __len__(self):
        return len(self.row)

    """
    Stations selected by a boolean mask or an index array.
    """
    def subset(self, keep):
        return Stations(self.x[keep], self.y[keep], self.row[keep], self.col[keep], self.prize[keep])

    """
    Stations with a new one inserted first (e.g. the habitat as station 0).
    """
    def prepend(self, x, y, row, col, prize=0.0):
        return Stations(np.r_[x, self.x], np.r_[y, self.y], np.r_[row, self.row],
                        np.r_[col, self.col], np.r_[prize, self.prize])


"""
Reads the 1 m base grid description (grid.json): origin of the top-left corner,
cell size and shape. Row 0 is the north edge.
"""
def read_grid(path=GRID_PATH):
    with open(path, encoding="utf-8") as file:
        g = json.load(file)["grid_1m"]
    return g["origin_x"], g["origin_y"], g["cell_size_m"], g["height"], g["width"]


"""
Converts coordinates (CRS of the DEM) to the (row, col) of the base grid cell
that contains them. It does not check that the cell is inside the grid.
"""
def xy_to_cell(x, y, grid_path=GRID_PATH):
    origin_x, origin_y, cell, _, _ = read_grid(grid_path)
    col = np.floor((np.asarray(x) - origin_x) / cell).astype(np.int64)
    row = np.floor((origin_y - np.asarray(y)) / cell).astype(np.int64)
    return row, col


"""
Reads a point layer (GeoPackage or GeoJSON) and places every point on the base grid.
Points outside the grid are dropped. Points falling in an already used cell are
dropped too (the first one is kept), so every station is a distinct graph node.
If the layer has a "tipo" column, "habitat" points are placed first, so the
habitat is station 0.
If prize_col is not a column of the layer, every point gets prize 1.
"""
def read_stations(path=STATIONS_PATH, layer=None, prize_col="valor", grid_path=GRID_PATH):
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

    _, _, _, height, width = read_grid(grid_path)
    row, col = xy_to_cell(x, y, grid_path)

    inside = (row >= 0) & (row < height) & (col >= 0) & (col < width)
    stations = Stations(x, y, row, col, p).subset(inside)

    _, first = np.unique(stations.row * width + stations.col, return_index=True)
    return stations.subset(np.sort(first))


"""
Reads the directed edge costs of E3 (edges_e3.npz) and returns:
    cost: float array (8, rows, cols); cost[k, r, c] is the cost of moving from
          cell (r, c) to its neighbour k. Missing edges (off-grid, nodata,
          too steep) are np.inf instead of NaN.
    neighbours: int array (8, 2) with the (d_row, d_col) of each k
                (N, NE, E, SE, S, SW, W, NW; rows grow southwards).
kind selects the cost: "energy_j" (joules) or "time_s" (seconds).
"""
def read_costs(path=NPZ_PATH, kind="energy_j"):
    if kind not in ("energy_j", "time_s"):
        raise ValueError(f"kind must be 'energy_j' or 'time_s', not {kind!r}")

    with np.load(path) as data:
        cost = data[kind].astype(np.float64)
        neighbours = data["neighbours"].astype(np.int64)

    cost[~np.isfinite(cost)] = np.inf
    return cost, neighbours


def build_gpkg():
    pass
