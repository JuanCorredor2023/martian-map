"""EVA planner API (FastAPI).

Run from the repo root:
    python -m uvicorn api.main:app --reload --port 8000
Then open http://localhost:8000/

The API and the HUD are served from the same origin, so no CORS setup is needed.
Reference: zero-to-hero guide REV3, sections 33-38.
"""

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .plan import PlanRequest, feature, feature_collection
from .raster_layers import blocked_layer, cost_layer
from . import stations as st

REPO = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("MARTIAN_DATA", REPO / "data"))
BASE = DATA / "base"
TILES = DATA / "tiles"
E2 = DATA / "e2"
STATIONS = DATA / "stations"
WEB = REPO / "web"

app = FastAPI(title="Mars EVA planner", version="0.1.0")


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/health")
def health():
    """Confirm the server is up and the base data is where we expect it."""
    return {
        "status": "ok",
        "base_grid": (BASE / "grid.json").exists(),
        "tiles": (TILES / "tiles.json").exists(),
    }


@app.get("/layers")
def layers():
    """Grid contract (CRS, bbox, resolution) and the tile layers for the HUD.

    Coordinates everywhere are metres in the DEM's Mars equirectangular CRS,
    never WGS84 (guide section 37).
    """
    return {
        "crs_wkt": (BASE / "crs.wkt").read_text(encoding="utf-8").strip(),
        "grid": _read_json(BASE / "grid.json"),
        "tiles": _read_json(TILES / "tiles.json"),
    }


@app.get("/layers/cost.png")
def cost_png():
    """E3 cost per cell (display only), coloured with the legend from /layers/cost."""
    return Response(cost_layer(str(BASE))[0], media_type="image/png")


@app.get("/layers/cost")
def cost_legend():
    return cost_layer(str(BASE))[1]


@app.get("/layers/blocked.png")
def blocked_png(max_cell_slope_deg: float = Query(30.0, ge=0, le=90)):
    """Cells blocked because their steepest slope exceeds the limit (red)."""
    return Response(blocked_layer(str(BASE), round(max_cell_slope_deg, 1))[0],
                    media_type="image/png")


@app.get("/layers/blocked")
def blocked_stats(max_cell_slope_deg: float = Query(30.0, ge=0, le=90)):
    fraction = blocked_layer(str(BASE), round(max_cell_slope_deg, 1))[1]
    return {"max_cell_slope_deg": max_cell_slope_deg, "blocked_fraction": fraction}


@app.get("/stations/rubric")
def stations_rubric():
    """Default rubric: type -> label, score and the reason behind it."""
    return st.DEFAULT_RUBRIC


@app.get("/stations")
def stations_get():
    """Saved manual stations and the rubric they were saved with."""
    return st.load(STATIONS)


@app.post("/stations")
def stations_save(body: st.StationSet):
    """Validate and save the manual stations as a GeoPackage for E5 (Diana)."""
    try:
        body.check_inside(_read_json(BASE / "grid.json")["bbox"])
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    crs_wkt = (BASE / "crs.wkt").read_text(encoding="utf-8").strip()
    path = st.save(body, STATIONS, crs_wkt)
    return {"saved": len(body.stations), "path": path.as_posix()}


@app.get("/stations/stations_manual.gpkg")
def stations_download():
    path = STATIONS / "stations_manual.gpkg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no stations saved yet")
    return FileResponse(path, filename="stations_manual.gpkg",
                        media_type="application/geopackage+sqlite3")


def _fixed_test_route():
    """Curiosity's trajectory (E2, Juan) used as a fixed route to test the whole
    pipeline before the planner is connected (guide section 38)."""
    route = _read_json(E2 / "trajectory.geojson")["features"][0]
    return route["geometry"]["coordinates"], route["properties"]


@app.post("/plan")
def plan(req: PlanRequest):
    """Plan an EVA. For now it returns a FIXED test route, not a planned one."""
    try:
        req.check_inside(_read_json(BASE / "grid.json")["bbox"])
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))

    coords, props = _fixed_test_route()
    warnings = ["fixed test route (Curiosity trajectory): the planner is not connected yet"]
    if req.service_energy_wh_per_min is None:
        warnings.append("service_energy_wh_per_min is null: the plan cannot be labelled "
                        "energy-feasible")

    features = [feature("LineString", coords, kind="route", source="curiosity_trajectory_e2",
                        length_m=props.get("length_m"), energy_wh=None, time_s=None)]
    features += [feature("Point", [s.x, s.y], kind="station", id=s.id, score=s.score,
                         service_time_min=s.service_time_min) for s in req.stations]
    features.append(feature("Point", list(req.start), kind="start"))

    crs_wkt = (BASE / "crs.wkt").read_text(encoding="utf-8").strip()
    return feature_collection(
        features, crs_wkt,
        model="santee_2001", units={"coordinates": "m", "energy": "Wh", "time": "s"},
        energy_budget_wh=req.energy_budget_wh,
        energy_usable_wh=req.energy_usable_j / 3600.0,
        max_cell_slope_deg=req.max_cell_slope_deg,
        feasible=None, warnings=warnings)


# Static files go last so they do not shadow the API routes.
app.mount("/tiles", StaticFiles(directory=TILES), name="tiles")
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
