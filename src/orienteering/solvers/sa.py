"""
Simulated annealing for the orienteering problem (E6). Each step tries one random move
on a feasible tour: add an unvisited station at its cheapest feasible position, drop a
visited one, swap one for an unvisited one, or reverse a segment. Infeasible moves are
rejected; a move that loses points is accepted with probability exp(-loss / T), with T
cooling geometrically from a fraction of the mean station prize. The best tour seen is
polished with the same local search as the ILS and returned.
Heuristic, seeded (seed) for reproducible runs.
"""
import math
import time

import numpy as np

from orienteering.solvers.heuristics import Evaluator

MAX_STATIONS = 500
STEPS = 20000
T_START = 0.5                # x mean positive prize
T_END = 0.005                # x mean positive prize
TIME_LIMIT_S = 10.0


def solve(problem, seed=0, steps=STEPS, time_limit_s=TIME_LIMIT_S):
    t0 = time.perf_counter()
    if problem.n > MAX_STATIONS:
        raise ValueError(f"SA is limited to {MAX_STATIONS} stations, got {problem.n}")
    if problem.timed and problem.time is None:
        raise ValueError("time windows and max_duration_s need problem.time")
    ev = Evaluator(problem)
    rng = np.random.default_rng(seed)
    current = ev.initial()
    if current is None:
        return ev.solution(None, "sa", time.perf_counter() - t0)

    positive = ev.prize[ev.prize > 0]
    scale = float(positive.mean()) if len(positive) else 1.0
    cooling = (T_END / T_START) ** (1.0 / max(1, steps))
    temp = T_START * scale
    free = [k for k in range(ev.n) if k not in ev.fixed and ev.prize[k] > 0]
    best = list(current)

    def score(route):
        # points, with a tie-break worth far less than any prize difference
        return ev.points(route) - 1e-6 * scale * ev.total(route) / max(ev.budget, 1e-12)

    cur_score = score(current)
    for step in range(steps):
        if step % 256 == 0 and time.perf_counter() - t0 > time_limit_s:
            break
        cand = move(ev, current, free, rng)
        temp *= cooling
        if cand is None or not ev.check(cand)[0]:
            continue
        cand_score = score(cand)
        if cand_score >= cur_score or rng.random() < math.exp((cand_score - cur_score) / temp):
            current, cur_score = cand, cand_score
            if ev.key(current) > ev.key(best):
                best = list(current)
    best = ev.local_search(best)
    return ev.solution(best, "sa", time.perf_counter() - t0)


def move(ev, route, free, rng):
    inner = route[1:-1]
    out = [k for k in free if k not in route]
    kind = rng.integers(4)
    if kind == 0 and out:                                   # add at the cheapest position
        k = out[rng.integers(len(out))]
        e = ev.energy
        pos = min(range(1, len(route)),
                  key=lambda m: e[route[m - 1], k] + e[k, route[m]] - e[route[m - 1], route[m]])
        return route[:pos] + [k] + route[pos:]
    if kind == 1 and inner:                                 # drop
        m = 1 + rng.integers(len(inner))
        return route[:m] + route[m + 1:]
    if kind == 2 and inner and out:                         # swap in place
        m = 1 + rng.integers(len(inner))
        return route[:m] + [out[rng.integers(len(out))]] + route[m + 1:]
    if len(inner) >= 2:                                     # reverse a segment
        i, j = sorted(1 + rng.choice(len(inner), 2, replace=False))
        return route[:i] + route[i:j + 1][::-1] + route[j + 1:]
    return None
