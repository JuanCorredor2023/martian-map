"""E3 - Directed edge costs over the base grid (8-neighbour graph).

Reference: zero-to-hero guide REV3, sections 17-18 and 22.

For every cell u and each of the 8 neighbours v we compute:
    alpha = atan((z_v - z_u) / d_h)           signed, along u -> v
    dt    = d_h / (V(alpha) * cos(alpha))     seconds
    E     = M_Santee(alpha, V, g) * dt        joules
The graph is DIRECTED: cost(u -> v) != cost(v -> u) when there is slope.

Output layout (shared contract with the graph code):
    time_s[k, row, col]   time to go from (row, col) to its neighbour k
    energy_j[k, row, col] energy for the same move
    k follows NEIGHBOURS below. NaN = edge does not exist (off-grid,
    nodata cell at either end, or |alpha| above the slope limit).
"""

import numpy as np

from .metabolic import G_MARS, TOTAL_MASS_KG

# (d_row, d_col) for k = 0..7. Row grows southwards (north-up raster).
NEIGHBOURS = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
#              N        NE       E       SE      S       SW       W        NW

DEFAULT_MAX_SLOPE_DEG = 20.0   # CSRM limit; the model is extrapolated beyond it


def _shifted(a, d_row, d_col):
    """a[row + d_row, col + d_col] aligned with a[row, col]; NaN off-grid."""
    out = np.full_like(a, np.nan)
    rows, cols = a.shape
    src_r = slice(max(d_row, 0), rows + min(d_row, 0))
    dst_r = slice(max(-d_row, 0), rows + min(-d_row, 0))
    src_c = slice(max(d_col, 0), cols + min(d_col, 0))
    dst_c = slice(max(-d_col, 0), cols + min(-d_col, 0))
    out[dst_r, dst_c] = a[src_r, src_c]
    return out


def santee_power_array(mass_kg, v, alpha_deg, g_mps2):
    """Vectorised version of metabolic.santee_2001_power (total only)."""
    a = np.radians(alpha_deg)
    w_level = (3.28 * mass_kg + 71.1) * (0.661 * v * np.cos(a) + 0.115)
    up = 3.5 * mass_kg * g_mps2 * v * np.sin(a)
    down = 2.4 * mass_kg * g_mps2 * v * np.sin(a) * 0.3 ** (np.abs(alpha_deg) / 7.65)
    w_slope = np.where(alpha_deg > 0, up, np.where(alpha_deg < 0, down, 0.0))
    return w_level + w_slope


def edge_costs(dem, cell_size_m=1.0, mass_kg=TOTAL_MASS_KG, g_mps2=G_MARS,
               signed=True, max_slope_deg=DEFAULT_MAX_SLOPE_DEG):
    """Directed time (s) and energy (J) for the 8 edges of every cell.

    dem: 2-D float array of elevations in metres, NaN = nodata.
    Returns (time_s, energy_j, alpha_deg), each float32 of shape (8, rows, cols).
    """
    dem = np.asarray(dem, dtype=np.float64)
    shape = (len(NEIGHBOURS),) + dem.shape
    time_s = np.full(shape, np.nan, dtype=np.float32)
    energy_j = np.full(shape, np.nan, dtype=np.float32)
    alpha_out = np.full(shape, np.nan, dtype=np.float32)

    for k, (dr, dc) in enumerate(NEIGHBOURS):
        d_h = cell_size_m * (np.sqrt(2.0) if dr and dc else 1.0)
        dz = _shifted(dem, dr, dc) - dem                     # NaN if either end is nodata
        alpha = np.degrees(np.arctan(dz / d_h))
        valid = np.isfinite(alpha) & (np.abs(alpha) <= max_slope_deg)
        alpha_v = np.where(valid, alpha, 0.0)                # placeholder to avoid warnings
        v = 0.75 - 0.01 * (alpha_v if signed else np.abs(alpha_v))
        dt = d_h / (v * np.cos(np.radians(alpha_v)))
        e = santee_power_array(mass_kg, v, alpha_v, g_mps2) * dt
        time_s[k] = np.where(valid, dt, np.nan)
        energy_j[k] = np.where(valid, e, np.nan)
        alpha_out[k] = np.where(valid, alpha, np.nan)

    return time_s, energy_j, alpha_out
