# Running the demo

The demo is a FastAPI backend (`api/`) that serves the HUD (`web/index.html`) and the map tiles from one address. Owner: Sebas (#10). Code freeze: **hour 40 = Sunday 2026-11-15, 01:15** (hour 0 = Saturday 09:15).

## 1. Set up (once per machine)

1. **Python packages** (normal terminal, not admin; inside the team's environment):
   ```
   python -m pip install -r api/requirements.txt
   ```
2. **Data.** Nothing large is in git. Download the releases from the repo root (`gh auth login` first). Then check what is missing:
   ```
   python -m api.check_data
   ```
   It lists each folder, what breaks without it and the exact download command.

   | Folder | Release | Needed for |
   |---|---|---|
   | `data/base/` | `base-grid-v2` | everything (DEM, slope, grid, ortho) |
   | `data/tiles/` | `tiles-v2` | map tiles |
   | `data/e2/` | `e2-trajectory-v1` | fixed test route (Curiosity) |
   | `data/stations/` | `stations-v1` | saved science stations (optional) |
   | `data/e12/` | `e12-dose-v1` | radiation panel (optional) |
   | `data/e8/` | `e8-v0` | sand layer (optional) |

   PowerShell example: `gh release download base-grid-v2 --dir data; Expand-Archive data\base_grid_v2.zip data\base -Force; Remove-Item data\base_grid_v2.zip`. The stations release has no zip: `gh release download stations-v1 --dir data\stations`.

## 2. Start

```
python -m uvicorn api.main:app --port 8000
```
Open **http://localhost:8000/**. The first plan or walkback takes about 10 s while the graph is built and cached; later calls take well under a second.

Health check: `http://localhost:8000/health`. Tests: `python -m pytest tests -q`.

No internet is needed at demo time: deck.gl is vendored in `web/vendor/` and all data is local.

**Guide mode (arm tablet):** after planning, open the link under the plan (or `http://localhost:8000/guide.html`). Press ▶ Walk; try *Detour (demo)* (off route → recalculating), *Solar storm (demo)* (automatic way home with the dose) and *Return home*.

## 3. Five-minute walkthrough

This follows the guide's demo script (zero-to-hero REV3, section 51).

1. **Terrain (30 s).** HiRISE ortho with the slope layer on top; switch on *Sand detected (E8)*. Say that the 1 m DEM does not resolve the boxwork ridges, but the 0.25 m image does.
2. **What a step costs (45 s).** Turn on *E3 walking cost*. The cost is Santee 2001 with Mars gravity only in the slope term. Whole-power scaling fails the lunar check (52 W against 292 W on flat ground). The cheapest metre is a gentle descent (338.75 J/m), not flat ground.
3. **Steep cells (20 s).** Move *Block cells steeper than N°* (30° by default; 20° blocks 30 % of the box). This is the decision that changes routes the most (E3 sensitivity).
4. **Science stations (45 s).** The right panel lists 13 stations. Three are Curiosity's real drill sites (Nevado Sajama ridge, Valle de la Luna hollow, Altadena); the rest are candidates. The rubric (ridge 5, hollow 4, contact 4, Curiosity site 3) is editable live; its literature review is in `docs/research/`.
5. **Plan (60 s).** Set the EVA limits (energy budget, margin, **max duration**) and press *Plan EVA*. E4 builds the round trip live. Press **▶ Play**: the budget bar splits energy into used, needed to return and free. It only shrinks, and the arrow shows the heading.
6. **Walkback (45 s).** Pause anywhere. The **red line** is the 30 min emergency-oxygen return (R_T = 1800 s); the **cyan line** is where the astronaut can still go and come back with the energy left (F_E + R_E). Neither is a circle: scarps and slopes shape them.
7. **Solar storm (30 s).** In *Radiation (E12)* pick a storm and press *Simulate SEP alert*: the dose on the way back is the return time × the storm rate. Background radiation does not change the plan; a storm does.

## 4. What to say honestly

- Santee 2001 with g = 3.71 m/s² is an extrapolation, not validated for a suited astronaut on Mars. O2 is a metabolic equivalent (20.1 kJ/L), not a tank reading.
- In this 2 × 2 km box energy rarely binds (the costliest round trip is about 560 Wh against 2,813 Wh xEMU); time does.
- E1 (learning from Curiosity's route) found no DEM terrain price, so the human cost is E3 alone until sand and rocks are added.
- Station values encode an expert ranking, not measurements. The walkback fields are on the same E3 costs as E4.
- There is no GPS on Mars: walking the route is simulated.

## 5. Code freeze checklist (hour 40)

- [ ] All MVP PRs merged into `main`; `python -m pytest tests -q` passes on a fresh clone.
- [ ] `python -m api.check_data` passes on the demo machine; the releases are the final versions.
- [ ] Demo machine: server starts, first plan built once before presenting (warm cache).
- [ ] Every piece's paper note is up to date (`paper/notes/`, AGENTS.md rule 7).
- [ ] Delivery branch created from `main` (`release/demo`); after hour 40 only bug fixes, each as a PR.
- [ ] Rehearse the walkthrough above twice with the timer.
