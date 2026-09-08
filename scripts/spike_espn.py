"""
Spike: explora los endpoints públicos de ESPN y guarda la respuesta cruda.

No parsea nada. Solo:
  1. Pega a cada endpoint candidato.
  2. Imprime un resumen estructural (keys, tipos, largos de listas, muestras).
  3. Guarda el JSON crudo en tests/fixtures/<nombre>.json

Uso:
    python scripts/spike_espn.py                # todos los endpoints
    python scripts/spike_espn.py standings      # solo uno
    python scripts/spike_espn.py --depth 6      # más profundidad en el resumen
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

# Candidatos del spec + variantes útiles para comparar shapes.
ENDPOINTS = {
    # level=3 → agrupa conferencia → división (8 grupos de 4). Sin level solo
    # agrupa por conferencia (2 grupos de 16) y NO dice a qué división pertenece
    # cada equipo. Este es el candidato para fetch_standings.py.
    "standings_v2_2026_level3": (
        "https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
        {"season": 2026, "level": 3},
    ),
    "standings_v2_2025_level3": (
        "https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
        {"season": 2025, "level": 3},
    ),
    "standings_v2_2026": (
        "https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
        {"season": 2026},
    ),
    "standings_v2_2025": (
        # Temporada ya terminada: sirve para ver el shape con datos completos
        # (playoff seeds, clinch flags, etc.) si 2026 viene vacía.
        "https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
        {"season": 2025},
    ),
    "scoreboard": (
        # Sin params devuelve la semana "actual" según ESPN.
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        {},
    ),
    "scoreboard_2025_wk18": (
        # Semana ya jugada: para ver el shape con score final y `winner`.
        # dates=<año> + seasontype=2 (regular) + week=N selecciona la semana.
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        {"dates": 2025, "seasontype": 2, "week": 18},
    ),
}

# OJO: ESPN (Akamai) devuelve 403 con User-Agent de navegador o custom.
# El UA por defecto de requests ("python-requests/x.y") pasa. No tocar.
HEADERS: dict = {}


def fetch(url: str, params: dict) -> dict:
    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    print(f"  GET {r.url}")
    print(f"  -> {r.status_code}  {len(r.content):,} bytes  {r.headers.get('content-type')}")
    r.raise_for_status()
    return r.json()


def describe(node, indent: int = 0, depth: int = 4, list_sample: int = 1) -> None:
    """Imprime la estructura de un JSON: keys, tipos, largos. No imprime valores largos."""
    pad = "  " * indent
    if depth < 0:
        print(f"{pad}…")
        return

    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, dict):
                print(f"{pad}{k}: {{}}  ({len(v)} keys)")
                describe(v, indent + 1, depth - 1, list_sample)
            elif isinstance(v, list):
                print(f"{pad}{k}: []  (len={len(v)})")
                describe(v, indent + 1, depth - 1, list_sample)
            else:
                print(f"{pad}{k}: {_scalar(v)}")
    elif isinstance(node, list):
        if not node:
            return
        # Solo el primer elemento (asumimos homogeneidad; se valida a ojo).
        for i, item in enumerate(node[:list_sample]):
            print(f"{pad}[{i}] {type(item).__name__}")
            describe(item, indent + 1, depth - 1, list_sample)
        if len(node) > list_sample:
            print(f"{pad}… +{len(node) - list_sample} más")
    else:
        print(f"{pad}{_scalar(node)}")


def _scalar(v) -> str:
    if isinstance(v, str):
        s = v if len(v) <= 60 else v[:57] + "..."
        return f"str {s!r}"
    return f"{type(v).__name__} {v!r}"


def save_fixture(name: str, data: dict, url: str) -> Path:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    meta = FIXTURES / f"{name}.meta.json"
    meta.write_text(
        json.dumps(
            {"url": url, "fetched_at": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help=f"subset de: {', '.join(ENDPOINTS)}")
    ap.add_argument("--depth", type=int, default=4, help="profundidad del resumen")
    ap.add_argument("--no-save", action="store_true", help="no escribir fixtures")
    args = ap.parse_args()

    names = args.names or list(ENDPOINTS)
    unknown = [n for n in names if n not in ENDPOINTS]
    if unknown:
        print(f"endpoints desconocidos: {unknown}", file=sys.stderr)
        return 2

    failures = 0
    for name in names:
        url, params = ENDPOINTS[name]
        print("=" * 78)
        print(f"[{name}]")
        try:
            data = fetch(url, params)
        except Exception as e:  # noqa: BLE001 - spike, queremos ver todo
            print(f"  !! error: {e}")
            failures += 1
            continue

        print("-" * 78)
        describe(data, depth=args.depth)

        if not args.no_save:
            path = save_fixture(name, data, url)
            print("-" * 78)
            print(f"  fixture: {path.relative_to(ROOT)}")
        print()

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
