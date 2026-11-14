"""
Walkback for E5 tours, on top of E4 (grafos.walkback.check_walkback, Aaron).

At every cell v of the route: used(v) + R(v) <= usable energy, where R(v) is the
minimum energy to walk from v back to the habitat and used(v) is the energy spent so
far, walking plus the service done at the stops already reached.

For a tour that starts and ends at the habitat this always holds once the whole tour
fits in the budget: R(v) is never more than the rest of the planned tour. It can
fail when the route ends elsewhere (end != start), so the check and the re-planning
below are what guarantee it.
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grafos.walkback import check_walkback  # noqa: E402


"""
R(v) for every cell: minimum energy (J) to walk from the cell back to the habitat
node, np.inf if it cannot return. One Dijkstra on the reversed graph.
"""
def return_costs(graph, habitat_node):
    return graph.costs_to(int(habitat_node))


"""
Walkback profile of a tour.
    path, stop_index : from network.route_path
    stop_service_j : (len(stop_index),) service energy done at each stop (0 where the
                     stop is not served, e.g. the final return to the habitat)
    rv_j : from return_costs
    usable_j : usable energy budget in J
Service is counted as done before leaving the stop, so at a stop's cell the check uses
the energy after its service (the stricter moment).
Returns check_walkback's dict with used_j and slack_j including service, plus:
    service_j : cumulative service energy along the path
    stop_slack_j : slack at each stop, after its service
    min_slack_j : smallest slack along the route
    first_violation_stop : position in the tour of the first stop at or after the
                           first violation, or None
"""
def tour_walkback(graph, path, stop_index, stop_service_j, rv_j, usable_j):
    path = np.asarray(path, dtype=np.int64)
    if len(path) < 2:
        rv = np.asarray(rv_j)[path]
        zero = np.zeros(len(path))
        profile = {"path": path, "used_j": zero, "rv_j": rv, "slack_j": usable_j - rv,
                   "time_s": zero, "length_m": zero, "usable_j": float(usable_j)}
    else:
        profile = check_walkback(graph, path, rv_j, usable_j)

    service = np.zeros(len(path))
    for at, energy in zip(stop_index, stop_service_j):
        service[at:] += float(energy)
    used = profile["used_j"] + service
    slack = usable_j - used - profile["rv_j"]
    bad = np.nonzero(slack < 0)[0]
    first = int(bad[0]) if len(bad) else None

    first_stop = None
    if first is not None:
        first_stop = int(np.searchsorted(np.asarray(stop_index), first))
    profile.update(used_j=used, slack_j=slack, service_j=service,
                   feasible=first is None, first_violation=first,
                   stop_slack_j=slack[np.asarray(stop_index)],
                   min_slack_j=float(slack.min()) if len(slack) else float(usable_j),
                   first_violation_stop=first_stop)
    return profile


"""
Solves the problem and checks the walkback of the tour; if it fails, lowers the
budget by the deficit (minus the smallest slack) and solves again, so the next tour
spends less. The trivial tour (stay at the habitat) always passes, so this ends.
    solve : solver function, solve(problem) -> Solution
    check : function route -> walkback profile (tour_walkback for that route)
Returns (solution, profile, retries); profile is None if no route fits at all.
"""
def solve_with_walkback(problem, solve, check, max_retries=5):
    budget = problem.budget
    solution, profile = None, None
    for retry in range(max_retries + 1):
        solution = solve(replace(problem, budget=budget))
        if not solution.route:
            return solution, None, retry
        profile = check(solution.route)
        if profile["feasible"]:
            return solution, profile, retry
        budget -= -profile["min_slack_j"] + 1.0
    return solution, profile, max_retries
