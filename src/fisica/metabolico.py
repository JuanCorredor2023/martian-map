"""E3 - Astronaut metabolic cost (nominal model: Santee 2001).

Reference: zero-to-hero guide REV3, sections 8.2, 9, 11.2, 12-14 and 16.

Conventions (do not change without posting in the contracts issue):
- alpha_deg: slope angle in DEGREES, signed, along the direction of travel
  (positive = uphill, negative = downhill).
- Speed: m/s, parallel to the terrain surface (SEXTANT convention).
- Mass: kg (total equipped mass: astronaut + suit/load).
- Gravity: m/s^2 (Mars 3.71). It only enters the slope term.
- Power in W, time in s, energy in J. Wh is for display only.
"""

from math import cos, radians, sin

# Nominal parameters (declared assumptions, guide section 9)
TOTAL_MASS_KG = 124.2          # 75 kg astronaut + 47.8 kg suit/load
G_MARS = 3.71                  # m/s^2
G_MOON = 1.62
G_EARTH = 9.81
KJ_PER_LITER_O2 = 20.1         # approximate metabolic equivalence (20.1-20.9)
J_PER_WH = 3600.0


def santee_2001_power(mass_kg, v_surface_mps, alpha_deg, g_mps2=G_MARS):
    """Metabolic power in W from Santee (2001), MIT/SEXTANT form.

    Returns (w_level, w_slope, total). W_level does not depend on g;
    gravity only appears in W_slope.
    """
    a = radians(alpha_deg)
    w_level = (3.28 * mass_kg + 71.1) * (0.661 * v_surface_mps * cos(a) + 0.115)
    if alpha_deg > 0:
        w_slope = 3.5 * mass_kg * g_mps2 * v_surface_mps * sin(a)
    elif alpha_deg < 0:
        w_slope = (2.4 * mass_kg * g_mps2 * v_surface_mps * sin(a)
                   * 0.3 ** (abs(alpha_deg) / 7.65))
    else:
        w_slope = 0.0
    return w_level, w_slope, w_level + w_slope


def apollo_speed(alpha_deg, signed=True):
    """Apollo regression (CSRM): V = 0.75 - 0.01*theta, in m/s, theta in degrees.

    signed=True: downhill is faster (-20 deg -> 0.95 m/s).
    signed=False: uses |theta| (downhill also slows down).
    The source is ambiguous here, so the choice must be declared.
    """
    theta = alpha_deg if signed else abs(alpha_deg)
    return 0.75 - 0.01 * theta


def segment_cost(d_horizontal_m, alpha_deg, mass_kg=TOTAL_MASS_KG,
                 g_mps2=G_MARS, signed=True):
    """Time (s) and energy (J) of a segment with HORIZONTAL length d_h.

    d_surface = d_h / cos(alpha);  dt = d_surface / V(alpha);  E = M * dt
    """
    v = apollo_speed(alpha_deg, signed)
    d_surface = d_horizontal_m / cos(radians(alpha_deg))
    dt = d_surface / v
    _, _, power = santee_2001_power(mass_kg, v, alpha_deg, g_mps2)
    return dt, power * dt


def liters_o2(energy_j):
    """Metabolic-equivalent O2 (L). This is NOT a PLSS tank reading."""
    return energy_j / 1000.0 / KJ_PER_LITER_O2
