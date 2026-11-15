<!-- Owner: JB assembles from every note's Limitations · Sources: all notes · Status: drafted from the notes by JB's Claude; owner to confirm -->

## 5. Discussion

**What the validation shows.** The walkback guarantee and the tour are exact on the model's costs, and the comparison with simple rules is made on the same graph, so the false-safe rates measure the rules, not noise. Curiosity's traverse validates something narrower: a planner on DEM features would choose the same valleys the drivers chose, but within the boxwork the drivers reacted to things the DEM does not resolve. That is why orthophoto sand, not slope, is the only learned price.

**Negative results.** Learned DEM prices are zero at every scale (E1). Boxwork ridges could not be mapped reliably from weak labels (E8). A boulder price did not hold out of sample (E1 with E9). THEMIS night infrared at 81 m does not see the sand. We keep these results because they tell the next team where the signal is not.

**Limitations.**
- **Metabolic model.** Santee (2001) with Mars gravity is an extrapolation, not validated for a suited astronaut on Mars, and O2 is a metabolic equivalent, not a tank reading.
- **Orbital data.** The 1 m DEM is coarser than its posting. The sand map finds about 1 in 9 sand pixels. Boulders below about 1 m are invisible.
- **Simulation.** Radio is pure line of sight. The dose was computed on a provisional route. The adaptive walkback is validated in simulation only. Its 90 % interval is overconfident when consumption errors are correlated in time, so k_p90 is a margin, not a guarantee.
- **Scope.** Station values encode an expert ranking, not measurements, and service time and power are placeholders. Everything is one 2 × 2 km box and, for most numbers, one habitat.

**Future work.** A filter that handles correlated errors, and a joint energy, time and O2 return (#120). Robustness to DEM errors (E7). Recomputing the dose on the planner's route. A planning cost for time without radio. A larger area with a two-level grid (rover between zones, walking within them).
