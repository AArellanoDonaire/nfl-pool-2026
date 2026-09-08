from score import (
    MAX_POINTS,
    division_leaders,
    playoff_teams,
    score_all,
    score_player,
)

LEADERS_2025 = {
    "AFC East": "NE", "AFC North": "PIT", "AFC South": "JAX", "AFC West": "DEN",
    "NFC East": "PHI", "NFC North": "CHI", "NFC South": "CAR", "NFC West": "SEA",
}
PLAYOFFS_2025 = {
    "AFC": ["DEN", "NE", "JAX", "PIT", "HOU", "BUF", "LAC"],
    "NFC": ["SEA", "CHI", "PHI", "CAR", "LAR", "SF", "GB"],
}


def test_max_points():
    assert MAX_POINTS == 80


def test_division_leaders_2025(standings_2025):
    assert division_leaders(standings_2025) == LEADERS_2025


def test_playoff_teams_2025_in_seed_order(standings_2025):
    assert playoff_teams(standings_2025) == PLAYOFFS_2025


def test_preseason_has_no_leaders_nor_playoffs(standings_2026):
    assert all(v is None for v in division_leaders(standings_2026).values())
    assert playoff_teams(standings_2026) == {"AFC": [], "NFC": []}


def test_provisional_score_without_results(picks_2025, standings_2025):
    alfredo = score_player(picks_2025["players"]["alfredo"], standings_2025)
    assert alfredo["breakdown"] == {
        "divisions": 3,        # solo PHI
        "playoffs": 18,        # AFC: HOU BUF LAC PIT DEN (5) + NFC: PHI SF GB LAR (4)
        "conf_champions": 0,
        "sb_winner": 0,
        "awards": 0,
    }
    assert alfredo["total"] == 21
    assert alfredo["details"]["divisions"]["NFC East"] == {"pick": "PHI", "actual": "PHI", "hit": True}
    assert alfredo["details"]["divisions"]["AFC West"] == {"pick": "KC", "actual": "DEN", "hit": False}
    assert alfredo["details"]["playoffs"]["AFC"]["hits"] == ["HOU", "BUF", "LAC", "PIT", "DEN"]

    oraculo = score_player(picks_2025["players"]["oraculo"], standings_2025)
    assert oraculo["breakdown"]["divisions"] == 24
    assert oraculo["breakdown"]["playoffs"] == 28
    assert oraculo["total"] == 52


def test_seed_order_does_not_matter_for_playoffs(picks_2025, standings_2025):
    p = dict(picks_2025["players"]["oraculo"])
    p["playoffs"] = {**p["playoffs"], "AFC": list(reversed(p["playoffs"]["AFC"]))}
    assert score_player(p, standings_2025)["breakdown"]["playoffs"] == 28


def test_final_score_with_results(picks_2025, standings_2025, results_2025):
    alfredo = score_player(picks_2025["players"]["alfredo"], standings_2025, results_2025)
    assert alfredo["breakdown"]["conf_champions"] == 0
    assert alfredo["breakdown"]["sb_winner"] == 0
    assert alfredo["breakdown"]["awards"] == 2          # solo DPOY
    assert alfredo["total"] == 23

    oraculo = score_player(picks_2025["players"]["oraculo"], standings_2025, results_2025)
    assert oraculo["breakdown"]["conf_champions"] == 8
    assert oraculo["breakdown"]["sb_winner"] == 5
    assert oraculo["breakdown"]["awards"] == 3 + 2 + 2  # MVP + OPOY + DPOY
    assert oraculo["total"] == 72
    # MVP se compara sin importar mayúsculas / espacios
    assert oraculo["details"]["awards"]["MVP"]["hit"] is True
    # Un pick sin resultado anunciado no puntúa
    assert oraculo["details"]["awards"]["COY"] == {"pick": "Mike Vrabel", "actual": None, "hit": False}


def test_empty_pick_never_matches_empty_result(picks_2025, standings_2025):
    p = picks_2025["players"]["alfredo"]
    res = {"awards": {"OROY": ""}}
    assert score_player(p, standings_2025, res)["details"]["awards"]["OROY"]["hit"] is False


def test_preseason_everyone_zero(picks_2025, standings_2026):
    out = score_all(picks_2025, standings_2026)
    assert all(p["total"] == 0 for p in out["players"].values())


def test_score_all_shape(picks_2025, standings_2025, results_2025):
    out = score_all(picks_2025, standings_2025, results_2025)
    assert out["season"] == 2025
    assert out["max_points"] == 80
    assert set(out["players"]) == {"alfredo", "oraculo"}
    assert out["players"]["oraculo"]["display_name"] == "Oráculo"
    assert "color" not in out["players"]["oraculo"]


def test_color_passthrough(picks_2025, standings_2025):
    import copy
    picks = copy.deepcopy(picks_2025)
    picks["players"]["alfredo"]["color"] = "#9085e9"
    out = score_all(picks, standings_2025)
    assert out["players"]["alfredo"]["color"] == "#9085e9"
    assert out["current"]["division_leaders"] == LEADERS_2025
    assert out["current"]["playoff_teams"] == PLAYOFFS_2025


def test_main_writes_scores_and_history(tmp_path, monkeypatch, picks_2025, standings_2025):
    import json
    import score

    monkeypatch.setattr(score, "DATA", tmp_path)
    (tmp_path / "picks.json").write_text(json.dumps(picks_2025), encoding="utf-8")
    (tmp_path / "standings.json").write_text(json.dumps(standings_2025), encoding="utf-8")

    assert score.main() == 0
    scores = json.loads((tmp_path / "scores.json").read_text(encoding="utf-8"))
    assert scores["players"]["oraculo"]["total"] == 52
    assert "computed_at" in scores

    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert len(history) == 1
    assert history[0]["totals"] == {"alfredo": 21, "oraculo": 52}

    # Segunda corrida: agrega snapshot, no pisa.
    assert score.main() == 0
    history = json.loads((tmp_path / "history.json").read_text(encoding="utf-8"))
    assert len(history) == 2


def test_main_fails_without_inputs(tmp_path, monkeypatch):
    import score

    monkeypatch.setattr(score, "DATA", tmp_path)
    assert score.main() == 1
