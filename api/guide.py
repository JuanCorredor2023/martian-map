"""Guide mode backend (#43): the saved plan and the instant way home.

- The last successful live plan is saved (data/plans/last_plan.json) so the
  guide screen on the arm tablet can load it after planning in the habitat.
- Return home: the FASTEST path from the astronaut's position to the habitat,
  from E4's reversed Dijkstra (Graph.costs_to with predecessors). It is the
  emergency way back (time is what the 30 min oxygen reserve limits), and it
  needs no new planning: pred[v] is already the next cell towards the habitat.
"""

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import planner
from grafos.graph import follow  # noqa: E402  (planner puts src/ on the path)

J_PER_WH = 3600.0


def save_plan(plans_dir, request, fc):
    plans_dir = Path(plans_dir)
    plans_dir.mkdir(parents=True, exist_ok=True)
    (plans_dir / "last_plan.json").write_text(
        json.dumps({"request": request, "plan": fc}), encoding="utf-8")


def load_plan(plans_dir):
    path = Path(plans_dir) / "last_plan.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@lru_cache(maxsize=8)
def _towards_home(base_dir, max_cell_slope_deg, habitat_node, human=True):
    g = planner.graph(base_dir, max_cell_slope_deg, human)
    t, pred = g.costs_to(habitat_node, "time_s", predecessors=True)
    return t, pred


def return_home(base_dir, max_cell_slope_deg, position_xy, habitat_xy, human=True):
    """LineString coordinates position -> habitat (fastest), with time, energy and length.
    Raises ValueError if a point is outside the box or the habitat is unreachable."""
    g = planner.graph(base_dir, max_cell_slope_deg, human)
    hr, hc, _ = g.place(*habitat_xy, label="habitat")
    pr, pc, moved = g.place(*position_xy, label="position")
    habitat, pos = int(g.node(hr, hc)), int(g.node(pr, pc))
    t, pred = _towards_home(base_dir, max_cell_slope_deg, habitat, human)
    if not np.isfinite(t[pos]):
        raise ValueError("no walkable way back to the habitat from here")
    path = follow(pred, pos, end=habitat) if pos != habitat else np.array([pos])
    rows, cols = g.cell(path)
    x, y = g.cell_to_xy(rows, cols)
    one = len(path) > 1
    energy = g.path_cost(path, "energy_j") if one else np.array([0.0])
    length = g.path_cost(path, "length_m") if one else np.array([0.0])
    times = g.path_cost(path, "time_s") if one else np.array([0.0])
    return {
        "coordinates": [[float(a), float(b)] for a, b in zip(x, y)],
        "time_s": float(t[pos]), "energy_wh": float(energy[-1] / J_PER_WH),
        "length_m": float(length[-1]), "position_moved_m": moved,
        # per-vertex profile, same order as the coordinates (for the guide simulation)
        "t_s": [round(float(v), 1) for v in times],
        "used_wh": [round(float(v) / J_PER_WH, 4) for v in energy],
    }


@lru_cache(maxsize=8)
def _return_energy(base_dir, max_cell_slope_deg, habitat_node, human=True):
    g = planner.graph(base_dir, max_cell_slope_deg, human)
    return g.costs_to(habitat_node, "energy_j")


def rejoin(base_dir, max_cell_slope_deg, position_xy, target_xy, habitat_xy, human=True):
    """Off-route recovery: the least-energy path position -> target (a point on the
    planned route ahead), with the same per-vertex profile as E4's route: t_s,
    used_wh, and what it takes to get home from each vertex (rv_wh, rv_time_s)."""
    g = planner.graph(base_dir, max_cell_slope_deg, human)
    hr, hc, _ = g.place(*habitat_xy, label="habitat")
    pr, pc, moved = g.place(*position_xy, label="position")
    tr, tc, _ = g.place(*target_xy, label="target")
    habitat, pos, target = (int(g.node(r, c)) for r, c in ((hr, hc), (pr, pc), (tr, tc)))
    if pos == target:
        path = np.array([pos])
    else:
        cost, pred = g.costs_from(pos, "energy_j", predecessors=True)
        if not np.isfinite(cost[target]):
            raise ValueError("cannot rejoin the route from here")
        path = follow(pred, target, end=pos)[::-1]           # pos -> target
    rows, cols = g.cell(path)
    x, y = g.cell_to_xy(rows, cols)
    one = len(path) > 1
    energy = g.path_cost(path, "energy_j") if one else np.array([0.0])
    times = g.path_cost(path, "time_s") if one else np.array([0.0])
    rv_t, _ = _towards_home(base_dir, max_cell_slope_deg, habitat, human)
    rv_e = _return_energy(base_dir, max_cell_slope_deg, habitat, human)
    return {
        "coordinates": [[float(a), float(b)] for a, b in zip(x, y)],
        "time_s": float(times[-1]), "energy_wh": float(energy[-1] / J_PER_WH),
        "position_moved_m": moved,
        "t_s": [round(float(v), 1) for v in times],
        "used_wh": [round(float(v) / J_PER_WH, 4) for v in energy],
        "rv_wh": [round(float(v) / J_PER_WH, 4) for v in rv_e[path]],
        "rv_time_s": [round(float(v), 1) for v in rv_t[path]],
    }
