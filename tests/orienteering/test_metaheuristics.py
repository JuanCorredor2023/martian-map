"""E6 metaheuristics (ILS, SA): always feasible, never above the optimum, and usually on it."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_dp_vs_brute import KINDS, random_problem, window_problem

from orienteering.instances import instance_dir, random_instance, read_op
from orienteering.problem import Problem, evaluate_route
from orienteering.solvers import SOLVERS, dp, ils, sa

HEURISTICS = {"ils": ils.solve, "sa": lambda p: sa.solve(p, seed=0, steps=4000)}


def small_case(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(2, 8))
    start = int(rng.integers(n))
    end = start if rng.random() < 0.5 else int(rng.integers(n))
    return random_problem(rng, n, start, end, KINDS[seed % len(KINDS)])


@pytest.mark.parametrize("name", HEURISTICS)
def test_feasible_and_never_above_the_optimum(name):
    hits = 0
    for seed in range(60):
        problem = small_case(seed)
        got, ref = HEURISTICS[name](problem), dp.solve(problem)
        assert got.prize <= ref.prize + 1e-9
        if got.route:
            result = evaluate_route(problem, got.route)
            assert result["feasible"] and result["energy"] <= problem.budget + 1e-9
            assert got.route[0] == problem.start and got.route[-1] == problem.end
            assert len(set(got.route[1:-1])) == len(got.route) - 2
            assert got.energy == pytest.approx(result["energy"])
        hits += abs(got.prize - ref.prize) < 1e-9
    assert hits >= 55                                       # heuristics: most, not all


@pytest.mark.parametrize("name", HEURISTICS)
def test_toy_circle_optimum(name):
    n_st, radius = 10, 10.0
    angles = 2 * np.pi * np.arange(n_st) / n_st
    pts = np.vstack([[0.0, 0.0], np.column_stack([radius * np.cos(angles), radius * np.sin(angles)])])
    problem = Problem(energy=np.linalg.norm(pts[:, None] - pts[None], axis=2),
                      prize=np.r_[0.0, np.ones(n_st)], budget=50.0)
    assert HEURISTICS[name](problem).prize == dp.solve(problem).prize


@pytest.mark.parametrize("name", HEURISTICS)
def test_windows_and_no_route(name):
    got = HEURISTICS[name](window_problem([[0, np.inf], [0, 15], [50, np.inf]]))
    assert got.route == [0, 1, 2, 0]
    problem = Problem(energy=np.zeros((2, 2)), prize=np.ones(2), budget=1.0,
                      service_j=np.array([2.0, 0.0]))
    assert HEURISTICS[name](problem).route == []


def test_sa_is_reproducible():
    problem = random_instance(np.random.default_rng(3), 12, "energy")
    assert sa.solve(problem, seed=5, steps=3000).route == sa.solve(problem, seed=5, steps=3000).route


def test_random_instance_and_op_reader(tmp_path):
    p = random_instance(np.random.default_rng(0), 9, "windows")
    assert p.n == 9 and p.prize[0] == 0 and p.windows[0].tolist() == [0.0, np.inf]
    assert 0 < p.budget and p.time is not None
    f = tmp_path / "op.txt"
    f.write_text("10\t1\n0\t0\t0\n3\t4\t0\n0\t4\t5\n")
    q = read_op(f)
    assert q.start == 0 and q.end == 1 and q.budget == 10.0 and q.energy[0, 1] == 5.0
    assert dp.solve(q).route == [0, 2, 1]                   # 4 + 3 = 7 <= 10


@pytest.mark.skipif(instance_dir() is None, reason="KU Leuven instances not available")
def test_tsiligirides_file_reads():
    from orienteering.instances import tsiligirides
    sets = tsiligirides()
    assert len(sets) == 49 and {p.n for _, p in sets} == {21, 32, 33}


def test_registry():
    assert SOLVERS["ils"] is ils.solve and SOLVERS["sa"] is sa.solve
