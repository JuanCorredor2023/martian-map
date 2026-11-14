"""
E5 entry point: stations + E4 grid graph (E3 costs) -> station-to-station matrix -> solver.

    python src/orienteering/run.py --habitat X Y [--solver dp] [--budget-wh 1000] [--margin 0.1]
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grafos.build_rv import SERVICE_POWER_W  # noqa: E402
from grafos.walkback import J_PER_WH  # noqa: E402

from orienteering.data_io import (ROUTE_PATH, STATIONS_LAYER, STATIONS_PATH,  # noqa: E402
                                  read_stations, write_route_gpkg)
from orienteering.network import (load_graph, place_habitat, reachable_stations,  # noqa: E402
                                  route_path, station_matrices)
from orienteering.problem import Problem, evaluate_route  # noqa: E402
from orienteering.safety import return_costs, solve_with_walkback, tour_walkback  # noqa: E402
from orienteering.solvers import MAX_STATIONS, SOLVERS  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="E5 orienteering over the E3 energy cost")
    ap.add_argument("--habitat", type=float, nargs=2, metavar=("X", "Y"), required=True,
                    help="habitat position, metres in the DEM's CRS (same input as E4)")
    ap.add_argument("--stations", default=STATIONS_PATH, help="GeoPackage with the stations")
    ap.add_argument("--layer", default=STATIONS_LAYER)
    ap.add_argument("--prize-col", default="score")
    ap.add_argument("--budget-wh", type=float, default=1000.0, help="energy budget (same as E4)")
    ap.add_argument("--margin", type=float, default=0.10, help="reserve kept out of the budget (same as E4)")
    ap.add_argument("--service-power-w", type=float, default=SERVICE_POWER_W,
                    help="metabolic power while working at a station (same default as E4; proposed in #2)")
    ap.add_argument("--max-duration-min", type=float, default=None,
                    help="maximum EVA duration, back at the habitat (default: no limit; same flag as E4)")
    ap.add_argument("--solver", choices=sorted(SOLVERS), default="dp")
    ap.add_argument("--out", default=ROUTE_PATH, help="GeoPackage for the route (layers route and stops)")
    args = ap.parse_args(argv)
    t0 = time.time()

    graph, main_cc = load_graph()
    stations = read_stations(graph, args.stations, layer=args.layer, prize_col=args.prize_col)

    hr, hc = place_habitat(graph, main_cc, args.habitat)
    hx, hy = (float(v) for v in graph.cell_to_xy(hr, hc))
    stations = stations.prepend("habitat", "habitat", hx, hy, hr, hc)

    ok = reachable_stations(main_cc, stations)
    if not ok.all():
        print(f"dropping stations outside the main connected area: {stations.id[~ok].tolist()}")
        stations = stations.subset(ok)
    limit = MAX_STATIONS[args.solver]
    if len(stations) > limit:
        raise SystemExit(f"{len(stations)} stations: solver {args.solver} supports up to {limit}, select fewer")

    dis, tim = station_matrices(graph, stations)
    budget_j = args.budget_wh * (1 - args.margin) * J_PER_WH
    max_duration_s = args.max_duration_min * 60.0 if args.max_duration_min is not None else None
    if stations.windows is not None:
        print(f"time windows on {int((np.isfinite(stations.windows[:, 1]) | (stations.windows[:, 0] > 0)).sum())} stations")

    service_j = stations.service_s * args.service_power_w
    problem = Problem(energy=dis, prize=stations.prize, budget=budget_j, time=tim,
                      service_s=stations.service_s, service_j=service_j,
                      windows=stations.windows, max_duration_s=max_duration_s)
    rv_j = return_costs(graph, graph.node(hr, hc))
    checked = {}

    def check(route):
        path, stop_index = route_path(graph, stations, route, dis)
        stop_service = [service_j[k] if k not in route[:m] else 0.0 for m, k in enumerate(route)]
        checked["path"], checked["stop_index"] = path, stop_index
        return tour_walkback(graph, path, stop_index, stop_service, rv_j, budget_j)

    try:
        solution, walkback, retries = solve_with_walkback(problem, SOLVERS[args.solver], check)
    except (ValueError, NotImplementedError) as err:
        raise SystemExit(f"solver {args.solver}: {err}")

    served_j = sum(service_j[k] for k in set(solution.route))
    print(f"{len(stations)} stations, usable budget {budget_j / J_PER_WH:.0f} Wh, solver {solution.solver} "
          f"({solution.runtime_s:.2f} s), total {time.time() - t0:.1f} s")
    print(f"habitat at ({hx:.1f}, {hy:.1f}); prize {solution.prize:g}, "
          f"spent {solution.energy / J_PER_WH:.1f} Wh "
          f"(walking {(solution.energy - served_j) / J_PER_WH:.1f}, service {served_j / J_PER_WH:.1f} "
          f"at {args.service_power_w:g} W)")
    for k in solution.route:
        print(f"  {stations.id[k]:>8} ({stations.type[k]}): x={stations.x[k]:.1f} "
              f"y={stations.y[k]:.1f} prize={stations.prize[k]:g}")

    if not solution.route:
        print("no route fits in the budget, windows and duration: nothing written")
        return solution
    timeline = evaluate_route(problem, solution.route)
    wait_s = float((timeline["begin"] - timeline["arrival"]).sum())
    served_s = sum(stations.service_s[k] for k in set(solution.route))
    print(f"duration {timeline['duration'] / 60:.0f} min (walking {(timeline['duration'] - served_s - wait_s) / 60:.0f}, "
          f"service {served_s / 60:.0f}, waiting {wait_s / 60:.0f})")

    if walkback["feasible"]:
        print(f"walkback ok: smallest slack {walkback['min_slack_j'] / J_PER_WH:.1f} Wh"
              + (f" (after {retries} re-plans with a lower budget)" if retries else ""))
    else:
        bad = stations.id[solution.route[walkback["first_violation_stop"]]]
        print(f"WARNING: walkback fails before reaching {bad} (slack {walkback['min_slack_j'] / J_PER_WH:.1f} Wh) "
              f"after {retries} re-plans")

    path, stop_index = checked["path"], checked["stop_index"]
    out = write_route_gpkg(args.out, graph, stations, solution, path, stop_index, budget_j,
                           args.service_power_w, timeline, walkback)
    print(f"route written to {out} ({len(path)} cells, {time.time() - t0:.1f} s total)")
    return solution


if __name__ == "__main__":
    main()
