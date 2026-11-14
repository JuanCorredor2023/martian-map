"""
Brute force over every ordered subset of stations. Exact but factorial:
only for validating other solvers on small instances (n <= 8).
"""
import itertools
import time

from orienteering.problem import Solution

MAX_STATIONS = 8


"""
Tries every route start -> (ordered subset of the other stations) -> end and
keeps the one with the highest prize that fits in problem.budget.
"""
def solve(problem):
    t0 = time.perf_counter()
    n = problem.n
    if n > MAX_STATIONS:
        raise ValueError(f"brute force is limited to {MAX_STATIONS} stations, got {n}")

    dis, prize = problem.energy, problem.prize
    start, end = problem.start, problem.end
    others = [k for k in range(n) if k not in (start, end)]

    best = None
    for size in range(len(others) + 1):
        for middle in itertools.permutations(others, size):
            route = [start, *middle, end]
            spent = sum(float(dis[a][b]) for a, b in zip(route, route[1:]))
            if spent > problem.budget:
                continue
            total = float(sum(prize[k] for k in set(route)))
            if best is None or total > best[0]:
                best = (total, route, spent)

    if best is None:
        return Solution([], 0.0, 0.0, "brute", time.perf_counter() - t0)
    return Solution(best[1], best[0], best[2], "brute", time.perf_counter() - t0)
