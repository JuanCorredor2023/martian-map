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
   | `data/e1/` | `e1-sand-v1` | human cost: E3 × E1 sand price (optional; without it E3 alone) |
   | `data/rems/` | `rems-v1` | surface weather panel (REMS) (optional) |
   | `data/minerals/` | `minerals-v1` | regional minerals panel (CRISM/OMEGA) (optional) |
   | `data/tiles/3d/` | generated | 3D view: run once `python src/viz3d/build_terrain_assets.py` (optional) |

   PowerShell example: `gh release download base-grid-v2 --dir data; Expand-Archive data\base_grid_v2.zip data\base -Force; Remove-Item data\base_grid_v2.zip`. The stations release has no zip: `gh release download stations-v1 --dir data\stations`.

## 2. Start

```
python -m uvicorn api.main:app --port 8000
```
Open **http://localhost:8000/**. The first plan or walkback takes about 10 s while the graph is built and cached; later calls take well under a second.

Health check: `http://localhost:8000/health`. Tests: `python -m pytest tests -q`.

No internet is needed at demo time: deck.gl is vendored in `web/vendor/` and all data is local.

**Guide mode (arm tablet):** after planning, open the link under the plan (or `http://localhost:8000/guide.html`). Press ▶ Walk; try *Detour (demo)* (off route → recalculating), *Solar storm (demo)* (automatic way home with the dose) and *Return home*.

## 3. Six-minute walkthrough

This follows the guide's demo script (zero-to-hero REV3, section 51).

1. **Terrain (30 s).** HiRISE ortho with the slope layer on top; switch on *Sand detected (E8)*. Say that the 1 m DEM does not resolve the boxwork ridges, but the 0.25 m image does. Open the line under the title: *6 data types from 3 missions* (HiRISE image and DEM, and CRISM minerals, from MRO; OMEGA from Mars Express; Curiosity's traverse, RAD and REMS from MSL), counted only when used.
2. **What a step costs (45 s).** Turn on *E3 walking cost*. *Human cost* (EVA limits) multiplies E3's energy by E1's sand price (up to +11.5 % on sand), the one terrain term learned from Curiosity's route that held up on unseen data. The cost is Santee 2001 with Mars gravity only in the slope term. Whole-power scaling fails the lunar check (52 W against 292 W on flat ground). The cheapest metre is a gentle descent (338.75 J/m), not flat ground.
3. **Steep cells (20 s).** Move *Block cells steeper than N°* (30° by default; 20° blocks 30 % of the box). This is the decision that changes routes the most (E3 sensitivity).
4. **Science stations (45 s).** The right panel lists 13 stations. Three are Curiosity's real drill sites (Nevado Sajama ridge, Valle de la Luna hollow, Altadena); the rest are candidates. The rubric (ridge 5, hollow 4, contact 4, Curiosity site 3) is editable live; its literature review is in `docs/research/`.
5. **Plan (60 s).** Set the EVA limits (energy budget, margin, **max duration**) and press *Plan EVA*. E4 builds the round trip live. Press **▶ Play**: the budget bar splits energy into used, needed to return and free. It only shrinks, and the arrow shows the heading.
6. **Walkback (45 s).** Pause anywhere. The **red line** is the 30 min emergency-oxygen return (R_T = 1800 s); the **cyan line** is where the astronaut can still go and come back with the energy left (F_E + R_E). Neither is a circle: scarps and slopes shape them. The thin circles are the classic fixed-radius rules (1.35 km, Apollo 1.7 km): about a third of what they call safe cannot get back in 30 min.
7. **Solar storm (30 s).** In *Radiation (E12)* pick a storm and press *Simulate SEP alert*: the dose on the way back is the return time × the storm rate. Background radiation does not change the plan; a storm does.
8. **Weather of the EVA's sol (20 s).** *Surface weather (REMS)*: sol 4711 (the Nevado Sajama drill) had air from −74 to −4 °C, ground from −86 to +12 °C and 11.9 h of daylight, so a 120 min EVA fits. Weather is context: REMS gives one value per sol, not a map. Below it, *Minerals from orbit*: the box sits inside Gale; the nearest hydrous detection (CRISM/OMEGA) is 16 km away and the nearest clay 30 km. Orbit only sees the region; Curiosity measured the box itself at the drill sites.
9. **3D rehearsal (40 s).** Press *3D view* (or open `/3d/`): the last plan is drawn on the terrain with the HiRISE photo. Press *Rehearse the route* to walk it at eye height with the same energy bar; the Sun is set for the same sol 4711 and local time, with shadows. Say that the relief of the 1–2 m ridges comes from the photo, not the DEM.

## 4. What to say honestly

- Santee 2001 with g = 3.71 m/s² is an extrapolation, not validated for a suited astronaut on Mars. O2 is a metabolic equivalent (20.1 kJ/L), not a tank reading.
- In this 2 × 2 km box energy rarely binds (the costliest round trip is about 560 Wh against 2,813 Wh xEMU); time does.
- E1 (learning from Curiosity's route) found no DEM terrain price; only E8's sand helps on unseen data. Its price is small: the route to Nevado Sajama moves up to 23 m and costs 1.8 % more, and the 120 min tour visits the same stations. It applies to astronauts what rover drivers avoided, which is an assumption.
- Station values encode an expert ranking, not measurements. The walkback fields are on the same E3 costs as E4.
- There is no GPS on Mars: walking the route is simulated.

## 5. Code freeze checklist (hour 40)

- [ ] All MVP PRs merged into `main`; `python -m pytest tests -q` passes on a fresh clone.
- [ ] `python -m api.check_data` passes on the demo machine; the releases are the final versions.
- [ ] Demo machine: server starts, first plan built once before presenting (warm cache).
- [ ] Every piece's paper note is up to date (`paper/notes/`, AGENTS.md rule 7).
- [ ] Delivery branch created from `main` (`release/demo`); after hour 40 only bug fixes, each as a PR.
- [ ] Rehearse the walkthrough above twice with the timer.
