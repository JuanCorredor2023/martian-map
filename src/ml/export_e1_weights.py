"""E1 -> E3 hand-off: write data/e1/e1_weights.json in the format agreed in #2 (read by fisica.human_cost).

Format (Sebas, issue #2, PR #41): per feature a weight >= 0, the raster it comes
from, the min/max of the 0-1 scaling, `transform` positive/negative for the
two halves of TPI, and `slope: true` for slope features (dropped by E3, which
already charges slope). `distance_weight` is the learned price of a metre.

Which weights are handed over: the per-sol model at 1 m (fit_irl.py, default
options) is the one that matches the base grid. Its terrain prices are only
handed over if they beat the distance-only control on held-out blocks
(validate_irl.py, held-out NLL per metre). Otherwise every weight is 0: a
price that does not generalise would add noise to the planner. The fitted
values are kept in `fitted_weight` for the record (ignored by E3).

E1 scales each feature as x / p99 (min 0, max = p99 of the box) without
clipping; fisica.human_cost clips at 1. The two only differ in the top 1 % of
cells, and not at all while the weights are 0.

Input:  data/e1/irl_fit_per_sol_cell1m_margin50m.json, data/e1/validation_per_sol_cell1m_margin50m.json
Output: data/e1/e1_weights.json
Usage:  python src/ml/export_e1_weights.py
"""
import json

import common

TAG = "per_sol_cell1m_margin50m"
# feature -> (raster in data/base/, transform, slope feature, extra note)
SOURCES = {
    "roughness": ("roughness.tif", None, False, None),
    "tpi_ridge": ("tpi.tif", "positive", False, None),
    "tpi_hollow": ("tpi.tif", "negative", False, None),
    "slope_deg": ("slope_deg.tif", None, True, None),
    "slope_mean_5m": ("slope_deg.tif", None, True, "mean of slope_deg.tif over a 5 x 5 m window"),
    "slope_mean_15m": ("slope_deg.tif", None, True, "mean of slope_deg.tif over a 15 x 15 m window"),
}


def main():
    fit = json.loads((common.E1_OUTPUT / f"irl_fit_{TAG}.json").read_text(encoding="utf-8"))
    val = json.loads((common.E1_OUTPUT / f"validation_{TAG}.json").read_text(encoding="utf-8"))
    held_out = val["summary"]
    validated = held_out["terrain"]["nll_per_m"] < held_out["distance_only"]["nll_per_m"]
    w = fit["terrain"]["w"]
    features = {}
    for name, (raster, transform, slope, note) in SOURCES.items():
        f = {"weight": w[name] if validated else 0.0, "fitted_weight": w[name], "raster": raster,
             "min": 0.0, "max": fit["feature_scale_p99"][name]}
        if transform:
            f["transform"] = transform
        if slope:
            f["slope"] = True
        if note:
            f["note"] = note
        features[name] = f
    spec = {
        "distance_weight": w["metre"],
        "features": features,
        "validated": validated,
        "result": ("terrain prices beat the distance-only control on held-out blocks" if validated else
                   "no terrain price beats the distance-only control on held-out blocks: every weight is 0, "
                   "so the human cost is E3 alone (factor 1)"),
        "held_out_nll_per_m": {"terrain": held_out["terrain"]["nll_per_m"],
                               "distance_only": held_out["distance_only"]["nll_per_m"]},
        "source": f"src/ml/fit_irl.py -> data/e1/irl_fit_{TAG}.json; "
                  f"src/ml/validate_irl.py -> data/e1/validation_{TAG}.json",
        "scaling": "E1 fitted x / max without clipping; human_cost clips at 1 (differs only above the 99th percentile)",
    }
    out = common.E1_OUTPUT / "e1_weights.json"
    out.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(json.dumps(spec, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
