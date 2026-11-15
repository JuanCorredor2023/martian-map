# Mars EVA Planner · User guide: the 3D map

**Illustrated version:** open `docs/user_guide_3d/index.html` in a browser: the same guide with annotated screenshots of every control.

*Draft (JB's Claude, 2026-11-15), from `web/3d/README.md` in main and checked against the running page (quoted texts are what the screen shows, with a plan of 120 min and 1,000 Wh over the 13 saved stations). The 2D planner has its own guide: `docs/user_guide_2d.md`.*

## 1. What the 3D map does

It shows the 2 × 2 km box of the Gale boxwork in 3D: the 1 m terrain model with the HiRISE photo (25 cm) on it. On top it draws the plan of the 2D planner (route, stations, habitat), lights the scene with the Sun of Mars at a sol and local time, drapes one map layer of the 2D, and lets you **rehearse** the walk at eye height with the arm tablet's meters, or **walk freely** anywhere. It reads the plan; it never makes one unless asked. No internet is needed.

## 2. Starting

```
python src/viz3d/build_terrain_assets.py      # once: the 3D terrain (a few seconds)
python -m uvicorn api.main:app --port 8000    # then open http://localhost:8000/3d/
```

Plan first in the 2D planner; its **3D** link (step 4, Walk) opens this page with the same plan. With no saved plan the terrain works and the panel offers **Plan with default settings**. **Careful:** it replaces the saved plan that the 2D planner and the tablet read.

## 3. The screen

- **Panel** (left): *Plan* (open at the start), *Sun*, *Map layer*, *Rover photos*, *About this view*. Click a title to open or fold it.
- **Local relief** slider: ×1 is the real terrain; ×1.5 to ×5 exaggerate the local relief (default ×2). Rehearsing and walking lock it at ×1.
- **← Planner**: back to the 2D planner.
- **Compass** (top right): face north. **Frame** (under it): back to the opening view.
- **Pins**: habitat and stations; stations the plan does not visit are dimmed. Click one for its card.
- **Readout** (bottom left): position and elevation under the cursor.
- Route colours: cyan outbound, pink return.

| | Mouse | Touch |
|---|---|---|
| Rotate around the point under the cursor | drag | one finger |
| Move | right-drag or Shift + drag | two fingers |
| Zoom towards the point under the cursor | wheel | pinch (twist turns) |

## 4. The plan

The *Plan* section says where the plan comes from ("Last plan from the planner"), its length, time and energy ("1392 m · 111 min · 448 Wh of 900 usable"), the stations visited and science value, the order (R3 → R2 → …), the stations left out and the power used at the stations. ⚠ in amber marks only what needs a look (for example a habitat the planner moved).

- **Stations (13)**: folded list in visiting order, then the stations not visited. A station ("1 · R3 · Boxwork ridge") flies there and opens its card: type, science score, service time, visit order, and the nearest rover photo within 150 m. **Fly here** views a pin from 60 m.
- **Reload plan** reads the planner's last plan again. **Rehearse** and **Walk freely**: sections 7 and 9.

## 5. Sun and shadows

**Curiosity sol** (default 4711) and **Local solar time**. Once a plan is drawn the Sun goes to the plan's best time to leave (11:00 for this plan), as in the 2D planner. The readout says the Sun's height and where the light comes from ("Sun 7° high, light from the west" at 17:30). **Relief only** hides the photo; **Shadows** casts the relief's shadows (true to scale only at ×1). The photo carries its own mid-afternoon shadows.

## 6. Map layer

One 2D layer on the relief, with its legend and an **Opacity** slider: Radio coverage (seen from the plan's habitat), Slope, Too steep to cross (the plan's slope limit), Sand detected, Walking cost, Boulders. Off by default. It stays on while rehearsing.

## 7. Rehearse the walk

**Rehearse** walks the plan at eye height on the EVA clock, with the tablet's guide. The panel hides (**Panel** shows it again); the relief locks at ×1 and the Sun follows the EVA clock.

The player, from top to bottom:
- the **next maneuver**: arrow, distance ("220 m") and instruction ("Arrive at station R3"), spoken with voice on;
- **Play/Pause** (Space outside controls), **Return home**, **Off route**, **Solar storm**; then **More**, **Panel**, **Exit** (Esc only closes a card and pauses);
- **More**: **Chase view**, **Recentre**, speed (×1, ×30, ×60, ×180), **Voice**, **Use ×k** (demo: energy use against the model, 1.0 → 1.2 → 1.5 → 0.8) and the energy numbers;
- the **scrubber** and the EVA clock ("EVA 6:01 of 111:27 · outbound · 262 of 1392 m"), the Sun line, the energy bar (used, needed to return, spare);
- the **tablet's meters**: Spare energy, Home in · limit 30, Radio, Spare energy at your pace, EVA time left, each with OK, LOW or TURN BACK;
- on pause, **Return home from here** ("✓ 6 min (limit 30) · ✓ 28 Wh, 839 Wh spare after it"), with the red 30 min line and the cyan energy-safe area on the terrain.

**At each station** the walk stops with the station's card (arrival, time standing, why it matters, tasks); **Done, continue** resumes.

**Energy at your pace.** With **Use ×1.5** the tablet learns the factor k as the walk goes ("k 1.06 (90 % 1.00–1.12) · 634 Wh") and recomputes the spare energy. If the way home no longer fits at that pace, a **RETURN NOW** alert appears (not with this plan's 900 Wh; yes with a tight budget).

**Contingencies.** **Return home** draws the fastest way home (red). **Off route** steps 25 m off the route and the guide brings the walker back (orange). **Solar storm** shows the banner "SOLAR STORM · return home now", a red vignette and the automatic way home ("EVA 11:32 · return home 2:30 of 8:23 · 112 of 380 m"); *Why and how much* gives the dose.

**At the habitat** the card **Plan against the walk** compares the rehearsal with the plan: time 111 min (plan 111), energy 447 Wh (448), distance 1363 m (1392), stations 8 (8), metres without direct radio, distance from the plan, learned k. **Replay** starts again; **Summary** shows the card again; **Exit** leaves.

## 8. Rover photos

Needs the photo catalogue (`data/tiles/3d/photos/`); without it the section says "No rover photos: the server has no photo catalogue" and the rest works. **Show photo stops** puts orange camera pins on the terrain; a pin opens the stop's card (photo, views, date, sol, time, direction, credit). **View from here** puts the camera where the Navcam stood, with the Sun of that photo, and lays the photo over the view: slider to fade, **Previous**/**Next**, **Realign**, **Exit** or Esc.

## 9. Walk freely

Walk anywhere in the box (works without a plan). The route becomes a path on the ground and each station a ring with a flag. **Run** (3 m/s, Shift), **Fast** (20 m/s, F), **Chase view** (C), **Exit** (Esc). W/S or ↑/↓ walk, A/D step sideways, ←/→ turn (90° per second), click the view and move the mouse to look. On touch: an arrow pad and drag. It is a game, not the EVA: no slope limit and no energy cost.

## 10. Share a view

*About this view*: **Copy link to this view** (camera, relief, sol, time, shadows) and **Save image** (PNG without the panels). Address options: `q=low|high` (quality), `k=` (relief), `sol=`, `lt=`, `shadows=0`, `drag=pan`, `photo=<id>`, and `plan=default` (**replaces the saved plan**).

## 11. Keyboard

| Keys | Where | Action |
|---|---|---|
| Tab, Enter or Space | Panel | Open a section or list; choose a station or photo stop |
| Space | Rehearsal, outside a control | Play / pause |
| Tab / Shift + Tab | Rehearsal | Main buttons, More, Panel, Exit, then the rest |
| Esc | Rehearsal | Close the top card or message and pause |
| W A S D, arrows, Shift, F, C, Esc | Walk freely | Walk, turn, run, fast travel, chase view, leave |
| Esc | Photo view | Leave it |

## 12. Suggested routes

1. **Read the ground (3 min).** Relief ×4; Map layer: Slope, then Too steep to cross.
2. **Rehearse the plan (5 min).** Rehearse, Play at ×60; read R3's card; pause and read Return home from here.
3. **Light at departure (3 min).** Sun: drag from 07:00 to 17:30 with Shadows on.
4. **Something goes wrong (3 min).** Solar storm; Replay; Off route; Return home.
5. **A tired astronaut (4 min).** More → Use ×1.5; watch Spare energy at your pace.
6. **Walk the ridges (3 min).** Walk freely, C for the chase view, follow the path to R3.

## 13. What it shows, and what it does not

- The 1 m relief shows the hillside, knolls and scarps, not the 1–2 m boxwork ridges (those are in the photo). Above ×1 it is exaggerated.
- Shadows are true only at ×1; light levels are a look (no dust or atmosphere).
- The rehearsal plays the plan back; it never changes the route. The energy is a model and k is simulated.
- Walking freely ignores the slope limit and the energy cost.
- A rover photo shows where the Navcam looked, not a promise that a station is in view.

## 14. When something looks wrong

| You see | What to do |
|---|---|
| A command instead of the terrain | `python src/viz3d/build_terrain_assets.py` |
| No route, or an old one | Plan in the 2D planner, then **Reload plan** |
| "No rover photos…" | The photo catalogue is missing; the rest works |
| Slow or choppy | Add `?q=low` |
| Copy link does nothing | The clipboard works only on localhost or https: copy from the box |
| Esc does not leave the rehearsal | By design; press **Exit** |
