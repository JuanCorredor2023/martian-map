# Landing page mock (issue #126)

A design mock of the landing page and of the "Watch the demo" page, for the team to review. It is not the product: it lives in `docs/`, and the app does not serve it.

From here on, Diana (@dianagrz) reviews and completes it. Juan's Claude made this first version on 2026-11-15.

## How to view it

- Open `index.html` in a browser. A double click is enough: everything is local, with no internet, CDN or web fonts.
- Or serve the folder: `python -m http.server 8050 --directory docs/mocks/landing`, then open http://localhost:8050/.
- **App buttons.** *Plan (2D)*, *Open in 3D* and *Guide (tablet)* point to `/`, `/3d/` and `/guide.html`, so they work once the app serves this page. Outside the app, `mock.js` shows a short notice instead.
- **Two heroes.** The small "Hero A / B" switch at the bottom left compares two versions of the top section: A shows the 3D view, B shows the boxwork from orbit. `?hero=b` opens B; `?clean` hides the switch.
- **Previews without running anything:** `screenshots/` has the whole landing page at 1440 and 375 px, the whole demo page at 1440 px, and hero B.

## Files

| File | What it is |
|---|---|
| `index.html` | Landing page: what the app does in two sentences, the four buttons, the video placeholder, four sections with real screenshots (Plan, Check the way back, Rehearse, Follow), limits, team and credits. |
| `demo.html` | The seven-minute walkthrough of `docs/demo.md`, step by step: what to press, what to look for and a screenshot for each step. |
| `styles.css` | Shared styles: system fonts, light and dark themes, works from 320 px. |
| `mock.js` | Mock-only helpers (hero switch, app-link notice). Delete it when the page moves into the app. |
| `assets/` | Screenshots of the real app as WebP, in three widths each (6 MB). |
| `screenshots/` | Captures of the mock itself. |
| `review.md` | Design and accessibility self-review, with the fixes made. |

## Design decisions

- **Headline:** "Every step keeps a way home." It is the paper's core claim: the planner checks at every point of the route that there is energy and time left to get back.
- **The app is the hero.** Real screenshots only, with no renders, stock images or icons. The colour comes from the Mars imagery; the only accent is the app's own orange. A red underline under "way home" recalls the app's 30 min red line.
- **Structure taken from Apple's product pages and the HIG:**
  - one message per section, a short headline over 1–2 sentences, and a large real image;
  - one filled button for the most likely action;
  - 44 px targets, contrast of at least 4.5:1 (most text is above 6:1), and light and dark modes.
- **Offline, like the demo.** No YouTube embed: the video is a still from the app with a "coming soon" label. When the video exists, put its URL in the hidden `<a data-youtube-link>` on both pages and remove `hidden`.
- **Button names** follow the brief: *Plan (2D)*, *Open in 3D*, *Guide (tablet)*, *Watch the demo*. The demo page quotes the app's current labels (for example *3D view*) so that whoever presents presses the right button.
- **Team:** first names only, alphabetical, no titles.

## Where every number comes from

| Number | Source |
|---|---|
| 2 × 2 km box, 1 m grid, 0.25 m photo | `paper/sections/00_abstract.md`, `02_study_area_data.md` |
| 30 min of emergency oxygen | `paper/sections/03_10_product.md` (R_T = 1800 s) |
| About a third of what a 1.35 km circle calls safe | `00_abstract.md`; `paper/notes/product_api_hud.md` (36 %) |
| 21–46 % false safe for simple rules, 0 % for the planner | `00_abstract.md`, `06_conclusions.md`, `04_results.md` |
| 13 stations, 120 min → 8 visited | `04_results.md`; `paper/notes/E5_orienteering.md` |
| 60 min → the 3 best ridges; 1,000 Wh | `paper/notes/product_api_hud.md` |
| 383 Curiosity photos | `03_10_product.md`; `paper/notes/P3_rover_photos.md` |
| 3–22 min radio delay to Earth | `01_introduction.md`; `paper/notes/P6_departure_time.md` |
| 1–3 m ridges the DEM misses | `02_study_area_data.md` |
| Sand adds up to 11.5 % | `paper/notes/E1_maxent_irl.md` |
| 30° default limit; 29.6 % of the box off limits at 20°; it is the setting that changes routes most | `paper/notes/E3_metabolic_cost.md`; `product_api_hud.md` |
| Values by type 5/4/4/3; 13 stations | `paper/notes/E5_orienteering.md` |
| 15 E8 stations | `paper/notes/product_api_hud.md` |
| 1.35 km and Apollo 1.7 km circles | `paper/notes/product_api_hud.md` |
| 22.6 % radio coverage; 41 % of the tour without direct radio | `paper/notes/E11_comms.md`; `04_results.md` |
| Sol 4711: −74 to −4 °C, 11.9 h of daylight | `paper/notes/product_api_hud.md` |
| Time binds before energy; the energy model is an extrapolation; no GPS on Mars | `00_abstract.md`, `05_discussion.md`, `product_api_hud.md` |
| Step durations (30 s, 45 s…) and "seven minutes" | `docs/demo.md` §3. These are script timings, not results. |

Two numbers from `docs/demo.md` were left out because the notes disagree:
- "three are Curiosity's real drill sites" (the E5 note lists one Curiosity site);
- "rank correlation 0.00" (the note gives −0.001).

## To decide and complete

1. Whether the landing page becomes `/`, and where the 2D planner moves (with @Seredial0326, who owns `web/`).
2. **The video (#123):** add the link when it exists.
3. **Links that change if the landing page takes `/`:**
   - "← 2D planner" in `web/3d/index.html`;
   - "Planner" in `web/guide.html`;
   - "Open http://localhost:8000/" in `docs/demo.md` and the README.
   - The wrist card's QR (`web/card.html`) points to `/guide.html`, so it stays as long as the guide stays.
4. **One name per view (#124).**
   - Today the 3D view is "3D view" in the HUD, "Open in 3D" on the photo card and "Same walk in 3D" in the guide.
   - The 2D planner is "2D planner" in the 3D view and "Planner" in the guide.
5. Product name: "Mars EVA Planner" (the app's title) or "Martian Map" (the challenge and repo).
6. Hero A or B.
7. **Retake the app screenshots on the demo machine.** The laptop used here lacked the REMS, minerals and THEMIS releases. So the HUD's source chip reads "4 data types from 2 missions", and step 9 (weather) has no screenshot yet.
8. Add "HiRISE: NASA/JPL-Caltech/University of Arizona" to `paper/references.md`. It is the usual HiRISE credit and is used here.

## How the app screenshots were made

- **Setup:** the real app from `main` (e422e69, the `martian-main` server), driven by headless Edge through the DevTools protocol.
- **Sizes:** 1440×900 at 2× for the HUD and the 3D view, 1600×900 for the 3D hero, and 820×1180 for the tablet guide.
- **Plan:** the default 120 min plan (13 stations, 1,000 Wh, 30°, human cost). Planning rewrites `data/plans/last_plan.json`, so the file was backed up and restored; its hash is unchanged.
- **No stations or walks were saved.**
