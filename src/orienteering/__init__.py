"""E5 orienteering: which stations to visit and in what order.

Pipeline: data_io (stations, grid, costs) -> graph (station-to-station matrix)
-> problem.Problem -> solvers.SOLVERS[name] -> problem.Solution.
Entry point: run.py.
"""
