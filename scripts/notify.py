"""
Resumen semanal por Telegram.

Lee docs/data/scores.json + history.json, baja el scoreboard de la semana
(ESPN: las semanas van de miércoles 07:00Z a miércoles 06:59Z, así que el
martes el scoreboard sin parámetros es la semana recién jugada) y manda un
mensaje al chat del pool.

Env:
  TG_TOKEN   token del bot (BotFather)
  TG_CHAT    chat id (número; negativo si es grupo)
  POOL_URL   opcional; si no, se arma desde GITHUB_REPOSITORY

Sin TG_TOKEN/TG_CHAT imprime el mensaje y termina en 0 (para probar local y
para que el workflow no falle antes de configurar los secrets).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
DIVISIONS = (
    "AFC East", "AFC North", "AFC South", "AFC West",
    "NFC East", "NFC North", "NFC South", "NFC West",
)


# ---------------------------------------------------------------- scoreboard


def parse_games(scoreboard: dict[str, Any]) -> dict[str, Any]:
    """Resultados de la semana: [{home, away, home_score, away_score, winner, final}]."""
    games = []
    for ev in scoreboard.get("events", []):
        comp = ev["competitions"][0]
        home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
        away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
        final = bool(ev["status"]["type"].get("completed"))
        winner = None
        if final:
            if home.get("winner"):
                winner = home["team"]["abbreviation"]
            elif away.get("winner"):
                winner = away["team"]["abbreviation"]
        games.append(
            {
                "home": home["team"]["abbreviation"],
                "away": away["team"]["abbreviation"],
                "home_score": int(home.get("score") or 0),
                "away_score": int(away.get("score") or 0),
                "winner": winner,
                "final": final,
            }
        )
    return {"week": (scoreboard.get("week") or {}).get("number"), "games": games}


# ---------------------------------------------------------------- mensaje


def _prev_snapshot(history: list[dict], current_day: str) -> dict | None:
    prev = [h for h in history if (h.get("computed_at") or "")[:10] < current_day]
    return prev[-1] if prev else None


def _fmt_delta(d: int | None) -> str:
    if d is None:
        return ""
    return f" ({'+' if d > 0 else ''}{d})" if d else " (=)"


def _breakdown(p: dict[str, Any]) -> str:
    """'div 12 (1 campeón · 9 lugares) · playoffs 18 · conf 4 · SB 5 · premios 3'."""
    bd = p["breakdown"]
    divs = (p.get("details") or {}).get("divisions") or {}
    n_champ = sum(1 for d in divs.values() if (d.get("hits") or [False])[0])
    places = sum(sum(1 for h in (d.get("hits") or [])[1:] if h) for d in divs.values())
    champ_txt = "1 campeón" if n_champ == 1 else f"{n_champ} campeones"
    place_txt = "1 lugar" if places == 1 else f"{places} lugares"
    parts = [f"div {bd['divisions']} ({champ_txt} · {place_txt})", f"playoffs {bd['playoffs']}"]
    for key, name in (("conf_champions", "conf"), ("sb_winner", "SB"), ("awards", "premios")):
        if bd.get(key):
            parts.append(f"{name} {bd[key]}")
    return " · ".join(parts)


def build_message(
    scores: dict[str, Any],
    history: list[dict],
    games: dict[str, Any] | None = None,
    url: str | None = None,
) -> str:
    """Texto del mensaje (HTML de Telegram). Función pura."""
    day = (scores.get("computed_at") or "")[:10]
    prev = _prev_snapshot(history, day)
    week = (games or {}).get("week")
    title = f"\U0001F3C8 <b>NFL Pool {scores.get('season', '')}</b>"
    if week:
        title += f" · semana {week}"
    lines = [title, ""]

    # Tabla de posiciones
    ranked = sorted(scores["players"].items(), key=lambda kv: -kv[1]["total"])
    tied = len(ranked) > 1 and ranked[0][1]["total"] == ranked[1][1]["total"]
    for pos, (pid, p) in enumerate(ranked, 1):
        delta = p["total"] - prev["totals"][pid] if prev and pid in prev.get("totals", {}) else None
        medal = "\U0001F947" if pos == 1 and not tied else "▪️"
        lines.append(
            f"{medal} <b>{p['display_name']}</b>: <b>{p['total']}</b>{_fmt_delta(delta)}"
            f"  <i>{_breakdown(p)}</i>"
        )
    if tied:
        lines.append("Empate \U0001F91D")

    # Cambios vs. la semana pasada
    cur_leaders = scores["current"]["division_leaders"]
    if prev and prev.get("current"):
        old_leaders = prev["current"].get("division_leaders", {})
        changes = [
            f"• {d}: {old_leaders.get(d) or '—'} → <b>{cur_leaders.get(d) or '—'}</b>"
            for d in DIVISIONS
            if old_leaders.get(d) != cur_leaders.get(d)
        ]
        if changes:
            lines += ["", "<b>Cambios de líder</b>"] + changes

        old_po = prev["current"].get("playoff_teams", {})
        cur_po = scores["current"]["playoff_teams"]
        moves = []
        for conf in ("AFC", "NFC"):
            entered = [t for t in cur_po.get(conf, []) if t not in old_po.get(conf, [])]
            left = [t for t in old_po.get(conf, []) if t not in cur_po.get(conf, [])]
            if entered or left:
                parts = []
                if entered:
                    parts.append(f"entra {', '.join(entered)}")
                if left:
                    parts.append(f"sale {', '.join(left)}")
                moves.append(f"• {conf}: {' · '.join(parts)}")
        if moves:
            lines += ["", "<b>Playoffs</b>"] + moves

    # Líderes actuales (compacto)
    lines += ["", "<b>Líderes</b>"]
    for conf in ("AFC", "NFC"):
        parts = [cur_leaders.get(d) or "—" for d in DIVISIONS if d.startswith(conf)]
        lines.append(f"{conf}: {' · '.join(parts)}")

    # Resultados de la semana
    if games and games.get("games"):
        finals = [g for g in games["games"] if g["final"]]
        lines += ["", f"<b>Resultados</b> ({len(finals)}/{len(games['games'])})"]
        for g in games["games"]:
            if not g["final"]:
                lines.append(f"{g['away']} @ {g['home']} — pendiente")
                continue
            a = f"<b>{g['away']}</b>" if g["winner"] == g["away"] else g["away"]
            h = f"<b>{g['home']}</b>" if g["winner"] == g["home"] else g["home"]
            lines.append(f"{a} {g['away_score']}–{g['home_score']} {h}")

    if url:
        lines += ["", f'<a href="{url}">Leaderboard</a>']
    return "\n".join(lines)


# ---------------------------------------------------------------- I/O


def pool_url() -> str | None:
    if os.environ.get("POOL_URL"):
        return os.environ["POOL_URL"]
    repo = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo"
    if repo and "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner.lower()}.github.io/{name}/"
    return None


def send(token: str, chat: str, text: str) -> None:
    r = requests.post(
        TELEGRAM_URL.format(token=token),
        json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=30,
    )
    if not r.ok:
        print(f"telegram {r.status_code}: {r.text[:300]}", file=sys.stderr)
    r.raise_for_status()


def main() -> int:
    scores_path = DATA / "scores.json"
    if not scores_path.exists():
        print("no hay docs/data/scores.json, nada que avisar")
        return 0
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    hist_path = DATA / "history.json"
    history = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else []

    games = None
    try:
        r = requests.get(SCOREBOARD_URL, timeout=30)
        r.raise_for_status()
        games = parse_games(r.json())
    except Exception as e:  # noqa: BLE001 - el resumen de resultados es opcional
        print(f"scoreboard no disponible: {e}", file=sys.stderr)

    text = build_message(scores, history, games, pool_url())

    token, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not token or not chat:
        print("TG_TOKEN/TG_CHAT no configurados; mensaje que se habría enviado:\n")
        print(text)
        return 0
    send(token, chat, text)
    print(f"enviado a {chat} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
