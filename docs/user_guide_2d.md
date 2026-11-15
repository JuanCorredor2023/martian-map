# Mars EVA Planner · User guide: the 2D planner (HUD)

*Draft (JB's Claude, 2026-11-15), from `web/index.html` and `docs/demo.md` in main. Covers the 2D planner at `http://localhost:8000/` only; the tablet guide, the 3D map and the wrist card have their own guides (to do).*

## 1. What the planner does

You choose science stations in a 2 × 2 km area of the Gale crater boxwork and set the EVA's limits (time, energy, reserve, oxygen). The planner returns a walk that:
- visits the stations that give the most science value within those limits, in the best order;
- **always lets the astronaut get back to the habitat**: at every point of the route, the energy used plus the energy needed to return fits the budget (*walkback*);
- avoids cells steeper than the slope limit.

Then you rehearse the walk and check, at any point, how far the astronaut can still go and come back.

Everything runs on the local server; no internet is needed during use.

## 2. Starting

1. Start the server: `python -m uvicorn api.main:app --port 8000` (data set-up: `docs/demo.md` and `python -m api.check_data`).
2. Open `http://localhost:8000/`.
3. The screen has the **map** and a **side panel with tabs**: **1 Terrain → 2 Stations → 3 Plan → 4 Walk**, plus **Context**. Follow them in order; each tab ends with a **Next** button.
4. **Tips** appear in context the first time each step matters. A tip you have seen, or whose suggestion you followed, does not come back.

**Coordinates and units.** Positions are metres in the Mars map projection of the terrain model, energy is Wh, time minutes, oxygen litres. Move the cursor over the map: the box in the corner reads the cell under it.

**On the map:** drag to pan, scroll to zoom. **Fit plan** zooms to the walk; **Whole area** shows the whole box. The **On the map** legend lists only what is drawn right now (closed by default on small screens).

## 3. Tab 1 · Terrain: read the ground

| Control | What it shows | How to read it |
|---|---|---|
| **Photo from orbit** (HiRISE, 25 cm) | The orbital photograph | The only layer that shows the boxwork ridges (bright lines) and the sand (dark grey-blue) |
| **Shaded relief** | Hillshade of the 1 m terrain model | Knolls and scarps; it does not resolve the 1–3 m ridges |
| **Slope** | Steepest slope per cell | Green 0°, yellow 15°, orange 30°, red 45° and more |
| **Never cross cells steeper than N°** | Cells blocked for the planner (dark hatch) | Default 30°. **The setting that changes routes the most.** 20° blocks about 30 % of the box. Changing it marks the plan out of date |
| **Sand detected** | Fraction of each 1 m cell detected as sand | Cautious: when it marks sand it is right about 91 % of the time, but it misses most sand |
| **Boulders** | Dots per 10 m square; bigger dot, more boulder cover | Boulders larger than about 1 m. Context only: the route cost does not use them |
| **Walking cost** | Wh to cross each 1 m cell | The cheapest metre is a gentle descent, not flat ground |

**More layers:**
- **Radio coverage:** cells from which a suit radio sees the habitat antenna, and, with a plan, the stretches of the route with no direct radio (magenta). Pure line of sight on the terrain model: cautious.
- **Night temperature** (Mars Odyssey, 81 m pixels): context, not a cost.
- **Rover photos:** where Curiosity's Navcam photos were taken, with the direction each one looks. Click one for its card. Photos show the view, not a promise that a station is visible.

## 4. Tab 2 · Stations: where to go

**Add a station:** pick a **Type** (ridge, hollow, contact, Curiosity site), switch on **＋ Add stations by clicking the map** and click. The banner on the map says what a click will do; **Esc** stops placing.
- **Load Curiosity sites** adds Curiosity's drill sites.
- **Advanced:**
  - **Load AI-found sites** adds sand-rock contacts found by the boxwork detector (E8). They are added unsaved.
  - **Science value by type** edits the points of each type. Default: ridge 5, hollow 4, contact 4, Curiosity site 3.

**Stations table:** id, type, work time (minutes of service at the station) and value; edit them in place or remove a row. A "?" after an id marks a rough position; hover the id for its source.

**Save stations** keeps the list for next time. **Careful:** saving rewrites the whole saved list (and the values) with what is loaded now. Plans already use the list without saving.

## 5. Tab 3 · Plan: set the limits and plan

**Habitat** (where the walk starts and ends): **Centre of the area** by default; **Set on the map** to move it (click), **Back to the centre** to reset. A habitat on a blocked or cut-off cell is moved to the nearest valid one, and the plan says by how much.

**Limits:**
| Field | Meaning |
|---|---|
| **EVA length** (min) | Maximum duration of the walk, station work included |
| **Energy budget** (Wh) | Suit energy for the walk; a full suit ≈ 2,800 Wh |
| **Reserve kept unused** (%) | Part of the budget never planned (default 10 %) |
| More options · **Oxygen budget** (L, 0 = no limit) | Metabolic oxygen, estimated from the energy |
| More options · **Charge extra energy on sand** | Uses the sand price learned from Curiosity's route (up to +11.5 % on sand) |

Press **Plan the walk** (or **Enter** in a field). The first plan takes 10–30 s while the terrain graph is built; later ones are fast. A value out of range is flagged at its field.

**The summary:**
- a chip: **"The astronaut can get back from every point"** (or a warning if not);
- **Stations visited**, **Time**, **Energy** (of the budget minus the reserve) and **Distance**, each with a bar of how much of the limit it uses;
- the **visiting order**, and the stations **left out** because they do not fit;
- **Radio:** metres and minutes with no direct radio; **Show on the map** draws them;
- **Best time to leave:** the departure window that keeps the whole walk in sunlight, and the best time;
- **Details:** oxygen estimate, planner and energy model used.

**Out of date:** if you change limits, stations or habitat after planning, the plan is marked out of date until you plan again. If a new plan fails, the previous one stays, marked **Not updated**.

**No plan:** when nothing fits, the planner says why and what would fit (for example, "short of energy: station C1 needs 56.4 Wh; a budget of at least 62.8 Wh fits"). It never invents a route.

## 6. Tab 4 · Walk: rehearse and check safety

**Rehearse:** **▶** plays the walk (**Space** plays or pauses), at ×30, ×60 or ×180. The panel shows, as the walker moves:
- **Home in N min · limit 30:** the time back to the habitat against the 30 min emergency-oxygen limit;
- **Spare energy:** energy left after returning;
- the energy bar split into **used**, **needed to return** and **spare**; it only shrinks.

Links open the same walk in the **Tablet** guide, the **3D** view and the **Wrist card**.

**Safety on the map** (**Show the safety lines**):
- **red line:** the cells from which the astronaut can still walk home in 30 min;
- **dark shade:** out of reach with the energy left;
- neither is a circle: scarps and slopes shape them;
- **Compare with a fixed-distance rule:** draws the classic 1.35 km and Apollo 1.7 km circles; about a third of what they call safe cannot get back in 30 min.

**Try another point:** **Place the astronaut on the map** anywhere and set the **Energy still in the suit**; the lines and the numbers are computed from there.

## 7. Context

- **Radiation:** the dose accumulated over a sample walk; **Simulate a solar storm** shows the alert and the way home with its dose. The background dose does not change the plan; a storm does.
- **Weather on the day:** air temperature for a chosen **Sol** (one value per sol, from Curiosity's REMS).
- **Minerals seen from orbit** within 100 km: regional context.
- **Data sources:** where every layer comes from.

None of these enter the route cost.

## 8. Keyboard and accessibility

| Key | Action |
|---|---|
| ← → Home End (on the tabs) | Move between tabs |
| Tab to the map, arrows (Shift: bigger steps), Enter | Place a station, the habitat or the astronaut without a mouse |
| Esc | Stop placing; close the photo card |
| Enter (in a limit field) | Plan |
| Space (Walk tab) | Play / pause the rehearsal |

Touch targets are 44 px on touch screens; on narrow screens the map goes on top and the legend starts closed.

## 9. Suggested routes to learn the tool

1. **First plan (5 min).** Terrain: turn on Slope and Sand. Stations: Load Curiosity sites. Plan: keep the defaults, Plan the walk. Walk: ▶, then pause and Show the safety lines.
2. **Time is the limit.** Plan with EVA length 120, then 60 min: fewer stations; at 60 min the highest-value ridges are kept. In this area time runs out long before energy.
3. **The slope limit.** Change *Never cross cells steeper than* from 30° to 20° and plan again: the route changes and more of the area is blocked.
4. **When nothing fits.** Set the energy budget to 40 Wh: read why there is no plan and the budget that would fit; plan with it.
5. **Fixed radius vs terrain.** Walk tab: Compare with a fixed-distance rule; look at the cells inside the circle but outside the red line.
6. **Any point.** Try another point: place the astronaut far from the habitat with little energy and watch the shade grow.
7. **Radio and light.** Plan: Show on the map the stretches with no radio; read the best time to leave.
8. **Science values.** Advanced: raise the value of hollows, plan with a short EVA, and see which stations change.

## 10. What the numbers mean (and do not)

- Energy is a model (Santee 2001 with Mars gravity), not validated for a suited astronaut; oxygen is estimated from energy, not a tank reading.
- The terrain model does not resolve the 1–3 m boxwork ridges; sand and boulder layers miss part of what is there.
- Station values are an expert ranking, not measurements; service time and power are placeholders.
- Walking is simulated: there is no GPS on Mars.
