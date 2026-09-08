import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def raw_2025():
    return load_fixture("standings_v2_2025_level3.json")


@pytest.fixture(scope="session")
def raw_2026():
    return load_fixture("standings_v2_2026_level3.json")


@pytest.fixture(scope="session")
def standings_2025(raw_2025):
    from espn import parse_standings
    return parse_standings(raw_2025)


@pytest.fixture(scope="session")
def standings_2026(raw_2026):
    from espn import parse_standings
    return parse_standings(raw_2026)


@pytest.fixture(scope="session")
def picks_2025():
    return load_fixture("picks_2025.json")


@pytest.fixture(scope="session")
def results_2025():
    return load_fixture("results_2025.json")
