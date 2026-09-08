import copy

import pytest

from espn import DIVISIONS, EspnShapeError, parse_standings


def test_parses_32_teams_in_8_divisions(standings_2025):
    teams = standings_2025["teams"]
    assert len(teams) == 32
    assert standings_2025["season"] == 2025
    assert standings_2025["season_type"] == 2
    for d in DIVISIONS:
        assert sum(1 for t in teams.values() if t["division"] == d) == 4
    assert sum(1 for t in teams.values() if t["conference"] == "AFC") == 16


def test_team_fields_2025(standings_2025):
    ne = standings_2025["teams"]["NE"]
    assert ne == {
        "conference": "AFC",
        "division": "AFC East",
        "wins": 14, "losses": 3, "ties": 0, "record": "14-3",
        "win_pct": 0.8235,
        "point_diff": 170,
        "seed": 2,
        "clincher": "z",
    }
    # Seed 1 aparece último en su división en el crudo: el orden no importa.
    assert standings_2025["teams"]["DEN"]["seed"] == 1
    assert standings_2025["teams"]["DEN"]["clincher"] == "*"
    assert standings_2025["teams"]["DAL"]["record"] == "7-9-1"
    assert standings_2025["teams"]["DAL"]["ties"] == 1


def test_seeds_are_1_to_16_per_conference(standings_2025):
    for conf in ("AFC", "NFC"):
        seeds = sorted(t["seed"] for t in standings_2025["teams"].values() if t["conference"] == conf)
        assert seeds == list(range(1, 17))


def test_preseason_2026_has_no_seed_nor_clincher(standings_2026):
    teams = standings_2026["teams"]
    assert len(teams) == 32
    assert standings_2026["season"] == 2026
    assert all(t["seed"] == 0 for t in teams.values())
    assert all(t["clincher"] is None for t in teams.values())
    assert all(t["record"] == "0-0" for t in teams.values())


def test_espn_abbreviations_present(standings_2026):
    for abbr in ("WSH", "LAR", "LAC", "LV", "JAX", "KC", "SF", "TB"):
        assert abbr in standings_2026["teams"]


def test_rejects_conference_only_shape(raw_2025):
    # Sin level=3 no hay children[] dentro de cada conferencia.
    flat = copy.deepcopy(raw_2025)
    for conf in flat["children"]:
        conf.pop("children")
        conf["standings"] = {"entries": []}
    with pytest.raises(EspnShapeError):
        parse_standings(flat)


def test_rejects_missing_team(raw_2025):
    broken = copy.deepcopy(raw_2025)
    broken["children"][0]["children"][0]["standings"]["entries"].pop()
    with pytest.raises(EspnShapeError):
        parse_standings(broken)
