"""
Puntaje del pool. Lógica pura: recibe picks + standings (+ results opcional)
y devuelve puntajes. Sin I/O salvo en main().

Reglas (spec §4):
  división acertada        3   (x8)
  equipo en playoffs       2   (x14, el orden del seed no importa)
  campeón de conferencia   4   (x2)
  ganador del Super Bowl   5
  MVP                      3
  otros premios            2   (x6)
  máximo teórico          80

Puntaje provisional: se puntúa como si la temporada terminara hoy.
  - Líder de división = menor `seed` (>0) de la división. Si nadie tiene
    seed todavía (pretemporada), la división no reparte puntos.
  - Playoffs = seed 1..7 por conferencia.
  - Campeones / SB / premios salen de `results` (manual), 0 si no están.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POINTS = {
    "division": 3,
    "playoff": 2,
    "conf_champion": 4,
    "sb_winner": 5,
    "MVP": 3,
    "award": 2,
}
AWARDS = ("MVP", "OPOY", "DPOY", "OROY", "DROY", "CPOY", "COY")
DIVISIONS = (
    "AFC East", "AFC North", "AFC South", "AFC West",
    "NFC East", "NFC North", "NFC South", "NFC West",
)
CONFERENCES = ("AFC", "NFC")
PLAYOFF_SPOTS = 7
MAX_POINTS = (
    8 * POINTS["division"]
    + 14 * POINTS["playoff"]
    + 2 * POINTS["conf_champion"]
    + POINTS["sb_winner"]
    + POINTS["MVP"]
    + 6 * POINTS["award"]
)
assert MAX_POINTS == 80


# ---------------------------------------------------------------- estado actual


def division_leaders(standings: dict[str, Any]) -> dict[str, str | None]:
    """Líder actual de cada división según `seed`. None si nadie tiene seed."""
    by_div: dict[str, list[tuple[int, str]]] = {d: [] for d in DIVISIONS}
    for abbr, t in standings["teams"].items():
        if t["seed"] > 0:
            by_div[t["division"]].append((t["seed"], abbr))
    return {d: (min(rows)[1] if rows else None) for d, rows in by_div.items()}


def playoff_teams(standings: dict[str, Any]) -> dict[str, list[str]]:
    """Clasificados actuales (seed 1..7) por conferencia, en orden de seed."""
    out: dict[str, list[str]] = {}
    for conf in CONFERENCES:
        rows = sorted(
            (t["seed"], abbr)
            for abbr, t in standings["teams"].items()
            if t["conference"] == conf and 1 <= t["seed"] <= PLAYOFF_SPOTS
        )
        out[conf] = [abbr for _, abbr in rows]
    return out


# ---------------------------------------------------------------- puntaje


def score_player(
    picks: dict[str, Any],
    standings: dict[str, Any],
    results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Puntaje de un jugador. Devuelve total, breakdown por categoría y detalle."""
    results = results or {}
    leaders = division_leaders(standings)
    playoffs = playoff_teams(standings)

    # Divisiones
    div_detail = {}
    div_pts = 0
    for d in DIVISIONS:
        pick = picks["divisions"].get(d)
        actual = leaders[d]
        hit = actual is not None and pick == actual
        div_pts += POINTS["division"] if hit else 0
        div_detail[d] = {"pick": pick, "actual": actual, "hit": hit}

    # Playoffs (solo pertenencia, no orden)
    po_detail = {}
    po_pts = 0
    for conf in CONFERENCES:
        pick = list(picks["playoffs"].get(conf, []))
        actual = playoffs[conf]
        hits = [t for t in pick if t in actual]
        po_pts += POINTS["playoff"] * len(hits)
        po_detail[conf] = {"pick": pick, "actual": actual, "hits": hits}

    # Campeones de conferencia y Super Bowl (de results, manual)
    champ_detail = {}
    champ_pts = 0
    for key, conf in (("afc_champion", "AFC"), ("nfc_champion", "NFC")):
        pick = picks["playoffs"].get(key)
        actual = results.get(key)
        hit = actual is not None and pick == actual
        champ_pts += POINTS["conf_champion"] if hit else 0
        champ_detail[conf] = {"pick": pick, "actual": actual, "hit": hit}

    sb_pick = picks["playoffs"].get("sb_winner")
    sb_actual = results.get("sb_winner")
    sb_hit = sb_actual is not None and sb_pick == sb_actual
    sb_pts = POINTS["sb_winner"] if sb_hit else 0

    # Premios
    aw_detail = {}
    aw_pts = 0
    actual_awards = results.get("awards") or {}
    for a in AWARDS:
        pick = picks.get("awards", {}).get(a) or None
        actual = actual_awards.get(a) or None
        hit = actual is not None and pick is not None and _norm(pick) == _norm(actual)
        pts = POINTS["MVP"] if a == "MVP" else POINTS["award"]
        aw_pts += pts if hit else 0
        aw_detail[a] = {"pick": pick, "actual": actual, "hit": hit}

    breakdown = {
        "divisions": div_pts,
        "playoffs": po_pts,
        "conf_champions": champ_pts,
        "sb_winner": sb_pts,
        "awards": aw_pts,
    }
    return {
        "total": sum(breakdown.values()),
        "breakdown": breakdown,
        "details": {
            "divisions": div_detail,
            "playoffs": po_detail,
            "conf_champions": champ_detail,
            "sb_winner": {"pick": sb_pick, "actual": sb_actual, "hit": sb_hit},
            "awards": aw_detail,
        },
    }


def _norm(name: str) -> str:
    return " ".join(name.strip().lower().split())


def score_all(
    picks_file: dict[str, Any],
    standings: dict[str, Any],
    results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Puntaje de todos los jugadores de picks.json + estado actual de la liga."""
    players = {
        pid: {"display_name": p.get("display_name", pid), **score_player(p, standings, results)}
        for pid, p in picks_file["players"].items()
    }
    return {
        "season": standings.get("season"),
        "max_points": MAX_POINTS,
        "players": players,
        "current": {
            "division_leaders": division_leaders(standings),
            "playoff_teams": playoff_teams(standings),
        },
    }


# ---------------------------------------------------------------- I/O (workflow)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"


def _load(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    picks = _load(DATA / "picks.json")
    standings = _load(DATA / "standings.json")
    if picks is None or standings is None:
        print("faltan docs/data/picks.json o docs/data/standings.json", file=sys.stderr)
        return 1
    results = _load(DATA / "results.json", {})

    scores = score_all(picks, standings, results)
    scores["computed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    scores["standings_fetched_at"] = standings.get("fetched_at")
    (DATA / "scores.json").write_text(
        json.dumps(scores, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # history.json: un snapshot por corrida, para el gráfico y el delta semanal.
    history = _load(DATA / "history.json", [])
    history.append(
        {
            "computed_at": scores["computed_at"],
            "totals": {pid: p["total"] for pid, p in scores["players"].items()},
            "breakdown": {pid: p["breakdown"] for pid, p in scores["players"].items()},
            "current": scores["current"],
        }
    )
    (DATA / "history.json").write_text(
        json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    for pid, p in scores["players"].items():
        print(f"{p['display_name']:12} {p['total']:3} / {MAX_POINTS}  {p['breakdown']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
