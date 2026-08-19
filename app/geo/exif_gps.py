"""Geo Engine — EXIF GPS extraction and normalization.

Parses raw GPS metadata (typically from `exiftool -json` or `exiv2 -pa`)
into a normalized WGS84 record. Pure Python: no dependency on external libs.
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404
import shutil
from typing import Any, Optional

from app.geo.convert import (
    DATUMS,
    datum_transform,
    normalize_coordinate,
    to_dms,
    to_mgrs,
    to_utm,
)

_GPS_FIELDS = {
    "GPSLatitude",
    "GPSLongitude",
    "GPSLatitudeRef",
    "GPSLongitudeRef",
    "GPSAltitude",
    "GPSAltitudeRef",
    "GPSImgDirection",
    "GPSImgDirectionRef",
    "GPSDOP",
    "GPSHPositioningError",
    "GPSDateTime",
    "GPSTimeStamp",
    "GPSDateStamp",
    "GPSAreaInformation",
    "GPSVersionID",
}


def _as_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    try:
        if "," in text and text.count(",") == 2:
            return _rational_to_float(text)
        return float(text)
    except ValueError:
        return None


def _rational_to_float(text: str) -> float:
    parts = [p.strip() for p in text.split(",")]
    value = 0.0
    for part in parts:
        if "/" in part:
            num, _, den = part.partition("/")
            value += float(num) / float(den)
        else:
            value += float(part)
    return value


def _parse_altitude(value: Any, ref: Any) -> Optional[float]:
    altitude = _as_number(value)
    if altitude is None:
        return None
    if isinstance(ref, str) and ref.strip().upper() == "1":
        altitude = -abs(altitude)
    return altitude


def parse_gps_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw GPS metadata dict into a single WGS84 record."""
    lat = _as_number(raw.get("GPSLatitude"))
    lon = _as_number(raw.get("GPSLongitude"))
    lat_ref = str(raw.get("GPSLatitudeRef") or "").strip().upper()
    lon_ref = str(raw.get("GPSLongitudeRef") or "").strip().upper()

    if lat is None or lon is None:
        raise ValueError("GPS record is missing GPSLatitude or GPSLongitude")

    lat_decimal = normalize_coordinate(lat, ref=lat_ref, axis="lat")["decimal"]
    lon_decimal = normalize_coordinate(lon, ref=lon_ref, axis="lon")["decimal"]

    altitude = _parse_altitude(raw.get("GPSAltitude"), raw.get("GPSAltitudeRef"))
    direction = _as_number(raw.get("GPSImgDirection"))
    direction_ref = str(raw.get("GPSImgDirectionRef") or "").strip().upper()
    dop = _as_number(raw.get("GPSDOP"))
    hpe = _as_number(raw.get("GPSHPositioningError"))
    date_time = str(raw.get("GPSDateTime") or "").strip() or None

    record: dict[str, Any] = {
        "lat": round(lat_decimal, 9),
        "lon": round(lon_decimal, 9),
        "datum": "WGS84",
        "altitude_m": altitude,
        "img_direction_deg": round(direction, 3) if direction is not None else None,
        "img_direction_ref": direction_ref or None,
        "dop": dop,
        "gps_hpe_m": hpe,
        "gps_datetime": date_time,
    }
    record["utm"] = to_utm(lat_decimal, lon_decimal)
    record["mgrs"] = to_mgrs(lat_decimal, lon_decimal)
    record["dms"] = {
        "lat": to_dms(lat_decimal, axis="lat"),
        "lon": to_dms(lon_decimal, axis="lon"),
    }
    return record


def extract_with_exiftool(path: str) -> dict[str, Any]:
    """Run exiftool with JSON output and extract the first GPS-bearing record."""
    exiftool = shutil.which("exiftool")
    if not exiftool:
        raise FileNotFoundError("exiftool is not available on this host")
    result = subprocess.run(  # nosec B603
        [exiftool, "-json", "-GPS*", "-n", path],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"exiftool failed: {result.stderr.strip()[:500]}")
    records = json.loads(result.stdout or "[]")
    for record in records:
        gps_keys = [key for key in _GPS_FIELDS if key in record]
        if "GPSLatitude" in record and "GPSLongitude" in record:
            return {"source": "exiftool", "path": path, "raw": record, "gps": parse_gps_record(record)}
    return {"source": "exiftool", "path": path, "raw": {}, "gps": None}


def extract_with_exiv2(path: str) -> dict[str, Any]:
    """Run exiv2 (key-value output) and extract GPS tags as fallback cross-check."""
    exiv2 = shutil.which("exiv2")
    if not exiv2:
        raise FileNotFoundError("exiv2 is not available on this host")
    result = subprocess.run(  # nosec B603
        [exiv2, "-pa", "-g", "GPS", path],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"exiv2 failed: {result.stderr.strip()[:500]}")
    raw: dict[str, Any] = {}
    for line in result.stdout.splitlines():
        match = re.match(r"^\s*([A-Za-z0-9.]+)\s+(.*)$", line)
        if match:
            raw[match.group(1)] = match.group(2).strip()
    if "GPSLatitude" not in raw or "GPSLongitude" not in raw:
        return {"source": "exiv2", "path": path, "raw": raw, "gps": None}
    return {"source": "exiv2", "path": path, "raw": raw, "gps": parse_gps_record(raw)}


def extract_cross_checked(path: str) -> dict[str, Any]:
    """Extract GPS with exiftool primary and exiv2 cross-check.

    Both sources must agree within a small tolerance; disagreement is reported
    instead of silently choosing one (evidence-first rule).
    """
    primary = extract_with_exiftool(path)
    cross = extract_with_exiv2(path)
    result = {
        "path": path,
        "primary": primary,
        "cross_check": cross,
        "gps": primary.get("gps"),
        "agreement": None,
    }
    gps_primary = primary.get("gps")
    gps_cross = cross.get("gps")
    if gps_primary and gps_cross:
        tolerance = 0.000001
        agree_lat = abs(gps_primary["lat"] - gps_cross["lat"]) < tolerance
        agree_lon = abs(gps_primary["lon"] - gps_cross["lon"]) < tolerance
        result["agreement"] = {"lat": agree_lat, "lon": agree_lon}
        if not (agree_lat and agree_lon):
            result["gps"] = None
            result["note"] = (
                "exiftool and exiv2 disagree on coordinates; refusing to pick one. "
                "Inspect raw values and datum/format handling."
            )
    return result