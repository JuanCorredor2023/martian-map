"""E1 step 3 - fit the terrain prices to Curiosity's drives (MaxEnt IRL).

Fits on every drive (src/ml/irl_data.py) two models:
  terrain        all features of irl_data.FEATURES
  distance_only  control: every terrain price held at 0, only the price of a metre
The control knows each drive's start and goal too, so it already explains a
lot ("go roughly straight"). Terrain only explains the route if the terrain
model beats the control. This in-sample fit gives the weights; the honest test
on drives the model has not seen is src/ml/validate_irl.py.

Output: data/e1/irl_fit.json
Usage:  python src/ml/fit_irl.py
"""
import json
import time

import numpy as np
import torch

import common
import irl_data
import maxent_irl as irl

L2 = 0.0
CHUNK = 32


def describe(w, ev, total_m):
    real = ev.expected.sum(0) + ev.grad.sum(0)
    return {
        "w": dict(zip(irl_data.FEATURES, np.round(w, 5).tolist())),
        "w_relative_to_metre": dict(zip(irl_data.FEATURES, np.round(w / w[0], 5).tolist())),
        "nll_per_m": float(ev.nll.sum() / total_m),
        "feature_counts_real": dict(zip(irl_data.FEATURES, np.round(real, 2).tolist())),
        "feature_counts_model": dict(zip(irl_data.FEATURES, np.round(ev.expected.sum(0), 2).tolist())),
        "w0_at_floor": bool(np.isclose(w[0], irl.W0_MIN)),
    }


def main():
    common.E1_OUTPUT.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.perf_counter()
    phi, scale, _ = irl_data.feature_stack()
    table = irl_data.drives()
    demos = irl_data.demos(phi, table)
    batches = irl.make_batches(demos, chunk=CHUNK, device=device)
    print(f"{len(demos)} drives ready in {time.perf_counter() - t0:.0f} s, device {device}", flush=True)

    n_f = len(irl_data.FEATURES)
    w_init = np.r_[3.0, np.full(n_f - 1, 0.5)]
    print("distance-only control:", flush=True)
    w_dist, info_dist = irl.fit(batches, w_init, fixed={i: 0.0 for i in range(1, n_f)}, verbose=True)
    print("terrain model:", flush=True)
    w_fit, info = irl.fit(batches, w_init, l2=L2, verbose=True)
    total_m = info["total_m"]
    ev_fit, ev_dist = irl.evaluate(w_fit, batches), irl.evaluate(w_dist, batches)

    report = {
        "features": irl_data.FEATURES, "feature_scale_p99": scale,
        "n_drives": len(demos), "route_grid_m": total_m, "min_drive_m": irl_data.MIN_DRIVE_M,
        "margin_m": irl_data.MARGIN_M, "l2": L2, "w0_min": irl.W0_MIN, "device": device,
        "terrain": describe(w_fit, ev_fit, total_m) | {
            "fit": {k: info[k] for k in ("success", "message", "n_eval", "seconds")}},
        "distance_only": describe(w_dist, ev_dist, total_m) | {
            "fit": {k: info_dist[k] for k in ("success", "message", "n_eval", "seconds")}},
        "per_drive": [{"sol": int(s), "block": int(b), "length_m": float(m),
                       "nll_terrain": float(a), "nll_distance_only": float(c)}
                      for s, b, m, a, c in zip(table.sol, table.block, table.length_m,
                                               ev_fit.nll, ev_dist.nll)],
    }
    (common.E1_OUTPUT / "irl_fit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    better = int((ev_fit.nll < ev_dist.nll).sum())
    print(f"\nNLL per metre: terrain {report['terrain']['nll_per_m']:.4f}, "
          f"distance only {report['distance_only']['nll_per_m']:.4f}; "
          f"terrain better on {better}/{len(demos)} drives")
    print("terrain weights:", report["terrain"]["w"])
    print(f"wrote {common.E1_OUTPUT / 'irl_fit.json'} ({time.perf_counter() - t0:.0f} s)")


if __name__ == "__main__":
    main()
