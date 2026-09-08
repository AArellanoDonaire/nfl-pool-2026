# NFL Pool 2026 — Especificación técnica

Proyecto de predicciones NFL para 2 jugadores, con leaderboard que se
actualiza solo cada martes. Este documento es el punto de partida para
implementar en Claude Code.

---

## 1. Arquitectura

Todo vive en un repo. Sin servidores, sin cuentas externas.

```
GitHub Actions (cron martes)
   → fetch standings desde ESPN
   → calcula puntaje provisional
   → commit de docs/data/*.json a main
   → GitHub Pages sirve la carpeta docs/ (modo "Deploy from a branch")
   → curl al bot de Telegram con el resumen de la semana
```

La página es 100% estática: HTML + JS que hace `fetch()` a los JSON del
mismo origen. No hay backend.

### Configuración de GitHub Pages

- Settings → Pages → Source: **Deploy from a branch**
- Branch: `main`, carpeta: `/docs`
- El repo debe ser **público** (Pages en repos privados requiere plan pago)
- URL resultante: `https://<usuario>.github.io/<repo>/`

**No usar el modo "GitHub Actions"**: un commit hecho con el `GITHUB_TOKEN`
por defecto no dispara otros workflows, así que el deploy nunca correría
después del cron. En modo branch no hay build que disparar.

### Límites relevantes (ninguno se alcanza acá)

- Sitio hasta 1 GB, ~100 GB de bandwidth al mes
- Soft limit de 10 builds/hora — el cron usa 1 por semana
- Los workflows se desactivan tras 60 días sin actividad en el repo;
  commiteando cada martes no aplica

---

## 2. Estructura del repo

```
nfl-pool-2026/
├── docs/                        ← el sitio publicado
│   ├── index.html               ← leaderboard (lee los JSON)
│   ├── picks.html               ← captura de picks (se usa una vez)
│   └── data/
│       ├── picks.json           ← los 2 pick sheets (commit manual, 1 vez)
│       ├── standings.json       ← generado cada martes
│       └── history.json         ← snapshot semanal para el gráfico
├── scripts/
│   ├── fetch_standings.py
│   ├── score.py                 ← lógica pura, sin I/O
│   └── test_score.py
├── .github/workflows/
│   └── weekly.yml
└── README.md
```

`score.py` debe ser una función pura (recibe picks + standings, devuelve
puntajes). Así la puedes testear con fixtures sin pegarle a la API.

---

## 3. Schema de `picks.json`

Se genera una sola vez desde `picks.html` y se commitea a mano antes del
kickoff.

```json
{
  "season": 2026,
  "locked_at": "2026-09-10T00:00:00Z",
  "players": {
    "alfredo": {
      "display_name": "Alfredo",
      "divisions": {
        "AFC East": "BUF", "AFC North": "BAL",
        "AFC South": "HOU", "AFC West": "KC",
        "NFC East": "PHI", "NFC North": "DET",
        "NFC South": "TB",  "NFC West": "SF"
      },
      "playoffs": {
        "AFC": ["KC", "BAL", "HOU", "BUF", "LAC", "PIT", "DEN"],
        "NFC": ["PHI", "DET", "TB", "SF", "GB", "LAR", "MIN"],
        "afc_champion": "KC",
        "nfc_champion": "PHI",
        "sb_winner": "KC"
      },
      "awards": {
        "MVP": "", "OPOY": "", "DPOY": "",
        "OROY": "", "DROY": "", "CPOY": "", "COY": ""
      }
    },
    "amigo": { "...": "misma estructura" }
  }
}
```

Los 7 clasificados por conferencia van **en orden de seed** (1 a 7).
Usar abreviaciones de ESPN para los equipos (BUF, KC, LAR, etc.) para no
tener que mapear nada después.

---

## 4. Reglas de puntaje

### Puntos

| Acierto | Puntos |
|---|---|
| Ganador de división (×8) | 3 |
| Equipo clasificado a playoffs (×14) | 2 |
| Campeón de conferencia (×2) | 4 |
| Ganador del Super Bowl | 5 |
| MVP | 3 |
| Otros premios (OPOY, DPOY, OROY, DROY, CPOY, COY) | 2 c/u |

Máximo teórico: 24 + 28 + 8 + 5 + 3 + 12 = **80 puntos**.

### Puntaje provisional (lo que hace vivo el leaderboard)

La clave del diseño: cada martes se puntúa **como si la temporada
terminara hoy**.

- **Divisiones**: se otorga el punto al que eligió al líder actual de esa
  división. Empates en el standing → se resuelve con el mismo criterio de
  ESPN (el orden en que vienen los equipos en la respuesta ya está
  desempatado).
- **Playoffs**: se toman los 7 clasificados actuales por conferencia según
  el seeding proyectado. El orden del seed no da puntos, solo estar dentro.
- **Campeón / Super Bowl**: 0 hasta enero. Alternativa opcional: puntaje
  fraccionario según probabilidad de título, pero agrega dependencia de
  otra fuente de datos — dejarlo para después si aburre.
- **Premios**: 0 hasta febrero. Se llenan a mano en un `results.json`
  cuando se anuncian.

Esto significa que el puntaje se mueve todas las semanas y hay narrativa
("perdiste la NFC North el martes pasado"). El puntaje final del año es el
mismo cálculo corriendo sobre los standings definitivos.

---

## 5. Fuente de datos

ESPN expone endpoints públicos sin key. **No están documentados
oficialmente**, así que el primer paso en Code es un spike: pegarle,
guardar la respuesta cruda en `tests/fixtures/` y recién ahí escribir el
parser contra el shape real.

Candidatos a probar:

```
https://site.api.espn.com/apis/v2/sports/football/nfl/standings?season=2026
https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
```

El segundo sirve para el resumen semanal de resultados en el mensaje de
Telegram.

Plan B si el shape resulta incómodo: `nflverse` publica CSVs de standings
en releases de GitHub, más estables pero con más latencia de actualización.

**Guardar siempre el JSON crudo de cada semana** en `docs/data/history.json`.
Es lo que permite reconstruir el gráfico de posiciones sin volver a
consultar la API.

---

## 6. Workflow (`.github/workflows/weekly.yml`)

```yaml
name: weekly-update
on:
  schedule:
    - cron: "0 12 * * 2"   # martes 12:00 UTC = 09:00 Chile (UTC-3)
  workflow_dispatch:        # botón manual, indispensable para probar

permissions:
  contents: write           # necesario para el commit

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install requests
      - run: python scripts/fetch_standings.py
      - run: python scripts/score.py
      - name: commit
        run: |
          git config user.name "nfl-pool-bot"
          git config user.email "actions@github.com"
          git add docs/data/
          git diff --staged --quiet || git commit -m "standings week $(date +%V)"
          git push
      - name: notify
        env:
          TG_TOKEN: ${{ secrets.TG_TOKEN }}
          TG_CHAT: ${{ secrets.TG_CHAT }}
        run: python scripts/notify.py
```

Notas:

- El cron de Actions usa **siempre UTC** y puede atrasarse hasta ~1h en
  horas peak. Irrelevante acá.
- Chile está en UTC-3 durante toda la temporada NFL (sept–feb), así que
  no hay que preocuparse del cambio de horario.
- `workflow_dispatch` es obligatorio: sin eso tendrías que esperar al
  martes para probar cada cambio.
- El `git diff --staged --quiet ||` evita que falle el job cuando no hubo
  cambios.

---

## 7. Detalles de la página

- **Cache-busting obligatorio**: el CDN de Pages cachea. El fetch debe ser
  `fetch('data/standings.json?v=' + Date.now())` o vas a ver datos viejos
  y creer que el workflow falló.
- Rutas **relativas** (`data/standings.json`, no `/data/standings.json`),
  porque el sitio vive bajo `/<repo>/` y no en la raíz del dominio.
- `picks.html` genera el JSON y ofrece copiarlo/descargarlo. No necesita
  backend ni almacenamiento: se usa una vez y el resultado se commitea.
- El leaderboard se va a ver en el proyector: tipografía grande, alto
  contraste, y que quepa en una pantalla sin scroll.
- Mostrar el **delta vs. la semana anterior** por jugador. Es lo que
  genera la conversación del martes.

---

## 8. Orden de implementación sugerido

1. Spike de la API de ESPN → guardar fixture real
2. `score.py` + tests con la fixture (la lógica es lo único no trivial)
3. `picks.html` → generar los dos pick sheets y commitearlos
4. `index.html` leyendo los JSON
5. Workflow, probado con `workflow_dispatch`
6. Telegram al final (es un `curl`, no vale la pena antes)

---

## 9. Prompt inicial para Claude Code

> Lee `nfl-pool-2026-spec.md`. Vamos a implementarlo en ese orden.
> Partamos por el paso 1: escribe un script que le pegue a los endpoints
> candidatos de ESPN, me muestre la estructura de la respuesta, y guarde
> el JSON crudo como fixture. No escribas el parser todavía — quiero ver
> el shape real antes de decidir cómo modelarlo.
