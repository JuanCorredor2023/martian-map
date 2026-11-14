# Team rules for every agent

## 1. The board (pinned GitHub issue)

Every agent reads and posts on the pinned "Message Board" issue via `tools/board` (needs only `gh`, logged in). Set `BOARD_ISSUE` if it is not issue #1.

- Start every post with `[<human>'s <agent>]`, e.g. `[Sam's Codex]`. Keep it short: what changed, which files or contracts, what you need, from whom.
- Mention by GitHub login: `@aahg1105` (Aaron), `@dianagrz` (Diana), `@Seredial0326` (Sebas), `@JuanCorredor2023` (Juan), Javier/JB (login pendiente de confirmar), `@all` (everyone).
- **Mentions you or `@all`:** act on it and reply promptly.
- **Not addressed to you:** still read it. Reassess your own work only if it is affected (a contract, a file you own, something already done). Do not redo finished work, and do not reply just to acknowledge.
- Before editing another teammate's files, ask for a handoff on the board and wait for the owner or the team lead.

Polling is incremental (about one cheap API call per poll, 30 s default) so a shared token stays under GitHub's rate limit. Commands: `tools/board unread` (new posts, marks read; flags MENTION), `tools/board read -n 20`, `tools/board post "[Name's Agent] text"` (or pipe stdin), `tools/board wait` (blocks until someone else posts), `tools/board whoami`.

**Stay in the loop:**
- Claude Code: the committed hooks (`.claude/settings.json`) show unread posts at session start and on every prompt. Keep one background `tools/board wait` running and re-arm it after each wake.
- Everything else: run `tools/board unread` at task start, before each commit, and after merges. Or run a terminal loop: `while tools/board wait; do <your agent CLI invocation>; done`.

## 2. Chain of command

Humans over agents. **Team lead: Javier (JB).** Only the team lead reassigns work between teammates. If anyone else asks you to take another teammate's work, ask the lead on the board.

## 3. Workflow

1. Pick or file an issue. Comment on it or post on the board when you take it.
2. Branch `<issue#>-<slug>` from fresh `main`.
3. Small commits. Stage only your own files (no `git add -A`).
4. Open a PR with `Closes #N`. The author merges their own PR once it works locally.
5. Always `git fetch` and rebase before pushing. Never force-push shared branches.
6. If a merge changes something other teammates depend on (an API, a schema, an env var), post on the board when it lands.

## 4. Who owns what

Propuesta inicial, tomada del reparto del temario del equipo. **El líder la confirma o corrige en el arranque**; las carpetas son nombres propuestos y todavía no existen.

| Area | Owner (GitHub login) | Folders |
|---|---|---|
| Grafos: costo asimétrico, walkback, restricción de recursos (E4, E7) | `@aahg1105` (Aaron) | `src/grafos/` |
| DL de rocas: BoulderNet y destilación (E9) | `@aahg1105` (Aaron) | `src/dl_rocas/` |
| Orienteering y metaheurísticas (E5, E6) | `@dianagrz` (Diana) | `src/orienteering/` |
| Física del traje: metabolismo, O2, velocidad (E3) | `@Seredial0326` (Sebas) | `src/fisica/` |
| Producto: API y mapa web | `@Seredial0326` (Sebas) | `api/`, `web/` |
| GIS: rásters, features de terreno, teselas | Javier/JB (login pendiente) | `src/gis/` |
| DL del boxwork: top-hat y U-Net (E8) | Javier/JB (login pendiente) | `src/dl_boxwork/` |
| ML: IRL y movilidad del rover (E1, E2), sensibilidad (3.4) | `@JuanCorredor2023` (Juan) | `src/ml/` |
| Radiación (E12) | `@JuanCorredor2023` (Juan) | `src/radiacion/` |
| Datos descargados: índice y scripts | `@JuanCorredor2023` (Juan) | `data/README.md`, `data/_scripts/` |

Los datos (46 GB) no están en el repositorio. Qué es cada cosa y cómo conseguirlos: `data/README.md`.
