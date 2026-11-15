# P122 · Public demonstration deployment preparation

Owner: Sebas (`@Seredial0326`) · Issue: #122 · Status: phase 1 prepared, not deployed · Last update: 2026-11-15

## Question
Can the existing local planner be demonstrated publicly without visitors overwriting its shared plan/stations, and what compute/storage does that require?

## Data
The selected local application data folders, current saved request and graph. No data were uploaded. The issue's size is an estimate, not an asset manifest. `docs/deploy.md` cites the official provider pages checked for this comparison.

## Method
`tools/deploy_audit.py` counts files/bytes and optionally samples process RSS while building the real E3 × E1 graph and planning the saved request. `api/public_mode.py` wraps the original ASGI application via a separate factory, without editing shared API or frontend files. The optional mode defaults off locally; read-only mode freezes a feasible saved plan, rejects writes and differing planning requests, and serializes bounded computational requests with pinned graph/habitat settings. Exact requests replay the frozen plan rather than recomputing or saving it. A public-only banner retains source attribution.

## Results
Source: `tools/deploy_audit.py` → `data/deploy-phase1/audit.json`. Inventory: 945,366,327 bytes across the selected folders; the selected E4 request has a sampled peak RSS of 3,149,279,232 bytes and retained RSS of 2,275,864,576 bytes after the first plan. Building the graph took 3.18 s; the first round trip took 6.98 s. These are one Windows process/request, not container sizing guarantees. Provider prices/capacities and the recommendation are in `docs/deploy.md`, with primary-source links. No figures are needed for this preparation block; no scientific model or published experiment number changes.

## Checks
`tests/deploy/test_public_mode.py` exercises write rejection, unknown methods, immutable replay, unchanged local behavior, pinned graph/habitat/query settings, credit insertion/content length, malformed/oversized requests and computational concurrency. Test inputs are synthetic; downloaded data and a network service are not needed. The JUnit result is `data/deploy-phase1/public_mode.xml`. A local TestClient smoke check with the existing data also opened `/`, `/3d/`, `/guide.html`, `/card.html`, the frozen plan, tile metadata, public status and health, and rejected station/walk writes. This is HTTP-level validation, not browser or hosting validation. The Linux image is not built because Docker is unavailable; no package was installed.

## Limitations
The concurrency regression also checks `/home/assets/hero.webp`: the new landing folder bypasses the computational gate while a route calculation is running. This change supports Diana's separate landing-page PR without editing its frontend files.

The fixed public mode still computes return fields and radio, so it does not fit a 512 MB server merely because planning is disabled. Full public optimization needs per-visitor storage isolation and bounded compute; it is not implemented. A fixed demo also needs Claude's client integration to explain disabled editing/logging. Banner positioning, Linux GDAL, data completeness, cold starts and the hosted walkthrough remain phase-2 checks. No address has been published and no data transferred. All such actions require explicit approval from Sebas.

## What other pieces can use
Claude can consume `GET /public/status` for the readonly capability/snapshot and launch with `api.public_mode:create_app --factory`; no edit to `api/main.py` is necessary. JB can use the resource measurements to select a budget and the phase-2 checklist to assess readiness. #122 must not close at this preparatory stage.

## Reproduce
Use the commands in `docs/deploy.md` from the repository root, in the existing scientific environment. The audit outputs and original data stay outside git.

## Outputs
`api/public_mode.py`, `tests/deploy/test_public_mode.py`, `Dockerfile`, `.dockerignore`, `docs/deploy.md`; local resource evidence at `data/deploy-phase1/audit.json`.
