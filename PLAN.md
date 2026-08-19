# BOT DUA CHUOT (BotDuachuot) — MASTER PLAN

> An MCP bot built on the BotQuangAnh platform, specialized in **Forensics + OSINT**,
> optimized for **leveraging installed tools** and **precise coordinate determination**.
> Not detectable as an AI agent during competitions (invisible architecture, like BotQuangAnh).
> Runs on **any Linux arch/distro + Windows**.
> Date: 2026-08-19 · Version: 2.0 (complete)

---

## TABLE OF CONTENTS

1. Vision & 5 design principles
2. OVERALL ARCHITECTURE DIAGRAM
3. OPERATION DIAGRAM (evidence investigation flow)
4. Inherited from BotQuangAnh
5. Directory structure
6. Geo Engine — "precise coordinates"
7. Tool Matrix & Resource Registry (ctf-tools repository)
8. Two-mode policy (ctf-live / investigation)
9. Anti-detection — invisible architecture
10. Cross-platform (all Linux arches + Windows)
11. Full MCP tool list
12. Roadmap (M1–M6)
13. Definition of Done
14. Risks & mitigations
15. Feature proposals (P0/P1/discarded)

---

## 1. VISION & 5 PRINCIPLES

BotDuaChuot = "digital investigation assistant" (not a general-purpose CTF solver):
extract evidence from images/videos/audio/PCAP/disk/memory → determine
**precise coordinates** → cross-check with >= 2 independent facts → conclude with confidence.

**5 design principles:**

| # | Principle | Meaning |
|---|---|---|
| P1 | **Invisible architecture** | Local MCP like BotQuangAnh: the CTF server never sees the bot, only the user's requests |
| P2 | **Evidence-first** | FACT/INFERENCE/HYPOTHESIS/BLOCKER in solve_log.md; >= 2 independent facts before concluding |
| P3 | **Offline deterministic** | Geo Engine runs offline, byte-for-byte round-trip; no dependency on online services while competing |
| P4 | **Cross-platform** | Pure-Python core + Platform Adapter for tools; runs on all Linux arches + Windows |
| P5 | **Tool-first** | Every tool in the ctf-tools repository is a managed resource (Resource Registry), real version probing |

---

## 2. OVERALL ARCHITECTURE DIAGRAM

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       USER (human-in-the-loop)                           │
│   approves each major step · submits the flag · controls via ChatGPT/opencode │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ MCP streamable HTTP (stateless JSON)
                                │ Cloudflare Tunnel (operator only, auth required)
┌───────────────────────────────▼──────────────────────────────────────────┐
│                      botduachuot_mcp — MCP SERVER                        │
│                                                                          │
│  ┌─────────────────────────────┐   ┌───────────────────────────────────┐ │
│  │  CORE (inherited)           │   │  INVESTIGATION TOOLS (new)        │ │
│  │  health · capabilities      │   │  media_probe   (image/audio/video)│ │
│  │  fs_* (read/write/search)   │   │  pcap_probe    (flows + geo hints)│ │
│  │  run/check_command          │   │  disk_probe    (fls/fsstat+carve) │ │
│  │  knowledge · inventory      │   │  mem_probe     (vol3)             │ │
│  └─────────────────────────────┘   │  stego_probe   (LSB/carrier)      │ │
│  ┌─────────────────────────────┐   │  ocr_probe     (tesseract+QR)     │ │
│  │  GEO TOOLS (new)            │   │  win_probe     (hives/MFT/LNK)    │ │
│  │  geo_extract · coord_convert│   └───────────────────────────────────┘ │
│  │  geo_calc · geo_reverse     │   ┌───────────────────────────────────┐ │
│  │  geo_verify · timezone_at   │   │  OPSEC GATE (every request)       │ │
│  └─────────────────────────────┘   │  local-first · jitter 0.8–3s      │ │
│                                    │  dry_run preview · zero telemetry │ │
│  ┌─────────────────────────────┐   │  human-submit · clean logs        │ │
│  │  GEO ENGINE (offline)       │   └───────────────────────────────────┘ │
│  │  EXIF GPS → DMS/decimal/    │   ┌───────────────────────────────────┐ │
│  │  UTM/MGRS → datum → geodesic│   │  RESOURCE REGISTRY                │ │
│  │  → heading → uncertainty    │   │  RESOURCE_MAP.json ← ctf-tools    │ │
│  │  → landmark → confidence    │   │  (14 skills, scripts, venv, tools)│ │
│  └─────────────────────────────┘   └───────────────────────────────────┘ │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  PLATFORM ADAPTER  (os: linux/win/darwin · distro · arch · shell)  │ │
│  │  python-portable → native PATH → pkg-mgr (apt/dnf/pacman/winget)   │ │
│  │  → WSL2 (Windows) → container (rare arches)                        │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────────┐
│                  SKILLS  (skills/ + inherited ctf-tools/skills)          │
│  NEW: ctf-forensics-plus · ctf-osint-plus · ctf-stego-plus · ctf-geo     │
│  INHERITED: solve-challenge · ctf-writeup · ctf-pattern-archive · policy │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ real PATH (version probe)
┌───────────────────────────────▼──────────────────────────────────────────┐
│   HOST TOOL CHAIN  (Tool Matrix levels A/B/C)                            │
│   A-available: exiftool exiv2 identify convert ffmpeg tshark tcpdump     │
│                binwalk foremost steghide fls fsstat vol strings yara     │
│   B-venv:      geographiclib piexif zxing-cpp pytesseract pymap3d z3     │
│   C-data:      tz database · landmark db · ellipsoid params              │
└──────────────────────────────────────────────────────────────────────────┘

═══ CHALLENGE BOUNDARY ═══════════════════════════════════════════════════
CTF server only sees: HTTP requests from the user's IP/machine (no MCP, no AI,
no telemetry, no scanning) ───────────────► challenge instance
```

---

## 3. OPERATION DIAGRAM (evidence investigation flow)

```
Evidence (image/video/pcap/disk/mem)
        │
        ▼
[1] TRIAGE         file · magic · exiftool -json · previous solve_log.md
        │
        ▼
[2] PROBE          media_probe / pcap_probe / disk_probe / mem_probe / stego_probe
        │            → run A-level tools in parallel (exiftool+exiv2 cross-check)
        ▼
[3] GEO EXTRACT    raw GPS → normalize → datum → WGS84 decimal
        │            (all sources: EXIF, QR/barcode, OCR text, landmark hints)
        ▼
[4] GEO CALC       distance/bearing/heading (GPSImgDirection) → uncertainty (DOP)
        │
        ▼
[5] GEO REVERSE    offline landmark match + timezone_at
        │
        ▼
[6] GEO VERIFY     >= 2 independent facts? ── no ──► BLOCKER (state clearly, no guessing)
        │              │ yes
        ▼              ▼
[7] CONCLUSION      {lat, lon, datum, accuracy_m, heading, timezone,
                    matches[], confidence 0–1 + reasons}
        │
        ▼
[8] HANDOFF        solve_log.md → writeup → HUMAN approves & submits the flag
```

---

## 4. INHERITED FROM BOTQUANGANH

| Component | Source | Usage |
|---|---|---|
| `app/` (host, tools, mcp_server, rest_api, auth, policy) | `mcp/botquanganh_mcp/app/` | Fork, rename prefix to `duachuot_*` |
| `knowledge/` (WORKING_GUIDE, HOST_ENVIRONMENT, TOOL_CATALOG) | same | Extend catalog to 80+ tools |
| Policy `guarded` + auth + tunnel + rate limit | same | Keep as-is |
| Skills `solve-challenge`, `ctf-writeup` | `ctf-tools/skills/` | Keep, add geo routing |
| Sandbox `run_untrusted.py` (bwrap, private netns) | `ctf-pattern-archive/scripts/` | Mandatory for unknown artifacts |
| Evidence-first + verify loop | `ctf-resource-policy.md` | Forked into the two-mode policy (§8) |
| Pattern archive (scripts + empty sqlite) | `ctf-pattern-archive/` | Keep the mechanism; fill after each event |

---

## 5. DIRECTORY STRUCTURE

```
botduachuot_mcp/
├── app/
│   ├── host/          # files, executor (shell-aware), policy, inventory
│   ├── tools/         # MCP adapters: core + investigation tools
│   ├── geo/           # GEO ENGINE (pure python, offline)
│   │   ├── exif_gps.py    # parse every EXIF GPS variant (rational, DMS, datum)
│   │   ├── convert.py     # DMS<->decimal<->UTM<->MGRS, datum transform
│   │   ├── geodesic.py    # distance/bearing/uncertainty (geographiclib)
│   │   ├── reverse.py     # reverse-geocoding offline (local dataset)
│   │   └── timezone.py    # lat/lon → timezone (local tz database)
│   ├── ops/           # OPSEC GATE (jitter, dry_run, zero-telemetry check)
│   ├── platform/      # PLATFORM ADAPTER (probe os/distro/arch/shell + resolver)
│   ├── mcp_server.py  # + rest_api.py + config.py
├── knowledge/
│   ├── WORKING_GUIDE.md · HOST_ENVIRONMENT.md · TOOL_CATALOG.json
│   ├── FORENSICS_PLAYBOOK.md · OSINT_PLAYBOOK.md · GEO_PLAYBOOK.md
├── skills/            # ctf-forensics-plus, ctf-osint-plus, ctf-stego-plus, ctf-geo
│                       + symlinks to ctf-tools/skills (inherited)
├── datasets/          # timezone map · landmark db · ellipsoid params (offline)
├── resources/         # RESOURCE_MAP.json (generated from the ctf-tools repo at install)
├── scripts/           # install, tunnel, dev, test, quality_gate
├── tests/             # geo round-trip, platform, ops, policy
└── .env · README.md · SECURITY.md
```

---

## 6. GEO ENGINE — "PRECISE COORDINATES"

Standard pipeline:

```
1. geo_extract   exiftool -json -GPS* + exiv2 (cross-check) → raw GPS
2. normalize     DMS "51°30'26.5\"N" | rational | decimal | UTM | MGRS → WGS84
                 └ original datum recorded (WGS84/ED50/NAD27/GRS80)
3. refine        GPSImgDirection → vector "standing at A, looking at B"
                 GPSAltitude · GPSDOP (accuracy) · GPSDateTime (timezone cross-check)
4. geo_calc      geodesic distance/bearing A→B · uncertainty = f(DOP)
5. geo_reverse   offline landmark match (local dataset)
6. geo_verify    >= 2 independent facts (EXIF + landmark + timezone + heading)
                 └ < 2 facts → BLOCKER
                 └ output: {lat, lon, datum, accuracy_m, heading,
                            timezone, matches[], confidence}
```

**Golden rule**: every conversion must round-trip byte-for-byte
(decimal→DMS→decimal); online reverse geocoding is forbidden while ctf-live; old
datums (NAD27/ED50) are annotated with ~100–500 m deviation notes.

---

## 7. TOOL MATRIX & RESOURCE REGISTRY

### 7.1 Three-level Tool Matrix

| Level | Definition | List |
|---|---|---|
| **A — available** | real PATH, version probe | exiftool exiv2 identify convert ffmpeg ffprobe tshark tcpdump binwalk foremost steghide fls fsstat vol strings yara tesseract file xxd |
| **B — install** | into the CTF venv | geographiclib piexif zxing-cpp pytesseract pymap3d numpy PIL |
| **C — offline data** | embedded in datasets/ | tz database · natural-earth landmarks · ellipsoid params · country/state polygons |

### 7.2 Resource Registry (ctf-tools repo = managed resources)

| Source | Used for |
|---|---|
| `skills/*` (14 skills) | routing + playbook |
| `skills/*/scripts` (crypto_triage, apk_triage, run_sage, model_triage, run_untrusted, 5 pattern-archive scripts) | called directly via the registry |
| `tools/RsaCtfTool` | specific crypto attacks (with evidence) |
| `tools/pentestcode` | investigation mode ONLY, initiated by the user |
| `bin/ctfpy` + venv `~/CTF/tools/venv` | default runtime |
| `notes/CTF-KNOWLEDGE.md` | knowledge base seed |

`RESOURCE_MAP.json` (generated at install): path + category + invoke template +
required platform. Missing resource → BLOCKER, never run the wrong thing.

---

## 8. TWO-MODE POLICY

| | **ctf-live** (default) | **investigation** (`OSINT_MODE=on`) |
|---|---|---|
| Web search / public sources | ❌ forbidden | ✅ only user-designated sources |
| sherlock/maigret/holehe/theHarvester/whois/dnsrecon | ❌ forbidden | ✅ narrow scope, user-approved |
| Online reverse geocoding | ❌ forbidden (offline instead) | ✅ user-designated sources |
| Pentestcode/sqlmap against scope | ❌ forbidden | ❌ manual by user only |
| Brute force / wordlists / fuzzing | ❌ forbidden (immutable) | ❌ forbidden (immutable) |
| >= 2 independent facts before concluding | ✅ | ✅ |
| Missing facts | BLOCKER | BLOCKER |

---

## 9. ANTI-DETECTION — INVISIBLE ARCHITECTURE (like BotQuangAnh)

**Principle**: botquanganh cannot be detected as an AI agent because the MCP
runs locally — the CTF server only sees HTTP from the user's IP/machine. Bot
Dua Chuot keeps the same model:

```
CTF server sees:     normal HTTP requests from the user's machine (like a human)
CTF server does NOT see: MCP · tunnel · AI client · skills · local logs
```

**3 hard barriers:**

| # | Barrier | Content |
|---|---|---|
| 1 | Local-only bridge | MCP on the user's machine; nothing on CTF infrastructure; user's IP (no VPS/datacenter) |
| 2 | Zero AI fingerprint | No opencode/ChatGPT/Claude UA on the wire; no LLM API calls from the host during the event; no telemetry |
| 3 | Human-in-the-loop | Human approves major steps; human submits the flag; the bot only prepares results |

**8 hard OPSEC rules**: (1) local-first, minimal requests · (2) human submission
gate · (3) jitter 0.8–3s, sequential, no blind retries · (4) no automated tools
against scope, browser-user UA · (5) zero outbound while competing · (6) no
traces left on the server (no extra uploads, no account creation) · (7) clean
logs, auto-clean temp files after solving · (8) no DoS/crashing instances; if
crashed → BLOCKER.

---

## 10. CROSS-PLATFORM (all Linux arches + Windows)

**Strategy**: pure-Python core (every platform) + layered Platform Adapter:

```
python-portable  →  native PATH  →  package-mgr (apt/dnf/pacman/apk/zypper/
brew/winget/choco/scoop)  →  WSL2 (Windows)  →  container (rare arches)
```

| Tool | Linux x86_64 | ARM aarch64 | Alpine musl | Windows native | Windows WSL2 |
|---|---|---|---|---|---|
| exiftool (perl) | ✅ | ✅ | ✅ | ⚠️ own Perl | ✅ |
| exiv2 | ✅ | ✅ build | ⚠️ | ✅ | ✅ |
| ffmpeg/ffprobe | ✅ | ✅ | ✅ | ✅ | ✅ |
| tshark/tcpdump | ✅ | ✅ | ⚠️ build | ✅ | ✅ |
| binwalk/vol/Geo Engine (python) | ✅ | ✅ | ✅ | ✅ | ✅ |
| foremost/steghide (C) | ✅ | ⚠️ build | ⚠️ | ❌ | ✅ |
| sleuthkit | ✅ | ✅ build | ⚠️ | ✅ | ✅ |
| yara/tesseract | ✅ | ✅ build | ⚠️ | ✅ | ✅ |

Windows additionally: cmd/powershell-aware executor, path adapter (C:\
UNC case-insensitive), `win_probe` (hives/$MFT/prefetch/LNK pure-python parsers —
also run on Linux when analyzing offline).

---

## 11. FULL MCP TOOL LIST

**Core (inherited, 12):** health · capabilities · fs_list · fs_read · fs_write ·
fs_replace · fs_append · fs_mkdir · fs_search · cmd_check · cmd_run · knowledge

**Investigation (new, 19):**

| Tool | Function |
|---|---|
| `geo_extract` | image/video → raw GPS, exiftool+exiv2 cross-check |
| `coord_convert` | DMS/decimal/UTM/MGRS inter-conversion, datum transform |
| `geo_calc` | distance/bearing/uncertainty (geodesic) |
| `geo_reverse` | offline landmark match |
| `geo_verify` | cross-check >= 2 facts, confidence score |
| `geo_landmark_check` | radius check around a landmark |
| `timezone_at` | lat/lon → timezone (offline) |
| `media_probe` | image/audio/video: metadata + streams + frames |
| `pcap_probe` | flows + geo hints + carving |
| `disk_probe` | fls/fsstat + carve |
| `mem_probe` | vol3 profile + scan |
| `stego_probe` | LSB/audio/carrier detection |
| `ocr_probe` | tesseract + QR/barcode → coordinates |
| `win_probe` | hives/$MFT/prefetch/LNK (pure python) |
| `ops_check` | OPSEC gate for commands/remote targets |
| `ops_jitter` | human-like delay between network queries |
| `ops_redact` | redact secrets before logging |
| `platform` | OS/distro/arch/shell + tool resolution |
| `plan` | investigation plan by artifact type |

---

## 12. ROADMAP (M1–M6)

| Phase | Content | Verify |
|---|---|---|
| **M1 Platform** | Fork `app/` from BotQuangAnh, rename prefix `duachuot_*`, auth+tunnel | `duachuot health`, `config validate` |
| **M2 Geo Engine** | 5 `app/geo/` modules + round-trip tests (DMS<->decimal<->UTM, datum) | `pytest tests/geo/` + 1 real GPS photo |
| **M3 Tool Matrix** | TOOL_CATALOG +30 tools, install geographiclib/piexif/zxing-cpp/tesseract, Platform Adapter | `duachuot knowledge tools --query geo --versions` |
| **M4 Skills** | 4 new skills + playbooks + routing from solve-challenge | run triage → correct skill |
| **M5 OPSEC + 2 modes** | OPSEC gate, `OSINT_MODE`, two-mode policy, win_probe | test case: GPS photo + username + domain |
| **M6 Dogfood** | 2 forensics + 2 OSINT sample challenges, write solve_log + writeup | 4/4 with confidence score |

---

## 13. DEFINITION OF DONE

1. MCP server connectable from ChatGPT/opencode (auth required, operator-only tunnel).
2. Geo Engine passes byte-for-byte round-trips (decimal<->DMS<->UTM, datum transform).
3. Platform Adapter runs on Linux x86_64 + aarch64 + Windows (native/WSL2).
4. Resource Registry generates RESOURCE_MAP.json from the ctf-tools repo; missing → BLOCKER.
5. OPSEC gate working: dry_run before every request, zero telemetry, human submission.
6. 4 new skills load in opencode, correctly routed from solve-challenge.
7. Dogfood 4/4 challenges with writeup + confidence score.
8. Docs: README, SECURITY (two-mode policy), PLAYBOOK ×3.

---

## 14. RISKS & MITIGATIONS

| Risk | Mitigation |
|---|---|
| Online reverse geocoding forbidden while live | offline landmarks + tz datasets |
| Old datums skew coordinates by 100–500 m | record the original datum, note deviation on transform |
| EXIF stripped / coordinates inside a carrier | cross-pipeline: exiftool+exiv2+stego+OCR barcode |
| Tool missing on unusual platforms | Platform Adapter fallback python/WSL2/container |
| Datacenter IP exposed (VPS) | run on the user's machine; VPS forbidden while competing |
| LLM gateway rate limits | dedicated free model / run locally |
| Empty pattern archive | fill after each event via pattern-record-proposal |

---

## 15. FEATURE PROPOSALS

**P0 — required (in M1–M5):**
Platform Adapter · OPSEC gate (dry_run + jitter + zero-telemetry) ·
Resource Registry · shell-aware executor (bash/zsh/cmd/powershell).

**P1 — after M5:**
- `geo_verify` with 3 sources (EXIF + heading + offline landmark + timezone)
- OCR pipeline (tesseract + zxing-cpp QR containing coordinates)
- `win_probe` pure-python parsers
- Cross-tool merged report (exiftool+exiv2+ffprobe+ocr+stego for one file)
- `duachuot plan` — generate an investigation plan before acting
- Standardized 0–1 confidence score with reasons
- Challenge instance guard (detect URL changes between calls)
- Auto-cleanup hook after solving

**Actively discarded:** auto flag submission · pentestcode/sqlmap automated against
scope · online reverse geocoding while ctf-live · telemetry/analytics inside the bot.
