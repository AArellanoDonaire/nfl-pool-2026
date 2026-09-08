import json

import pytest

from conftest import load_fixture
from notify import build_message, parse_games, pool_url
from score import score_all


@pytest.fixture(scope="session")
def games_wk18():
    return parse_games(load_fixture("scoreboard_2025_wk18.json"))


@pytest.fixture(scope="session")
def games_pre():
    return parse_games(load_fixture("scoreboard.json"))


@pytest.fixture
def scores_2025(picks_2025, standings_2025):
    s = score_all(picks_2025, standings_2025)
    s["computed_at"] = "2026-10-20T12:00:00+00:00"
    return s


def test_parse_games_completed_week(games_wk18):
    assert games_wk18["week"] == 18
    assert len(games_wk18["games"]) == 16
    g = games_wk18["games"][0]
    assert g == {"home": "TB", "away": "CAR", "home_score": 16, "away_score": 14, "winner": "TB", "final": True}
    assert all(g["final"] and g["winner"] for g in games_wk18["games"])


def test_parse_games_pregame(games_pre):
    assert games_pre["week"] == 1
    assert all(not g["final"] and g["winner"] is None for g in games_pre["games"])


def test_message_without_history(scores_2025, games_wk18):
    msg = build_message(scores_2025, [], games_wk18, "https://x.github.io/pool/")
    assert msg.startswith("\U0001F3C8 <b>NFL Pool 2025</b> · semana 18")
    # ranking: Oráculo primero con medalla, sin delta porque no hay historial
    lines = msg.splitlines()
    assert lines[2].startswith("\U0001F947 <b>Oráculo</b>: <b>52</b>  <i>div 24")
    assert lines[3].startswith("▪️ <b>Alfredo</b>: <b>21</b>  <i>div 3")
    assert "Cambios de líder" not in msg
    assert "AFC: NE · PIT · JAX · DEN" in msg
    assert "NFC: PHI · CHI · CAR · SEA" in msg
    assert "<b>Resultados</b> (16/16)" in msg
    assert "CAR 14–16 <b>TB</b>" in msg
    assert '<a href="https://x.github.io/pool/">Leaderboard</a>' in msg


def test_message_with_history_shows_delta_and_changes(scores_2025, games_wk18):
    prev_current = json.loads(json.dumps(scores_2025["current"]))
    prev_current["division_leaders"]["AFC West"] = "KC"
    prev_current["playoff_teams"]["AFC"] = ["KC", "NE", "JAX", "PIT", "HOU", "BUF", "LAC"]
    history = [
        {"computed_at": "2026-10-06T12:00:00+00:00", "totals": {"alfredo": 10, "oraculo": 40}, "current": {}},
        {"computed_at": "2026-10-13T12:00:00+00:00", "totals": {"alfredo": 19, "oraculo": 45}, "current": prev_current},
        # misma fecha que el actual: se ignora para el delta
        {"computed_at": "2026-10-20T11:00:00+00:00", "totals": {"alfredo": 21, "oraculo": 52}, "current": scores_2025["current"]},
    ]
    msg = build_message(scores_2025, history, games_wk18)
    assert "<b>Oráculo</b>: <b>52</b> (+7)" in msg
    assert "<b>Alfredo</b>: <b>21</b> (+2)" in msg
    assert "• AFC West: KC → <b>DEN</b>" in msg
    assert "• AFC: entra DEN · sale KC" in msg
    assert "Leaderboard" not in msg  # sin url


def test_message_pending_games_and_tie(scores_2025, games_pre):
    scores_2025["players"]["alfredo"]["total"] = 52
    msg = build_message(scores_2025, [], games_pre)
    assert "Empate" in msg
    assert "\U0001F947" not in msg
    assert "<b>Resultados</b> (0/16)" in msg
    assert "NE @ SEA — pendiente" in msg


def test_message_no_games(scores_2025):
    msg = build_message(scores_2025, [], None)
    assert "Resultados" not in msg
    assert "semana" not in msg.splitlines()[0]


def test_pool_url(monkeypatch):
    monkeypatch.delenv("POOL_URL", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "AArellanoDonaire/nfl-pool-2026")
    assert pool_url() == "https://aarellanodonaire.github.io/nfl-pool-2026/"
    monkeypatch.setenv("POOL_URL", "https://custom/")
    assert pool_url() == "https://custom/"
    monkeypatch.delenv("POOL_URL")
    monkeypatch.delenv("GITHUB_REPOSITORY")
    assert pool_url() is None
