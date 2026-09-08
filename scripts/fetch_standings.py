"""
Baja los standings de ESPN y escribe docs/data/standings.json (schema propio).

Uso:
    python scripts/fetch_standings.py                  # temporada del año actual
    python scripts/fetch_standings.py --season 2025
    python scripts/fetch_standings.py --out /tmp/x.json

Notas:
  - level=3 es obligatorio (agrupa por división). Ver tests/fixtures/README.md.
  - NO setear User-Agent: Akamai bloquea UAs de navegador; el default de
    requests pasa.
  - Además del parseado, guarda el crudo en docs/data/raw/standings_<fecha>.json
    para poder reconstruir cualquier semana sin volver a pegarle a la API.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from espn import EspnShapeError, parse_standings

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
URL = "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"


def fetch_raw(season: int) -> dict:
    r = requests.get(URL, params={"season": season, "level": 3}, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_week() -> int | None:
    """Semana NFL actual según ESPN (las semanas van de miércoles a miércoles,
    así que el martes es la semana recién jugada). None si falla."""
    try:
        r = requests.get(SCOREBOARD_URL, timeout=30)
        r.raise_for_status()
        d = r.json()
        if (d.get("season") or {}).get("type") != 2:  # solo temporada regular
            return None
        return int(d["week"]["number"])
    except Exception as e:  # noqa: BLE001
        print(f"no pude leer la semana del scoreboard: {e}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=datetime.now(timezone.utc).year)
    ap.add_argument("--out", type=Path, default=DATA / "standings.json")
    ap.add_argument("--no-raw", action="store_true", help="no guardar el crudo")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    raw = fetch_raw(args.season)
    try:
        standings = parse_standings(raw)
    except EspnShapeError as e:
        print(f"shape inesperado de ESPN: {e}", file=sys.stderr)
        return 1
    standings["fetched_at"] = now.isoformat(timespec="seconds")
    standings["week"] = fetch_week()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(standings, indent=2, ensure_ascii=False), encoding="utf-8")

    if not args.no_raw:
        raw_dir = args.out.parent / "raw"
        raw_dir.mkdir(exist_ok=True)
        raw_path = raw_dir / f"standings_{now:%Y-%m-%d}.json"
        raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    leaders = {
        t["division"]: abbr for abbr, t in standings["teams"].items() if t["seed"] in (1, 2, 3, 4)
    }
    print(f"season {standings['season']}  semana {standings['week']}  {len(standings['teams'])} equipos  -> {args.out}")
    print("líderes:", leaders or "(sin seeds todavía)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
