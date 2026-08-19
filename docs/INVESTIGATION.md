# Investigation Subsystem — BotDuaChuot

Technical documentation for the investigation stack (Forensics + OSINT + Geo) of BotDuaChuot:
`app/geo/`, `app/ops/`, `app/platform/`, the new `duachuot_*` MCP tools, playbooks
and skills. Complements `ARCHITECTURE.md` (runtime) and `SECURITY.md` (security).

## 1. Geo Engine (`app/geo/`) — offline, deterministic

| Module | Responsibility |
|---|---|
| `convert.py` | DMS ↔ decimal ↔ UTM ↔ MGRS; datum transform WGS84/ED50/NAD27/GRS80 (7-parameter Helmert) |
| `geodesic.py` | Vincenty inverse + great-circle fallback; `uncertainty_from_dop` (HPE/DOP → error radius) |
| `exif_gps.py` | EXIF GPS extraction: exiftool (primary) + exiv2 (cross-check); conflicting sources → `None`, never merged silently |
| `reverse.py` | Offline reverse geocoding over `datasets/landmarks.json` (46 landmarks, haversine + geodesic) |
| `timezone.py` | Offline timezone table (50+ zones) keyed by bbox |

Notable design decisions:

- **NGA-standard MGRS**: odd zones use the 8-character column set first, even zones
  the 20-character row set first. MGRS northing is measured from the equator on both
  hemispheres (unlike UTM south: `utm_S = 10,000,000 - mgrs_northing`).
- **`from_mgrs` disambiguates the 2,000,000 m period** via the latitude band: it
  generates 6 candidates (k=0..5) and keeps the candidate inside the band's
  latitude range (0.01° tolerance for 5-digit truncation error) and inside the
  central-meridian window of ±3.5° (rejects garbage produced by the inverse UTM
  when the northing crosses a pole). Band X is 12° (72–84); other bands are 8°.
- **Round-trip within ≤4 m** across 20 test points covering both hemispheres, the
  poles, the antimeridian and band edges. Test suite: `tests/geo/test_geo_engine.py` (36 tests).

## 2. OPSEC Gate (`app/ops/gate.py`)

8 hard rules (from PLAN v2.0, section 7). API:

- `gate_command(cmd, mode, dry_run)` — inspects local commands: blocks telemetry
  hosts (ip-api, api.ipify, geoip-db, ipinfo, shodan, censys...), blocks automated
  attack tools (sqlmap, nmap, hydra, masscan, ffuf, metasploit...), blocks public
  discovery when `ctf-live` (sherlock/maigret/whois/dnsrecon/search engines),
  blocks flag-like strings inside commands.
- `gate_remote_request(target, mode, dry_run)` — same rules for network targets.
- `redact_secrets(text)` — redacts flag/token/secret before writing logs.
- `jitter_delay()` / `suggest_jitter_seconds()` — 800–3000 ms delay between network
  queries (human-like pacing, no parallel bursts).

Default mode is `ctf-live` from `app.config.OSINT_MODE` (False). Set
`OSINT_MODE=true` only when the operator confirms the challenge allows external lookups.

## 3. Platform Adapter (`app/platform/`)

- `probe_platform()` — OS/arch/distro (`/etc/os-release`)/shell/package managers,
  cached with `lru_cache`.
- `choose_executable(name)` — native PATH → (Windows) WSL bridge `wsl.exe which`.
- `tool_supported(name)` — reports availability/method (native|wsl|missing).
- `executor.py` uses `_shell_invocation()`: bash `--noprofile --norc` on
  Linux/macOS; WSL bridge, `powershell -NoProfile`, or `cmd /d /s /c` on Windows.
  Strategy: python-portable > native PATH > pkg-manager > WSL2.

## 4. New MCP tools (19)

`app/tools/geo_tools.py` — `duachuot_geo_extract`, `duachuot_coord_convert`
(DMS/decimal/UTM/**MGRS** input), `duachuot_geo_calc`, `duachuot_geo_reverse`,
`duachuot_geo_verify` (≥2 independent facts → confidence; fewer → BLOCKER),
`duachuot_geo_landmark_check`, `duachuot_timezone_at`.

`app/tools/probes.py` — `duachuot_media_probe` (file+exiftool+ffprobe),
`duachuot_pcap_probe` (tshark: conversations/endpoints/DNS + GPS hints NMEA/Wi-Fi),
`duachuot_disk_probe` (fsstat+fls), `duachuot_mem_probe` (vol), `duachuot_stego_probe`
(binwalk+steghide), `duachuot_ocr_probe` (tesseract+QR zxing), `duachuot_win_probe`
(SAM/SYSTEM hives, LNK, prefetch — pure-Python).

`app/tools/ops_tools.py` — `duachuot_ops_check`, `duachuot_ops_jitter`,
`duachuot_ops_redact`, `duachuot_platform`, `duachuot_plan` (investigation plan by
artifact type).

Probe principle: missing tool → explicit BLOCKER error naming the command to install;
results are never guessed. Registered in `app/main.py`.

## 5. CLI (`duachuot`)

```
duachuot geo convert   [--lat --lon | --dms-lat --dms-lon | --utm-zone --easting --northing] [--datum-src --datum-dst]
duachuot geo reverse   LAT LON [--limit N]
duachuot geo verify    LAT LON
duachuot ops check     TARGET [--kind command|remote]
duachuot ops jitter
duachuot platform      [--tool NAME]
```

Install: `bin/duachuot` (venv-aware). Add to PATH or use `scripts/install_cli.sh`.

## 6. Testing

```bash
.venv/bin/python -m pytest tests/ -q                 # 54 tests
.venv/bin/python scripts/smoke_investigation.py      # MCP inventory + 7 functional checks
.venv/bin/python scripts/install_datasets.py         # validate datasets (offline)
```

## 7. CTF operations

1. `duachuot platform --tool <tool>` — check a tool before using it.
2. Every command/network target → `duachuot_ops_check` first; wait for the jitter between steps.
3. Coordinates: `geo_extract` → `coord_convert` → `geo_reverse` → `geo_verify` (≥2 facts).
4. Logs go through `ops_redact`; flags are only shown to humans, never auto-submitted.
