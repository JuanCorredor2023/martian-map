"""
Exact bitmask DP for small orienteering instances (up to 20 stations).
"""
import time

from orienteering.problem import Solution, evaluate_route

MAX_STATIONS = 20


"""
Bitmask DP to solve small instances of the orienteering problem (18-20 nodes).
Uses problem.energy, problem.prize, problem.budget, problem.start, problem.end and,
if given, problem.service_j: the service energy of a station is paid when the route
arrives at it (the start's when the route begins), so walking plus service must fit
in the budget.
By default it traces a path starting and ending in node 0. If end != start,
end is always the last stop.
With time windows or a maximum duration (problem.timed) it switches to solve_timed.
"""
def solve(problem):
    t0 = time.perf_counter()
    n = problem.n
    if n > MAX_STATIONS:
        raise ValueError(f"the bitmask DP supports up to {MAX_STATIONS} stations, got {n}")
    if problem.timed:
        if problem.time is None:
            raise ValueError("time windows and max_duration_s need problem.time")
        return solve_timed(problem, t0)

    INF = float('inf')
    svc = [float(v) for v in problem.service_j] if problem.service_j is not None else [0.0] * n
    dis = [[float(d) + svc[j] for j, d in enumerate(row)] for row in problem.energy]
    prize = [float(v) for v in problem.prize]
    cost, start, end = problem.budget, problem.start, problem.end

    # Closing leg i -> end: the end is served unless it is the start again
    close = [float(problem.energy[i][end]) + (svc[end] if end != start else 0.0) for i in range(n)]

    mask_prize = prizes_by_mask(prize, n)
    end_prize = prize[end] if end != start else 0.0

    # n columns, 2^n rows; dp[mask][i] = least cost to visit (and serve) mask finishing at i
    dp = [[INF] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]
    dp[1 << start][start] = svc[start]
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
            if c + close[i] <= cost and total > best:
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
    spent = dp[mask][i] + close[i]
    route = []
    while i != -1:
        route.append(i)
        mask, i = mask ^ (1 << i), parent[mask][i]
    route.reverse()
    route.append(end)

    duration = evaluate_route(problem, route)["duration"]
    return Solution(route, best, spent, "dp", time.perf_counter() - t0, duration)


"""
Prize collected by each mask: the mask without its lowest bit plus that bit's station.
"""
def prizes_by_mask(prize, n):
    mask_prize = [0.0] * (1 << n)
    for mask in range(1, 1 << n):
        low = mask & -mask
        mask_prize[mask] = mask_prize[mask ^ low] + prize[low.bit_length() - 1]
    return mask_prize


"""
Same DP with time windows and a maximum duration. With two resources (energy and
time) one value per (mask, i) is no longer enough: a route that spends more energy
but arrives earlier can still be the only one that meets a later window. So each
state keeps its Pareto labels, the (energy, departure time) pairs no other label
beats in both. A label is (energy, departure, previous station, index of the
previous label).
Arriving before a window opens means waiting until it opens; the service then
starts and must start no later than the window closes.
"""
def solve_timed(problem, t0):
    n = problem.n
    INF = float('inf')
    svc = [float(v) for v in problem.service_j] if problem.service_j is not None else [0.0] * n
    svc_s = [float(v) for v in problem.service_s] if problem.service_s is not None else [0.0] * n
    dis = [[float(d) + svc[j] for j, d in enumerate(row)] for row in problem.energy]
    tim = [[float(t) for t in row] for row in problem.time]
    if problem.windows is not None:
        opens = [float(w[0]) for w in problem.windows]
        closes = [float(w[1]) for w in problem.windows]
    else:
        opens, closes = [0.0] * n, [INF] * n
    max_t = problem.max_duration_s if problem.max_duration_s is not None else INF
    prize = [float(v) for v in problem.prize]
    cost, start, end = problem.budget, problem.start, problem.end

    mask_prize = prizes_by_mask(prize, n)
    end_prize = prize[end] if end != start else 0.0

    labels = [dict() for _ in range(1 << n)]
    begin0 = opens[start]
    if begin0 > closes[start] or svc[start] > cost:
        return Solution([], 0.0, 0.0, "dp", time.perf_counter() - t0, None)
    labels[1 << start][start] = [(svc[start], begin0 + svc_s[start], -1, -1)]
    best, best_state = -INF, None

    for mask in range(1, 1 << n):
        if not mask & (1 << start):
            continue
        for i, here in labels[mask].items():
            for li, (c, t, _, _) in enumerate(here):

                # If the route can close here within energy, windows and duration and its prize would be better, update it
                total = mask_prize[mask] + end_prize
                if total > best:
                    finish = close_route(i, c, t, start, end, problem.energy, svc, svc_s, tim,
                                         opens, closes, max_t)
                    if finish is not None and finish[0] <= cost:
                        best, best_state = total, (mask, i, li, finish)

                # Extend the label to each station not yet in the mask
                for j in range(n):
                    bit = 1 << j
                    if mask & bit or (j == end and end != start):
                        continue
                    new = c + dis[i][j]
                    begin = max(t + tim[i][j], opens[j])
                    depart = begin + svc_s[j]
                    if new > cost or begin > closes[j] or depart > max_t:
                        continue
                    add_label(labels[mask | bit], j, (new, depart, i, li))

    if best_state is None:
        return Solution([], 0.0, 0.0, "dp", time.perf_counter() - t0, None)

    mask, i, li, (spent, finish) = best_state
    route = []
    while i != -1:
        route.append(i)
        _, _, prev, prev_li = labels[mask][i][li]
        mask, i, li = mask ^ (1 << i), prev, prev_li
    route.reverse()
    route.append(end)

    return Solution(route, best, spent, "dp", time.perf_counter() - t0, finish)


"""
Energy and finishing time of closing the route from station i (label energy c,
departure t) to end, or None if a window or the maximum duration is broken.
"""
def close_route(i, c, t, start, end, energy, svc, svc_s, tim, opens, closes, max_t):
    arrive = t + tim[i][end]
    if end == start:
        if arrive > closes[end] or arrive > max_t:
            return None
        return c + float(energy[i][end]), arrive
    begin = max(arrive, opens[end])
    finish = begin + svc_s[end]
    if begin > closes[end] or finish > max_t:
        return None
    return c + float(energy[i][end]) + svc[end], finish


"""
Adds a label to state[j] unless another label is at least as good in energy and
time; drops the labels the new one beats in both. Only states of larger masks
change here, and their labels are not referenced yet, so indices stay valid.
"""
def add_label(state, j, label):
    current = state.get(j)
    if current is None:
        state[j] = [label]
        return
    e, t = label[0], label[1]
    for e2, t2, _, _ in current:
        if e2 <= e and t2 <= t:
            return
    state[j] = [lab for lab in current if not (e <= lab[0] and t <= lab[1])] + [label]
