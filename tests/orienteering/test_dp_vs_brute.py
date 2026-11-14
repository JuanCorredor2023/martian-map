"""The bitmask DP must match brute force on small random instances."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from orienteering.problem import Problem
from orienteering.solvers import brute, dp


def random_problem(rng, n, start, end):
    pts = rng.random((n, 2)) * 10
    energy = np.linalg.norm(pts[:, None] - pts[None], axis=2) * rng.uniform(0.8, 1.5, (n, n))
    np.fill_diagonal(energy, 0.0)
    prize = rng.integers(1, 6, n).astype(float)
    return Problem(energy=energy, prize=prize, budget=rng.uniform(0, 30), start=start, end=end)


def route_cost(problem, route):
    return sum(problem.energy[a][b] for a, b in zip(route, route[1:]))


@pytest.mark.parametrize("seed", range(200))
def test_dp_matches_brute_force(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(2, 8))
    start = int(rng.integers(n))
    end = start if rng.random() < 0.5 else int(rng.integers(n))
    problem = random_problem(rng, n, start, end)

    got, ref = dp.solve(problem), brute.solve(problem)

    assert got.prize == pytest.approx(ref.prize)
    if ref.route:
        assert got.route[0] == start and got.route[-1] == end
        assert got.energy == pytest.approx(route_cost(problem, got.route))
        assert got.energy <= problem.budget
        assert got.prize == pytest.approx(sum(problem.prize[k] for k in set(got.route)))
    else:
        assert got.route == []


def test_dp_rejects_too_many_stations():
    problem = Problem(energy=np.zeros((21, 21)), prize=np.ones(21), budget=1.0)
    with pytest.raises(ValueError):
        dp.solve(problem)
