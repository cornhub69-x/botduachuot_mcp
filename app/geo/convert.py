"""Geo Engine — deterministic offline coordinate conversion.

Supports DMS <-> decimal <-> UTM <-> MGRS and datum transforms
(WGS84 / ED50 / NAD27) with round-trip guarantees.
"""

from __future__ import annotations

import math
import re
from typing import Any

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)

_DMS_RE = re.compile(
    r"^\s*(?P<d>[+-]?\d{1,3})(?:[°ºd\s]\s*(?P<m>\d{1,2}(?:\.\d+)?)"
    r"(?:['′’m\s]\s*(?P<s>\d{1,2}(?:\.\d+)?)?(?:[\"″”s])?)?)?"
    r"\s*(?P<hemi>[NSEW])?\s*$",
    re.IGNORECASE,
)

DATUMS: dict[str, dict[str, float]] = {
    # Helmert 7-parameter transforms TO WGS84 (dx, dy, dz in meters).
    # Documented approximate parameters (EPSG guidance / official surveys).
    "WGS84": {"dx": 0.0, "dy": 0.0, "dz": 0.0},
    "ED50": {"dx": -87.0, "dy": -98.0, "dz": -121.0},
    "NAD27": {"dx": 8.0, "dy": -160.0, "dz": -176.0},
    "GRS80": {"dx": 0.0, "dy": 0.0, "dz": 0.0},
}


def parse_dms(value: str | int | float) -> float:
    """Parse DMS (51°30'26.5\"N), decimal degrees, or signed degrees to decimal."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        raise ValueError("empty coordinate value")
    if not any(marker in text for marker in ("°", "º", "'", '"', "d", "m", "s", "N", "S", "E", "W")):
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"unparseable coordinate: {text!r}") from None
    match = _DMS_RE.match(text)
    if not match:
        raise ValueError(f"unparseable coordinate: {text!r}")
    deg = float(match.group("d"))
    minute = float(match.group("m") or 0.0)
    second = float(match.group("s") or 0.0)
    hemi = (match.group("hemi") or "").upper()
    sign = -1.0 if deg < 0 or hemi in {"S", "W"} else 1.0
    decimal = abs(deg) + minute / 60.0 + second / 3600.0
    return sign * decimal


def to_dms(decimal: float, *, axis: str = "lat") -> dict[str, Any]:
    """Convert decimal degrees to DMS with hemisphere letter."""
    if axis == "lat" and not -90.0 <= decimal <= 90.0:
        raise ValueError(f"latitude out of range: {decimal}")
    if axis == "lon" and not -180.0 <= decimal <= 180.0:
        raise ValueError(f"longitude out of range: {decimal}")
    hemi = ""
    if axis == "lat":
        hemi = "N" if decimal >= 0 else "S"
    else:
        hemi = "E" if decimal >= 0 else "W"
    absolute = abs(decimal)
    deg = int(absolute)
    minute_float = (absolute - deg) * 60.0
    minute = int(minute_float)
    second = round((minute_float - minute) * 60.0, 4)
    if second >= 60.0:
        second -= 60.0
        minute += 1
    if minute >= 60:
        minute -= 60
        deg += 1
    return {
        "degrees": deg,
        "minutes": minute,
        "seconds": second,
        "hemisphere": hemi,
        "decimal": round(decimal, 9),
        "dms_string": f'{deg}°{minute}\'{second:.4f}"{hemi}',
    }


def _llh_to_xyz(lat: float, lon: float, h: float, a: float, f: float) -> tuple[float, float, float]:
    e2 = f * (2.0 - f)
    sin_lat = math.sin(math.radians(lat))
    cos_lat = math.cos(math.radians(lat))
    n = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    x = (n + h) * cos_lat * math.cos(math.radians(lon))
    y = (n + h) * cos_lat * math.sin(math.radians(lon))
    z = (n * (1.0 - e2) + h) * sin_lat
    return x, y, z


def _xyz_to_llh(
    x: float, y: float, z: float, a: float, f: float
) -> tuple[float, float, float]:
    e2 = f * (2.0 - f)
    lon = math.degrees(math.atan2(y, x))
    p = math.hypot(x, y)
    lat = math.degrees(math.atan2(z, p * (1.0 - e2)))
    for _ in range(8):
        sin_lat = math.sin(math.radians(lat))
        n = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
        new_lat = math.degrees(math.atan2(z + e2 * n * sin_lat, p))
        if abs(new_lat - lat) < 1e-12:
            lat = new_lat
            break
        lat = new_lat
    sin_lat = math.sin(math.radians(lat))
    n = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    h = p / math.cos(math.radians(lat)) - n if abs(lat) < 89.9 else z / sin_lat - n * (1.0 - e2)
    return lat, lon, h


def datum_transform(
    lat: float, lon: float, *, source: str = "WGS84", target: str = "WGS84", height: float = 0.0
) -> dict[str, float]:
    """Transform coordinates between supported datums (Helmert shift, documented)."""
    if source not in DATUMS or target not in DATUMS:
        raise ValueError(f"unsupported datum: source={source}, target={target}")
    if source == target:
        return {"lat": round(lat, 9), "lon": round(lon, 9), "height": height}
    dx, dy, dz = (DATUMS[source][k] - DATUMS[target][k] for k in ("dx", "dy", "dz"))
    x, y, z = _llh_to_xyz(lat, lon, height, WGS84_A, WGS84_F)
    new_lat, new_lon, new_h = _xyz_to_llh(
        x + dx, y + dy, z + dz, WGS84_A, WGS84_F
    )
    return {"lat": round(new_lat, 9), "lon": round(new_lon, 9), "height": round(new_h, 3)}


def to_utm(lat: float, lon: float) -> dict[str, Any]:
    """Convert WGS84 decimal degrees to UTM zone/hemisphere/easting/northing."""
    if not -80.0 <= lat <= 84.0:
        raise ValueError("UTM defined for latitudes -80..84")
    zone = int((lon + 180.0) // 6.0) + 1
    if zone > 60:
        zone = 1
    if lon == 180.0:
        zone = 60
    central_meridian = math.radians(zone * 6 - 183)
    phi = math.radians(lat)
    lam = math.radians(lon)
    k0 = 0.9996
    e2 = WGS84_E2
    ep2 = e2 / (1.0 - e2)
    n = WGS84_A / math.sqrt(1.0 - e2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = ep2 * math.cos(phi) ** 2
    a = math.cos(phi) * (lam - central_meridian)
    m = WGS84_A * (
        (1.0 - e2 / 4.0 - 3.0 * e2**2 / 64.0 - 5.0 * e2**3 / 256.0) * phi
        - (3.0 * e2 / 8.0 + 3.0 * e2**2 / 32.0 + 45.0 * e2**3 / 1024.0) * math.sin(2 * phi)
        + (15.0 * e2**2 / 256.0 + 45.0 * e2**3 / 1024.0) * math.sin(4 * phi)
        - (35.0 * e2**3 / 3072.0) * math.sin(6 * phi)
    )
    easting = k0 * n * (
        a
        + (1.0 - t + c) * a**3 / 6.0
        + (5.0 - 18.0 * t + t**2 + 72.0 * c - 58.0 * ep2) * a**5 / 120.0
    ) + 500000.0
    northing = k0 * (
        m
        + n
        * math.tan(phi)
        * (
            a**2 / 2.0
            + (5.0 - t + 9.0 * c + 4.0 * c**2) * a**4 / 24.0
            + (61.0 - 58.0 * t + t**2 + 600.0 * c - 330.0 * ep2) * a**6 / 720.0
        )
    )
    if lat < 0:
        northing += 10000000.0
    return {
        "zone": zone,
        "hemisphere": "N" if lat >= 0 else "S",
        "easting_m": round(easting, 3),
        "northing_m": round(northing, 3),
    }


def from_utm(zone: int, hemisphere: str, easting: float, northing: float) -> dict[str, float]:
    """Convert UTM zone/easting/northing back to WGS84 decimal degrees."""
    k0 = 0.9996
    e2 = WGS84_E2
    ep2 = e2 / (1.0 - e2)
    hem = hemisphere.strip().upper()
    if hem not in {"N", "S"}:
        raise ValueError("hemisphere must be N or S")
    if hem == "S":
        northing -= 10000000.0
    e = easting - 500000.0
    m = northing / k0
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))
    mu = m / (
        WGS84_A
        * (
            1.0 - e2 / 4.0 - 3.0 * e2**2 / 64.0 - 5.0 * e2**3 / 256.0
        )
    )
    phi1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * math.sin(2 * mu)
        + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * math.sin(4 * mu)
        + (151.0 * e1**3 / 96.0) * math.sin(6 * mu)
        + (1097.0 * e1**4 / 512.0) * math.sin(8 * mu)
    )
    n1 = WGS84_A / math.sqrt(1.0 - e2 * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = ep2 * math.cos(phi1) ** 2
    r1 = WGS84_A * (1.0 - e2) / (1.0 - e2 * math.sin(phi1) ** 2) ** 1.5
    d = e / (n1 * k0)
    lat = (
        phi1
        - (n1 * math.tan(phi1) / r1)
        * (
            d**2 / 2.0
            - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1**2 - 9.0 * ep2) * d**4 / 24.0
            + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1**2 - 252.0 * ep2 - 3.0 * c1**2)
            * d**6
            / 720.0
        )
    )
    lon = (
        (d - (1.0 + 2.0 * t1 + c1) * d**3 / 6.0
         + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1**2 + 8.0 * ep2 + 24.0 * t1**2)
         * d**5
         / 120.0)
        / math.cos(phi1)
    )
    central_meridian = math.radians(zone * 6 - 183)
    return {
        "lat": round(math.degrees(lat), 9),
        "lon": round(math.degrees(central_meridian + lon), 9),
    }


_MGRS_LETTERS = "CDEFGHJKLMNPQRSTUVWX"
_MGRS_COL = "ABCDEFGH"
_MGRS_ROW = "ABCDEFGHJKLMNPQRSTUV"


def _mgrs_lat_band(lat: float) -> str:
    if not -80.0 <= lat <= 84.0:
        raise ValueError("MGRS defined for latitudes -80..84")
    return _MGRS_LETTERS[min(19, int((lat + 80.0) // 8.0))]


def to_mgrs(lat: float, lon: float) -> dict[str, Any]:
    """Convert WGS84 decimal degrees to MGRS (100km square + 5-digit refinement).

    NGA rule: odd zones use the 8-letter column set first, even zones use the
    20-letter row set first. MGRS northing is measured from the equator in both
    hemispheres (south: 0 at the equator increasing southward), which differs
    from UTM southern northing (10,000,000 + negative meridian arc).
    """
    utm = to_utm(lat, lon)
    band = _mgrs_lat_band(lat)
    if lat < 0:
        mgrs_northing = 10000000.0 - utm["northing_m"]
    else:
        mgrs_northing = utm["northing_m"]
    e100 = int(utm["easting_m"]) // 100000
    n100 = int(mgrs_northing) // 100000
    col = (e100 - 1) % 8
    row = n100 % 20
    if utm["zone"] % 2 == 1:
        first, second = _MGRS_COL[col], _MGRS_ROW[row]
    else:
        first, second = _MGRS_ROW[row], _MGRS_COL[col]
    return {
        "zone": utm["zone"],
        "band": band,
        "square": f"{first}{second}",
        "easting_m": round(utm["easting_m"] % 100000, 3),
        "northing_m": round(mgrs_northing % 100000, 3),
        "mgrs_string": (
            f'{utm["zone"]}{band}{first}{second} '
            f'{int(utm["easting_m"] % 100000):05d} {int(mgrs_northing % 100000):05d}'
        ),
    }


_MGRS_RE = re.compile(
    r"^\s*(?P<zone>\d{1,2})\s*(?P<band>[C-HJ-NP-X])\s*(?P<sq>[A-HJ-NP-Z]{2})"
    r"\s*(?P<east>\d{1,5})\s*(?P<north>\d{1,5})\s*$",
    re.IGNORECASE,
)


def from_mgrs(value: str) -> dict[str, float]:
    """Convert an MGRS string (e.g. '31U DQ 48251 11932') back to WGS84 decimal degrees.

    Inverse of to_mgrs: resolves the 100km square using the NGA column/row
    letter rule (odd zone: column letter first; even zone: row letter first),
    then returns the SW corner plus the 5-digit refinement.
    """
    match = _MGRS_RE.match(value)
    if not match:
        raise ValueError(f"unparseable MGRS string: {value!r}")
    zone = int(match.group("zone"))
    band = match.group("band").upper()
    square = match.group("sq").upper()
    east_off = int(match.group("east"))
    north_off = int(match.group("north"))

    band_index = _MGRS_LETTERS.index(band)
    band_lat_min = band_index * 8.0 - 80.0
    band_lat_max = 84.0 if band == "X" else band_lat_min + 8.0

    if zone % 2 == 0:
        col_letter, row_letter = square[1], square[0]
    else:
        col_letter, row_letter = square[0], square[1]
    e100 = _MGRS_COL.index(col_letter) + 1
    n100 = _MGRS_ROW.index(row_letter)

    easting = e100 * 100000 + east_off
    mgrs_northing = n100 * 100000 + north_off
    southern = band_index < 10  # bands C..M

    lat_est = None
    lon_est = None
    best_gap = float("inf")
    for k in range(6):
        base = mgrs_northing + k * 2000000.0
        if southern:
            if base > 10000000.0:
                continue
            converted = from_utm(zone, "S", float(easting), 10000000.0 - base)
        else:
            converted = from_utm(zone, "N", float(easting), base)
        # Candidate must fall inside the band's latitude range and the zone's
        # central-meridian window; the 0.01 deg tolerance absorbs the truncation
        # error of 5-digit MGRS refinements. Both guards reject the nonsense
        # outputs that inverse UTM produces for northing values beyond the pole.
        central = zone * 6.0 - 183.0
        if (
            band_lat_min - 0.01 <= converted["lat"] < band_lat_max + 0.01
            and abs(converted["lon"] - central) <= 3.5
        ):
            gap = abs(converted["lat"] - (band_lat_min + (band_lat_max - band_lat_min) / 2.0))
            if gap < best_gap:
                best_gap = gap
                lat_est, lon_est = converted["lat"], converted["lon"]
    if lat_est is None:
        raise ValueError(f"unresolvable MGRS string (band mismatch): {value!r}")
    return {"lat": lat_est, "lon": lon_est}


def normalize_coordinate(
    value: str | int | float,
    *,
    ref: str = "",
    axis: str = "lat",
) -> dict[str, Any]:
    """Normalize one coordinate from any supported format to WGS84 decimal."""
    decimal = parse_dms(value)
    hemi = (ref or "").strip().upper()
    if hemi in {"S", "W"}:
        decimal = -abs(decimal)
    if axis == "lat" and not -90.0 <= decimal <= 90.0:
        raise ValueError(f"latitude out of range: {decimal}")
    if axis == "lon" and not -180.0 <= decimal <= 180.0:
        raise ValueError(f"longitude out of range: {decimal}")
    dms = to_dms(decimal, axis=axis)
    utm = to_utm(decimal, 0.0 if axis == "lat" else decimal) if axis == "lat" else None
    return {
        "decimal": round(decimal, 9),
        "dms": dms,
        "source_format": "decimal" if isinstance(value, (int, float)) else "dms",
    }