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


def station_set(**overrides):
    body = {"rubric": {"ridge": 5, "hollow": 4, "contact": 3, "curiosity": 3},
            "stations": [{"id": "R1", "type": "ridge", "x": CENTRE[0], "y": CENTRE[1]},
                         {"id": "H1", "type": "hollow", "x": CENTRE[0] + 50, "y": CENTRE[1],
                          "service_time_min": 15, "note": "dark sand"}]}
    body.update(overrides)
    return body


def test_stations_roundtrip_gpkg(tmp_path, monkeypatch):
    import geopandas as gpd
    import api.main as main
    monkeypatch.setattr(main, "STATIONS", tmp_path)          # never touch the real file
    assert client.get("/stations").json()["stations"] == []
    rubric = {"ridge": 7, "hollow": 4, "contact": 3, "curiosity": 3}  # edited live
    assert client.post("/stations", json=station_set(rubric=rubric)).json()["saved"] == 2
    gdf = gpd.read_file(tmp_path / "stations_manual.gpkg", layer="stations")
    assert list(gdf["score"]) == [7.0, 4.0]                  # score comes from the rubric
    assert "Mars" in gdf.crs.to_wkt()
    back = client.get("/stations").json()
    assert back["rubric"]["ridge"] == 7 and back["stations"][1]["note"] == "dark sand"
    assert client.get("/stations/stations_manual.gpkg").status_code == 200


@pytest.mark.parametrize("bad", [
    {"stations": [{"id": "X", "type": "crater", "x": CENTRE[0], "y": CENTRE[1]}]},
    {"stations": [{"id": "X", "type": "ridge", "x": 0.0, "y": 0.0}]},
    {"rubric": {"ridge": -1, "hollow": 4, "contact": 3, "curiosity": 3}},
    {"stations": [{"id": "X", "type": "ridge", "x": CENTRE[0], "y": CENTRE[1]},
                  {"id": "X", "type": "hollow", "x": CENTRE[0], "y": CENTRE[1]}]},
])
def test_stations_reject_invalid(bad, tmp_path, monkeypatch):
    import api.main as main
    monkeypatch.setattr(main, "STATIONS", tmp_path)
    assert client.post("/stations", json=station_set(**bad)).status_code == 422


def test_candidates_endpoint(tmp_path, monkeypatch):
    import json as _json
    import api.main as main
    monkeypatch.setattr(main, "STATIONS", tmp_path)
    assert client.get("/stations/candidates").status_code == 404
    (tmp_path / "candidates.json").write_text(_json.dumps(
        {"candidates": [{"id": "R0", "type": "ridge", "x": CENTRE[0], "y": CENTRE[1]}]}))
    assert client.get("/stations/candidates").json()["candidates"][0]["id"] == "R0"


def test_curiosity_drill_targets_match_places():
    from api.candidates import curiosity_targets
    t = {c["id"]: c for c in curiosity_targets()}
    ridge, hollow = t["R0"], t["H0"]
    d = ((ridge["x"] - hollow["x"]) ** 2 + (ridge["y"] - hollow["y"]) ** 2) ** 0.5
    assert 8 < d < 12                      # NASA: drilled ridge ~10 m from the drilled hollow


def test_walkback_fields_and_boundaries():
    body = {"current_position": [CENTRE[0] + 300, CENTRE[1]], "energy_remaining_wh": 150}
    fc = client.post("/walkback", json=body).json()
    p = fc["properties"]
    assert 400 <= p["return_time_s"] <= 600            # 300 m at ~0.75 m/s, plus detours
    assert 30 <= p["return_energy_wh"] <= 60           # 300 m x ~390 J/m = 32.5 Wh on flat ground
    assert p["contingency_ok"] and p["energy_ok"]
    kinds = {f["properties"]["kind"]: f for f in fc["features"]}
    assert kinds["emergency_time_boundary"]["geometry"]["coordinates"]       # red line exists
    assert kinds["energy_safe_boundary"]["properties"]["energy_remaining_wh"] == 150


def test_walkback_return_is_directed():
    import numpy as np
    import api.main as main
    from api import walkback as wb
    g = wb.grid(str(main.BASE), 30.0)
    base = g.node(*main._box_centre())
    r_t, r_e = wb.return_fields(str(main.BASE), 30.0, base)
    assert r_t.flat[base] == 0 and r_e.flat[base] == 0
    f_e = wb.forward_energy(str(main.BASE), 30.0, base, np.inf)            # base -> v
    both = np.isfinite(f_e) & np.isfinite(r_e)
    assert np.abs(f_e[both] - r_e[both]).max() > 1.0                       # going != coming back


def test_walkback_rejects_bad_requests():
    assert client.post("/walkback", json={"current_position": [0, 0],
                                          "energy_remaining_wh": 10}).status_code == 422
    assert client.post("/walkback", json={"current_position": CENTRE,
                                          "energy_remaining_wh": -1}).status_code == 422


def test_walkback_boundaries_are_few_closed_rings():
    body = {"current_position": [CENTRE[0] + 300, CENTRE[1]], "energy_remaining_wh": 150}
    fc = client.post("/walkback", json=body).json()
    for f in fc["features"][:2]:
        rings = f["geometry"]["coordinates"]
        assert 1 <= len(rings) <= 3                        # not thousands of fragments
        assert all(r[0] == r[-1] for r in rings)           # closed along scarps and box edge


def test_radiation_summary_and_scenarios():
    if not (REPO / "data" / "e12" / "sep_alert.json").exists():
        pytest.skip("E12 outputs not generated")
    r = client.get("/radiation").json()
    assert 5 < r["background_ugy_h"] < 9                      # E12: 6.52 uGy/h in the boxwork
    rates = [s["rate_ugy_h"] for s in r["scenarios"]]
    assert rates == sorted(rates) and r["scenarios"][0]["measured"]
    assert abs(r["curve"][-1]["dose_ugy"] - r["provisional_eva"]["dose_ugy"]) < 0.1
