"""E5 tour for POST /plan, with the real request model (api/plan.py) on synthetic grids."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_network import grid_graph

from api.plan import PlanRequest
from grafos.labels import NoFeasibleRoute
from orienteering.tour import plan_tour

WH = 3600.0


def station(graph, sid, row, col, score, service_min=0.0):
    x, y = (float(v) for v in graph.cell_to_xy(row, col))
    return {"id": sid, "x": x, "y": y, "type": "ridge", "score": score,
            "service_time_min": service_min}


def request(graph, stations, budget_j, **kw):
    start = [float(v) for v in graph.cell_to_xy(1, 0)]
    return PlanRequest(start=start, stations=stations, energy_budget_wh=budget_j / WH,
                       margin=0.0, service_energy_wh_per_min=0.0, **kw)


def features(fc, kind):
    return [f for f in fc["features"] if f["properties"]["kind"] == kind]


def test_full_tour_in_e4_route_format():
    graph = grid_graph(3, 8)
    sts = [station(graph, "A", 1, 3, 5), station(graph, "B", 1, 7, 4), station(graph, "C", 0, 5, 3)]

    fc, info = plan_tour(request(graph, sts, 100.0), graph)

    line = features(fc, "route")[0]
    p = line["properties"]
    n = len(line["geometry"]["coordinates"])
    for key in ("used_wh", "rv_wh", "slack_wh", "t_s", "rv_time_s", "o2_used_l"):
        assert len(p[key]) == n
    assert p["approach"] == "E5_tour" and p["feasible"] and p["exact"]
    assert p["order"][0] == p["order"][-1] == "habitat"
    assert sorted(p["order"][1:-1]) == ["A", "B", "C"] and p["prize"] == 12.0
    assert p["stop_index"][0] == 0 and p["stop_index"][-1] == n - 1
    assert p["energy_wh"] == pytest.approx(p["used_wh"][-1], abs=1e-3)
    assert p["rv_wh"][-1] == 0.0
    assert [f["properties"]["id"] for f in features(fc, "stop")] == p["order"][1:-1]
    assert features(fc, "start")[0]["properties"]["moved_m"] == 0.0
    assert info["skipped"] == [] and info["goal_station"] is None and info["warnings"] == []


def test_tight_budget_skips_stations():
    graph = grid_graph(3, 8)
    sts = [station(graph, "near", 1, 2, 1), station(graph, "far", 1, 7, 5)]
    fc, info = plan_tour(request(graph, sts, 5.0), graph)
    assert features(fc, "route")[0]["properties"]["order"] == ["habitat", "near", "habitat"]
    assert info["skipped"] == ["far"]


def test_service_energy_and_time_in_the_profile():
    graph = grid_graph(3, 8)
    sts = [station(graph, "A", 1, 3, 5, service_min=2.0)]
    req = request(graph, sts, 1000.0)
    req.service_energy_wh_per_min = 1.0 / 60.0          # 1 W -> 120 J for 2 min
    fc, _ = plan_tour(req, graph)
    p = features(fc, "route")[0]["properties"]
    assert p["energy_wh"] * WH == pytest.approx(6.0 + 120.0, abs=0.1)
    assert p["time_s"] == pytest.approx(6.0 + 120.0)
    stop = features(fc, "stop")[0]["properties"]
    assert stop["departure_time_s"] - stop["arrival_time_s"] == pytest.approx(120.0)


def test_o2_budget_is_the_tighter_limit():
    graph = grid_graph(3, 8)
    sts = [station(graph, "near", 1, 2, 1), station(graph, "far", 1, 7, 5)]
    o2_l = 5.0 / 20100.0                                 # O2 for 5 J
    fc, info = plan_tour(request(graph, sts, 100.0, o2_budget_l=o2_l), graph)
    p = features(fc, "route")[0]["properties"]
    assert p["order"] == ["habitat", "near", "habitat"]
    assert p["usable_wh"] == pytest.approx(5.0 / WH, abs=1e-3)       # rounded to 3 decimals like E4
    assert p["usable_wh"] < 100.0 / WH
    assert any("O2" in w for w in info["warnings"])


def test_max_duration_is_respected():
    graph = grid_graph(3, 8)
    sts = [station(graph, "near", 1, 2, 1), station(graph, "far", 1, 7, 5)]
    fc, _ = plan_tour(request(graph, sts, 100.0, max_duration_min=5.0 / 60.0), graph)
    p = features(fc, "route")[0]["properties"]
    assert p["order"] == ["habitat", "near", "habitat"] and p["time_s"] <= 5.0


def test_blocked_station_is_moved_and_reported():
    graph = grid_graph(3, 8, blocked=[(1, 4)])
    fc, info = plan_tour(request(graph, [station(graph, "A", 1, 4, 5)], 100.0), graph)
    stop = features(fc, "stop")[0]["properties"]
    assert stop["moved_m"] > 0 and stop["requested"] != features(fc, "stop")[0]["geometry"]["coordinates"]
    assert any("station A moved" in w for w in info["warnings"])


def test_no_station_fits():
    graph = grid_graph(3, 8)
    with pytest.raises(NoFeasibleRoute):
        plan_tour(request(graph, [station(graph, "far", 1, 7, 5)], 3.0), graph)


def test_input_errors():
    graph = grid_graph(3, 8)
    with pytest.raises(ValueError):
        plan_tour(request(graph, [], 100.0), graph)
    many = [station(graph, f"S{k}", k % 3, 1 + k % 7, 1) for k in range(20)]
    with pytest.raises(ValueError):
        plan_tour(request(graph, many, 100.0), graph)
