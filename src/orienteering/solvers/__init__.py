"""
Orienteering solvers. Every solver is solve(problem: Problem) -> Solution.
"""
from orienteering.solvers import brute, dp

SOLVERS = {
    "dp": dp.solve,
    "brute": brute.solve,
}

MAX_STATIONS = {
    "dp": dp.MAX_STATIONS,
    "brute": brute.MAX_STATIONS,
}
