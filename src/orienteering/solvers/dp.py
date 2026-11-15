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
With time windows or a maximum duration (problem.timed) the states keep Pareto labels
(see closable_timed). Among tours with the same prize, the one using less energy wins.
"""
def solve(problem):
    return solve_many(problem, [problem.prize])[0]


"""
Solves the same problem for several prize vectors (e.g. scoring rubrics) at once.
Which station sets can be visited within the limits does not depend on the prizes,
so the DP tables are built once and only the choice of the best set is repeated:
for each prize vector, the closable set with the highest prize (ties: least energy).
Returns one Solution per prize vector; runtime_s is the total time of the call.
"""
def solve_many(problem, prizes):
    t0 = time.perf_counter()
    n = problem.n
    if n > MAX_STATIONS:
        raise ValueError(f"the bitmask DP supports up to {MAX_STATIONS} stations, got {n}")
    if problem.timed and problem.time is None:
        raise ValueError("time windows and max_duration_s need problem.time")

    closable, rebuild = closable_timed(problem) if problem.timed else closable_fast(problem)
    start, end = problem.start, problem.end

    chosen = []
    for prize in prizes:
        prize = [float(v) for v in prize]
        mask_prize = prizes_by_mask(prize, n)
        end_prize = prize[end] if end != start else 0.0
        best = None
        for mask, (spent, finish, state) in closable.items():
            key = (mask_prize[mask] + end_prize, -spent)
            if best is None or key > best[0]:
                best = (key, spent, finish, state)
        chosen.append(best)

    runtime = time.perf_counter() - t0
    solutions = []
    for best in chosen:
        if best is None:
            solutions.append(Solution([], 0.0, 0.0, "dp", runtime, None))
            continue
        (total, _), spent, finish, state = best
        route = rebuild(state)
        if finish is None:
            finish = evaluate_route(problem, route)["duration"]
        solutions.append(Solution(route, total, spent, "dp", runtime, finish))
    return solutions


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
Energy-only DP. dp[mask][i] = least energy to visit (and serve) the set `mask` ending
at station i. Returns (closable, rebuild): closable maps each set that can be closed
within the budget (leg back to the end included) to (energy, None, state) with its
least-energy closing; rebuild(state) gives the route.
"""
def closable_fast(problem):
    n = problem.n
    INF = float('inf')
    svc = [float(v) for v in problem.service_j] if problem.service_j is not None else [0.0] * n
    dis = [[float(d) + svc[j] for j, d in enumerate(row)] for row in problem.energy]
    cost, start, end = problem.budget, problem.start, problem.end

    # Closing leg i -> end: the end is served unless it is the start again
    close = [float(problem.energy[i][end]) + (svc[end] if end != start else 0.0) for i in range(n)]

    # n columns, 2^n rows; dp[mask][i] = least cost to visit (and serve) mask finishing at i
    dp = [[INF] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]
    dp[1 << start][start] = svc[start]
    closable = {}

    for mask in range(1, 1 << n):
        if not mask & (1 << start):
            continue
        for i in range(n):
            c = dp[mask][i]

            # If node is unreachable, skip it
            if c == INF:
                continue

            # If the route can close here within cost, remember the cheapest closing of this set
            spent = c + close[i]
            if spent <= cost and (mask not in closable or spent < closable[mask][0]):
                closable[mask] = (spent, None, (mask, i))

            # Update dp values for each station not yet in the mask
            for j in range(n):
                bit = 1 << j
                if mask & bit or (j == end and end != start):
                    continue
                new = c + dis[i][j]
                if new <= cost and new < dp[mask | bit][j]:
                    dp[mask | bit][j] = new
                    parent[mask | bit][j] = i

    def rebuild(state):
        mask, i = state
        route = []
        while i != -1:
            route.append(i)
            mask, i = mask ^ (1 << i), parent[mask][i]
        route.reverse()
        route.append(end)
        return route

    return closable, rebuild


"""
Same DP with time windows and a maximum duration. With two resources (energy and
time) one value per (mask, i) is no longer enough: a route that spends more energy
but arrives earlier can still be the only one that meets a later window. So each
state keeps its Pareto labels (see add_label). A label is (energy, departure time,
previous station, index of the previous label).
Arriving before a window opens means waiting until it opens (at problem.wait_power_w);
the service then starts and must start no later than the window closes.
Returns (closable, rebuild) like closable_fast, with the finishing time of each closing.
"""
def closable_timed(problem):
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
    wp = float(problem.wait_power_w)
    cost, start, end = problem.budget, problem.start, problem.end

    labels = [dict() for _ in range(1 << n)]
    closable = {}
    begin0 = max(0.0, opens[start])
    e0 = svc[start] + wp * begin0
    if begin0 <= closes[start] and e0 <= cost:
        labels[1 << start][start] = [(e0, begin0 + svc_s[start], -1, -1)]

    for mask in range(1, 1 << n):
        if not mask & (1 << start):
            continue
        for i, here in labels[mask].items():
            for li, (c, t, _, _) in enumerate(here):

                # If the route can close here within energy, windows and duration, remember the cheapest closing
                finish = close_route(i, c, t, start, end, problem.energy, svc, svc_s, tim,
                                     opens, closes, max_t, wp)
                if finish is not None and finish[0] <= cost and (
                        mask not in closable or finish[0] < closable[mask][0]):
                    closable[mask] = (finish[0], finish[1], (mask, i, li))

                # Extend the label to each station not yet in the mask
                for j in range(n):
                    bit = 1 << j
                    if mask & bit or (j == end and end != start):
                        continue
                    arrive = t + tim[i][j]
                    begin = max(arrive, opens[j])
                    new = c + dis[i][j] + wp * (begin - arrive)
                    depart = begin + svc_s[j]
                    if new > cost or begin > closes[j] or depart > max_t:
                        continue
                    add_label(labels[mask | bit], j, (new, depart, i, li), wp)

    def rebuild(state):
        mask, i, li = state
        route = []
        while i != -1:
            route.append(i)
            _, _, prev, prev_li = labels[mask][i][li]
            mask, i, li = mask ^ (1 << i), prev, prev_li
        route.reverse()
        route.append(end)
        return route

    return closable, rebuild


"""
Energy and finishing time of closing the route from station i (label energy c,
departure t) to end, or None if a window or the maximum duration is broken.
Waiting for the end's window costs wp per second.
"""
def close_route(i, c, t, start, end, energy, svc, svc_s, tim, opens, closes, max_t, wp=0.0):
    arrive = t + tim[i][end]
    if end == start:
        if arrive > closes[end] or arrive > max_t:
            return None
        return c + float(energy[i][end]), arrive
    begin = max(arrive, opens[end])
    finish = begin + svc_s[end]
    if begin > closes[end] or finish > max_t:
        return None
    return c + float(energy[i][end]) + svc[end] + wp * (begin - arrive), finish


"""
Adds a label to state[j] unless another label already dominates it; drops the labels
the new one dominates. Label A (e1, t1) dominates B (e2, t2) when t1 <= t2 and
e1 + wp * (t2 - t1) <= e2: A could wait until t2 at power wp and still spend no more
than B, so anything B can do afterwards A can do as cheaply (with wp = 0 this is
plain Pareto dominance on energy and time). Only states of larger masks change here,
and their labels are not referenced yet, so indices stay valid.
"""
def add_label(state, j, label, wp=0.0):
    current = state.get(j)
    if current is None:
        state[j] = [label]
        return
    e, t = label[0], label[1]
    for e2, t2, _, _ in current:
        if t2 <= t and e2 + wp * (t - t2) <= e:
            return
    state[j] = [lab for lab in current
                if not (t <= lab[1] and e + wp * (lab[1] - t) <= lab[0])] + [label]
