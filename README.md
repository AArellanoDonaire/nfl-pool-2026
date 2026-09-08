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

## Puesta en marcha

1. **Crear el repo en GitHub** (público) y pushear `main`.
2. **Pages**: Settings → Pages → Source *Deploy from a branch*, branch `main`,
   carpeta `/docs`. No usar el modo "GitHub Actions" (ver spec §1).
3. **Picks**: abrir `docs/picks.html` (localmente o en Pages), llenar los dos
   jugadores, *Generar JSON*, descargar y commitear como `docs/data/picks.json`.
   Hay que hacerlo antes del kickoff.
4. **Probar el workflow**: Actions → *weekly-update* → *Run workflow*. Debería
   commitear `docs/data/standings.json` y `scores.json`. Si `picks.json` no
   existe todavía, solo commitea standings y avisa.
5. **Resultados manuales** (enero/febrero): crear `docs/data/results.json`:

   ```json
   {
     "afc_champion": "KC", "nfc_champion": "PHI", "sb_winner": "PHI",
     "awards": { "MVP": "Josh Allen", "OPOY": "", "DPOY": "", "OROY": "", "DROY": "", "CPOY": "", "COY": "" }
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

## Estructura

```
docs/            sitio publicado (index.html, picks.html, data/)
scripts/         espn.py (parser), fetch_standings.py, score.py (lógica pura), notify.py, spike_espn.py
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
