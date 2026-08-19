# Geo Playbook — BotDuaChuot

Standard playbook for every **coordinate / location** task in CTF. Goal: find precise coordinates, prove them with >= 2 independent facts, fully offline and deterministic.

## Pipeline (8 standard steps)

1. **Triage the artifact** — `duachuot_media_probe` (or `file` + `exiftool -json -n`). Identify the file type and metadata source.
2. **Extract GPS** — `duachuot_geo_extract(path, cross_check=True)`. exiftool is the primary source, exiv2 the cross-check. **If the two sources disagree → return None + warning; never merge silently.**
3. **Convert** — `duachuot_coord_convert` for every coordinate form seen in the challenge:
   - DMS: `21°01'44.6"N 105°51'13.2"E` (mind N/S/E/W)
   - Decimal: `21.02906, 105.85367`
   - UTM: zone + hemisphere + easting/northing (ED50/NAD27/WGS84 differ by 100-500 m!)
   - MGRS: `48Q UJ 12345 67890` (NGA standard: odd zones use the 8-letter column set first, even zones the 20-letter row set first)
4. **Offline reverse** — `duachuot_geo_reverse` against the bundled landmarks.json dataset. Always note this is an offline estimate, not a real GPS fix.
5. **Verify** — `duachuot_geo_verify`: needs >= 2 independent facts (nearby landmark, matching timezone, matching heading, EXIF). Fewer → **BLOCKER**, do not conclude.
6. **Cross-check time** — `duachuot_timezone_at` vs the EXIF GPSDateTime (UTC → local).
7. **Cross-check heading** — bearing from the capture point to a landmark vs GPSImgDirection.
8. **Report** — record fact/inference clearly with accuracy (HPE/DOP) and source for every value.

## Principles

- **Strictly offline**: no online reverse geocoding (Google/OSM APIs) while live. If a landmark is missing from the dataset, record a BLOCKER.
- **Byte-for-byte round-trip**: every conversion must round-trip exactly; run round-trip tests before trusting any result.
- **Datum is the classic trap**: challenges often provide UTM/ED50 or "Lat: 21 01 44.6 N". Always try all 3 datums when a result does not match a landmark.
- **Every conclusion carries accuracy**: always output the error radius (DOP*HPE or an estimate).

## Common traps

| Trap | Signal | Handling |
|---|---|---|
| Lat/Lon swapped | landmark far away | try swapped axes |
| DMS without minute/second marks | "21 01 44.6" | parse as plain decimal |
| Wrong MGRS zone parity | invalid square | use the correct NGA tables |
| ED50/NAD27 datum | consistent 100-500 m offset | transform → WGS84 |
| GPSDateTime local vs UTC | timezone mismatch | try 7/8 h offsets |

## Evidence recording

- FACT: an extracted value + source (exiftool/exiv2/where read).
- INFERENCE: a derivation with support (bearing + heading → shot direction).
- HYPOTHESIS: not enough facts yet (needs the verify step).
- BLOCKER: insufficient independent facts → do not conclude; state what is missing.
