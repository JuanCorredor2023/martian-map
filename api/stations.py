"""Manual science stations: rubric, validation and GeoPackage export for E5.

The score of a station is NOT chosen per station: it comes from the rubric of
its type, so the value of every station can be traced to an explicit,
editable rule (guide REV3, section 24). The HUD can edit the rubric live.

Output for Diana (E5): data/stations/stations_manual.gpkg, layer "stations",
DEM CRS, columns id, type, score, service_time_min, note. The rubric used is
saved next to it as stations_rubric.json.
"""

import json
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
from pydantic import BaseModel, Field, field_validator, model_validator
from shapely.geometry import Point

# Default rubric (team decision, 2026-11-14). The reasons are design
# assumptions to be checked against the literature review.
DEFAULT_RUBRIC = {
    "ridge":     {"label": "Boxwork ridge", "score": 5,
                  "why": "ridge cements: record of late groundwater (clays assumed)"},
    "hollow":    {"label": "Hollow between ridges", "score": 4,
                  "why": "hollow fill (carbonates assumed); loose sand is a hazard"},
    "contact":   {"label": "Contact between units", "score": 3,
                  "why": "geologic diversity, stratigraphic context"},
    "curiosity": {"label": "Curiosity measurement site", "score": 3,
                  "why": "ground truth from the rover (drill or long stop)"},
}

LAYER = "stations"


class ManualStation(BaseModel):
    id: str = Field(min_length=1)
    type: str
    x: float
    y: float
    service_time_min: float = Field(default=10.0, ge=0)
    note: str = ""


class StationSet(BaseModel):
    rubric: Dict[str, float]                       # type -> score
    stations: List[ManualStation] = []

    @field_validator("rubric")
    @classmethod
    def non_negative_scores(cls, rubric):
        if any(v < 0 for v in rubric.values()):
            raise ValueError("rubric scores must be >= 0")
        return rubric

    @model_validator(mode="after")
    def consistent(self):
        ids = [s.id for s in self.stations]
        if len(ids) != len(set(ids)):
            raise ValueError("station ids must be unique")
        unknown = {s.type for s in self.stations} - set(self.rubric)
        if unknown:
            raise ValueError(f"station types not in the rubric: {sorted(unknown)}")
        return self

    def check_inside(self, bbox):
        for s in self.stations:
            if not (bbox["xmin"] <= s.x <= bbox["xmax"] and bbox["ymin"] <= s.y <= bbox["ymax"]):
                raise ValueError(f"station {s.id} is outside the study box")


def save(station_set, out_dir, crs_wkt):
    """Write the GeoPackage and the rubric. Returns the GeoPackage path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "stations_manual.gpkg"
    rows = [{"id": s.id, "type": s.type, "score": float(station_set.rubric[s.type]),
             "service_time_min": s.service_time_min, "note": s.note,
             "geometry": Point(s.x, s.y)} for s in station_set.stations]
    columns = ["id", "type", "score", "service_time_min", "note", "geometry"]
    gdf = gpd.GeoDataFrame(rows, columns=columns, geometry="geometry", crs=crs_wkt)
    if path.exists():
        path.unlink()                                 # overwrite the whole file
    gdf.to_file(path, layer=LAYER, driver="GPKG")
    (out_dir / "stations_rubric.json").write_text(
        json.dumps({"rubric": station_set.rubric}, indent=2), encoding="utf-8")
    return path


def load(out_dir):
    """Saved stations and rubric, or empty defaults if nothing was saved yet."""
    out_dir = Path(out_dir)
    path = out_dir / "stations_manual.gpkg"
    rubric_path = out_dir / "stations_rubric.json"
    rubric = ({k: v["score"] for k, v in DEFAULT_RUBRIC.items()} if not rubric_path.exists()
              else json.loads(rubric_path.read_text(encoding="utf-8"))["rubric"])
    stations = []
    if path.exists():
        gdf = gpd.read_file(path, layer=LAYER)
        stations = [{"id": r.id, "type": r.type, "x": r.geometry.x, "y": r.geometry.y,
                     "service_time_min": float(r.service_time_min), "note": r.note or ""}
                    for r in gdf.itertuples()]
    return {"rubric": rubric, "stations": stations}
