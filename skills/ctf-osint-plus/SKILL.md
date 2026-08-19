---
name: ctf-osint-plus
description: CTF OSINT with strict OPSEC. Local evidence first (metadata, EXIF, OCR, offline landmark reverse-geo); public-source discovery is BLOCKED in ctf-live mode and only allowed in investigation mode. Use when the challenge needs identity/location correlation from supplied artifacts.
---

# CTF OSINT Plus

Core principle: **default mode is `ctf-live`** — the OPSEC gate blocks sherlock/maigret/whois/dnsrecon and search engines. Set `OSINT_MODE=true` (investigation mode) only when the operator confirms external lookups are authorized.

## Workflow

1. **Local evidence first** — everything extractable offline:
   - `duachuot_media_probe` + `duachuot_geo_extract` (GPS in EXIF is often the answer).
   - `duachuot_ocr_probe` (text, QR codes).
   - `duachuot_win_probe` / `duachuot_disk_probe` for artifacts.
2. **Correlate**: username ↔ platforms, domain ↔ certs, coords ↔ offline landmarks, timestamps ↔ offline timezone (`duachuot_timezone_at`).
3. **Investigation mode only** (explicit): sherlock/maigret for usernames, whois/dnsrecon for domains, targeted search per the operator's instructions.
4. **Verify**: >= 2 independent facts per conclusion (e.g. photo metadata + landmark match + timezone).

## OPSEC reminders

- Before any network call: `duachuot_ops_check(kind='remote')`; between calls: `duachuot_ops_jitter()`.
- Never submit flags automatically — always the human.
- Redact logs with `duachuot_ops_redact` before storing.
- Read `knowledge/OSINT_PLAYBOOK.md` for the full playbook and traps.
