# Fixtures ESPN (spike, paso 1)

Generados con `python scripts/spike_espn.py`. Cada `<nombre>.json` es la
respuesta cruda sin tocar; `<nombre>.meta.json` guarda URL y timestamp.

| Fixture | Para qué |
|---|---|
| `standings_v2_2026_level3.json` | **Candidato para `fetch_standings.py`.** Conferencia → división → 4 equipos. Temporada 2026 antes del kickoff (todo 0-0). |
| `standings_v2_2025_level3.json` | Mismo endpoint, temporada 2025 terminada. Sirve para testear `score.py` con seeds y clinchers reales. |
| `standings_v2_2026.json` / `_2025.json` | Sin `level=3`: solo 2 grupos de 16. No dice a qué división pertenece cada equipo. Descartado. |
| `scoreboard.json` | Semana "actual" según ESPN (2026 wk1, todo `pre`). |
| `scoreboard_2025_wk18.json` | Semana jugada: trae `winner` y `score` finales. Para el resumen de Telegram. |

## Hallazgos que afectan el diseño

1. **User-Agent**: Akamai devuelve 403 a UAs de navegador o custom. El UA
   por defecto de `requests` (`python-requests/x.y`) pasa. No setear header.

2. **`level=3` es obligatorio** para tener divisiones. Sin él, el endpoint
   no expone la división de cada equipo en ningún campo.

3. **El orden de `entries` NO es el rank.** Ni a nivel conferencia ni a
   nivel división. En 2025, DEN (14-3, seed 1) aparece 4° en AFC West y
   SEA (14-3, seed 1) aparece 4° en NFC West. Lo que dice la spec
   ("el orden ya viene desempatado") es falso para este endpoint.
   **Usar el stat `playoffSeed`** (1..16 dentro de la conferencia):
   - Ganador de división = el equipo con menor `playoffSeed` de su división
     (seeds 1-4 son siempre campeones divisionales).
   - Clasificados a playoffs = `playoffSeed` en 1..7.
   - Pendiente de confirmar en temporada: si ESPN desempata `playoffSeed`
     correctamente semana a semana, o si a mitad de año viene 0 / repetido.

4. **`clincher` no existe hasta que alguien clinchea.** En 2026 el stat no
   está en la lista. Valores vistos en 2025: `*` (home field), `z` (división),
   `y` (playoffs), `e` (eliminado). El parser debe tolerar su ausencia.

5. **Stats vienen como lista, no dict.** `entries[].stats[]` con `name`,
   `value` (float), `displayValue` (str). Los records (`overall`, `Home`,
   `Road`, `vs. Div.`, `vs. Conf.`) traen `value: null`, solo `displayValue`.

6. **Abreviaciones ESPN**: WSH (no WAS), LAR, LAC, LV, JAX. Usar estas en
   `picks.json`.

7. **Scoreboard**: sin params devuelve la semana actual. Para una semana
   específica: `?dates=<año>&seasontype=2&week=N`. `competitors[].winner`
   solo aparece cuando el partido terminó (`status.type.completed: true`).

## Estructura mínima relevante (`level=3`)

```
children[]                        # 2: AFC (id 8), NFC (id 7). El NFL raíz es id 9.
  abbreviation                    # "AFC" | "NFC"
  children[]                      # 4 divisiones
    name                          # "AFC East", ...
    standings.entries[]           # 4 equipos, orden NO confiable
      team.abbreviation           # "BUF"
      team.id                     # "2"
      stats[] {name, value, displayValue}
        playoffSeed  wins  losses  ties  winPercent  clincher?  overall
```
