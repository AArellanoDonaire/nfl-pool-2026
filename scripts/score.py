"""
Puntaje del pool. Lógica pura: recibe picks + standings (+ results opcional)
y devuelve puntajes. Sin I/O salvo en main().

Reglas (spec §4, ampliadas):
  campeón de división      3   (x8)
  lugares 2, 3 y 4 de la división   1 c/u  (x24)
  equipo en playoffs       2   (x14, el orden del seed no importa)
  campeón de conferencia   4   (x2)
  ganador del Super Bowl   5
  MVP                      3
  otros premios            2   (ver AWARDS)
  máximo teórico           MAX_POINTS (se calcula)

Puntaje provisional: se puntúa como si la temporada terminara hoy.
  - Orden de la división = por `seed` ascendente (ESPN da seed 1..16 dentro
    de la conferencia, así que ordena a los 4). Si alguien no tiene seed
    (pretemporada), la división no reparte puntos.
  - `picks.divisions[d]` es una lista de 4 en orden; el primero es el campeón.
    Por compatibilidad se acepta un string (solo campeón).
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
    "division": 3,      # campeón (lugar 1)
    "division_place": 1,  # lugares 2, 3 y 4
    "playoff": 2,
    "conf_champion": 4,
    "sb_winner": 5,
}
# Premios y puntos. Mantener en sincronía con AWARDS en docs/picks.html.
AWARDS = {
    "MVP": 3,
    "OPOY": 2,   # Offensive Player of the Year
    "DPOY": 2,   # Defensive Player of the Year
    "OROY": 2,   # Offensive Rookie of the Year
    "DROY": 2,   # Defensive Rookie of the Year
    "CPOY": 2,   # Comeback Player of the Year
    "COY": 2,    # Coach of the Year
    "ACOY": 2,   # Assistant Coach of the Year
    "SB_MVP": 2, # MVP del Super Bowl
}
DIVISIONS = (
    "AFC East", "AFC North", "AFC South", "AFC West",
    "NFC East", "NFC North", "NFC South", "NFC West",
)
CONFERENCES = ("AFC", "NFC")
PLAYOFF_SPOTS = 7
MAX_POINTS = (
    8 * (POINTS["division"] + 3 * POINTS["division_place"])
    + 14 * POINTS["playoff"]
    + 2 * POINTS["conf_champion"]
    + POINTS["sb_winner"]
    + sum(AWARDS.values())
)


# ---------------------------------------------------------------- estado actual


def division_order(standings: dict[str, Any]) -> dict[str, list[str] | None]:
    """Orden actual (1 a 4) de cada división por `seed`. None si falta algún seed."""
    by_div: dict[str, list[tuple[int, str]]] = {d: [] for d in DIVISIONS}
    for abbr, t in standings["teams"].items():
        by_div[t["division"]].append((t["seed"], abbr))
    out: dict[str, list[str] | None] = {}
    for d, rows in by_div.items():
        if len(rows) == 4 and all(seed > 0 for seed, _ in rows):
            out[d] = [abbr for _, abbr in sorted(rows)]
        else:
            out[d] = None
    return out


def division_leaders(standings: dict[str, Any]) -> dict[str, str | None]:
    """Líder actual de cada división (primero del orden). None si no hay seeds."""
    return {d: (order[0] if order else None) for d, order in division_order(standings).items()}


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
    orders = division_order(standings)
    playoffs = playoff_teams(standings)

    # Divisiones: lugar 1 vale POINTS["division"], lugares 2-4 POINTS["division_place"]
    div_detail = {}
    div_pts = 0
    for d in DIVISIONS:
        raw = picks["divisions"].get(d)
        pick = list(raw) if isinstance(raw, list) else ([raw] if raw else [])
        actual = orders[d]
        hits = [actual is not None and k < len(actual) and t == actual[k] for k, t in enumerate(pick)]
        pts = sum(
            (POINTS["division"] if k == 0 else POINTS["division_place"]) if h else 0
            for k, h in enumerate(hits)
        )
        div_pts += pts
        div_detail[d] = {"pick": pick, "actual": actual, "hits": hits, "points": pts}

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
    for a, pts in AWARDS.items():
        pick = picks.get("awards", {}).get(a) or None
        actual = actual_awards.get(a) or None
        hit = actual is not None and pick is not None and _norm(pick) == _norm(actual)
        aw_pts += pts if hit else 0
        aw_detail[a] = {"pick": pick, "actual": actual, "hit": hit, "points": pts if hit else 0}

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
    players = {}
    for pid, p in picks_file["players"].items():
        entry = {"display_name": p.get("display_name", pid)}
        if p.get("color"):
            entry["color"] = p["color"]  # opcional, hex; lo usa index.html
        entry.update(score_player(p, standings, results))
        players[pid] = entry
    return {
        "season": standings.get("season"),
        "week": standings.get("week"),
        "max_points": MAX_POINTS,
        "players": players,
        "current": {
            "division_leaders": division_leaders(standings),
            "division_order": division_order(standings),
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
            "week": scores.get("week"),
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
