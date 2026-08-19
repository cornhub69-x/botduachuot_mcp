"""Geo Engine — coordinate extraction from structured files.

File-type dispatch for coordinate-bearing artifacts: GPX, KML, GeoJSON/JSON,
NMEA logs, drone telemetry (DJI .srt), and arbitrary text. Runs the tolerant
scanner on unstructured content. Deterministic and offline.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from app.geo.scanner import scan_text

_STRUCTURED_EXTENSIONS = {".gpx", ".kml", ".geojson", ".json", ".srt"}
_TEXT_EXTENSIONS = {".txt", ".log", ".csv", ".html", ".htm", ".xml", ".md", ".srt", ".nmea", ".nma", ".ubx"}


def _from_gpx(raw: bytes, source: str) -> list[dict[str, Any]]:
    root = ET.fromstring(raw)
    hits: list[dict[str, Any]] = []
    for tag in ("wpt", "trkpt", "rtept"):
        for node in root.iter(tag):
            lat = node.get("lat")
            lon = node.get("lon")
            if lat is None or lon is None:
                continue
            try:
                lat_f, lon_f = float(lat), float(lon)
            except ValueError:
                continue
            if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
                continue
            name = None
            name_node = node.find("name")
            if name_node is not None and name_node.text:
                name = name_node.text.strip()[:60]
            hits.append(
                {
                    "lat": round(lat_f, 7),
                    "lon": round(lon_f, 7),
                    "format": "gpx",
                    "raw": f"<{tag} lat={lat} lon={lon}>",
                    "confidence": "high",
                    "source": source,
                    "name": name,
                }
            )
    return hits


def _from_kml(raw: bytes, source: str) -> list[dict[str, Any]]:
    root = ET.fromstring(raw)
    hits: list[dict[str, Any]] = []
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}")[0] + "}"
    for coords_node in root.iter(f"{namespace}coordinates"):
        text = (coords_node.text or "").strip()
        for token in text.split():
            parts = token.split(",")
            if len(parts) < 2:
                continue
            try:
                lon, lat = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            hits.append(
                {
                    "lat": round(lat, 7),
                    "lon": round(lon, 7),
                    "format": "kml",
                    "raw": token,
                    "confidence": "high",
                    "source": source,
                }
            )
    return hits


def _from_geojson(raw: bytes, source: str) -> list[dict[str, Any]]:
    data = json.loads(raw)
    hits: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "Point" and isinstance(value.get("coordinates"), list):
                coords = value["coordinates"]
                if len(coords) >= 2:
                    lon, lat = float(coords[0]), float(coords[1])
                    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                        hits.append(
                            {
                                "lat": round(lat, 7),
                                "lon": round(lon, 7),
                                "format": "geojson_point",
                                "raw": json.dumps(value.get("coordinates")),
                                "confidence": "high",
                                "source": source,
                            }
                        )
                return
            if value.get("type") in {"LineString", "MultiPoint"} and isinstance(
                value.get("coordinates"), list
            ):
                for coords in value["coordinates"]:
                    if len(coords) >= 2:
                        lon, lat = float(coords[0]), float(coords[1])
                        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                            hits.append(
                                {
                                    "lat": round(lat, 7),
                                    "lon": round(lon, 7),
                                    "format": "geojson_line",
                                    "raw": json.dumps(coords),
                                    "confidence": "high",
                                    "source": source,
                                }
                            )
                return
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return hits


def _from_json_keys(raw: bytes, source: str) -> list[dict[str, Any]]:
    """Generic JSON: find lat/lon key pairs or [lon, lat] pairs anywhere."""
    data = json.loads(raw)
    hits: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            lat_key = next((k for k in value if k.lower() in {"lat", "latitude"}), None)
            lon_key = next((k for k in value if k.lower() in {"lon", "lng", "longitude"}), None)
            if lat_key and lon_key:
                try:
                    lat, lon = float(value[lat_key]), float(value[lon_key])
                except (TypeError, ValueError):
                    lat, lon = None, None
                if lat is not None and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                    hits.append(
                        {
                            "lat": round(lat, 7),
                            "lon": round(lon, 7),
                            "format": "json_keys",
                            "raw": json.dumps({lat_key: value[lat_key], lon_key: value[lon_key]}),
                            "confidence": "high",
                            "source": source,
                        }
                    )
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            if (
                len(value) >= 2
                and all(isinstance(item, (int, float)) for item in value[:2])
                and -180.0 <= float(value[0]) <= 180.0
                and -90.0 <= float(value[1]) <= 90.0
            ):
                hits.append(
                    {
                        "lat": round(float(value[1]), 7),
                        "lon": round(float(value[0]), 7),
                        "format": "json_lonlat",
                        "raw": json.dumps(value[:2]),
                        "confidence": "high",
                        "source": source,
                    }
                )
            for child in value:
                walk(child)

    walk(data)
    return hits


def extract_file_coordinates(path: str) -> dict[str, Any]:
    """Extract coordinates from a structured or text file."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(path)
    source = str(file_path)
    raw = file_path.read_bytes()[: 4 * 1024 * 1024]
    extension = file_path.suffix.lower()

    try:
        if extension == ".gpx":
            hits = _from_gpx(raw, source)
        elif extension == ".kml":
            hits = _from_kml(raw, source)
        elif extension == ".geojson":
            hits = _from_geojson(raw, source)
        elif extension == ".json":
            try:
                hits = _from_json_keys(raw, source)
            except json.JSONDecodeError:
                hits = []
        elif extension == ".srt":
            hits = scan_text(raw.decode("utf-8", errors="replace"), source=source)["hits"]
        else:
            hits = scan_text(raw.decode("utf-8", errors="replace"), source=source)["hits"]
    except ET.ParseError:
        hits = scan_text(raw.decode("utf-8", errors="replace"), source=source)["hits"]

    best: dict[str, Any] | None = None
    if hits:
        best = hits[0]
        best["total_candidates"] = len(hits)
    return {"ok": True, "file": source, "count": len(hits), "best": best, "hits": hits[:25]}