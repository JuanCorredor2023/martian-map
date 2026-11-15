"""E6 benchmark: exact solvers (bitmask DP, OR-Tools CP-SAT) against two metaheuristics
(iterated local search, simulated annealing): gap to the optimum and running time.

Run from the repo root:
    python src/orienteering/e6_benchmark.py [--quick] [--no-real] [--figure-only]

Instance sets:
    random_energy / random_windows : 10 random instances per N in (10, 14, 18), E5 rules
                                     (service; plus time windows); optimum from the DP
    tsiligirides                   : the 49 classic OP instances of Tsiligirides (1984), 21-33
                                     points (KU Leuven files, data/08_instancias_orienteering);
                                     optimum from CP-SAT, which must prove it
    e5_real                        : the E5 instances on the real terrain (13 manual stations,
                                     and with E8's stations) from the box-centre habitat,
                                     nominal and 120 min; optimum from the DP or CP-SAT
Writes data/e6/e6_results.json (one row per instance and method), data/e6/e6_table.csv
(the summary table for the team's results table) and paper/figures/e6_fig1_gap_runtime.png.
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import matplotlib
import matplotlib.ticker  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orienteering.instances import instance_dir, random_instance, tsiligirides  # noqa: E402
from orienteering.problem import evaluate_route  # noqa: E402
from orienteering.solvers import cpsat, dp, ils, sa  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT, FIG = REPO / "data" / "e6", REPO / "paper" / "figures"
SIZES, PER_SIZE = (10, 14, 18), 10
SA_SEEDS = (0, 1, 2)
CPSAT_LIMIT_S = 120.0
METHODS = ("exact", "ils", "sa")
LABELS = {"exact": "Exact (DP / CP-SAT)", "ils": "ILS", "sa": "SA"}
COLOURS = {"exact": "#2a78d6", "ils": "#eb6834", "sa": "#1baf7a"}   # dataviz slots 1-3, validated
SETS = ("random_energy", "random_windows", "tsiligirides", "e5_real")
SET_LABELS = {"random_energy": "Random, energy\n(N 10-18)", "random_windows": "Random, windows\n(N 10-18)",
              "tsiligirides": "Tsiligirides\n(N 21-33)", "e5_real": "E5 real terrain\n(N 14, 27)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="2 instances per size, for a smoke test")
    ap.add_argument("--no-real", action="store_true", help="skip the E5 instances (no terrain data)")
    ap.add_argument("--figure-only", action="store_true", help="redraw the figure from e6_results.json")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    if args.figure_only:
        figure(json.loads((OUT / "e6_results.json").read_text(encoding="utf-8"))["summary"])
        return

    instances = []
    per_size = 2 if args.quick else PER_SIZE
    for kind in ("energy", "windows"):
        for n in SIZES:
            for case in range(per_size):
                rng = np.random.default_rng(1000 * n + case + (0 if kind == "energy" else 500))
                instances.append((f"random_{kind}", f"{kind}-n{n}-{case}", random_instance(rng, n, kind)))
    if instance_dir() is not None:
        ts = tsiligirides()
        instances += [("tsiligirides", name, p) for name, p in (ts[::8] if args.quick else ts)]
    else:
        print("KU Leuven instances not found: skipping tsiligirides")
    if not args.no_real:
        instances += real_instances()

    rows = []
    t0 = time.time()
    for k, (group, name, p) in enumerate(instances):
        rows += run(group, name, p)
        if k % 10 == 0:
            print(f"{k + 1}/{len(instances)} instances, {time.time() - t0:.0f} s")

    summary = summarise(rows)
    out = {"sizes": SIZES, "per_size": per_size, "sa_seeds": SA_SEEDS, "cpsat_limit_s": CPSAT_LIMIT_S,
           "ils": {"max_no_improve": ils.MAX_NO_IMPROVE, "time_limit_s": ils.TIME_LIMIT_S},
           "sa": {"steps": sa.STEPS, "t_start": sa.T_START, "t_end": sa.T_END},
           "summary": summary, "rows": rows}
    (OUT / "e6_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    with open(OUT / "e6_table.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    for r in summary:
        print(r)
    figure(summary)


def run(group, name, p):
    """Exact reference first (DP up to 20 nodes, else CP-SAT), then ILS and SA."""
    rows = []
    if p.n <= dp.MAX_STATIONS:
        ref = dp.solve(p)
        exact_name, proven = "dp", True
    else:
        ref = cpsat.solve(p, CPSAT_LIMIT_S)
        exact_name, proven = "cpsat", bool(ref.optimal)
    rows.append(row(group, name, p, "exact", exact_name, ref, ref.prize, proven))
    rows.append(row(group, name, p, "ils", "ils", ils.solve(p), ref.prize, proven))
    for seed in SA_SEEDS:
        rows.append(row(group, name, p, "sa", f"sa-{seed}", sa.solve(p, seed=seed), ref.prize, proven))
    return rows


def row(group, name, p, method, solver, sol, best, proven):
    if sol.route:
        check = evaluate_route(p, sol.route)
        assert check["feasible"] and check["energy"] <= p.budget + 1e-6, (name, solver)
    gap = 0.0 if best <= 0 else (best - sol.prize) / best
    return {"set": group, "instance": name, "n": p.n, "method": method, "solver": solver,
            "prize": round(sol.prize, 4), "optimum": round(best, 4), "optimum_proven": proven,
            "gap": round(gap, 5), "runtime_s": round(sol.runtime_s, 4)}


def summarise(rows):
    out = []
    for group in SETS:
        for method in METHODS:
            sel = [r for r in rows if r["set"] == group and r["method"] == method]
            if not sel:
                continue
            gaps = np.array([r["gap"] for r in sel])
            times = np.array([r["runtime_s"] for r in sel])
            out.append({"set": group, "method": method,
                        "n_range": f"{min(r['n'] for r in sel)}-{max(r['n'] for r in sel)}",
                        "instances": len({r["instance"] for r in sel}), "runs": len(sel),
                        "optimum_proven": sum(r["optimum_proven"] for r in sel),
                        "optimal_share": round(float((gaps < 1e-9).mean()), 3),
                        "mean_gap_pct": round(100 * float(gaps.mean()), 2),
                        "max_gap_pct": round(100 * float(gaps.max()), 2),
                        "median_time_s": round(float(np.median(times)), 3),
                        "max_time_s": round(float(times.max()), 3)})
    return out


def real_instances():
    """The E5 instances on the real terrain (same setup as paper_figures / paper_ortools)."""
    from grafos.build_rv import SERVICE_POWER_W
    from grafos.walkback import J_PER_WH

    from orienteering.data_io import DATA_DIR, STATIONS_PATH, read_station_files
    from orienteering.network import load_graph, place_habitat, reachable_stations, station_matrices
    from orienteering.paper_figures import BOX_CENTRE, BUDGET_WH, MARGIN
    from orienteering.problem import Problem

    e8 = DATA_DIR / "stations" / "stations_e8.gpkg"
    if not STATIONS_PATH.exists():
        print("manual stations not found: skipping e5_real")
        return []
    graph, main_cc = load_graph()
    paths = [STATIONS_PATH] + ([e8] if e8.exists() else [])
    stations = read_station_files(graph, paths)
    hr, hc, _ = place_habitat(graph, BOX_CENTRE)
    hx, hy = (float(v) for v in graph.cell_to_xy(hr, hc))
    stations = stations.prepend("habitat", "habitat", hx, hy, hr, hc)
    stations = stations.subset(reachable_stations(main_cc, stations))
    dis, tim = station_matrices(graph, stations)
    manual = np.array([not str(i).startswith("E8-") for i in stations.id])
    usable = BUDGET_WH * (1 - MARGIN) * J_PER_WH
    out = []
    for label, keep in (("manual", np.flatnonzero(manual)), ("manual+E8", np.arange(len(stations)))):
        if label == "manual+E8" and manual.all():
            continue
        ix = np.ix_(keep, keep)
        for scen, max_d in (("nominal", None), ("120min", 7200.0)):
            p = Problem(energy=dis[ix], prize=stations.prize[keep], budget=usable, time=tim[ix],
                        service_s=stations.service_s[keep],
                        service_j=stations.service_s[keep] * SERVICE_POWER_W, max_duration_s=max_d)
            out.append(("e5_real", f"{label}-{scen}", p))
    return out


def figure(summary):
    groups = [g for g in SETS if any(r["set"] == g for r in summary)]
    fig, (ax_gap, ax_time) = plt.subplots(1, 2, figsize=(12, 4.6), constrained_layout=True)
    width = 0.26
    x = np.arange(len(groups))
    for m, method in enumerate(METHODS):
        get = {r["set"]: r for r in summary if r["method"] == method}
        xs = x + (m - 1) * width
        gaps = [get[g]["mean_gap_pct"] if g in get else np.nan for g in groups]
        times = [get[g]["median_time_s"] if g in get else np.nan for g in groups]
        ax_gap.bar(xs, gaps, width - 0.03, color=COLOURS[method], label=LABELS[method],
                   edgecolor="white", linewidth=1.0, zorder=2)
        ax_time.scatter(xs, times, s=46, color=COLOURS[method], edgecolor="white", linewidth=1.5,
                        label=LABELS[method], zorder=3)
        for ax, vals, fmt in ((ax_gap, gaps, "{:.1f}"), (ax_time, times, "{:.2g}")):
            for xi, v in zip(xs, vals):
                if np.isfinite(v):
                    ax.annotate(fmt.format(v), (xi, v), xytext=(0, 5), textcoords="offset points",
                                ha="center", va="bottom", fontsize=7, color="#3a3a38")
    ax_gap.set_ylabel("Mean gap to the optimum (% of points)")
    ax_time.set_ylabel("Median running time (s, log scale)")
    ax_time.set_yscale("log")
    ax_time.set_ylim(0.02, 1.5)
    ax_time.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax_time.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax_time.set_yticks([0.02, 0.05, 0.1, 0.2, 0.5, 1.0])
    for ax in (ax_gap, ax_time):
        ax.set_xticks(x, [SET_LABELS[g] for g in groups], fontsize=8)
        ax.grid(axis="y", color="#e4e3df", linewidth=0.6, zorder=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.tick_params(labelsize=8)
    ax_gap.legend(fontsize=8, frameon=False, loc="upper left")
    fig.savefig(FIG / "e6_fig1_gap_runtime.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
