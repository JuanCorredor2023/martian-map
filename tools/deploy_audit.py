"""Local-only deployment inventory and optional one-process planning memory probe.

No data are uploaded or downloaded. Run with the scientific environment; psutil
is required only for --profile. Outputs belong under data/, outside git.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time

FOLDERS = ("base", "tiles", "e1", "e2", "e8", "e9", "e12", "stations", "plans",
           "rems", "minerals", "thermal")


def inventory(data):
    rows = {}
    for name in FOLDERS:
        files = [f for f in (data / name).rglob("*") if f.is_file()]
        rows[name] = {"files": len(files), "bytes": sum(f.stat().st_size for f in files)}
    required = ("base/grid.json", "base/crs.wkt", "base/dem_1m.tif", "base/slope_deg.tif",
                "tiles/tiles.json", "tiles/3d/terrain.json", "plans/last_plan.json")
    return {"folders": rows, "total_bytes": sum(r["bytes"] for r in rows.values()),
            "missing_demo_files": [f for f in required if not (data / f).is_file()],
            "rover_photo_catalog_present": (data / "tiles/3d/photos/catalog.json").is_file(),
            "warning": "Inventory is not a minimal publishable kit; it can include unused raw rasters."}


def profile(data):
    import psutil
    process = psutil.Process()
    peak = [process.memory_info().rss]
    done = threading.Event()

    def sample():
        while not done.wait(.05):
            peak[0] = max(peak[0], process.memory_info().rss)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        repo = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo))
        os.environ["MARTIAN_DATA"] = str(data)
        from api import planner, tour
        from api.plan import PlanRequest
        saved = json.loads((data / "plans/last_plan.json").read_text(encoding="utf-8"))
        request = PlanRequest.model_validate(saved["request"])
        start = time.perf_counter()
        graph = planner.graph(str(data / "base"), request.max_cell_slope_deg, request.human_cost)
        graph_seconds = time.perf_counter() - start
        start = time.perf_counter()
        if request.goal is None and request.stations:
            result, _ = tour.plan_tour(request, data / "base", planner.SERVICE_POWER_W)
        else:
            result, _ = planner.plan(request, data / "base")
        plan_seconds = time.perf_counter() - start
        return {"sample_period_s": .05, "rss_peak_bytes": max(peak[0], process.memory_info().rss),
                "rss_after_tour_bytes": process.memory_info().rss,
                "graph_seconds": graph_seconds, "first_tour_seconds": plan_seconds,
                "nodes": graph.n, "route_features": len(result["features"]),
                "request": request.model_dump(),
                "limitations": "Windows process RSS, one tour/configuration; not Linux container capacity or a concurrency load test."}
    finally:
        done.set()
        sampler.join()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--profile", action="store_true")
    args = p.parse_args()
    report = inventory(args.data)
    if args.profile:
        report["profile"] = profile(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
