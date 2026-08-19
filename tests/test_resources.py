"""Tests for the Resource Registry (app/resources.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.resources import (
    generate_resource_map,
    load_resource_map,
    resolve_resource,
)


@pytest.fixture
def fake_ctf_tools(tmp_path: Path) -> Path:
    root = tmp_path / "ctf-tools"
    (root / "skills" / "ctf-geo" / "scripts").mkdir(parents=True)
    (root / "skills" / "ctf-geo" / "SKILL.md").write_text("# geo\n", encoding="utf-8")
    (root / "skills" / "ctf-geo" / "scripts" / "geo_triage.py").write_text("print(1)\n", encoding="utf-8")
    (root / "skills" / "ctf-writeup").mkdir(parents=True)
    (root / "skills" / "ctf-writeup" / "SKILL.md").write_text("# writeup\n", encoding="utf-8")
    (root / "tools" / "RsaCtfTool").mkdir(parents=True)
    (root / "tools" / "RsaCtfTool" / "README.md").write_text("rsa\n", encoding="utf-8")
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "ctfpy").write_text("#!/bin/sh\n", encoding="utf-8")
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "CTF-KNOWLEDGE.md").write_text("notes\n", encoding="utf-8")
    return root


@pytest.fixture
def resource_map(tmp_path: Path, fake_ctf_tools: Path) -> Path:
    document = generate_resource_map(fake_ctf_tools)
    path = tmp_path / "RESOURCE_MAP.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_generate_covers_all_categories(fake_ctf_tools: Path) -> None:
    document = generate_resource_map(fake_ctf_tools)
    categories = {entry["category"] for entry in document["resources"].values()}
    assert categories == {"skill", "script", "tool", "bin", "note"}
    assert "ctf-geo" in document["resources"]
    assert "ctf-geo/geo_triage.py" in document["resources"]
    assert "RsaCtfTool" in document["resources"]
    assert "ctfpy" in document["resources"]
    assert "CTF-KNOWLEDGE" in document["resources"]


def test_resolve_existing_resource(resource_map: Path) -> None:
    entry = resolve_resource("ctf-geo", map_path=resource_map)
    assert entry["name"] == "ctf-geo"
    assert entry["category"] == "skill"
    assert entry["path"].endswith("SKILL.md")
    assert entry["invoke"].startswith("read ")
    assert entry["available"] is True
    assert "reason" not in entry


def test_resolve_missing_resource_is_blocker(resource_map: Path) -> None:
    with pytest.raises(LookupError, match="not in RESOURCE_MAP.json"):
        resolve_resource("no-such-resource", map_path=resource_map)


def test_resolve_broken_path_is_blocker(tmp_path: Path, fake_ctf_tools: Path) -> None:
    document = generate_resource_map(fake_ctf_tools)
    document["resources"]["broken"] = {
        "name": "broken",
        "category": "tool",
        "path": str(tmp_path / "does-not-exist"),
        "invoke": str(tmp_path / "does-not-exist"),
        "platform": "any",
    }
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    entry = resolve_resource("broken", map_path=path)
    assert entry["available"] is False
    assert "BLOCKER" in entry["reason"]


def test_map_validation(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"foo": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_resource_map(bad)
