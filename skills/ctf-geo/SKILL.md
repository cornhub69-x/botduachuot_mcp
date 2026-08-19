---
name: ctf-geo
description: Solve CTF geolocation/coordinate challenges with the offline Geo Engine. Use when the task involves GPS coords, EXIF GPS, DMS/UTM/MGRS conversion, datum shifts, or locating a photo. Evidence-first: >= 2 independent facts before concluding.
---

# CTF Geo

Use for: EXIF GPS extraction, coordinate conversion (DMS/decimal/UTM/MGRS), datum transforms, offline reverse geocoding, timezone cross-checks, heading/bearing verification, and "where was this taken" challenges.

## Workflow (follow in order)

1. **Triage**: call `duachuot_geo_extract` on the artifact (cross_check=True). Primary: exiftool; cross-check: exiv2. If the two disagree, report BOTH values — never merge silently.
2. **Convert** every coordinate form you see:
   - `duachuot_coord_convert(lat=..., lon=...)` or DMS/UTM variants.
   - Always try datum_source=ED50 and NAD27 when WGS84 results don't fit landmarks (100-500 m shifts).
   - MGRS uses the NGA standard: odd zones use the 8-char column set first, even zones the 20-char row set first.
3. **Reverse offline**: `duachuot_geo_reverse(lat, lon)` against the bundled landmarks.json dataset. Never call an online reverse-geocoding API while a CTF is live.
4. **Verify**: `duachuot_geo_verify(lat, lon, ...)` — needs >= 2 independent facts (landmark proximity, timezone match, heading vs bearing, EXIF). Fewer → BLOCKER; do not conclude.
5. **Cross-check time**: `duachuot_timezone_at(lat, lon)` vs EXIF GPSDateTime (UTC→local).
6. **Cross-check heading**: GPSImgDirection vs bearing to nearest landmark.

## Rules

- Offline and deterministic: every conversion must round-trip; when in doubt, run both directions.
- Always output an accuracy estimate (DOP/HPE or conservative radius).
- Record evidence as FACT (value + source), INFERENCE (derived with support), HYPOTHESIS (not enough), BLOCKER (cannot proceed).
- Read `knowledge/GEO_PLAYBOOK.md` for the full playbook and common traps.
