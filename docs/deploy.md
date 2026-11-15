# Deployment preparation (#122), phase 1 only

Owner: Sebas's Codex. **Nothing has been published or uploaded.** Phase 2 (data
transfer, account purchases or a public address) needs Sebas's explicit approval.
PRs for this work also require Sebas's explicit approval before merge.

## Recommendation

Prepare a **fixed-plan, read-only public demo first**, using the independent
`api.public_mode:create_app` ASGI factory. It serves the existing application and
protects its shared files. Local `uvicorn api.main:app` stays unchanged. A full
public planner is a second project: each visitor needs isolated plans, stations
and walk storage plus resource limits. Merely adding authentication to the Plan
button or trusting a browser cookie would not isolate the current global paths.

Leading low-cost compute candidate: **Hugging Face PRO + CPU Basic Docker Space**,
subject to account eligibility and a phase-2 data-hydration procedure. Its current
docs require a paid plan to create compute Spaces; CPU Basic itself has no hourly
charge. PRO is listed at $9/month. It offers enough nominal RAM for the measured
single-process workload. A Linux VM with at least 8 GB RAM and a read-only data
mount is the simplest fallback when predictable startup/storage matters; obtain
an actual regional quote and approve its cost before provisioning. No promise is
made that the entire demo is free.

## Options checked against official documentation

Checked 2026-11-15; prices/quotas can change. Storage size alone is not RAM demand.

| Option | Cost and capacity evidence | Full API | Fixed-plan demo |
|---|---|---|---|
| Hugging Face Docker Spaces | PRO $9/month required for new compute Spaces; CPU Basic has no hourly cost, 2 CPU, 16 GB RAM and 50 GB ephemeral disk | Memory plausible; session isolation still required | Preferred budget candidate, but approved external data hydration and sleep/cold-start rehearsal are required |
| Render Free | $0, 512 MB; sleeps after 15 minutes; no persistent disk | Insufficient for measured graph workload | Only a **fully precomputed** viewer with heavy endpoints removed; current read-only guard still performs graph calculations |
| Render paid | Pricing page lists 2 GB at $25/month, 4 GB at $85 and 8 GB at $135; disk $0.25/GB-month | 2 GB is below the measured peak; validate headroom on 8 GB or higher | Works in principle; comparatively expensive for this demo |
| Railway | Hobby $5/month minimum credited toward usage; RAM $10/GB-month, CPU $20/vCPU-month, storage $0.15/GB-month, egress $0.05/GB | Feasible after isolation; persistent in-memory graph makes the $5 headline misleading | On continuously retained 4 GB RAM, RAM alone is about $40/month, before CPU/storage/egress; not a $5 total quote |
| Fly.io | Compute plus volume and egress; current trial is only 2 VM-hours across 7 days, trial machines stop after 5 minutes | Feasible paid configuration; quote memory/region first | Trial is not a durable jury demo; persistent data volume and enough RAM required |
| GitHub Pages / static hosting | No Python process | No | Requires exporting responses and adapting the client to fixed data; existing FastAPI UI cannot simply be copied and expected to plan |

Sources: [HF Spaces overview](https://huggingface.co/docs/hub/spaces-overview),
[HF pricing](https://huggingface.co/pricing),
[HF Docker port configuration](https://huggingface.co/docs/hub/en/spaces-sdks-docker),
[Render pricing](https://render.com/pricing), [Render free limits](https://render.com/docs/free),
[Railway pricing](https://docs.railway.com/pricing),
[Fly trial](https://fly.io/docs/about/free-trial/),
[Fly resource pricing](https://fly.io/docs/about/pricing/).

## Data and memory measurements

The issue estimates a roughly 920 MB demo kit. The local selected-folder inventory
contains 945,366,327 bytes, but has different contents: base 672,554,754 bytes and
tiles 219,288,717 bytes. This is an inventory, **not the final minimal kit** or a
claim that all rover photographs are present. Source: `tools/deploy_audit.py` →
`data/deploy-phase1/audit.json`. Do not publish the whole raw-data directory.

In one cold Windows process, building the graph and planning a saved E4 round trip
used a sampled peak RSS of 3,149,279,232 bytes (about 2.93 GiB), with
2,275,864,576 bytes retained afterward. Graph construction took 3.18 s and the
first round trip 6.98 s. Same script/output, `profile` fields. This is not a Linux
container measurement, concurrency test, or upper bound: raster layers, cached
returns and a larger tour can consume more. Start with one process and one heavy
calculation at a time; validate 8 GB or more and leave headroom before phase 2.

Required public kit: the DEM/grid/CRS/slope, existing raster tiles, generated 3D
terrain, frozen plan and stations/rubric, E1 and its E8 feature rasters, E9/RAD/REMS
and context products used by the walkthrough. Include the rover-photo catalogue
and images if demonstrating that feature. Generate a manifest of exact approved
files and SHA-256 values before transfer. Exclude training data/checkpoints,
raw mosaics not read by the app, existing personal walk logs and credentials.

## Public-mode behavior

`MARTIAN_PUBLIC_MODE` is `off` by default in Python. Only the separate container
entry point sets it to `readonly` by default. An unknown value fails startup.

- `/plan/last` is an immutable startup snapshot.
- `POST /plan` replays that plan only when the normalized request exactly matches
  its saved request. A different request is denied; it never calls the planner or
  overwrites the demo. The response says `public_mode=readonly` and includes the
  snapshot hash. This is not interactive optimization.
- `POST /stations`, `POST /walks`, unknown POST endpoints and other write methods
  are blocked. Walk logging is intentionally unavailable; client-side playback
  and its in-memory summary remain separate from server persistence.
- Computational POST endpoints for walkback, adaptive estimation, radio and
  return/rejoin remain available. The habitat and graph settings are fixed; radio
  geometry and route are restricted to the frozen demonstration. These operations
  still need the graph and substantial RAM.
- Heavy requests are serialized with a busy response instead of an unbounded
  queue. There is a request-body limit. Use provider-level rate limiting too;
  this middleware is not a complete abuse-prevention service.
- `/public/status` describes capabilities and the snapshot; `/public/credits`
  lists sources/limits. Public HTML responses receive a small visible credit
  banner with NASA/JPL-Caltech and USGS attribution. Source-specific photographic
  credits are retained. No file in `web/` is edited.

Claude owns the client. Before phase 2, integrate `/public/status` into the HUD:
load the fixed plan, explain disabled editing, and handle blocked persistence
without suggesting a walk was saved. Confirm banner placement with the current
HUD/tablet/3D layouts; this has not been browser-tested. No hook in `api/main.py`
is required, and none was changed.

## Local preparation and verification

Use the existing scientific environment; no dependency installation is needed to
run the guard tests. ASGI tests on Windows need the event loop's local socket
permission. They do not contact a hosting provider.

```powershell
python -m pytest tests/deploy -q
python tools/deploy_audit.py --data C:/path/to/data --out data/deploy-phase1/audit.json --profile
$env:MARTIAN_DATA = 'C:/path/to/curated-data'
$env:MARTIAN_PUBLIC_MODE = 'readonly'
python -m uvicorn api.public_mode:create_app --factory --host 127.0.0.1 --port 7860 --workers 1
```

Start only after selecting a coherent frozen plan with its stations, costs and
profiles. Exporting a plan alone is not enough for graph-based guide operations.
Mount a dedicated immutable copy of the kit, not a directory another local agent
or test suite is changing. The factory fails if no feasible saved plan is present.

`Dockerfile` installs GDAL bindings matching its system library and OR-Tools for
large tours, runs as UID 1000, and uses a single Uvicorn worker. The `.dockerignore`
allowlist excludes scientific data, git/worktree state, tests, papers and secrets
from the build context. `/app/data` links to `/data` for older source modules that
resolve data relative to the repository rather than `MARTIAN_DATA`.

Docker is unavailable on the preparation machine. The image has **not been built**
and the Linux GDAL/dependency combination still needs a build and smoke test.
Building it installs dependencies inside an image and requires Sebas's approval
under this task's installation rule. After approval, local-only examples are:

```text
docker build -t martian-map:phase1 .
docker run --rm -p 127.0.0.1:7860:7860 --mount type=bind,src=<absolute-curated-data>,dst=/data,readonly martian-map:phase1
```

No data are copied into an image, pushed to a registry, or downloaded at startup.
For HF's ephemeral disk, an approved hydration mechanism/source is a phase-2
prerequisite; the mount example applies to a VM/local Docker host.

## Phase 2 approval and acceptance checklist (not executed)

- [ ] Sebas explicitly approves provider, cost, public visibility and exact data transfer.
- [ ] Confirm rights/credits and any raw-image redistribution conditions; no secrets in code/image.
- [ ] Build/smoke-test the image, GDAL radio and OR-Tools; record Linux peak memory.
- [ ] Prepare immutable kit manifest/checksums and selected E5 plan; verify photographs and 3D assets.
- [ ] Have Claude integrate public capabilities and gracefully handle blocked writes.
- [ ] Test `/`, 2D, `/3d/`, `/guide.html`, `/card.html`, voice, departure time and radio.
- [ ] Rehearse `docs/demo.md`; mark plan editing and saved walks as unavailable in fixed mode.
- [ ] Test two simultaneous browsers: neither changes the other's plan/stations; busy recovery is clear.
- [ ] Check visible credits, cold-start recovery, memory, tile egress and account spending limits.
- [ ] Only then, with approval, upload the approved data and publish/test the address.

The issue remains open until its public-address acceptance criteria are met.
