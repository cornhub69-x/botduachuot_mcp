"""Geo Engine — offline reverse geocoding against a local landmark dataset."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import app.config
from app.geo.geodesic import vincenty_inverse

_default_dataset_path = app.config.GEO_DATASETS_DIR / "landmarks.json"


def load_landmarks(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load the offline landmark dataset (deterministic, no network)."""
    dataset_path = Path(path or _default_dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"landmark dataset not found: {dataset_path}. "
            "Install with scripts/install_datasets.py or provide --dataset."
        )
    with open(dataset_path, encoding="utf-8") as handle:
        data = json.load(handle)
    landmarks = data if isinstance(data, list) else data.get("landmarks", [])
    return [entry for entry in landmarks if "lat" in entry and "lon" in entry]


def nearest_landmarks(
    lat: float,
    lon: float,
    *,
    dataset: Path | str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return the nearest landmarks with geodesic distance and bearing."""
    max_matches = limit or app.config.GEO_MAX_LANDMARK_MATCHES
    matches: list[dict[str, Any]] = []
    for entry in load_landmarks(dataset):
        geo = vincenty_inverse(lat, lon, float(entry["lat"]), float(entry["lon"]))
        matches.append(
            {
                "name": entry.get("name"),
                "country": entry.get("country"),
                "category": entry.get("category"),
                "lat": entry["lat"],
                "lon": entry["lon"],
                "distance_m": geo["distance_m"],
                "bearing_deg": geo["azimuth1_deg"],
                "method": geo["method"],
            }
        )
    matches.sort(key=lambda item: item["distance_m"])
    return matches[:max_matches]


def is_within(
    lat: float, lon: float, landmark: dict[str, Any], radius_m: float
) -> dict[str, Any]:
    """Check whether a coordinate falls within a radius of a landmark."""
    geo = vincenty_inverse(lat, lon, float(landmark["lat"]), float(landmark["lon"]))
    return {
        "inside": geo["distance_m"] <= radius_m,
        "distance_m": round(geo["distance_m"], 3),
        "landmark": landmark.get("name"),
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Quick haversine distance (km) for coarse checks."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    )
    return 2.0 * 6371.0 * math.asin(math.sqrt(a))