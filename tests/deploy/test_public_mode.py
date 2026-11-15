"""Public entry-point isolation without data, a running planner, or hosting."""
import asyncio
import copy
from pathlib import Path
import sys

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.public_mode import PublicMode


@pytest.fixture
def saved():
    return {"request": {"start": [1, 2], "energy_budget_wh": 100,
                        "max_cell_slope_deg": 30, "human_cost": True},
            "plan": {"type": "FeatureCollection", "properties": {"feasible": True, "habitat": [1, 2]},
                     "features": [{"properties": {"kind": "route"},
                                   "geometry": {"type": "LineString", "coordinates": [[1, 2], [2, 2], [1, 2]]}}]}}


@pytest.fixture
def backend():
    calls = []

    async def handle(request):
        calls.append(request.url.path)
        return JSONResponse(await request.json() if request.method == "POST" else {"ok": True})

    async def page(request):
        return HTMLResponse("<html><body>Map</body></html>")

    app = Starlette(routes=[Route("/", page), Route("/{path:path}", handle,
                                                  methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH"])])
    return app, calls


@pytest.mark.parametrize("path,method", [("/stations", "POST"), ("/stations/", "POST"),
                                         ("/walks", "POST"), ("/future/write", "POST"),
                                         ("/stations", "DELETE"), ("/plan", "PUT")])
def test_writes_never_reach_backend(saved, backend, path, method):
    app, calls = backend
    with TestClient(PublicMode(app, mode="readonly", snapshot=saved)) as client:
        response = client.request(method, path, json={})
        assert response.status_code == 403
        assert response.headers["x-martian-public-mode"] == "readonly"
    assert calls == []


def test_matching_plan_replays_snapshot_without_writes(saved, backend):
    app, calls = backend
    snapshot = copy.deepcopy(saved)
    with TestClient(PublicMode(app, mode="readonly", snapshot=saved)) as client:
        saved["request"]["energy_budget_wh"] = 999  # caller mutation cannot alter the frozen plan
        result = client.post("/plan", json=snapshot["request"])
        assert result.status_code == 200
        assert result.json()["properties"]["public_mode"] == "readonly"
        assert client.get("/plan/last").json() == snapshot
        assert client.post("/plan", json=saved["request"]).status_code == 403
    assert not calls


def test_local_default_preserves_writes_and_html(saved, backend):
    app, calls = backend
    with TestClient(PublicMode(app)) as client:
        assert client.post("/stations", json={}).status_code == 200
        assert "Fixed-plan public demo" not in client.get("/").text
        assert "x-martian-public-mode" not in client.get("/").headers
    assert calls == ["/stations"]


def test_pure_computation_pins_habitat_and_graph(saved, backend):
    app, _ = backend
    with TestClient(PublicMode(app, mode="readonly", snapshot=saved)) as client:
        result = client.post("/walkback", json={"current_position": [2, 2]})
        assert result.json()["base"] == [1, 2]
        assert result.json()["max_cell_slope_deg"] == 30
        assert result.json()["human_cost"] is True
        assert client.post("/guide/return_home", json={"habitat": [9, 9]}).status_code == 400
        assert client.post("/walkback", json={"max_cell_slope_deg": 20}).status_code == 400
        assert client.get("/layers/blocked?max_cell_slope_deg=20").status_code == 400
        assert client.get("/layers/comms?x=9&y=9").status_code == 400
        assert client.get("/plan/departure?sol=999").status_code == 400


def test_credits_visible_and_response_length_correct(saved, backend):
    app, _ = backend
    with TestClient(PublicMode(app, mode="readonly", snapshot=saved)) as client:
        response = client.get("/")
        assert "NASA/JPL-Caltech" in response.text
        assert int(response.headers["content-length"]) == len(response.content)
        assert client.get("/public/credits").status_code == 200
        assert client.get("/public/status").json()["persistent_writes"] is False


@pytest.mark.parametrize("body", [b"not json", b"[]", b"{\"oversized\":\"" + b"x" * 100 + b"\"}"])
def test_invalid_or_large_body_cannot_reach_engine(saved, backend, body):
    app, calls = backend
    with TestClient(PublicMode(app, mode="readonly", snapshot=saved, max_body_bytes=70)) as client:
        assert client.post("/walkback", content=body).status_code == 400
    assert not calls


def test_unknown_mode_and_missing_snapshot_fail_closed(backend):
    with pytest.raises(ValueError):
        PublicMode(backend[0], mode="public")
    with pytest.raises(ValueError):
        PublicMode(backend[0], mode="readonly")


def test_computations_do_not_overlap_but_static_pages_remain_available(saved):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow(request):
            entered.set()
            await release.wait()
            return JSONResponse({"ok": True})

        app = PublicMode(Starlette(routes=[Route("/walkback", slow, methods=["POST"]),
                                           Route("/map.html", lambda req: HTMLResponse("<body>Map</body>")),
                                           Route("/home/assets/hero.webp", lambda req: JSONResponse({"asset": True}))]),
                         mode="readonly", snapshot=saved)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            first = asyncio.create_task(client.post("/walkback", json={}))
            await entered.wait()
            assert (await client.post("/walkback", json={})).status_code == 503
            assert (await client.get("/layers/cost.png")).status_code == 503
            assert (await client.get("/map.html")).status_code == 200
            assert (await client.get("/home/assets/hero.webp")).status_code == 200
            release.set()
            assert (await first).status_code == 200
            assert not app.gate.locked()
    asyncio.run(scenario())


def test_public_factory_off_does_not_modify_shared_application(monkeypatch):
    from types import SimpleNamespace
    from api.public_mode import create_app
    sentinel = object()
    monkeypatch.setenv("MARTIAN_PUBLIC_MODE", "off")
    monkeypatch.setitem(sys.modules, "api.main", SimpleNamespace(app=sentinel, DATA=Path("unused")))
    assert create_app() is sentinel


def test_readonly_rejects_unverified_plan(saved, backend):
    saved["plan"]["properties"]["feasible"] = "false"
    with pytest.raises(ValueError, match="feasible"):
        PublicMode(backend[0], mode="readonly", snapshot=saved)
