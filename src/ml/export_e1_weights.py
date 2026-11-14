"""E1 -> E3 hand-off: write data/e1/e1_weights.json in the format agreed in #2 (read by fisica.human_cost).

Format (Sebas, issue #2, PR #41): per feature a weight >= 0, the raster it comes
from, the min/max of the 0-1 scaling, `transform` positive/negative for the
two halves of TPI, and `slope: true` for slope features (dropped by E3, which
already charges slope). `distance_weight` is the learned price of a metre.
Rasters are given relative to the feature directory of
src/fisica/build_cost_layers.py (by default the DEM's folder, data/base/).

Which weights are handed over: the per-sol models at 1 m (fit_irl.py and
validate_irl.py with --features dem, sand and dem_sand) are the candidates.
Only a model whose terrain prices beat the distance-only control on held-out
blocks (held-out NLL per metre) can be handed over; among those, the one with
the lowest held-out NLL wins. If none beats the control, every weight is 0: a
price that does not generalise would add noise to the planner. The fitted
values are always kept in `fitted_weight` (ignored by E3).

Exact scaling: E1 uses x / p99 without clipping; fisica.human_cost uses
clip(x / max, 0, 1). We export max = the true maximum of x over the box (so the
clip never acts) and weight = w * max / p99, which gives exactly the same
cost. For the sand layers p99 = max = 1, so the weights are unchanged.

The 5 x 5 m mean of sand has no raster of its own, so this script writes it to
data/e1/sand_mean_5m.tif (float32, base grid) when the chosen model uses it.

Input:  data/e1/irl_fit_<tag>.json and data/e1/validation_<tag>.json for every candidate
Output: data/e1/e1_weights.json (and data/e1/sand_mean_5m.tif if needed)
Usage:  python src/ml/export_e1_weights.py
"""
import json

import numpy as np
import rasterio

import common
import irl_data

CANDIDATES = {"dem": "per_sol_cell1m_margin50m",
              "sand": "per_sol_cell1m_margin50m_sand",
              "dem_sand": "per_sol_cell1m_margin50m_dem_sand"}
SAND_MEAN_TIF = common.E1_OUTPUT / "sand_mean_5m.tif"
# feature -> (raster relative to data/base/, transform, slope feature, note)
SOURCES = {
    "roughness": ("roughness.tif", None, False, None),
    "tpi_ridge": ("tpi.tif", "positive", False, None),
    "tpi_hollow": ("tpi.tif", "negative", False, None),
    "slope_deg": ("slope_deg.tif", None, True, None),
    "slope_mean_5m": ("slope_deg.tif", None, True, "mean of slope_deg.tif over a 5 x 5 m window"),
    "slope_mean_15m": ("slope_deg.tif", None, True, "mean of slope_deg.tif over a 15 x 15 m window"),
    "sand": ("../e8/sand.tif", None, False, "E8 sand fraction (release e8-v0)"),
    "sand_mean_5m": ("../e1/sand_mean_5m.tif", None, False,
                     "mean of sand.tif over a 5 x 5 m window, written by src/ml/export_e1_weights.py"),
}


def load(kind, tag):
    path = common.E1_OUTPUT / f"{kind}_{tag}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def candidates():
    out = {}
    for name, tag in CANDIDATES.items():
        fit, val = load("irl_fit", tag), load("validation", tag)
        if fit is None or val is None:
            continue
        s = val["summary"]
        out[name] = {"tag": tag, "fit": fit,
                     "held_out_nll_per_m": {"terrain": s["terrain"]["nll_per_m"],
                                            "distance_only": s["distance_only"]["nll_per_m"]},
                     "beats_control": s["terrain"]["nll_per_m"] < s["distance_only"]["nll_per_m"]}
    return out


def write_sand_mean():
    phi, _, transform = irl_data.feature_stack(["metre", "sand", "sand_mean_5m"])
    with rasterio.open(common.base_layer("dem_1m.tif")) as dem:
        profile = dem.profile | {"dtype": "float32", "count": 1, "nodata": np.nan}
    with rasterio.open(SAND_MEAN_TIF, "w", **profile) as dst:
        dst.write(phi[2].astype(np.float32), 1)   # scale is 1: phi = the 5 x 5 m mean itself


def factor_check(spec, phi, feats, w):
    """Run E3's own reader (fisica.human_cost) on the spec and compare with E1's formula."""
    from fisica import human_cost as hc        # src/ is on sys.path (maxent_irl)
    tmp = common.E1_OUTPUT / "_e1_weights_check.json"
    tmp.write_text(json.dumps(spec), encoding="utf-8")
    try:
        loaded = hc.load_weights(tmp)
        factor = hc.terrain_factor(loaded, hc.load_rasters(loaded, common.BASE), phi.shape[1:])
    finally:
        tmp.unlink()
    # E1's own price relative to a metre: fitted weights on E1's scaled features (x / p99).
    non_slope = [j for j, n in enumerate(feats) if j > 0 and not SOURCES[n][2]]
    e1 = np.ones(phi.shape[1:])
    if spec["validated"]:
        e1 = e1 + sum(w[feats[j]] * phi[j].astype(np.float64) for j in non_slope) / w["metre"]
    return {"min": float(factor.min()), "median": float(np.median(factor)),
            "p95": float(np.percentile(factor, 95)), "max": float(factor.max()),
            "share_above_1_05": float((factor > 1.05).mean()),
            "max_abs_diff_vs_e1_formula": float(np.abs(factor - e1).max())}


def main():
    cands = candidates()
    if "dem" not in cands:
        raise SystemExit("run fit_irl.py and validate_irl.py (default features) first")
    passing = {k: c for k, c in cands.items() if c["beats_control"]}
    chosen = min(passing, key=lambda k: passing[k]["held_out_nll_per_m"]["terrain"]) if passing else "dem"
    c = cands[chosen]
    fit, validated = c["fit"], bool(passing)
    feats = fit["features"]
    phi, scale, _ = irl_data.feature_stack(feats)
    w = fit["terrain"]["w"]
    features = {}
    for j, name in enumerate(feats[1:], start=1):
        raster, transform, slope, note = SOURCES[name]
        true_max = float(np.nanmax(phi[j])) * scale[name]
        factor = true_max / scale[name]          # weight conversion for clip(x / true_max)
        f = {"weight": w[name] * factor if validated else 0.0, "fitted_weight": w[name],
             "raster": raster, "min": 0.0, "max": true_max}
        if transform:
            f["transform"] = transform
        if slope:
            f["slope"] = True
        if note:
            f["note"] = note
        features[name] = f
    if validated and "sand_mean_5m" in feats:
        write_sand_mean()
    non_slope = [n for n in feats[1:] if not SOURCES[n][2]]
    max_factor = 1 + sum(features[n]["weight"] for n in non_slope) / w["metre"]
    spec = {
        "distance_weight": w["metre"],
        "features": features,
        "validated": validated,
        "model": chosen,
        "result": (f"the '{chosen}' model beats the distance-only control on held-out blocks; its prices are "
                   f"handed over (terrain factor 1 to {max_factor:.3f})" if validated else
                   "no terrain price beats the distance-only control on held-out blocks: every weight is 0, "
                   "so the human cost is E3 alone (factor 1)"),
        "candidates": {k: {"tag": v["tag"], "held_out_nll_per_m": v["held_out_nll_per_m"],
                           "beats_control": v["beats_control"]} for k, v in cands.items()},
        "source": f"src/ml/fit_irl.py -> data/e1/irl_fit_{c['tag']}.json; "
                  f"src/ml/validate_irl.py -> data/e1/validation_{c['tag']}.json",
        "raster_paths": "relative to the feature directory of build_cost_layers.py (default: data/base/)",
        "scaling": "max = true maximum over the box and weight = w * max / p99, so human_cost's clip never acts "
                   "and the cost equals E1's w * x / p99",
    }
    spec["terrain_factor_check"] = factor_check(spec, phi, feats, w)
    out = common.E1_OUTPUT / "e1_weights.json"
    out.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(json.dumps({k: spec[k] for k in ("model", "validated", "result", "candidates")}, indent=2))
    print(f"wrote {out}" + (f" and {SAND_MEAN_TIF}" if validated and "sand_mean_5m" in feats else ""))


if __name__ == "__main__":
    main()
