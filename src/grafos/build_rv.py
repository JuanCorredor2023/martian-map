"""Build R(v) and an E4 round trip with walkback on the real grid.

Run from the repo root:
    python src/grafos/build_rv.py --habitat X Y [--budget-wh 1000] [--margin 0.1]
        [--goal X Y] [--base-dir data/base] [--out-dir data/e4]

--habitat is required (user input, metres in the DEM's CRS; the box spans
x 8142537.49 .. 8144537.49, y -285463.08 .. -283463.08). If it falls on a
blocked cell (slope > 30 deg) or outside the main connected area, it is moved
to the nearest valid cell and the move is reported.

Uses data/base/edges_e3.npz if present; otherwise computes the E3 costs in
memory from dem_1m.tif and slope_deg.tif (~3 s).

Writes to OUT_DIR:
    rv.tif         R(v): energy (Wh) to return to the habitat, float32, NaN = cannot return
    g.tif          energy (Wh) to reach each cell from the habitat, NaN = unreachable
    safe.tif       1 where g + R <= usable budget, 0 elsewhere (float32, NaN off-graph)
    e4_route.geojson  round trip habitat -> goal -> habitat with the walkback profile
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grafos.graph import Graph  # noqa: E402
from grafos.walkback import J_PER_WH, Walkback  # noqa: E402


def write_raster(path, a, profile):
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(a.astype("float32"), 1)


def route_geojson(graph, prof, habitat_xy, goal_xy, crs_wkt, **props):
    rows, cols = graph.cell(prof["path"])
    x, y = graph.cell_to_xy(rows, cols)
    wh = lambda a: [round(float(v) / J_PER_WH, 4) for v in a]   # noqa: E731
    line = {"type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [[float(a), float(b)] for a, b in zip(x, y)]},
            "properties": {"kind": "route", "approach": "E4_walkback",
                           "feasible": prof["feasible"],
                           "first_violation": prof["first_violation"],
                           "turn_index": prof.get("turn_index"),
                           "energy_wh": round(float(prof["used_j"][-1]) / J_PER_WH, 3),
                           "time_s": round(float(prof["time_s"][-1]), 1),
                           "length_m": round(float(prof["length_m"][-1]), 1),
                           "usable_wh": round(prof["usable_j"] / J_PER_WH, 3),
                           # per-vertex profile, same order as the coordinates
                           "used_wh": wh(prof["used_j"]), "rv_wh": wh(prof["rv_j"]),
                           "slack_wh": wh(prof["slack_j"]), **props}}
    pts = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": list(p)},
            "properties": {"kind": k}} for k, p in (("start", habitat_xy), ("goal", goal_xy))]
    return {"type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": crs_wkt}},
            "features": [line] + pts}


def place(graph, main_cc, xy, label):
    """User (x, y) -> valid (row, col); exits with a clear message if outside the box."""
    r, c = (int(v) for v in graph.xy_to_cell(*xy))
    if not graph.inside(r, c):
        sys.exit(f"error: {label} {xy} is outside the study box")
    sr, sc = graph.snap(r, c, mask=main_cc)
    if (sr, sc) != (r, c):
        print(f"warning: {label} cell ({r}, {c}) is blocked or outside the main connected "
              f"area; moved {np.hypot(sr - r, sc - c):.1f} m to ({sr}, {sc})")
    return sr, sc


def main():
    repo = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description="R(v) and E4 walkback round trip.")
    ap.add_argument("--habitat", type=float, nargs=2, metavar=("X", "Y"), required=True,
                    help="habitat position, metres in the DEM's CRS")
    ap.add_argument("--budget-wh", type=float, default=1000.0)
    ap.add_argument("--margin", type=float, default=0.10)
    ap.add_argument("--goal", type=float, nargs=2, metavar=("X", "Y"),
                    help="default: the safe cell farthest (in energy) from the habitat")
    ap.add_argument("--base-dir", default=str(repo / "data" / "base"))
    ap.add_argument("--out-dir", default=str(repo / "data" / "e4"))
    args = ap.parse_args()

    base, out = Path(args.base_dir), Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    graph = Graph.from_base_dir(base)
    labels, sizes = graph.components()
    main_cc = (labels == np.argmax(sizes)).reshape(graph.shape)
    print(f"graph: {graph.n:,} nodes, {graph.csr().nnz:,} arcs; largest SCC "
          f"{100 * sizes.max() / graph.n:.1f}% ({time.time() - t0:.1f}s)")

    hr, hc = place(graph, main_cc, args.habitat, "habitat")
    habitat = int(graph.node(hr, hc))
    habitat_xy = [float(v) for v in graph.cell_to_xy(hr, hc)]

    t0 = time.time()
    wb = Walkback.compute(graph, habitat)
    usable = args.budget_wh * (1 - args.margin) * J_PER_WH
    safe = wb.safe_mask(usable)
    print(f"R(v) + g(v): {time.time() - t0:.1f}s; safe cells {safe.sum():,} "
          f"({100 * safe.mean():.1f}%) for usable {usable / J_PER_WH:.0f} Wh")

    with rasterio.open(base / "dem_1m.tif") as src:
        profile = src.profile | {"dtype": "float32", "nodata": np.nan, "count": 1,
                                 "compress": "deflate"}
    write_raster(out / "rv.tif", wb.raster(wb.rv_j / J_PER_WH), profile)
    write_raster(out / "g.tif", wb.raster(wb.g_j / J_PER_WH), profile)
    reach = np.isfinite(wb.g_j) & np.isfinite(wb.rv_j)
    write_raster(out / "safe.tif",
                 np.where(reach, safe, np.nan).reshape(graph.shape), profile)

    if args.goal:
        gr, gc = place(graph, main_cc, args.goal, "goal")
        goal = int(graph.node(gr, gc))
    else:
        total = np.where(safe, wb.g_j + wb.rv_j, -np.inf)
        goal = int(np.argmax(total))
        gr, gc = graph.cell(goal)
    goal_xy = [float(v) for v in graph.cell_to_xy(gr, gc)]

    prof = wb.round_trip(goal, usable)
    fc = route_geojson(graph, prof, habitat_xy, goal_xy, graph.crs_wkt,
                       budget_wh=args.budget_wh, margin=args.margin)
    (out / "e4_route.geojson").write_text(json.dumps(fc), encoding="utf-8")
    print(f"habitat {habitat_xy}, goal {goal_xy}: round trip "
          f"{prof['used_j'][-1] / J_PER_WH:.1f} Wh, {prof['time_s'][-1] / 60:.1f} min, "
          f"{prof['length_m'][-1]:.0f} m, feasible={prof['feasible']}, "
          f"min slack {prof['slack_j'].min() / J_PER_WH:.1f} Wh")


if __name__ == "__main__":
    main()
