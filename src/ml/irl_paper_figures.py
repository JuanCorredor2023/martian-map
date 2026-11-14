"""Figures and summary numbers of E1 for the paper (paper/figures/e1_*, paper/notes/E1_maxent_irl.md).

Reads the E1 outputs in data/e1/ and writes:
  data/e1/e1_summary.json        every number quoted in the E1 note that is not in another E1 file
  e1_fig2_scales.png             terrain model vs distance-only control at every demonstration scale
  e1_fig3_validation.png         leave-one-block-out NLL and cell-level AUC against E2's baseline
  e1_fig4_whole_box_routes.png   real route vs the cheapest route between the same points (whole box)
  e1_fig5_sand.png               held-out NLL with E8 sand and the sand prices fitted without each block
(e1_fig1_toy_check.png is written by irl_toy_check.py.)

Usage:  python src/ml/irl_paper_figures.py
        (after irl_toy_check.py, fit_irl.py for every scale in SCALES, validate_irl.py for VALIDATIONS,
        fit_irl.py and validate_irl.py with --features sand and dem_sand, logistic_sand.py)
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from skimage.graph import route_through_array  # noqa: E402

import common  # noqa: E402
import irl_data  # noqa: E402

FIGURES = common.REPO / "paper" / "figures"
# (tag of data/e1/irl_fit_<tag>.json, label)
SCALES = [
    ("per_sol_cell1m_margin50m", "one sol (~30 m)\n1 m cells, 50 m margin"),
    ("piece100m_cell1m_margin50m", "100 m pieces\n1 m, 50 m margin"),
    ("piece250m_cell1m_margin75m", "250 m pieces\n1 m, 75 m margin"),
    ("piece500m_cell1m_margin100m", "500 m pieces\n1 m, 100 m margin"),
    ("piece250m_cell5m_box", "250 m pieces\n5 m, whole box"),
    ("piece1000m_cell5m_box", "1000 m pieces\n5 m, whole box"),
]
SHORT = ["one sol\n1 m", "100 m\n1 m", "250 m\n1 m", "500 m\n1 m", "250 m\n5 m, box", "1 km\n5 m, box"]
VALIDATIONS = [("per_sol_cell1m_margin50m", "one sol, 1 m"), ("piece250m_cell5m_box", "250 m, 5 m, whole box")]
# Per-sol, 1 m models with E8 sand: (tag suffix, label)
SAND_MODELS = [("", "DEM features"), ("_sand", "sand only"), ("_dem_sand", "DEM features + sand")]


def load(name):
    return json.loads((common.E1_OUTPUT / name).read_text(encoding="utf-8"))


def summary():
    fits = {tag: load(f"irl_fit_{tag}.json") for tag, _ in SCALES}
    vals = {tag: load(f"validation_{tag}.json") for tag, _ in VALIDATIONS}
    out = {"feature_scale_p99": fits[SCALES[0][0]]["feature_scale_p99"], "scales": [], "validation": {}}
    for tag, _ in SCALES:
        f = fits[tag]
        terrain_w = {k: v for k, v in f["terrain"]["w"].items() if k != "metre"}
        out["scales"].append({
            "tag": tag, "n_demos": f["n_demos"], "route_m": round(f["route_m"], 1),
            "nll_per_m_terrain": round(f["terrain"]["nll_per_m"], 5),
            "nll_per_m_distance_only": round(f["distance_only"]["nll_per_m"], 5),
            "w_metre_terrain_model": f["terrain"]["w"]["metre"],
            "w_metre_distance_only": f["distance_only"]["w"]["metre"],
            "max_terrain_weight": max(terrain_w.values()),
            "max_terrain_weight_relative_to_metre": max(terrain_w.values()) / f["terrain"]["w"]["metre"],
            "max_abs_z": max(abs(v["z"]) for v in f["preference_check_at_distance_only"].values()),
            "demos_where_terrain_better": sum(d["nll_terrain"] < d["nll_distance_only"] - 1e-9
                                              for d in f["per_demo"]),
        })
    for tag, _ in VALIDATIONS:
        v = vals[tag]
        out["validation"][tag] = {
            "summary": v["summary"], "auc_terrain_cost": {k: a["mean"] for k, a in v["auc_terrain_cost"].items()},
            "auc_e2_logistic": v["auc_e2_logistic"],
            "blocks_with_terrain_weight": sum(any(x > 0 for k, x in b["w_terrain"].items() if k != "metre")
                                              for b in v["per_block"]),
            "nonzero_terrain_weights_by_block": [{k: x for k, x in b["w_terrain"].items() if k != "metre" and x > 0}
                                                 for b in v["per_block"]],
        }
    out["sand"] = sand_summary()
    (common.E1_OUTPUT / "e1_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return fits, vals, out


def sand_summary():
    """Numbers of the E8 sand models (per sol, 1 m) and of E2's logistic baseline with sand."""
    with rasterio.open(irl_data.SAND) as src:
        sand = src.read(1)
    out = {"sand_layer": {"share_cells_with_sand": float((sand > 0).mean()),
                          "p99": float(np.percentile(sand, 99)), "mean": float(sand.mean())},
           "models": {}}
    for suffix, label in SAND_MODELS:
        tag = "per_sol_cell1m_margin50m" + suffix
        f, v = load(f"irl_fit_{tag}.json"), load(f"validation_{tag}.json")
        diffs = [b["summary"]["terrain"]["nll_per_m"] - b["summary"]["distance_only"]["nll_per_m"]
                 for b in v["per_block"]]
        entry = {
            "label": label, "tag": tag,
            "w_full_fit": {k: x for k, x in f["terrain"]["w"].items() if x > 0},
            "in_sample_nll_per_m": {"terrain": f["terrain"]["nll_per_m"], "distance_only": f["distance_only"]["nll_per_m"]},
            "demos_where_terrain_better": sum(d["nll_terrain"] < d["nll_distance_only"] - 1e-9 for d in f["per_demo"]),
            "held_out_nll_per_m": {"terrain": v["summary"]["terrain"]["nll_per_m"],
                                   "distance_only": v["summary"]["distance_only"]["nll_per_m"]},
            "held_out_diff_per_block": diffs,
            "blocks_where_terrain_better": int(sum(d < 0 for d in diffs)),
            "auc_terrain_cost": {k: a["mean"] for k, a in v["auc_terrain_cost"].items()},
            "w_by_held_out_block": [{k: x for k, x in b["w_terrain"].items() if k != "metre" and x > 0}
                                    for b in v["per_block"]],
        }
        pc = f.get("preference_check_at_distance_only", {})
        entry["preference_check_sand"] = {k: x for k, x in pc.items() if "sand" in k}
        if "sand" in f["features"]:
            w = f["terrain"]["w"]
            entry["max_terrain_factor"] = 1 + sum(w[k] for k in ("sand", "sand_mean_5m")) / w["metre"]
        out["models"][suffix.strip("_") or "dem"] = entry
    lg = json.loads((common.E2_OUTPUT / "logistic_baseline_sand.json").read_text(encoding="utf-8"))
    out["logistic_with_sand"] = {
        s: {m: lg["sets"][s][m]["auc_mean"] for m in ("dem_only", "dem_plus_sand", "sand_only")}
        for s in ("corridor_50m", "whole_box")}
    out["logistic_with_sand"]["source"] = "src/ml/logistic_sand.py -> data/e2/logistic_baseline_sand.json"
    return out


def fig_sand(out):
    s = out["sand"]["models"]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    for i, (key, m) in enumerate(s.items()):
        ax[0].plot(np.arange(5) + (i - 1) * 0.15, [1000 * d for d in m["held_out_diff_per_block"]], "o", ms=7,
                   label=f"{m['label']} (overall {1000 * (m['held_out_nll_per_m']['terrain'] - m['held_out_nll_per_m']['distance_only']):+.2f})")
    ax[0].axhline(0, color="0.3", lw=0.8)
    ax[0].set_xticks(range(5), [f"block {b}" for b in range(5)])
    ax[0].set_ylabel("held-out NLL per metre: model − distance only (× 1000)\n< 0: the model explains the route better")
    ax[0].set_title("(a) Leave-one-block-out, one demonstration per sol, 1 m")
    ax[0].legend(fontsize=8)

    m = s["sand"]
    for j, (feat, col) in enumerate([("sand", "tab:orange"), ("sand_mean_5m", "tab:brown")]):
        vals_ = [b.get(feat, 0.0) for b in m["w_by_held_out_block"]]
        ax[1].bar(np.arange(5) + (j - 0.5) * 0.35, vals_, 0.35, color=col, label=f"{feat} (fit without the block)")
        ax[1].axhline(m["w_full_fit"].get(feat, 0.0), color=col, ls="--", lw=1, label=f"{feat}, fit on all blocks")
    ax[1].set_xticks(range(5), [f"without block {b}" for b in range(5)], fontsize=8)
    ax[1].set_ylabel("price per metre at full sand (metre price ≈ 2.58)")
    ax[1].set_title("(b) Sand prices fitted without each block (sand-only model)")
    ax[1].set_ylim(0, 0.36)
    ax[1].legend(fontsize=8, loc="upper right", ncol=2)
    fig.tight_layout()
    fig.savefig(FIGURES / "e1_fig5_sand.png", dpi=130)
    plt.close(fig)


def fig_scales(fits):
    feats = irl_data.FEATURES[1:]
    fig, ax = plt.subplots(1, 2, figsize=(16, 5), gridspec_kw={"width_ratios": [1, 1.4]})
    x = np.arange(len(SCALES))
    gain = [1000 * (fits[t]["distance_only"]["nll_per_m"] - fits[t]["terrain"]["nll_per_m"]) for t, _ in SCALES]
    ax[0].bar(x, gain, color="tab:blue")
    ax[0].axhline(0, color="0.3", lw=0.8)
    ax[0].set_xticks(x, SHORT, fontsize=8)
    ax[0].set_ylabel("NLL per metre: control − terrain (× 1000)")
    ax[0].set_title("(a) What terrain adds over distance (in-sample fit)")
    ax[0].set_xlabel("demonstrations: length, cell size")
    lim = max(1.0, max(abs(g) for g in gain) * 1.5)
    ax[0].set_ylim(-lim, lim)

    for i, (t, lab) in enumerate(SCALES):
        z = [fits[t]["preference_check_at_distance_only"][f]["z"] for f in feats]
        ax[1].scatter(z, np.arange(len(feats)) + (i - 2.5) * 0.11, s=22, label=lab.replace("\n", ", "))
    ax[1].axvspan(-2, 2, color="0.9", zorder=0, label="|z| < 2: chance")
    ax[1].axvline(0, color="0.3", lw=0.8)
    ax[1].set_yticks(np.arange(len(feats)), feats)
    ax[1].set_xlabel("z of (real − model) feature per metre, at the distance-only fit\n"
                     "> 0: the real route crosses more of it;  < 0: less (a positive price would help)")
    ax[1].set_title("(b) Does the real route avoid or seek each feature?")
    ax[1].legend(fontsize=7.5, loc="upper left", bbox_to_anchor=(1.01, 1), title="demonstrations")
    fig.tight_layout()
    fig.savefig(FIGURES / "e1_fig2_scales.png", dpi=130)
    plt.close(fig)


def fig_validation(vals):
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    for i, (t, lab) in enumerate(VALIDATIONS):
        diffs = [1000 * (b["summary"]["terrain"]["nll_per_m"] - b["summary"]["distance_only"]["nll_per_m"])
                 for b in vals[t]["per_block"]]
        ax[0].plot(np.arange(5) + (i - 0.5) * 0.15, diffs, "o", ms=7, label=lab)
    ax[0].axhline(0, color="0.3", lw=0.8)
    ax[0].set_xticks(range(5), [f"block {b}" for b in range(5)])
    ax[0].set_ylabel("held-out NLL per metre: terrain − control (× 1000)\n> 0: terrain model worse")
    ax[0].set_title("(a) Leave-one-block-out: terrain model vs distance-only")
    ax[0].legend()

    sets = ["corridor_50m", "whole_box"]
    e2 = vals[VALIDATIONS[0][0]]["auc_e2_logistic"]
    bars = [("E2 logistic baseline", [e2[s] for s in sets], "0.6")]
    for t, lab in VALIDATIONS:
        bars.append((f"E1 learned cost ({lab})", [vals[t]["auc_terrain_cost"][s]["mean"] for s in sets], None))
    w = 0.25
    for i, (lab, vals_, col) in enumerate(bars):
        ax[1].bar(np.arange(2) + (i - 1) * w, vals_, w, label=lab, color=col)
    ax[1].axhline(0.5, color="tab:red", ls=":", label="chance")
    ax[1].set_xticks(range(2), ["50 m corridor", "whole box"])
    ax[1].set_ylim(0.4, 0.8)
    ax[1].set_ylabel("AUC, mean over held-out blocks")
    ax[1].set_title("(b) Visited vs not visited cells (same sets as E2)")
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "e1_fig3_validation.png", dpi=130)
    plt.close(fig)


def fig_whole_box_routes(fits):
    cell = 5
    phi, scale, _ = irl_data.feature_stack()
    pc = irl_data.coarse_features(phi, cell)
    table = irl_data.coarse_table(irl_data.pieces(250), cell)
    w = np.array([fits["piece250m_cell5m_box"]["distance_only"]["w"][f] for f in irl_data.FEATURES])
    cost = np.tensordot(w, pc, axes=1)
    slope15 = pc[irl_data.FEATURES.index("slope_mean_15m")] * scale["slope_mean_15m"]
    fig, ax = plt.subplots(figsize=(7.6, 7))
    im = ax.imshow(slope15, cmap="Greys", vmin=0, vmax=40, extent=(0, 2000, 2000, 0))
    fig.colorbar(im, ax=ax, label="mean slope over 15 m (°), 5 m cells", shrink=0.8)
    for i, r in enumerate(table.itertuples()):
        pred, _ = route_through_array(cost, tuple(r.path[0]), tuple(r.path[-1]), fully_connected=True, geometric=True)
        pred = (np.asarray(pred) + 0.5) * cell
        real = (r.path + 0.5) * cell
        ax.plot(real[:, 1], real[:, 0], color="tab:orange", lw=1.6, label="real route" if i == 0 else None)
        ax.plot(pred[:, 1], pred[:, 0], color="tab:blue", lw=1.0, ls="--",
                label="cheapest route, distance only" if i == 0 else None)
        ax.plot(*real[0, ::-1], "k.", ms=4)
    ax.set_xlabel("m east of the box's west edge")
    ax.set_ylabel("m south of the box's north edge")
    ax.set_title("Real route vs cheapest route between the same points\n(19 pieces of ~250 m; dots = piece starts)")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "e1_fig4_whole_box_routes.png", dpi=130)
    plt.close(fig)


def main():
    fits, vals, out = summary()
    fig_scales(fits)
    fig_validation(vals)
    fig_whole_box_routes(fits)
    fig_sand(out)
    print(json.dumps(out["sand"], indent=1))
    print(f"wrote {common.E1_OUTPUT / 'e1_summary.json'} and e1_fig2-5 in {FIGURES}")


if __name__ == "__main__":
    main()
