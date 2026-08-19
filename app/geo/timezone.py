"""Geo Engine — offline timezone lookup by latitude/longitude.

Uses a compact local zone table (no network). Table rows cover the populated
world with polygon-ish lon/lat bounds; the first containing zone wins.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import app.config

# (lon_min, lon_max, lat_min, lat_max, tz_name, utc_offset_hours)
_ZONE_TABLE: list[tuple[float, float, float, float, str, float]] = [
    (-180.0, -142.0, 48.0, 72.0, "America/Adak", -10.0),
    (-142.0, -125.0, 48.0, 72.0, "America/Anchorage", -9.0),
    (-125.0, -103.0, 29.0, 50.0, "America/Los_Angeles", -8.0),
    (-103.0, -87.0, 25.0, 50.0, "America/Denver", -7.0),
    (-87.0, -76.0, 24.0, 50.0, "America/Chicago", -6.0),
    (-76.0, -52.0, 24.0, 48.0, "America/New_York", -5.0),
    (-82.0, -60.0, -55.0, 24.0, "America/Argentina/Buenos_Aires", -3.0),
    (-60.0, -35.0, -55.0, 5.0, "America/Sao_Paulo", -3.0),
    (-95.0, -80.0, -20.0, 20.0, "America/Mexico_City", -6.0),
    (-85.0, -70.0, 8.0, 24.0, "America/Panama", -5.0),
    (-78.0, -65.0, -18.0, 12.0, "America/Bogota", -5.0),
    (-168.0, -155.0, 18.0, 22.0, "Pacific/Honolulu", -10.0),
    (-62.0, -50.0, 40.0, 48.0, "America/Halifax", -4.0),
    (-52.0, -30.0, 60.0, 70.0, "America/Godthab", -3.0),
    (-30.0, 3.0, 35.0, 72.0, "Europe/London", 0.0),
    (-10.0, 15.0, 35.0, 50.0, "Europe/Paris", 1.0),
    (15.0, 30.0, 35.0, 55.0, "Europe/Berlin", 1.0),
    (20.0, 32.0, 33.0, 42.0, "Europe/Athens", 2.0),
    (12.0, 25.0, 54.0, 62.0, "Europe/Helsinki", 2.0),
    (-8.0, 0.0, 35.0, 44.0, "Europe/Madrid", 1.0),
    (7.0, 19.0, 41.0, 48.0, "Europe/Rome", 1.0),
    (30.0, 45.0, 30.0, 48.0, "Europe/Istanbul", 3.0),
    (28.0, 42.0, 48.0, 62.0, "Europe/Moscow", 3.0),
    (45.0, 65.0, 23.0, 45.0, "Asia/Tehran", 3.5),
    (60.0, 75.0, 25.0, 45.0, "Asia/Karachi", 5.0),
    (68.0, 90.0, 8.0, 38.0, "Asia/Kolkata", 5.5),
    (80.0, 100.0, 5.0, 30.0, "Asia/Bangkok", 7.0),
    (100.0, 110.0, 8.0, 25.0, "Asia/Ho_Chi_Minh", 7.0),
    (95.0, 130.0, 18.0, 40.0, "Asia/Shanghai", 8.0),
    (100.0, 120.0, -12.0, 8.0, "Asia/Jakarta", 7.0),
    (120.0, 145.0, 30.0, 50.0, "Asia/Tokyo", 9.0),
    (125.0, 135.0, 33.0, 44.0, "Asia/Seoul", 9.0),
    (115.0, 127.0, 5.0, 20.0, "Asia/Manila", 8.0),
    (90.0, 110.0, 20.0, 32.0, "Asia/Kathmandu", 5.75),
    (60.0, 75.0, 45.0, 70.0, "Asia/Yekaterinburg", 5.0),
    (75.0, 100.0, 45.0, 72.0, "Asia/Krasnoyarsk", 7.0),
    (100.0, 130.0, 45.0, 72.0, "Asia/Yakutsk", 9.0),
    (110.0, 125.0, -40.0, -10.0, "Australia/Perth", 8.0),
    (130.0, 155.0, -40.0, -10.0, "Australia/Sydney", 10.0),
    (135.0, 155.0, -45.0, -25.0, "Australia/Adelaide", 9.5),
    (160.0, 180.0, -50.0, -10.0, "Pacific/Auckland", 12.0),
    (145.0, 160.0, -55.0, -35.0, "Pacific/Noumea", 11.0),
    (-75.0, -70.0, -55.0, -30.0, "America/Santiago", -4.0),
    (-90.0, -75.0, -20.0, 0.0, "America/Lima", -5.0),
    (-70.0, -60.0, 5.0, 15.0, "America/Caracas", -4.0),
    (-90.0, -83.0, 10.0, 18.0, "America/Guatemala", -6.0),
    (15.0, 35.0, -35.0, 0.0, "Africa/Johannesburg", 2.0),
    (-20.0, 10.0, -40.0, -15.0, "Africa/Windhoek", 2.0),
    (25.0, 45.0, -30.0, 5.0, "Africa/Nairobi", 3.0),
    (-20.0, 10.0, 5.0, 35.0, "Africa/Lagos", 1.0),
    (25.0, 40.0, 5.0, 32.0, "Africa/Cairo", 2.0),
    (-10.0, -3.0, 50.0, 60.0, "Europe/Dublin", 0.0),
    (-170.0, -160.0, -20.0, 0.0, "Pacific/Tahiti", -10.0),
    (172.0, 178.0, -40.0, -35.0, "Pacific/Auckland", 12.0),
]


def _load_extra_zones() -> list[tuple[float, float, float, float, str, float]]:
    extra_path = Path(app.config.GEO_DATASETS_DIR) / "timezone_extra.csv"
    rows: list[tuple[float, float, float, float, str, float]] = []
    if extra_path.exists():
        for line in extra_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) != 6:
                continue
            try:
                rows.append(
                    (
                        float(parts[0]),
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3]),
                        parts[4],
                        float(parts[5]),
                    )
                )
            except ValueError:
                continue
    return rows


def timezone_at(lat: float, lon: float) -> dict[str, Any]:
    """Return the best-effort local timezone and UTC offset for a coordinate."""
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        raise ValueError("coordinates out of range")
    rows = _ZONE_TABLE + _load_extra_zones()
    for lon_min, lon_max, lat_min, lat_max, tz_name, offset in rows:
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            return {
                "timezone": tz_name,
                "utc_offset_hours": offset,
                "method": "offline_table",
                "note": "offline approximation; verify against GPSDateTime when available",
            }
    return {
        "timezone": None,
        "utc_offset_hours": None,
        "method": "offline_table",
        "note": "no offline zone entry for these coordinates",
    }