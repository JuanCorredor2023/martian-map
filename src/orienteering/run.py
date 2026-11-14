"""
E5 entry point: stations + E3 cost -> station-to-station matrix -> solver.

    python src/orienteering/run.py [--solver dp] [--budget 2e6] [--habitat X Y]
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orienteering.data_io import STATIONS_PATH, read_costs, read_grid, read_stations, xy_to_cell  # noqa: E402
from orienteering.graph import blocked_stations, build_graph, calculate_distances  # noqa: E402
from orienteering.problem import Problem  # noqa: E402
from orienteering.solvers import MAX_STATIONS, SOLVERS  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="E5 orienteering over the E3 energy cost")
    ap.add_argument("--stations", default=STATIONS_PATH, help="GeoPackage or GeoJSON with the stations")
    ap.add_argument("--layer", default="stations")
    ap.add_argument("--prize-col", default="score")
    ap.add_argument("--budget", type=float, default=2e6, help="energy budget of the route in J")
    ap.add_argument("--habitat", type=float, nargs=2, metavar=("X", "Y"),
                    help="start and end of the route; if missing, station 0 is used")
    ap.add_argument("--solver", choices=sorted(SOLVERS), default="dp")
    args = ap.parse_args(argv)
    t0 = time.time()

    _, _, _, height, width = read_grid()
    stations = read_stations(args.stations, layer=args.layer, prize_col=args.prize_col)
    if args.habitat:
        hr, hc = xy_to_cell(*args.habitat)
        if not (0 <= hr < height and 0 <= hc < width):
            raise SystemExit(f"habitat {args.habitat} is outside the grid")
        stations = stations.prepend(*args.habitat, hr, hc)

    cost, neighbours = read_costs()
    blocked = blocked_stations(cost, stations.row, stations.col)
    if blocked[0]:
        raise SystemExit("the start station (habitat) sits on a blocked cell")
    if blocked.any():
        print(f"dropping {blocked.sum()} stations on blocked cells: {np.flatnonzero(blocked).tolist()}")
        stations = stations.subset(~blocked)
    limit = MAX_STATIONS[args.solver]
    if len(stations) > limit:
        raise SystemExit(f"{len(stations)} stations: solver {args.solver} supports up to {limit}, select fewer")

    graph = build_graph(cost, neighbours)
    del cost
    dis = calculate_distances(graph, stations.row, stations.col, width)

    problem = Problem(energy=dis, prize=stations.prize, budget=args.budget)
    try:
        solution = SOLVERS[args.solver](problem)
    except (ValueError, NotImplementedError) as err:
        raise SystemExit(f"solver {args.solver}: {err}")

    print(f"{len(stations)} stations, budget {args.budget:.0f} J, solver {solution.solver} "
          f"({solution.runtime_s:.2f} s), total {time.time() - t0:.1f} s")
    print(f"prize {solution.prize:g}, spent {solution.energy:.0f} J ({solution.energy / 3600:.1f} Wh)")
    for k in solution.route:
        print(f"  station {k}: x={stations.x[k]:.1f} y={stations.y[k]:.1f} prize={stations.prize[k]:g}")
    return solution


if __name__ == "__main__":
    main()
