"""
Exact bitmask DP for small orienteering instances (up to 20 stations).
"""
import time

from orienteering.problem import Solution

MAX_STATIONS = 20


"""
Bitmask DP to solve small instances of the orienteering problem (18-20 nodes).
Uses problem.energy, problem.prize, problem.budget, problem.start and problem.end.
By default it traces a path starting and ending in node 0. If end != start,
end is always the last stop.
Time windows, service times and the time matrix are not supported yet.
"""
def solve(problem):
    t0 = time.perf_counter()
    n = problem.n
    if n > MAX_STATIONS:
        raise ValueError(f"the bitmask DP supports up to {MAX_STATIONS} stations, got {n}")
    if problem.windows is not None or problem.service_s is not None:
        raise NotImplementedError("the DP does not handle time windows or service times yet")

    INF = float('inf')
    dis = [[float(d) for d in row] for row in problem.energy]
    prize = [float(v) for v in problem.prize]
    cost, start, end = problem.budget, problem.start, problem.end

    # Prize collected by each mask: the mask without its lowest bit plus that bit's station
    mask_prize = [0.0] * (1 << n)
    for mask in range(1, 1 << n):
        low = mask & -mask
        mask_prize[mask] = mask_prize[mask ^ low] + prize[low.bit_length() - 1]
    end_prize = prize[end] if end != start else 0.0

    # n columns, 2^n rows; dp[mask][i] = least cost to visit mask finishing at i
    dp = [[INF] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]
    dp[1 << start][start] = 0.0
    best, best_state = -INF, None

    for mask in range(1, 1 << n):
        if not mask & (1 << start):
            continue
        for i in range(n):
            c = dp[mask][i]

            # If node is unreachable, skip it
            if c == INF:
                continue

            # If the route can close here within cost and its prize would be better, update it
            total = mask_prize[mask] + end_prize
            if c + dis[i][end] <= cost and total > best:
                best, best_state = total, (mask, i)

            # Update dp values for each station not yet in the mask
            for j in range(n):
                bit = 1 << j
                if mask & bit or (j == end and end != start):
                    continue
                new = c + dis[i][j]
                if new <= cost and new < dp[mask | bit][j]:
                    dp[mask | bit][j] = new
                    parent[mask | bit][j] = i

    if best_state is None:
        return Solution([], 0.0, 0.0, "dp", time.perf_counter() - t0)

    mask, i = best_state
    spent = dp[mask][i] + dis[i][end]
    route = []
    while i != -1:
        route.append(i)
        mask, i = mask ^ (1 << i), parent[mask][i]
    route.reverse()
    route.append(end)

    return Solution(route, best, spent, "dp", time.perf_counter() - t0)
