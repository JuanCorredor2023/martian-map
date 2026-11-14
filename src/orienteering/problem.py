"""
Contract between the data pipeline and the solvers.
Every solver takes a Problem and returns a Solution; solvers only see matrices,
never grids, files or coordinates.
"""
from dataclasses import dataclass

import numpy as np


"""
Orienteering instance over n stations.
    energy : (n, n) station-to-station cost matrix in J (not symmetric)
    prize : (n,) prize of each station
    budget : energy budget in J; the whole route, including the final leg to end, must fit in it
    start, end : first and last station of the route (end != start: end is always the last stop)
    time : (n, n) station-to-station time in s, for time windows and the duration budget
    service_s : (n,) service time at each station in s
    windows : (n, 2) earliest and latest arrival time at each station in s
"""
@dataclass
class Problem:
    energy: np.ndarray
    prize: np.ndarray
    budget: float
    start: int = 0
    end: int = 0
    time: np.ndarray | None = None
    service_s: np.ndarray | None = None
    windows: np.ndarray | None = None

    @property
    def n(self):
        return len(self.energy)


"""
Result of a solver.
    route : station indices from start to end (empty if no route fits in the budget)
    prize : prize collected by the route
    energy : energy spent by the route in J
    solver : name of the solver that produced it
    runtime_s : time the solver took
"""
@dataclass
class Solution:
    route: list[int]
    prize: float
    energy: float
    solver: str
    runtime_s: float
