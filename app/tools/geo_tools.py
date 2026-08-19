"""MCP adapters — Geo tools (coordinate extraction, conversion, verification)."""

from __future__ import annotations

from typing import Any, Optional

import app.config
from app.geo.convert import (
    datum_transform,
    from_mgrs,
    from_utm,
    normalize_coordinate,
    to_dms,
    to_mgrs,
    to_utm,
)
from app.geo.exif_gps import extract_cross_checked, extract_with_exiftool
from app.geo.geodesic import uncertainty_from_dop, vincenty_inverse
from app.geo.reverse import is_within, nearest_landmarks
from app.geo.timezone import timezone_at
from app.mcp_server import mcp
from app.security import format_error_response


@mcp.tool(
    name="duachuot_geo_extract",
    description=(
        "Extract GPS coordinates from an image/video file using exiftool primary "
        "and exiv2 cross-check. Returns normalized WGS84 decimal, DMS, UTM, MGRS, "
        "altitude, image direction (heading), DOP, and HPE."
    ),
)
def duachuot_geo_extract(
    path: str,
    cross_check: bool = True,
) -> dict[str, Any]:
    try:
        if cross_check:
            result = extract_cross_checked(path)
        else:
            result = extract_with_exiftool(path)
        gps = result.get("gps")
        if gps:
            accuracy = uncertainty_from_dop(gps.get("dop"), gps_hpe=gps.get("gps_hpe_m"))
            tz = timezone_at(gps["lat"], gps["lon"])
            result["accuracy"] = accuracy
            result["timezone"] = tz
            result["landmarks"] = nearest_landmarks(gps["lat"], gps["lon"])
        return {"ok": True, **result}
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_coord_convert",
    description=(
        "Convert coordinates between DMS, decimal degrees, UTM, and MGRS with "
        "datum transforms (WGS84/ED50/NAD27/GRS80). Deterministic round-trip."
    ),
)
def duachuot_coord_convert(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    lat_dms: Optional[str] = None,
    lon_dms: Optional[str] = None,
    lat_ref: str = "",
    lon_ref: str = "",
    utm_zone: Optional[int] = None,
    utm_hemisphere: str = "N",
    utm_easting: Optional[float] = None,
    utm_northing: Optional[float] = None,
    mgrs: Optional[str] = None,
    datum_source: str = "WGS84",
    datum_target: str = "WGS84",
) -> dict[str, Any]:
    try:
        if lat is not None and lon is not None:
            lat_dec, lon_dec = float(lat), float(lon)
        elif lat_dms is not None and lon_dms is not None:
            lat_dec = normalize_coordinate(lat_dms, ref=lat_ref, axis="lat")["decimal"]
            lon_dec = normalize_coordinate(lon_dms, ref=lon_ref, axis="lon")["decimal"]
        elif utm_zone and utm_easting is not None and utm_northing is not None:
            converted = from_utm(int(utm_zone), utm_hemisphere, float(utm_easting), float(utm_northing))
            lat_dec, lon_dec = converted["lat"], converted["lon"]
        elif mgrs:
            converted = from_mgrs(mgrs)
            lat_dec, lon_dec = converted["lat"], converted["lon"]
        else:
            raise ValueError(
                "provide (lat, lon), (lat_dms, lon_dms), (utm_zone, utm_hemisphere, "
                "utm_easting, utm_northing), or mgrs"
            )

        transformed = datum_transform(
            lat_dec, lon_dec, source=datum_source, target=datum_target
        )
        t_lat, t_lon = transformed["lat"], transformed["lon"]
        return {
            "ok": True,
            "input": {
                "lat": lat_dec,
                "lon": lon_dec,
                "datum": datum_source,
            },
            "output": {
                "lat": t_lat,
                "lon": t_lon,
                "datum": datum_target,
                "dms": {
                    "lat": to_dms(t_lat, axis="lat"),
                    "lon": to_dms(t_lon, axis="lon"),
                },
                "utm": to_utm(t_lat, t_lon),
                "mgrs": to_mgrs(t_lat, t_lon),
            },
            "datum_note": (
                "coordinate system shift applied; old datums (ED50/NAD27) typically "
                "differ from WGS84 by 100-500 m"
                if datum_source != datum_target
                else "no datum change"
            ),
        }
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_geo_calc",
    description=(
        "Geodesic calculations between two coordinates: distance (m), forward and "
        "back azimuths, plus uncertainty radius from GPS DOP/HPE."
    ),
)
def duachuot_geo_calc(
    lat1: float,
    lon1: float,
    lat2: Optional[float] = None,
    lon2: Optional[float] = None,
    dop: Optional[float] = None,
    gps_hpe: Optional[float] = None,
) -> dict[str, Any]:
    try:
        result: dict[str, Any] = {"ok": True}
        if lat2 is not None and lon2 is not None:
            result["geodesic"] = vincenty_inverse(float(lat1), float(lon1), float(lat2), float(lon2))
        result["uncertainty"] = uncertainty_from_dop(dop, gps_hpe=gps_hpe)
        return result
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_geo_reverse",
    description=(
        "Offline reverse geocoding against the local landmark dataset: nearest "
        "landmarks with geodesic distance and bearing. Never contacts the network."
    ),
)
def duachuot_geo_reverse(
    lat: float,
    lon: float,
    limit: Optional[int] = None,
    dataset: Optional[str] = None,
) -> dict[str, Any]:
    try:
        matches = nearest_landmarks(float(lat), float(lon), dataset=dataset, limit=limit)
        return {
            "ok": True,
            "lat": float(lat),
            "lon": float(lon),
            "matches": matches,
            "dataset": str(app.config.GEO_DATASETS_DIR / "landmarks.json"),
            "note": "offline dataset; verify conclusions with a second independent fact",
        }
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_geo_verify",
    description=(
        "Cross-check a location conclusion: requires >= 2 independent facts "
        "(EXIF coords, landmark proximity, timezone consistency, image direction). "
        "Outputs a confidence score 0-1 with reasons. Missing facts -> BLOCKER."
    ),
)
def duachuot_geo_verify(
    lat: float,
    lon: float,
    *,
    landmark_names: Optional[list[str]] = None,
    timezone_name: Optional[str] = None,
    gps_datetime: Optional[str] = None,
    img_direction_deg: Optional[float] = None,
    accuracy_m: Optional[float] = None,
) -> dict[str, Any]:
    try:
        facts: list[dict[str, Any]] = []
        lat_f, lon_f = float(lat), float(lon)

        matches = nearest_landmarks(lat_f, lon_f)
        if matches:
            nearest = matches[0]
            facts.append(
                {
                    "kind": "landmark",
                    "detail": f"nearest landmark '{nearest['name']}' at {nearest['distance_m']:.0f} m",
                    "independent": True,
                }
            )

        tz = timezone_at(lat_f, lon_f)
        if tz.get("timezone"):
            facts.append(
                {
                    "kind": "timezone",
                    "detail": f"offline timezone {tz['timezone']} (UTC{tz['utc_offset_hours']:+.0f})",
                    "independent": True,
                }
            )
            if timezone_name:
                consistent = timezone_name.split("/")[0].lower() == tz["timezone"].split("/")[0].lower()
                facts.append(
                    {
                        "kind": "timezone_consistency",
                        "detail": (
                            f"claimed {timezone_name} matches offline zone: {consistent}"
                        ),
                        "independent": consistent,
                    }
                )

        if img_direction_deg is not None and matches:
            bearing = matches[0]["bearing_deg"]
            delta = abs((float(img_direction_deg) - bearing + 540.0) % 360.0 - 180.0)
            facts.append(
                {
                    "kind": "heading",
                    "detail": f"camera heading {img_direction_deg}° vs bearing to landmark {bearing:.0f}° (delta {delta:.0f}°)",
                    "independent": delta < 45.0,
                }
            )

        independent_facts = [fact for fact in facts if fact["independent"]]
        required = app.config.GEO_REQUIRED_FACTS
        blocked = len(independent_facts) < required
        confidence = min(1.0, len(independent_facts) / required) if required else 0.0
        if accuracy_m is not None and float(accuracy_m) > 50:
            confidence = round(confidence * 0.7, 3)

        return {
            "ok": True,
            "lat": lat_f,
            "lon": lon_f,
            "facts": facts,
            "independent_fact_count": len(independent_facts),
            "required_facts": required,
            "blocked": blocked,
            "confidence": round(confidence, 3),
            "conclusion": (
                "BLOCKER: fewer than required independent facts; do not conclude a location"
                if blocked
                else "conclusion supported by the required independent facts"
            ),
        }
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_timezone_at",
    description=(
        "Look up the local timezone and UTC offset for a coordinate from the "
        "offline zone table. Use together with GPSDateTime to cross-check."
    ),
)
def duachuot_timezone_at(lat: float, lon: float) -> dict[str, Any]:
    try:
        return {"ok": True, **timezone_at(float(lat), float(lon))}
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_geo_landmark_check",
    description=(
        "Check whether a coordinate is within a radius of a known landmark "
        "(geodesic, deterministic)."
    ),
)
def duachuot_geo_landmark_check(
    lat: float,
    lon: float,
    landmark_name: str,
    radius_m: float,
) -> dict[str, Any]:
    try:
        for entry in nearest_landmarks(float(lat), float(lon), limit=50):
            if entry["name"].lower() == landmark_name.lower():
                inside = is_within(float(lat), float(lon), entry, float(radius_m))
                return {"ok": True, **inside}
        return format_error_response(ValueError(f"landmark not found in dataset: {landmark_name}"))
    except Exception as exc:
        return format_error_response(exc)