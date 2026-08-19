"""Validate (and optionally extend) BotDuaChuot offline datasets.

Usage:
    python scripts/install_datasets.py            # validate local datasets
    python scripts/install_datasets.py --fetch    # download optional datasets (network)

The Geo Engine works fully offline with the bundled landmark dataset.
Optional datasets (Natural Earth cities) improve offline reverse geocoding
but require network access; keep --fetch off during a live CTF.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.config  # noqa: E402

DATASETS = ("landmarks.json",)

OPTIONAL_FETCHES = (
    {
        "name": "ne_cities_1000",
        "url": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places_simple.geojson",
        "dest": "ne_cities_simple.geojson",
        "purpose": "larger offline reverse-geocoding dataset (50k+ places)",
    },
)


def validate() -> bool:
    datasets_dir = Path(app.config.GEO_DATASETS_DIR)
    if not datasets_dir.is_dir():
        print(f"[!] datasets directory missing: {datasets_dir}")
        return False
    ok = True
    for name in DATASETS:
        path = datasets_dir / name
        if not path.is_file():
            print(f"[!] missing dataset: {name}")
            ok = False
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            count = len(data) if isinstance(data, list) else len(data.get("landmarks", []))
            print(f"[+] {name}: {count} entries")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[!] {name}: unreadable ({exc})")
            ok = False
    return ok


def fetch() -> bool:
    import urllib.request

    datasets_dir = Path(app.config.GEO_DATASETS_DIR)
    datasets_dir.mkdir(parents=True, exist_ok=True)
    ok = True
    for entry in OPTIONAL_FETCHES:
        dest = datasets_dir / entry["dest"]
        if dest.exists():
            print(f"[+] {entry['name']}: already present, skipping")
            continue
        print(f"[~] downloading {entry['name']} ...")
        try:
            with urllib.request.urlopen(entry["url"], timeout=60) as response:  # nosec B310
                dest.write_bytes(response.read())
            print(f"[+] {entry['name']}: saved to {dest}")
        except Exception as exc:  # nosec B110
            print(f"[!] {entry['name']}: download failed ({exc})")
            ok = False
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="download optional datasets (network)")
    args = parser.parse_args(argv)

    ok = validate()
    if args.fetch:
        ok = fetch() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())