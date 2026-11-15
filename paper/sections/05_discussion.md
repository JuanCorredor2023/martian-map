<!-- Owner: JB assembles from every note's Limitations · Sources: all notes · Status: drafted from the notes by JB's Claude; owner to confirm -->

## 5. Discussion

**What the validation shows.** The walkback guarantee and the tour are exact on the model's costs, and the comparison with simple rules is made on the same graph, so the false-safe rates measure the rules, not noise. Curiosity's traverse tests something narrower. DEM features separate the valleys the drivers chose from the rest of the box (AUC 0.73), but within the boxwork they do not explain the path, which also followed science targets, operations and features the DEM does not resolve. Between given start and goal points, orthophoto sand is the only learned price that holds out of sample.

**Negative results.** Learned DEM prices are near zero (at most 4 % of the price of a metre), and none beats distance alone on held-out drives (E1). Boxwork ridges could not be mapped reliably from weak labels (E8). A boulder price did not hold out of sample (E1 with E9). A Gaussian process on boulder cover is no more accurate than a 20 m smoothing (X1). THEMIS night infrared at 81 m does not see the sand. We keep these results because they tell the next team where the signal is not.

**Limitations.**
- **Metabolic model.** Santee (2001) with Mars gravity is an extrapolation, not validated for a suited astronaut on Mars, and O2 is a metabolic equivalent, not a tank reading.
- **Learned price.** The sand price is learned from a rover's route and applied to an astronaut, which is an assumption.
- **Orbital data.** The 1 m DEM is coarser than its posting. The sand map finds about 1 in 9 sand pixels. Boulders below about 1 m are invisible, BoulderNet misses about 4 in 10 labelled boulders on Mars, and no label exists in Gale. The boulder uncertainty (X1) covers interpolation, not that undercount.
- **Simulation.** Radio is pure line of sight. The dose was computed on a provisional route. The adaptive walkback is validated in simulation only. Its 90 % interval is overconfident when consumption errors are correlated in time, so k_p90 is a margin, not a guarantee.
- **Scope.** Station values encode an expert ranking, not measurements, and service time and power are placeholders. Everything is one 2 × 2 km box and, for most numbers, one habitat.

**Future work.** A filter that handles correlated errors, and a joint energy, time and O2 return (#119, evaluated in #120; C1 did not implement the operational return). Robustness to DEM errors (E7). Recomputing the dose on the planner's route. A planning cost for time without radio. A larger area with a two-level grid (rover between zones, walking within them).
