"""API tests with FastAPI's TestClient. Need data/base, data/tiles and data/e2."""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

if not (REPO / "data" / "e2" / "trajectory.geojson").exists():
    pytest.skip("team data not available", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)
CENTRE = [8143537.49, -284463.08]          # middle of the 2 x 2 km box


def plan_body(**overrides):
    body = {"start": CENTRE, "energy_budget_wh": 1000.0, "margin": 0.1,
            "stations": [{"id": "S1", "x": CENTRE[0] + 100, "y": CENTRE[1], "score": 5}]}
    body.update(overrides)
    return body


def test_health_and_layers():
    assert client.get("/health").json()["status"] == "ok"
    layers = client.get("/layers").json()
    assert layers["grid"]["grid_1m"]["width"] == 2000
    assert "Mars" in layers["crs_wkt"]


def test_plan_returns_fixed_route_in_mars_metres():
    fc = client.post("/plan", json=plan_body()).json()
    kinds = [f["properties"]["kind"] for f in fc["features"]]
    assert kinds == ["route", "station", "start"]
    route = fc["features"][0]
    x, y = route["geometry"]["coordinates"][0]
    assert 8142537 < x < 8144538 and -285464 < y < -283463   # inside the box, metres
    assert fc["properties"]["energy_usable_wh"] == pytest.approx(900.0)
    assert fc["properties"]["feasible"] is None              # never claim feasibility yet


@pytest.mark.parametrize("bad", [
    {"energy_budget_wh": 0},
    {"margin": 1.0},
    {"gravity_m_s2": -3.71},
    {"start": [0.0, 0.0]},                                   # outside the box
    {"stations": [{"id": "A", "x": CENTRE[0], "y": CENTRE[1], "score": 1},
                  {"id": "A", "x": CENTRE[0], "y": CENTRE[1], "score": 2}]},
    {"stations": [{"id": "A", "x": CENTRE[0], "y": CENTRE[1], "score": -1}]},
])
def test_plan_rejects_invalid_requests(bad):
    assert client.post("/plan", json=plan_body(**bad)).status_code == 422


def test_cost_layer_png_and_legend():
    res = client.get("/layers/cost.png")
    assert res.status_code == 200 and res.content[:8] == b"\x89PNG\r\n\x1a\n"
    legend = client.get("/layers/cost").json()
    assert legend["vmin_j_per_m"] == pytest.approx(338.75, abs=0.1)   # guide c_min,h


def test_blocked_mask_follows_the_limit():
    frac = lambda v: client.get("/layers/blocked", params={"max_cell_slope_deg": v}).json()["blocked_fraction"]
    assert frac(30) == pytest.approx(0.12, abs=0.02)                  # JB: 12 % > 30 deg
    assert frac(15) > frac(30) > frac(60)
    assert client.get("/layers/blocked.png", params={"max_cell_slope_deg": 120}).status_code == 422


def test_plan_accepts_disabled_block():
    fc = client.post("/plan", json=plan_body(max_cell_slope_deg=None)).json()
    assert fc["properties"]["max_cell_slope_deg"] is None
