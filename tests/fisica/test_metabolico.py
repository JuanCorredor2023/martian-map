"""Tests for the nominal model: reference values from guide REV3 (sections 9, 16 and 47)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from fisica.metabolico import (G_EARTH, G_MARS, G_MOON, J_PER_WH, TOTAL_MASS_KG,
                               apollo_speed, liters_o2, santee_2001_power,
                               segment_cost)

m = TOTAL_MASS_KG


def test_flat_292_same_on_every_planet():
    for g in (G_EARTH, G_MOON, G_MARS):
        w_level, w_slope, total = santee_2001_power(m, 0.75, 0, g)
        assert total == pytest.approx(292.23, abs=0.01)
        assert w_slope == 0.0


@pytest.mark.parametrize("alpha, expected", [
    (-20, 321.93), (-10, 285.94), (-5, 271.98), (0, 292.23), (10, 439.51), (20, 521.86),
])
def test_toy_problem_table(alpha, expected):
    v = apollo_speed(alpha)
    assert santee_2001_power(m, v, alpha, G_MARS)[2] == pytest.approx(expected, abs=0.01)


def test_gravity_only_changes_w_slope():
    le, se, _ = santee_2001_power(m, 0.65, 10, G_EARTH)
    lm, sm, _ = santee_2001_power(m, 0.65, 10, G_MARS)
    assert le == lm and se != sm


def test_downhill_negative_w_slope_but_positive_total():
    for alpha in range(-20, 0):
        _, w_slope, total = santee_2001_power(m, apollo_speed(alpha), alpha)
        assert w_slope < 0 < total


def test_apollo_speed():
    assert apollo_speed(10) == pytest.approx(0.65)
    assert apollo_speed(-20) == pytest.approx(0.95)
    assert apollo_speed(-20, signed=False) == pytest.approx(0.55)


def test_toy_5_km():
    t1, e1 = segment_cost(4100, 0)
    t2, e2 = segment_cost(900, 10)
    energy, time = e1 + e2, t1 + t2
    assert energy / 1000 == pytest.approx(2215.5, abs=0.1)     # kJ
    assert energy / J_PER_WH == pytest.approx(615.4, abs=0.1)  # Wh
    assert liters_o2(energy) == pytest.approx(110.2, abs=0.1)  # L O2 eq.
    assert time / 3600 == pytest.approx(1.91, abs=0.01)        # h


def test_uphill_downhill_asymmetry():
    _, e_up = segment_cost(1.0, 10)
    _, e_down = segment_cost(1.0, -10)
    assert e_up != pytest.approx(e_down)
