"""Multi-station EVA for POST /plan: E5 (Diana, src/orienteering) chooses which
stations to visit and in what order; E4 (Aaron) gives the legs and checks the
walkback; the HUD and the guide get the same per-vertex profile as E4's route.

E5 is imported lazily: until it is merged in main, AVAILABLE is False and /plan
keeps planning the single-goal E4 round trip.
"""

import numpy as np

from . import planner
from fisica.metabolic import J_PER_WH, KJ_PER_LITER_O2  # noqa: E402 (planner sets the path)
from grafos.walkback import check_walkback  # noqa: E402

try:
    from orienteering.data_io import Stations
    from orienteering.network import route_path, station_matrices
    from orienteering.problem import Problem
    from orienteering.solvers import MAX_STATIONS, SOLVERS
    AVAILABLE = True
except ImportError:                       # E5 not merged yet
    AVAILABLE = False


class NoTour(Exception):
    pass


def plan_tour(req, base_dir, service_power_w):
    """FeatureCollection of the best station tour habitat -> ... -> habitat.

    Raises ValueError (bad input) or NoTour (nothing fits the limits)."""
    g = planner.graph(str(base_dir), req.max_cell_slope_deg, req.human_cost)
    hr, hc, h_moved = g.place(*req.start, label="habitat")
    hx, hy = (float(v) for v in g.cell_to_xy(hr, hc))

    # Stations on the grid: snapped like E4, one station per cell, habitat first.
    rows, cols, keep, moved = [], [], [], {}
    used_cells = {(hr, hc)}
    for s in req.stations:
        r, c, m = g.place(s.x, s.y, label=f"station {s.id}")
        if (r, c) in used_cells:
            continue
        used_cells.add((r, c)); rows.append(r); cols.append(c); keep.append(s); moved[s.id] = m
    if not keep:
        raise ValueError("no station left after placing them on the grid")
    limit = MAX_STATIONS["dp"]
    if len(keep) + 1 > limit:
        raise ValueError(f"{len(keep)} stations: the exact DP supports up to {limit - 1}")
    xs, ys = g.cell_to_xy(np.array(rows), np.array(cols))
    st = Stations(id=np.array([s.id for s in keep]), type=np.array([s.type or "" for s in keep]),
                  x=np.asarray(xs, float), y=np.asarray(ys, float),
                  row=np.array(rows), col=np.array(cols),
                  prize=np.array([s.score for s in keep], float),
                  service_s=np.array([s.service_time_min * 60.0 for s in keep], float))
    st = st.prepend("habitat", "habitat", hx, hy, hr, hc)

    dis, tim = station_matrices(g, st)
    usable_j = req.energy_budget_wh * (1 - req.margin) * J_PER_WH
    service_j = st.service_s * service_power_w
    problem = Problem(energy=dis, prize=st.prize, budget=usable_j, time=tim,
                      service_s=st.service_s, service_j=service_j,
                      max_duration_s=None if req.max_duration_min is None
                      else req.max_duration_min * 60.0)
    sol = SOLVERS["dp"](problem)
    if not sol.route or len(sol.route) < 3:
        raise NoTour("no station fits in the energy budget and EVA duration")

    path, stop_index = route_path(g, st, sol.route, dis)
    habitat = int(g.node(hr, hc))
    rv_e = g.costs_to(habitat, "energy_j")
    rv_t = g.costs_to(habitat, "time_s")
    wb = check_walkback(g, path, rv_e, usable_j)

    # Per-vertex profile: walking from E4's graph plus service added at each stop.
    used, t = wb["used_j"].copy(), wb["time_s"].copy()
    for k, idx in zip(sol.route[1:-1], stop_index[1:-1]):
        used[idx:] += service_j[k]
        t[idx:] += st.service_s[k]
    rv = rv_e[path]
    slack = usable_j - used - rv
    o2 = used / 1000.0 / KJ_PER_LITER_O2
    rows_p, cols_p = g.cell(path)
    x, y = g.cell_to_xy(rows_p, cols_p)
    visit = [str(st.id[k]) for k in sol.route[1:-1]]
    wh = lambda a: [round(float(v) / J_PER_WH, 4) for v in a]   # noqa: E731
    line = {"type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [[float(a), float(b)] for a, b in zip(x, y)]},
            "properties": {
                "kind": "route", "approach": "E5_orienteering_on_E4",
                "feasible": bool((slack >= -1e-6).all()),
                "first_violation": wb["first_violation"],
                "energy_wh": round(float(used[-1]) / J_PER_WH, 3), "time_s": round(float(t[-1]), 1),
                "length_m": round(float(wb["length_m"][-1]), 1), "o2_l": round(float(o2[-1]), 2),
                "usable_wh": round(usable_j / J_PER_WH, 3), "prize": float(sol.prize),
                "visit_order": visit, "stop_index": [int(i) for i in stop_index[1:-1]],
                "turn_index": int(stop_index[-2]) if len(stop_index) > 2 else None,
                "used_wh": wh(used), "rv_wh": wh(rv), "slack_wh": wh(slack),
                "t_s": [round(float(v), 1) for v in t],
                "rv_time_s": [round(float(v), 1) for v in rv_t[path]],
                "o2_used_l": [round(float(v), 3) for v in o2],
                "solver": sol.solver, "solver_runtime_s": round(sol.runtime_s, 3)}}
    start = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [hx, hy]},
             "properties": {"kind": "start", "requested": list(req.start), "moved_m": h_moved}}
    info = {"cost_model": g.cost_model, "habitat_moved_m": h_moved, "visit_order": visit, "prize": float(sol.prize),
            "stations_considered": len(keep), "service_power_w": service_power_w,
            "moved": moved}
    return {"type": "FeatureCollection", "features": [line, start]}, info
