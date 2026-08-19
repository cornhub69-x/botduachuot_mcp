"""Geo Engine — tolerant coordinate scanner for arbitrary text.

Finds and normalizes coordinates embedded in chat logs, HTML, JSON, GPX/KML
text, NMEA sentences, drone telemetry (DJI .srt), MGRS/UTM grids, and
labelled or bare decimal pairs. Deterministic and offline; every hit reports
its format, raw fragment, surrounding context, and a confidence level.
"""

from __future__ import annotations

import re
from typing import Any

from app.geo.convert import from_mgrs, from_utm, parse_dms

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_HEMI_LABEL = r"(?P<hemi>[NSEWnsew])"
_DD = r"(?P<dd>\d{1,3})"
_DM = r"(?P<dm>\d{1,2}(?:\.\d+)?)"
_DS = r"(?P<ds>\d{1,2}(?:\.\d+)?)"
_DEC = r"(?P<dec>-?\d{1,3}\.\d+)"

_DMS_VALUE = rf"{_DD}\s*(?:°|º|d)\s*(?:{_DM}\s*(?:'|′|’|m))?\s*(?:{_DS}\s*(?:\"|″|”|s))?\s*{_HEMI_LABEL}?"
_DM_VALUE = rf"{_DD}\s*(?:°|º|d)\s*{_DM}\s*(?:'|′|’)\s*{_HEMI_LABEL}?"

# One coordinate value with optional hemisphere; we pair two of them when
# found on the same line, otherwise accept a single labeled value.
_DMS_RE = re.compile(_DMS_VALUE, re.IGNORECASE)
_DM_RE = re.compile(_DM_VALUE, re.IGNORECASE)

_LABELED_RE = re.compile(
    rf"\b(?P<axis>lat(?:itude)?|lon(?:gitude)?)\s*[\"']?\s*[:=]?\s*"
    rf"(?P<value>{_DD}\s*(?:°|º|d)\s*(?:{_DM}\s*(?:'|′|’|m))?\s*"
    rf"(?:{_DS}\s*(?:\"|″|”|s))?\s*{_HEMI_LABEL}?|-?\d{{1,3}}(?:\.\d+)?)",
    re.IGNORECASE,
)

_DECIMAL_PAIR_RE = re.compile(
    r"\b(?P<dec1>-?\d{1,3}\.\d+)\s*[,;]\s*(?P<dec2>-?\d{1,3}\.\d+)\b"
)

_NMEA_LAT_RE = re.compile(r"\b(\d{2,4}(?:\.\d+)?),([NS])\b")
_NMEA_LON_RE = re.compile(r"\b(\d{3,5}(?:\.\d+)?),([EW])\b")
_NMEA_SENTENCE_RE = re.compile(r"\$G[PNR]?[GAMR]?(?:GGA|RMC|GLL|WPL)\b")

_UTM_RE = re.compile(
    r"\bUTM\s*(?:zone\s*)?(?P<zone>\d{1,2})(?P<band>[C-X])\s+"
    r"(?P<east>\d{5,7})\s+(?P<north>\d{5,7})\b",
    re.IGNORECASE,
)

_MGRS_RE = re.compile(
    r"\b(?P<zone>\d{1,2})(?P<band>[C-HJ-NP-Xc-hj-np-x])"
    r"\s*(?P<sq1>[A-Za-z])(?P<sq2>[A-Za-z])"
    r"\s*(?P<east>\d{3,7})\s*(?P<north>\d{3,7})\b"
)


def _parse_dms_value(match: re.Match[str]) -> float | None:
    try:
        deg = float(match.group("dd"))
        minute = float(match.group("dm") or 0.0)
        second = float(match.group("ds") or 0.0)
        hemi = (match.group("hemi") or "").upper()
        if minute >= 60.0 or second >= 60.0:
            return None
        value = deg + minute / 60.0 + second / 3600.0
        if hemi in {"S", "W"}:
            value = -value
        return value
    except (TypeError, ValueError):
        return None


def _nmea_to_decimal(raw: str, hemi: str) -> float:
    """Convert ddmm.mmmm / dddmm.mmmm NMEA fields to decimal degrees."""
    degrees_digits = 2 if hemi in {"N", "S"} else 3
    degrees = float(raw[:degrees_digits])
    minutes = float(raw[degrees_digits:])
    value = degrees + minutes / 60.0
    return -value if hemi in {"S", "W"} else value


def _in_range(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _context(text: str, start: int, end: int, radius: int = 40) -> str:
    snippet = text[max(0, start - radius): end + radius]
    return " ".join(snippet.split())


def scan_text(text: str, source: str = "") -> dict[str, Any]:
    """Scan arbitrary text for coordinates; return normalized hits."""
    if not isinstance(text, str) or not text.strip():
        return {"ok": True, "source": source, "count": 0, "hits": []}
    hits: list[dict[str, Any]] = []
    lines = text.splitlines()

    for line_index, line in enumerate(lines):
        # --- NMEA sentences (GGA/RMC/GLL/WPL): lat,hemi lon,hemi ---
        if _NMEA_SENTENCE_RE.search(line):
            lat_m = _NMEA_LAT_RE.search(line)
            lon_m = _NMEA_LON_RE.search(line)
            if lat_m and lon_m:
                lat = _nmea_to_decimal(lat_m.group(1), lat_m.group(2).upper())
                lon = _nmea_to_decimal(lon_m.group(1), lon_m.group(2).upper())
                if _in_range(lat, lon):
                    hits.append(
                        {
                            "lat": round(lat, 7),
                            "lon": round(lon, 7),
                            "format": "nmea",
                            "raw": line.strip()[:120],
                            "line": line_index + 1,
                            "confidence": "high",
                            "source": source,
                        }
                    )
                continue

        # --- MGRS grid reference ---
        for mgrs_match in _MGRS_RE.finditer(line):
            value = re.sub(r"\s+", "", mgrs_match.group(0))
            try:
                converted = from_mgrs(value)
            except Exception:
                continue
            hits.append(
                {
                    "lat": round(float(converted["lat"]), 7),
                    "lon": round(float(converted["lon"]), 7),
                    "format": "mgrs",
                    "raw": value,
                    "line": line_index + 1,
                    "confidence": "high",
                    "source": source,
                }
            )

        # --- UTM zone+band with easting/northing ---
        for utm_match in _UTM_RE.finditer(line):
            try:
                converted = from_utm(
                    int(utm_match.group("zone")),
                    "N" if utm_match.group("band").isupper() else "S",
                    float(utm_match.group("east")),
                    float(utm_match.group("north")),
                )
            except Exception:
                continue
            hits.append(
                {
                    "lat": round(float(converted["lat"]), 7),
                    "lon": round(float(converted["lon"]), 7),
                    "format": "utm",
                    "raw": utm_match.group(0).strip(),
                    "line": line_index + 1,
                    "confidence": "high",
                    "source": source,
                }
            )

        # --- Labelled lat/lon values ---
        labeled: dict[str, float] = {}
        for label_match in _LABELED_RE.finditer(line):
            axis = "lat" if label_match.group("axis").lower().startswith("lat") else "lon"
            raw_value = label_match.group("value").strip()
            if raw_value.startswith(("lat", "lon")):
                continue
            try:
                value = parse_dms(raw_value)
            except ValueError:
                try:
                    value = float(raw_value)
                except ValueError:
                    continue
            if not -180.0 <= value <= 180.0:
                continue
            if axis.startswith("lat") and not -90.0 <= value <= 90.0:
                continue
            labeled[axis] = value
            labeled[f"{axis}_raw"] = raw_value  # type: ignore[assignment]
        if labeled.get("lat") is not None and labeled.get("lon") is not None:
            hits.append(
                {
                    "lat": round(labeled["lat"], 7),
                    "lon": round(labeled["lon"], 7),
                    "format": "labelled",
                    "raw": labeled.get("lat_raw"),
                    "line": line_index + 1,
                    "confidence": "high",
                    "source": source,
                }
            )

        # --- DMS/DM values with hemisphere letters ---
        dms_values: dict[str, float] = {}
        for dms_match in _DMS_RE.finditer(line):
            value = _parse_dms_value(dms_match)
            if value is None:
                continue
            hemi = (dms_match.group("hemi") or "").upper()
            if hemi in {"N", "S"} and -90.0 <= value <= 90.0:
                dms_values.setdefault("lat", value)
            elif hemi in {"E", "W"} and -180.0 <= value <= 180.0:
                dms_values.setdefault("lon", value)
            elif not hemi and value in dms_values.values():
                continue
        if dms_values.get("lat") is not None and dms_values.get("lon") is not None:
            hits.append(
                {
                    "lat": round(dms_values["lat"], 7),
                    "lon": round(dms_values["lon"], 7),
                    "format": "dms",
                    "raw": line.strip()[:120],
                    "line": line_index + 1,
                    "confidence": "high",
                    "source": source,
                }
            )

        # --- Bare decimal pairs (lat, lon) ---
        for pair_match in _DECIMAL_PAIR_RE.finditer(line):
            first, second = float(pair_match.group("dec1")), float(pair_match.group("dec2"))
            lat, lon = None, None
            if -90.0 <= first <= 90.0 and -180.0 <= second <= 180.0:
                lat, lon = first, second
            elif -180.0 <= first <= 180.0 and -90.0 <= second <= 90.0:
                lat, lon = second, first
            if lat is None:
                continue
            hits.append(
                {
                    "lat": round(lat, 7),
                    "lon": round(lon, 7),
                    "format": "decimal_pair",
                    "raw": pair_match.group(0).strip(),
                    "line": line_index + 1,
                    "confidence": "medium",
                    "source": source,
                }
            )

    # De-duplicate: same rounded coordinate within the same line.
    unique: list[dict[str, Any]] = []
    seen: set[tuple[float, float, int]] = set()
    for hit in hits:
        key = (hit["lat"], hit["lon"], hit["line"])
        if key in seen:
            continue
        seen.add(key)
        hit["context"] = _context(lines[hit["line"] - 1], 0, len(lines[hit["line"] - 1]))
        unique.append(hit)

    order = {"high": 0, "medium": 1, "low": 2}
    unique.sort(key=lambda item: (order.get(item["confidence"], 3), item["line"]))
    return {"ok": True, "source": source, "count": len(unique), "hits": unique[:25]}