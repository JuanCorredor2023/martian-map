"""E12 numbers and figures for the paper (paper/notes/E12_radiation_dose.md).

Usage (repo root), after rad_data.py, route_dose.py --out-and-back, sensitivity.py
and sep_alert.py:
    python src/radiation/paper_figures.py
Inputs:  data/e12/*.json, rad_dose_rate.csv, sensitivity.csv, sep_return_time_s.tif,
         data/base/dem_1m.tif, slope_deg.tif, data/e2/trajectory.geojson, cell_sequence.csv
Outputs: data/e12/e12_summary.json   every number quoted in the note
         paper/figures/e12_fig1_rad_dose_rate.png
         paper/figures/e12_fig2_eva_dose_timeline.png
         paper/figures/e12_fig3_sensitivity.png
         paper/figures/e12_fig4_return_time_map.png
"""
import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fisica.edge_cost import NEIGHBOURS, edge_costs  # noqa: E402
from radiation.common import BASE, E2_OUTPUT, E12_OUTPUT, REPO  # noqa: E402
from radiation.route_dose import (DoseRate, background_rate, load_route, out_and_back,  # noqa: E402
                                  route_timeline, sample_raster)
from radiation.sep_alert import BASELINE_WINDOW, K_ON, load_rates  # noqa: E402

FIG_DIR = REPO / "paper" / "figures"

# Reference palette (dataviz skill, light mode)
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]      # blue, orange, aqua (fixed order)
CRITICAL = "#d03b3b"                            # status: alarm
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": MUTED, "axes.labelcolor": TEXT_2, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": TEXT, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9, "axes.titlesize": 10,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
    "lines.linewidth": 1.8,
})


def load_json(name):
    return json.loads((E12_OUTPUT / name).read_text(encoding="utf-8"))


# ------------------------------------------------------------------------ check

def e3_edge_check(dem_path, slope_path):
    """Curiosity's one-way route timed two ways: E12 resampling vs E3 edges on the cell sequence."""
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float64)
    with rasterio.open(slope_path) as src:
        slope = src.read(1).astype(np.float64)
    # no slope limits: the rover's real path crosses steeper edges than a planner would
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)          # 60 deg is on purpose here
        time_s, _, _ = edge_costs(dem, 1.0, max_slope_deg=60.0, cell_slope_deg=slope, max_cell_slope_deg=None)
    seq = pd.read_csv(E2_OUTPUT / "cell_sequence.csv")
    k_of = {d: k for k, d in enumerate(NEIGHBOURS)}
    total, length, missing = 0.0, 0.0, 0
    r, c = seq["row"].to_numpy(), seq["col"].to_numpy()
    for i in range(len(seq) - 1):
        k = k_of.get((int(r[i + 1] - r[i]), int(c[i + 1] - c[i])))
        t = time_s[k, r[i], c[i]] if k is not None else np.nan
        if np.isfinite(t):
            total += float(t)
            length += float(np.hypot(*NEIGHBOURS[k]))
        else:
            missing += 1
    xy, _ = load_route(E2_OUTPUT / "trajectory.geojson")
    tl = route_timeline(xy, dem_path, DoseRate.constant(1.0))
    t_line, l_line = float(tl["t_s"].iloc[-1]), float(tl["dist_m"].iloc[-1])
    return {"e3_edges_cell_sequence_h": round(total / 3600, 3), "e12_resampled_line_h": round(t_line / 3600, 3),
            "cell_path_length_m": round(length, 1), "line_length_m": round(l_line, 1),
            "cell_steps": int(len(seq) - 1), "steps_without_edge": missing,
            "time_relative_difference": round(t_line / total - 1, 4),
            "s_per_m_cells": round(total / length, 4), "s_per_m_line": round(t_line / l_line, 4),
            "s_per_m_relative_difference": round((t_line / l_line) / (total / length) - 1, 4)}


# ---------------------------------------------------------------------- figures

def fig1_rad(rad, sep):
    df = pd.read_csv(E12_OUTPUT / "rad_dose_rate.csv", parse_dates=["utc"])
    good = df[df["quality_ok"]].set_index("utc")
    daily = good[["dose_e_ugy_day", "dose_b_rtg_ugy_day"]].resample("D").mean()
    ev = sep["strongest_event"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.2, 3.4), gridspec_kw={"width_ratios": [1.7, 1]})

    b0, b1 = pd.Timestamp(rad["boxwork_utc"][0]), pd.Timestamp(rad["boxwork_utc"][1])
    a.axvspan(b0, b1, color=GRID, alpha=0.6, lw=0)
    a.text(b0 + (b1 - b0) / 2, 86, "boxwork sols 4541–4848", ha="center", color=TEXT_2, fontsize=8)
    a.plot(daily.index, daily["dose_e_ugy_day"], color=SERIES[0], label="Tissue-equivalent (E)")
    a.plot(daily.index, daily["dose_b_rtg_ugy_day"], color=SERIES[1], label="Silicon, MMRTG-corrected (B)")
    a.annotate("SEP 2025-11-11", xy=(pd.Timestamp(ev["onset_utc"]), daily["dose_e_ugy_day"].loc["2025-11-11"]),
               xytext=(28, 12), textcoords="offset points", ha="left", color=TEXT_2, fontsize=8,
               arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    a.set_ylim(80, 210)
    a.set_ylabel("Daily mean dose rate (µGy/day)")
    a.set_title("(a) RAD surface dose rate, 2025–2026")
    a.legend(loc="upper left", fontsize=8)
    a.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    a.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 5, 9]))

    rates = load_rates()
    w = rates.loc["2025-11-10T12:00":"2025-11-12T12:00"]
    base = rates.rolling(BASELINE_WINDOW, min_periods=10).median().shift(1).loc[w.index]
    b.plot(w.index, w.to_numpy(), color=SERIES[0], lw=1.4, marker="o", ms=2.5, label="Detector E, 17 min")
    b.plot(base.index, K_ON * base.to_numpy(), color=MUTED, lw=1.2, ls="--", label=f"{K_ON}× baseline")
    t_alarm = pd.Timestamp(ev["alarm_utc"])
    b.axvline(t_alarm, color=CRITICAL, lw=1.2)
    b.text(t_alarm, 300, " alarm " + t_alarm.strftime("%H:%M UTC"), color=TEXT, fontsize=8, va="top")
    b.set_ylim(120, 310)
    b.set_ylabel("Dose rate (µGy/day)")
    b.set_title("(b) 2025-11-11 event and alarm")
    b.legend(loc="upper left", fontsize=7.5, bbox_to_anchor=(0.0, 0.9))
    b.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    b.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 12]))
    fig.tight_layout()
    fig.savefig(FIG_DIR / "e12_fig1_rad_dose_rate.png", dpi=150)
    plt.close(fig)


def fig2_timeline(sep, rate_bg):
    xy, _ = load_route(E2_OUTPUT / "trajectory.geojson")
    xy = out_and_back(xy)
    dem = BASE / "dem_1m.tif"
    tl_bg = route_timeline(xy, dem, DoseRate.constant(rate_bg))
    far = sep["replay"]["farthest"]
    tl_sep = route_timeline(xy, dem, DoseRate.series(), start_utc=far["eva_start_utc"])
    short = sample_raster(E12_OUTPUT / "sep_return_time_s.tif", tl_bg[["x", "y"]].to_numpy(), order=0)
    h = tl_bg["t_s"] / 3600
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.2, 3.3))
    a.plot(h, tl_bg["dose_ugy"], color=SERIES[0], label=f"Boxwork background ({rate_bg:.0f} µGy/day)")
    a.plot(h, tl_sep["dose_ugy"], color=SERIES[1], label="Real series, EVA during the 2025-11-11 SEP")
    t_alarm_h = (pd.Timestamp(sep["strongest_event"]["alarm_utc"])
                 - pd.Timestamp(far["eva_start_utc"])).total_seconds() / 3600
    a.axvline(t_alarm_h, color=CRITICAL, lw=1.2)
    a.text(t_alarm_h, 26, "alarm ", color=TEXT, fontsize=8, va="center", ha="right")
    a.text(h.iloc[-1], tl_bg["dose_ugy"].iloc[-1], f" {tl_bg['dose_ugy'].iloc[-1]:.1f} µGy", color=TEXT_2,
           fontsize=8, va="center")
    a.text(h.iloc[-1], tl_sep["dose_ugy"].iloc[-1], f" {tl_sep['dose_ugy'].iloc[-1]:.1f} µGy", color=TEXT_2,
           fontsize=8, va="center")
    a.set_xlim(0, h.iloc[-1] * 1.18)
    a.set_xlabel("EVA time (h)")
    a.set_ylabel("Accumulated absorbed dose (µGy)")
    a.set_title("(a) Dose along the provisional EVA (out and back)")
    a.legend(loc="lower right", fontsize=7.5, bbox_to_anchor=(1.0, 0.0))

    b.plot(h, tl_bg["return_s"] / 3600, color=SERIES[0], label="Along the route (retrace or go on)")
    b.plot(h, short / 3600, color=SERIES[2], label="Shortest-time path (E3 edges)")
    b.set_xlabel("EVA time (h)")
    b.set_ylabel("Walking time back to the habitat (h)")
    b.set_title("(b) Time to shelter if the alarm comes now")
    b.legend(loc="upper right", fontsize=7.5)
    b.set_ylim(0, 1.75)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "e12_fig2_eva_dose_timeline.png", dpi=150)
    plt.close(fig)
    return {"eva_out_and_back_h": round(float(h.iloc[-1]), 3),
            "dose_background_ugy": round(float(tl_bg["dose_ugy"].iloc[-1]), 2),
            "dose_during_sep_ugy": round(float(tl_sep["dose_ugy"].iloc[-1]), 2)}


def fig3_sensitivity():
    df = pd.read_csv(E12_OUTPUT / "sensitivity.csv")
    m = df[df.gravity == "mars"]
    sp, en = m[m.eta_mode == "speed"], m[m.eta_mode == "energy"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.2, 3.3), sharex=True)
    lines = [(sp, "dose_ugy_rel", SERIES[1], "Sand slows the walk (V/η)"),
             (en, "dose_ugy_rel", SERIES[0], "Sand only raises energy (E·η)"),
             (en, "budget_dose_ugy_rel", SERIES[2], "Energy only, fixed energy budget")]
    for d, col, color, label in lines:
        a.plot(d.eta, d[col], color=color, marker="o", ms=4, label=label)
    a.set_ylabel("Dose / nominal")
    a.set_xlabel("Terrain factor η (applied to the whole route)")
    a.set_title("(a) Dose, Mars gravity")
    a.legend(loc="upper left", fontsize=7.5)
    for d, color, label in [(sp, SERIES[1], "Sand slows the walk (V/η)"),
                            (en, SERIES[0], "Sand only raises energy (E·η)")]:
        b.plot(d.eta, d.energy_wh_rel, color=color, marker="o", ms=4, label=label)
    g = df[(df.eta == 1.0) & (df.eta_mode == "energy")].set_index("gravity").energy_wh_rel
    b.text(0.40, 0.36, "Gravity at η = 1 (energy / nominal):\n"
           f"Moon {g['moon']:.2f} · Mars {g['mars']:.2f} · Earth {g['earth']:.2f}\n"
           "EVA time and dose: identical for all three", transform=b.transAxes, fontsize=7.5, color=TEXT_2,
           va="top")
    b.set_ylabel("Energy / nominal")
    b.set_xlabel("Terrain factor η (applied to the whole route)")
    b.set_title("(b) Energy, Mars gravity")
    b.legend(loc="upper left", fontsize=7.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "e12_fig3_sensitivity.png", dpi=150)
    plt.close(fig)


def fig4_map(sep):
    with rasterio.open(E12_OUTPUT / "sep_return_time_s.tif") as src:
        ret = src.read(1) / 60.0
        b = src.bounds
    xy, _ = load_route(E2_OUTPUT / "trajectory.geojson")
    cmap = LinearSegmentedColormap.from_list("blue_seq", BLUE_RAMP)
    cmap.set_bad(GRID)
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    ext = [0, b.right - b.left, 0, b.top - b.bottom]
    im = ax.imshow(ret, cmap=cmap, extent=ext, interpolation="nearest")
    ax.plot(xy[:, 0] - b.left, xy[:, 1] - b.bottom, color=SERIES[1], lw=1.4, label="Curiosity's route (provisional EVA)")
    hx, hy = sep["return_time_map"]["habitat_xy"]
    ax.plot(hx - b.left, hy - b.bottom, marker="s", ms=7, color=TEXT, ls="none", label="Habitat (route start)")
    ax.grid(False)
    ax.set_xlabel("Easting in the crop (m)")
    ax.set_ylabel("Northing in the crop (m)")
    ax.set_title("Fastest walk back to the habitat (min)")
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("minutes; grey = blocked or unreachable", color=TEXT_2)
    cb.outline.set_visible(False)
    ax.legend(loc="upper left", fontsize=7.5, frameon=True, facecolor=SURFACE, edgecolor=GRID, framealpha=0.92)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "e12_fig4_return_time_map.png", dpi=150)
    plt.close(fig)


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    rad, sep, sens = load_json("rad_summary.json"), load_json("sep_alert.json"), load_json("sensitivity.json")
    route = load_json("route_dose_summary.json")
    rate_bg = background_rate()
    fig1_rad(rad, sep)
    timeline = fig2_timeline(sep, rate_bg)
    fig3_sensitivity()
    fig4_map(sep)
    summary = {
        "rad": {k: rad[k] for k in ["observations", "observations_flagged_fill", "first_utc", "last_utc",
                                    "boxwork_utc", "nominal", "unit_check", "within_day_cv_median",
                                    "mmrtg_share_of_b", "isolated_spikes"]},
        "rad_daily_boxwork": rad["boxwork_daily_mean_stats"],
        "rad_monthly_dose_e": {k: v["dose_e"] for k, v in rad["monthly_median"].items()},
        "route_out_and_back": route,
        "timeline_figure": timeline,
        "sensitivity": sens,
        "sep": {k: sep[k] for k in ["rule", "events", "return_time_map", "replay"]},
        "sep_threshold_sweep": sep["threshold_sweep"],
        "check_against_e3_edges": e3_edge_check(BASE / "dem_1m.tif", BASE / "slope_deg.tif"),
    }
    (E12_OUTPUT / "e12_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["check_against_e3_edges"], indent=2))
    print(json.dumps(timeline, indent=2))
    for p in sorted(FIG_DIR.glob("e12_*.png")):
        print(p.name, p.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
