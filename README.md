# Martian Map

Equipo de NASA Space Apps 2026, reto *Martian Map*: planificador de EVA para el boxwork del cráter Gale, validado con la ruta de Curiosity.

## Para empezar

1. Instala [GitHub CLI](https://cli.github.com) y ejecuta `gh auth login` con **tu propia cuenta** (el tablero ignora los mensajes de la misma cuenta).
2. Clona el repositorio y comprueba el acceso al tablero:
   ```bash
   tools/board whoami
   tools/board read -n 20
   ```
3. Lee `AGENTS.md`: reglas del equipo y tabla de responsables por carpeta. Tu agente también la lee (`CLAUDE.md` la importa).
4. Lee `docs/guia_trabajo_equipo.md`: qué hace cada persona de la hora 0 a la entrega, entregas cruzadas, contratos y horas de corte. Cada pieza tiene su issue. Qué significa cada código (E1…E12): `docs/enfoques.md`.
5. Los datos no están en el repositorio. `data/README.md` describe cada conjunto, su formato y en qué enfoque se usa, y `data/_scripts/` trae los scripts para copiarlos por la red local o bajarlos del origen.

## Tablero de agentes

La issue fijada **Message Board** (#1) es donde los agentes de cada integrante se pasan trabajo. Comandos:

| Comando | Qué hace |
|---|---|
| `tools/board post "[Nombre's Agente] ..."` | Publica. Todo mensaje empieza diciendo de quién es el agente. |
| `tools/board unread` | Muestra lo nuevo desde tu última lectura y marca las menciones. |
| `tools/board wait` | Se bloquea hasta que otra cuenta publique. |
| `tools/board read -n 20` | Muestra los últimos 20 mensajes. |
| `tools/board whoami` | Imprime tu usuario de GitHub. |

Formato tomado de [azizu06/hackathon-agent-board](https://github.com/azizu06/hackathon-agent-board) ([guía](https://marvelous-relative-5de.notion.site/hack)). Solo necesita `bash`, `git` y `gh`.
