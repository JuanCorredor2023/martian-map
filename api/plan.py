"""Request/response contract for POST /plan (guide REV3, sections 34-35).

Units: the API takes budgets in Wh; the engine works in J (1 Wh = 3600 J).
Coordinates: metres in the DEM's Mars equirectangular CRS, never WGS84.
"""

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


class Station(BaseModel):
    id: str
    x: float
    y: float
    score: float = Field(ge=0)
    service_time_min: float = Field(default=0.0, ge=0)


class PlanRequest(BaseModel):
    start: Tuple[float, float]
    stations: List[Station] = []
    energy_budget_wh: float = Field(gt=0)
    gravity_m_s2: float = Field(default=3.71, gt=0)          # m/s^2, NOT a 0.38 factor
    margin: float = Field(default=0.10, ge=0, lt=1)
    apollo_speed_uses_signed_slope: bool = True
    service_energy_wh_per_min: Optional[float] = Field(default=None, ge=0)
    # Cells steeper than this (slope_deg.tif) are blocked; null disables the block.
    max_cell_slope_deg: Optional[float] = Field(default=30.0, ge=0, le=90)

    @field_validator("stations")
    @classmethod
    def unique_ids(cls, stations):
        ids = [s.id for s in stations]
        if len(ids) != len(set(ids)):
            raise ValueError("station ids must be unique")
        return stations

    def check_inside(self, bbox):
        """Raise ValueError if start or any station falls outside the grid bbox."""
        def inside(x, y):
            return bbox["xmin"] <= x <= bbox["xmax"] and bbox["ymin"] <= y <= bbox["ymax"]
        if not inside(*self.start):
            raise ValueError("start is outside the study box")
        for s in self.stations:
            if not inside(s.x, s.y):
                raise ValueError(f"station {s.id} is outside the study box")

    @property
    def energy_usable_j(self):
        return self.energy_budget_wh * (1 - self.margin) * 3600.0


def feature(geometry_type, coordinates, **properties):
    return {"type": "Feature",
            "geometry": {"type": geometry_type, "coordinates": coordinates},
            "properties": properties}


def feature_collection(features, crs_wkt, **properties):
    return {"type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": crs_wkt}},
            "properties": properties,
            "features": features}
