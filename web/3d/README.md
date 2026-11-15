# 3D map of the boxwork box (`/3d/`)

A page that shows the 2 × 2 km study box in 3D: the DEM with the HiRISE photo on it, the
plan of the 2D planner drawn on the ground (route, stations, habitat), a walk-through of
the route at eye height, and the light and shadows of the Sun of Mars at a sol and a local
time. It reads the plan; it never makes one unless asked. three.js is vendored
(`vendor/`), so the page needs no internet. Method, numbers and limits:
`paper/notes/P1_3d_map.md`.

## Run it

From the repo root, with `data/base/` in place:

```
python src/viz3d/build_terrain_assets.py      # once: writes data/tiles/3d/ (a few seconds)
python -m uvicorn api.main:app --port 8000    # the API serves the page and the assets
```

Open `http://localhost:8000/3d/` (the 2D planner links to it). `MARTIAN_DATA` selects
another data folder, as for the API. `data/tiles/3d/` is not in the tiles release: if
`data/tiles/` is replaced, build again; without it the page shows the command.

The route comes from `GET /plan/last`: plan an EVA in the 2D planner, then open the page
or press "Reload plan". With no saved plan the terrain still works.

## Controls

| | Mouse | Touch |
|---|---|---|
| Rotate around the point under the cursor | drag | one finger |
| Move | right-drag or Shift + drag | two fingers |
| Zoom towards the point under the cursor | wheel | pinch (twist turns) |

- Compass (top right): face north. House: back to the opening view.
- **Relief slider**: ×1 is the DEM; ×1.5 to ×5 exaggerate only the local relief.
- **Plan**: source, length, time, energy and warnings of the plan; "Reload plan";
  "Rehearse the route". "Plan with default settings" appears only when there is no plan,
  and makes the server plan and save (it replaces the last plan of the 2D planner).
- **Pins**: click one for its card; "Fly here" views it from 60 m. Stations a tour did not
  visit are dimmed.
- **Rehearsal**: play / pause (space bar), ×1 to ×180, scrubber, "Chase view", drag to look
  around, double-click or "Recentre" to look forward, "Exit". It pauses at every stop with
  the station's card; on pause it draws the walkback lines from there (red: 30 min return,
  cyan: energy-safe area). The relief is locked at ×1 and the Sun follows the EVA clock.
- **Sun**: Curiosity sol, local true solar time, "Relief only" (hide the photo), "Shadows".
- **About this view**: "Copy link to this view" (the address of the free-flight view, with
  relief, sol, time and the shadows switch) and "Save image" (the picture without the
  panels, as a PNG, through the browser's download).

## Address parameters

All optional; they combine with `&`.

| Parameter | Meaning |
|---|---|
| `q=low` / `q=high` | quality preset. Low: 4 m mesh, one 4096 px photo, 2048 shadow map. High: 2 m mesh, photo at 0.25 m, 4096 shadow map. Default: low on touch or small screens, else high |
| `k=1..5` | relief exaggeration at the start, in steps of 0.5 (default 2) |
| `view=x,y,z,heading,pitch` | where the camera starts: Mars CRS metres, elevation of the camera in metres (DEM datum), heading from north and pitch below the horizon in degrees. Example (the opening view): `view=8143537.49,-286459.66,-2146.25,0,37` |
| `sol=4711` | Curiosity sol whose Sun lights the scene (default 4711) |
| `lt=15:00` | local true solar time at the box centre (default 15:00) |
| `shadows=0` | start without cast shadows |
| `light=az,el` | debug: a fixed light direction in degrees instead of the Sun |
| `drag=pan` | map-style mouse: drag moves, right-drag rotates |
| `plan=default` | on load, ask the server for a plan with the default settings. **It replaces the saved plan**, like the button |
| `fps=1` | draw every frame and show frames per second in the readout |
| `spin=1` | slowly orbit the camera (to measure speed without touching anything) |
| `check=<name>` | run a check (below) and show its result as JSON |

## Checks in the page

`/3d/?check=<name>` runs a measurement in the running page and shows the result (also in
`viz3d.checkResult` and the console). Add `&q=low` for the low preset. They ask nothing
from the server and leave the page as they found it.

| Name | What it answers |
|---|---|
| `shading` | is the terrain lit from the right side? (lit from N, S, E, W against the slopes) |
| `route` | is the route 0.3 m above the drawn ground at relief ×1, ×3 and ×5, as long as the plan says, with the pins where the plan puts them? |
| `rehearse` | the whole walk in steps of 0.1 s: eye height, turns, distance from the route, pauses at the stops; does leaving put everything back? |
| `sun` | is the light where the Sun of Mars is at five times of the sol; morning against afternoon; does the Sun follow the rehearsal? |
| `shadows` | rendered shadows against a ray march over the mesh, 07:00, 15:00 and 17:00 at ×1 and ×5 (about 12 s; 7 s in the low preset) |

From the console, `viz3d` gives the page's objects, and `viz3d.showPlan({fc})` draws any
plan answer without touching the server (how the test fixtures were looked at).

## Files

| File | What it does |
|---|---|
| `index.html` | the page: panels, styles, import map for three.js |
| `main.js` | entry point: address parameters, scene, frame loop, plan panel, view link and image |
| `terrain.js` | loads the assets, builds the meshes, heights, CRS ↔ scene coordinates, relief factor |
| `controls.js` | free-flight camera (arcball on the terrain), `flyTo` |
| `camera_math.js` | the camera's maths: axes, orbit, pan, zoom, ray against the heights |
| `api.js` | the requests: saved plan, default plan, rubric, walkback |
| `plan_model.js` | plan answer → routes, points, profile, markers |
| `overlays.js` | route and walkback lines draped on the mesh |
| `markers.js` | pins and the habitat dome; picking |
| `card.js` | the side card of a station |
| `rehearse_model.js` | where the walker is at a time of the plan: clock, stops, camera path |
| `rehearse.js` | the rehearsal mode: camera, player, stops, walkback on pause |
| `mars_sun.js` | Mars24: where the Sun is for a UTC instant; sols and local times |
| `sun_model.js` | sol and local time → light direction, light levels, panel texts |
| `sun.js` | the lights, the sky colour, the Sun section, "Relief only" |
| `shadow_fit.js` | the box the shadow map must cover for a Sun direction |
| `shadows.js` | cast shadows: when the shadow map is drawn again |
| `view_link.js` | `?view=`: a free-flight view as text, and the link that carries it |
| `checks.js` | the `?check=` measurements |
| `vendor/` | three.js r187, only the files the page imports (`vendor/README.md`) |

The files with "model", "math", "fit" or "link" in the name, `mars_sun.js` and `api.js`
import nothing from three.js and are tested in Node.

## Tests

From the repo root (Node 26, nothing to install):

```
node --test tests/viz3d/            # camera, plan, rehearsal, Sun, shadow camera, view link
python -m pytest tests/viz3d -q     # the terrain assets against the DEM
```

Fixtures in `tests/viz3d/fixtures/` are real answers of the API: an E4 round trip, the
fixed route with no profile, and a multi-station E5 tour
(`src/viz3d/make_tour_fixture.py` says how it was made).

## Known limits

- The DEM (1 m) does not resolve the 1–2 m boxwork ridges: the relief and the shadows show
  the hillside, knolls and scarps; the ridges are seen in the photo only.
- Relief above ×1 is exaggerated and no longer to scale; shadows follow the relief as
  shown, so they are true only at ×1. The photo also carries its own mid-afternoon shadows.
- Light levels are a look, not a physical model (no atmosphere or dust). Only the box
  casts shadows.
- The rehearsal plays the plan back on its own clock; with no profile in the plan it
  assumes 1 m/s. The camera follows a smoothed copy of the route (up to about 1 m from it).
- "Plan with default settings" and `plan=default` replace the saved plan that the guide
  screen loads. A copied view link never carries `plan`.
- The view link is of the free-flight view (not offered while rehearsing) and does not
  carry "Relief only". The page keeps the camera 2 m above the shown ground and the pitch
  between 2° and 89.5°, also when it opens a link.
- "Copy link" writes to the clipboard only on `localhost` or https; from another machine of
  the local network the link is shown in a box to copy by hand.
- "Save image" saves the canvas at its size on screen (times the pixel ratio, at most 2;
  1.5 in the low preset): terrain, route and pins, without the panels, the card or the player.
- The pixel ratio is read when the page loads: moving the window to a screen with another
  density needs a reload.
- Speed was measured on one laptop (60 fps in both presets); no tablet was measured.
