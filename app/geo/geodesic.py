"""Geo Engine — geodesic math (pure Python Vincenty + great-circle fallback)."""

from __future__ import annotations

import math
from typing import Any

from app.geo.convert import WGS84_A, WGS84_F

_INVERSE_ITERATIONS = 200


def vincenty_inverse(lat1: float, lon1: float, lat2: float, lon2: float) -> dict[str, Any]:
    """Vincenty inverse solution: geodesic distance (m) and forward/back azimuths (deg)."""
    phi1, lam1 = math.radians(lat1), math.radians(lon1)
    phi2, lam2 = math.radians(lat2), math.radians(lon2)
    f = WGS84_F
    l = lam2 - lam1
    u1 = math.atan((1.0 - f) * math.tan(phi1))
    u2 = math.atan((1.0 - f) * math.tan(phi2))
    sin_u1, cos_u1 = math.sin(u1), math.cos(u1)
    sin_u2, cos_u2 = math.sin(u2), math.cos(u2)
    lam = l
    sin_sigma = cos_sigma = sigma = sin_alpha = cos_sq_alpha = cos2_sigma_m = 0.0
    converged = False
    for _ in range(_INVERSE_ITERATIONS):
        sin_lam = math.sin(lam)
        cos_lam = math.cos(lam)
        sin_sigma = math.hypot(
            cos_u2 * sin_lam,
            cos_u1 * sin_u2 - sin_u1 * cos_u2 * cos_lam,
        )
        if sin_sigma == 0.0:
            return {
                "distance_m": 0.0,
                "azimuth1_deg": 0.0,
                "azimuth2_deg": 0.0,
                "method": "vincenty",
                "converged": True,
            }
        cos_sigma = sin_u1 * sin_u2 + cos_u1 * cos_u2 * cos_lam
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cos_u1 * cos_u2 * sin_lam / sin_sigma
        cos_sq_alpha = 1.0 - sin_alpha * sin_alpha
        cos2_sigma_m = (
            cos_sigma - 2.0 * sin_u1 * sin_u2 / cos_sq_alpha
            if cos_sq_alpha != 0.0
            else 0.0
        )
        c = f / 16.0 * cos_sq_alpha * (4.0 + f * (4.0 - 3.0 * cos_sq_alpha))
        lam_prev = lam
        lam = l + (1.0 - c) * f * sin_alpha * (
            sigma
            + c * sin_sigma
            * (
                cos2_sigma_m
                + c * cos_sigma * (-1.0 + 2.0 * cos2_sigma_m * cos2_sigma_m)
            )
        )
        if abs(lam - lam_prev) < 1e-12:
            converged = True
            break
    if not converged:
        return _great_circle_fallback(lat1, lon1, lat2, lon2)
    u_sq = cos_sq_alpha * (WGS84_A**2 - WGS84_B2()) / WGS84_B2()
    a_coeff = 1.0 + u_sq / 16384.0 * (4096.0 + u_sq * (-768.0 + u_sq * (320.0 - 175.0 * u_sq)))
    b_coeff = u_sq / 1024.0 * (256.0 + u_sq * (-128.0 + u_sq * (74.0 - 47.0 * u_sq)))
    delta_sigma = (
        b_coeff
        * sin_sigma
        * (
            cos2_sigma_m
            + b_coeff
            / 4.0
            * (
                cos_sigma * (-1.0 + 2.0 * cos2_sigma_m**2)
                - b_coeff / 6.0 * cos2_sigma_m * (-3.0 + 4.0 * sin_sigma**2)
                * (-3.0 + 4.0 * cos2_sigma_m**2)
            )
        )
    )
    distance = WGS84_B2_AXIS() * a_coeff * (sigma - delta_sigma)
    azimuth1 = math.degrees(
        math.atan2(
            cos_u2 * math.sin(lam),
            cos_u1 * sin_u2 - sin_u1 * cos_u2 * math.cos(lam),
        )
    )
    azimuth2 = math.degrees(
        math.atan2(
            cos_u1 * math.sin(lam),
            -sin_u1 * cos_u2 + cos_u1 * sin_u2 * math.cos(lam),
        )
    )
    return {
        "distance_m": round(distance, 3),
        "azimuth1_deg": round(azimuth1 % 360.0, 6),
        "azimuth2_deg": round(azimuth2 % 360.0, 6),
        "method": "vincenty",
        "converged": True,
    }


def WGS84_B2_AXIS() -> float:
    return WGS84_A * (1.0 - WGS84_F)


def WGS84_B2() -> float:
    return WGS84_B2_AXIS() ** 2


def _great_circle_fallback(lat1: float, lon1: float, lat2: float, lon2: float) -> dict[str, Any]:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lam = math.radians(lon2 - lon1)
    sin_phi1, cos_phi1 = math.sin(phi1), math.cos(phi1)
    sin_phi2, cos_phi2 = math.sin(phi2), math.cos(phi2)
    central = math.acos(
        max(-1.0, min(1.0, sin_phi1 * sin_phi2 + cos_phi1 * cos_phi2 * math.cos(d_lam)))
    )
    distance = 6371008.8 * central
    y = math.sin(d_lam) * cos_phi2
    x = cos_phi1 * sin_phi2 - sin_phi1 * cos_phi2 * math.cos(d_lam)
    azimuth1 = math.degrees(math.atan2(y, x)) % 360.0
    return {
        "distance_m": round(distance, 3),
        "azimuth1_deg": round(azimuth1, 6),
        "azimuth2_deg": round((azimuth1 + 180.0) % 360.0, 6),
        "method": "great_circle",
        "converged": False,
        "note": "vincenty did not converge; great-circle approximation returned",
    }


def uncertainty_from_dop(dop: float | None, *, gps_hpe: float | None = None) -> dict[str, Any]:
    """Estimate positional accuracy radius from GPS DOP or HPE.

    Rule of thumb: horizontal accuracy ~ DOP * UERE (user equivalent range
    error). With typical consumer UERE of 5 m, accuracy ≈ DOP * 5 m; when an
    explicit GPSHPositioningError is present, prefer it.
    """
    if gps_hpe is not None and gps_hpe > 0:
        return {
            "accuracy_m": round(float(gps_hpe), 2),
            "source": "gps_hpe",
            "dop": dop,
            "note": "explicit horizontal positioning error reported by device",
        }
    if dop is None or dop <= 0:
        return {
            "accuracy_m": None,
            "source": "unknown",
            "dop": dop,
            "note": "no DOP/HPE available; accuracy cannot be estimated",
        }
    accuracy = float(dop) * 5.0
    return {
        "accuracy_m": round(accuracy, 2),
        "source": "dop_x_uere5m",
        "dop": dop,
        "note": "estimated as DOP * 5 m UERE rule of thumb",
    }