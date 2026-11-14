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

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

REPO = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("MARTIAN_DATA", REPO / "data"))
BASE = DATA / "base"
TILES = DATA / "tiles"
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


# Static files go last so they do not shadow the API routes.
app.mount("/tiles", StaticFiles(directory=TILES), name="tiles")
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
