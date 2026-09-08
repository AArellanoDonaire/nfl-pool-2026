"""
Parser de la respuesta cruda de ESPN standings (level=3) a un schema propio.

Ver tests/fixtures/README.md para los hallazgos sobre el shape. Resumen:
  - children[] = conferencias (AFC id 8, NFC id 7)
  - children[].children[] = divisiones
  - .standings.entries[] = equipos; el ORDEN NO ES EL RANK, usar playoffSeed
  - stats[] es lista de {name, value, displayValue}; `clincher` puede faltar

Schema de salida (docs/data/standings.json):

{
  "season": 2025,
  "season_type": 2,
  "teams": {
    "NE": {
      "conference": "AFC", "division": "AFC East",
      "wins": 14, "losses": 3, "ties": 0, "record": "14-3",
      "win_pct": 0.8235, "point_diff": 170,
      "seed": 2,            # 1..16 dentro de la conferencia, 0 = sin definir
      "clincher": "z"       # "*" | "z" | "y" | "e" | null
    }, ...
  }
}
"""

from __future__ import annotations

from typing import Any

DIVISIONS = (
    "AFC East", "AFC North", "AFC South", "AFC West",
    "NFC East", "NFC North", "NFC South", "NFC West",
)
CONFERENCES = ("AFC", "NFC")


class EspnShapeError(ValueError):
    """La respuesta no tiene el shape esperado (cambió la API o falta level=3)."""


def _stats(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["name"]: s for s in entry.get("stats", [])}


def _num(stats: dict, name: str, default: float = 0.0) -> float:
    s = stats.get(name)
    if s is None or s.get("value") is None:
        return default
    return float(s["value"])


def parse_standings(raw: dict[str, Any]) -> dict[str, Any]:
    """Convierte el JSON crudo de `standings?level=3` al schema propio."""
    conferences = raw.get("children")
    if not conferences or len(conferences) != 2:
        raise EspnShapeError("esperaba 2 conferencias en children[]")

    teams: dict[str, dict[str, Any]] = {}
    season: int | None = None
    season_type: int | None = None

    for conf in conferences:
        conf_abbr = conf.get("abbreviation")
        if conf_abbr not in CONFERENCES:
            raise EspnShapeError(f"conferencia desconocida: {conf_abbr!r}")
        divisions = conf.get("children")
        if not divisions or len(divisions) != 4:
            raise EspnShapeError(
                f"{conf_abbr}: esperaba 4 divisiones en children[] (¿falta level=3?)"
            )

        for div in divisions:
            div_name = div.get("name")
            if div_name not in DIVISIONS:
                raise EspnShapeError(f"división desconocida: {div_name!r}")
            standings = div.get("standings") or {}
            season = season or standings.get("season")
            season_type = season_type or standings.get("seasonType")
            entries = standings.get("entries") or []
            if len(entries) != 4:
                raise EspnShapeError(f"{div_name}: esperaba 4 equipos, vinieron {len(entries)}")

            for entry in entries:
                abbr = entry["team"]["abbreviation"]
                st = _stats(entry)
                clincher = st.get("clincher", {}).get("displayValue") or None
                teams[abbr] = {
                    "conference": conf_abbr,
                    "division": div_name,
                    "wins": int(_num(st, "wins")),
                    "losses": int(_num(st, "losses")),
                    "ties": int(_num(st, "ties")),
                    "record": st.get("overall", {}).get("displayValue", ""),
                    "win_pct": round(_num(st, "winPercent"), 4),
                    "point_diff": int(_num(st, "pointDifferential")),
                    "seed": int(_num(st, "playoffSeed")),
                    "clincher": clincher,
                }

    if len(teams) != 32:
        raise EspnShapeError(f"esperaba 32 equipos, parseé {len(teams)}")

    return {"season": season, "season_type": season_type, "teams": teams}
