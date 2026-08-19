#!/usr/bin/env python3
"""Generate resources/RESOURCE_MAP.json from the host ctf-tools repository.

Usage:
    python scripts/generate_resource_map.py [--root /path/to/ctf-tools] [--output resources/RESOURCE_MAP.json]

Default root: $CTF_TOOLS_DIR or ~/ctf-tools. The script is offline and
read-only — it never executes or downloads anything from the scanned repo.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.resources import default_root, generate_resource_map  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="ctf-tools repo root")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output path (default: resources/RESOURCE_MAP.json)",
    )
    args = parser.parse_args()

    root = args.root or default_root()
    if not root.is_dir():
        print(f"error: ctf-tools root not found: {root}", file=sys.stderr)
        return 1

    output = args.output or (Path(__file__).resolve().parent.parent / "resources" / "RESOURCE_MAP.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    document = generate_resource_map(root)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(f"RESOURCE_MAP.json written: {output}")
    print(f"root: {document['root']}")
    categories = sorted({entry["category"] for entry in document["resources"].values()})
    print(f"resources: {len(document['resources'])} ({', '.join(categories)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
