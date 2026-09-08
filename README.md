# NFL Pool 2026

Pool de predicciones NFL para 2 jugadores. Leaderboard estático en GitHub Pages
que se actualiza solo cada martes con los standings de ESPN.

Spec completa en [`nfl-pool-2026-spec.md`](nfl-pool-2026-spec.md).

## Cómo funciona

```
GitHub Actions (cron martes 12:00 UTC)
  → scripts/fetch_standings.py   ESPN → docs/data/standings.json (+ crudo en docs/data/raw/)
  → scripts/score.py             picks + standings (+ results) → scores.json, history.json
  → commit a main
  → GitHub Pages sirve docs/
```

Todo es estático: `docs/index.html` hace `fetch()` a los JSON del mismo origen.

## Reglas de puntaje

| Acierto | Puntos |
|---|---|
| Campeón de división (x8) | 3 |
| Lugares 2, 3 y 4 de cada división (x24) | 1 c/u |
| Equipo clasificado a playoffs (x14, el seed no importa) | 2 |
| Campeón de conferencia (x2) | 4 |
| Ganador del Super Bowl | 5 |
| MVP | 3 |
| OPOY, DPOY, OROY, DROY, CPOY, COY, ACOY, MVP del Super Bowl | 2 c/u |

Máximo teórico: **108**. La tabla vive en `AWARDS` y `POINTS` de
`scripts/score.py`; los premios también en `AWARDS` de `docs/picks.html`
(mantener ambos en sincronía).

El puntaje es provisional cada martes: se puntúa como si la temporada
terminara hoy. El orden de cada división sale del `playoffSeed` de ESPN.
Campeones, Super Bowl y premios salen de `docs/data/results.json` (manual).

## Puesta en marcha

1. **Crear el repo en GitHub** (público) y pushear `main`.
2. **Pages**: Settings → Pages → Source *Deploy from a branch*, branch `main`,
   carpeta `/docs`. No usar el modo "GitHub Actions" (ver spec §1).
3. **Picks**: abrir `docs/picks.html` (localmente o en Pages). Cada jugador
   puede llenar su pestaña por su cuenta y usar *Descargar solo este jugador*;
   el otro lo carga con *Importar JSON*. Con los dos completos, *Generar JSON*,
   descargar y commitear como `docs/data/picks.json`. Antes del kickoff.
4. **Probar el workflow**: Actions → *weekly-update* → *Run workflow*. Debería
   commitear `docs/data/standings.json` y `scores.json`. Si `picks.json` no
   existe todavía, solo commitea standings y avisa.
5. **Resultados manuales** (enero/febrero): crear `docs/data/results.json`:

   ```json
   {
     "afc_champion": "KC", "nfc_champion": "PHI", "sb_winner": "PHI",
     "awards": { "MVP": "Josh Allen", "OPOY": "", "DPOY": "", "OROY": "", "DROY": "",
                 "CPOY": "", "COY": "", "ACOY": "", "SB_MVP": "" }
   }
   ```

   Se compara por nombre sin importar mayúsculas ni espacios. Vacío = no puntúa.

6. **Telegram** (opcional): crear un bot con @BotFather, agregarlo al chat del
   pool y guardar en Settings → Secrets and variables → Actions:
   - `TG_TOKEN`: token del bot
   - `TG_CHAT`: id del chat (negativo si es grupo; se obtiene con
     `https://api.telegram.org/bot<TOKEN>/getUpdates` después de escribirle)

   Sin los secrets el workflow igual corre y solo imprime el mensaje en el log.
   Probar local: `python scripts/notify.py` (usa `docs/data/scores.json`).

## Local

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python scripts/fetch_standings.py --season 2025   # cualquier temporada
python scripts/score.py                           # necesita docs/data/picks.json
python -m http.server 8765 --directory docs       # http://localhost:8765
```

`python scripts/spike_espn.py` vuelve a bajar los fixtures crudos de ESPN.
`python scripts/gen_teams.py` regenera `docs/teams.js` (logos y colores).

## Estructura

```
docs/            sitio publicado (index.html, picks.html, teams.js, data/)
scripts/         espn.py (parser), fetch_standings.py, score.py (lógica pura), notify.py, gen_teams.py, spike_espn.py
tests/           tests + fixtures crudos de ESPN (ver tests/fixtures/README.md)
.github/         weekly.yml (cron martes), ci.yml (tests en cada push)
```

## Notas sobre ESPN

- La API no está documentada. Los hallazgos del spike están en
  [`tests/fixtures/README.md`](tests/fixtures/README.md).
- `level=3` es obligatorio para tener divisiones.
- El orden de los equipos en la respuesta **no** es el rank: se usa `playoffSeed`.
- No setear `User-Agent`: Akamai bloquea UAs de navegador, el default de
  `requests` pasa.
