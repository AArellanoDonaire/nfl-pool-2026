"""
Genera docs/teams.js con nombre, división, colores y logo de los 32 equipos.

Fuentes (ESPN, sin key):
  - teams:     colores y logos
  - standings level=3: a qué división pertenece cada equipo

Se corre una vez por temporada (o cuando cambie un logo/color):
    python scripts/gen_teams.py [--season 2026]

El resultado se commitea; las páginas lo cargan con <script src="teams.js">.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from espn import parse_standings

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "teams.js"
TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=datetime.now(timezone.utc).year)
    args = ap.parse_args()

    r = requests.get(TEAMS_URL, params={"limit": 40}, timeout=30)
    r.raise_for_status()
    raw_teams = [t["team"] for t in r.json()["sports"][0]["leagues"][0]["teams"]]

    r = requests.get(STANDINGS_URL, params={"season": args.season, "level": 3}, timeout=30)
    r.raise_for_status()
    standings = parse_standings(r.json())

    teams = {}
    for t in raw_teams:
        abbr = t["abbreviation"]
        st = standings["teams"].get(abbr)
        if not st:
            print(f"{abbr} no está en standings, lo salto", file=sys.stderr)
            continue
        logo = next((l["href"] for l in t.get("logos", []) if "default" in l.get("rel", [])), None)
        teams[abbr] = {
            "name": t["displayName"],
            "short": t["shortDisplayName"],
            "conference": st["conference"],
            "division": st["division"],
            "color": "#" + t.get("color", "666666").lstrip("#"),
            "alt": "#" + t.get("alternateColor", "ffffff").lstrip("#"),
            "logo": logo or f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png",
        }
    if len(teams) != 32:
        print(f"esperaba 32 equipos, tengo {len(teams)}", file=sys.stderr)
        return 1

    teams = dict(sorted(teams.items(), key=lambda kv: (kv[1]["division"], kv[0])))
    body = json.dumps(teams, indent=2, ensure_ascii=False)
    OUT.write_text(
        f"// Generado por scripts/gen_teams.py el {datetime.now(timezone.utc):%Y-%m-%d} desde ESPN. No editar a mano.\n"
        f"window.NFL_TEAMS = {body};\n",
        encoding="utf-8",
    )
    print(f"{len(teams)} equipos -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
