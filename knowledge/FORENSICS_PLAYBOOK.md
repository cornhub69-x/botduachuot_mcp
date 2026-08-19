# Forensics Playbook — BotDuaChuot

Standard playbook for **forensics** tasks (media, pcap, disk, memory, stego, Windows artifacts). Evidence-first: only conclude with >= 2 independent facts, or 1 fact plus a clear chain of reasoning.

## Pipeline by artifact type

### Media (image/video)
1. `duachuot_media_probe` — file + exiftool JSON + ffprobe streams.
2. `duachuot_geo_extract` if GPS exists; otherwise check: thumbnail, comment, XPComment, Creator, Software, timestamps (GPSDateTime vs ModifyDate mismatch → travel hint).
3. `duachuot_stego_probe` — binwalk + steghide info (payload may hold coordinates/flag).
4. `duachuot_ocr_probe` — tesseract text + QR (zxing-cpp) — QR codes often carry coordinates.
5. If LSB is suspected: zsteg, try each plane (stegsolve).

### PCAP
1. `duachuot_pcap_probe` — conversations, endpoints, DNS queries.
2. Geo hints: Wi-Fi probe requests (SSID/AP MAC → landmark), GPS NMEA (`$GPRMC`/`$GPGGA` in payloads), cellular/Bluetooth.
3. Flag hunting: `tshark -Y` + strings; follow HTTP streams to inspect files.
4. If SSH/TLS flows carry certs: extract cert (CN/SAN can be a domain hint).

### Disk image
1. `duachuot_disk_probe` — file → fsstat (type/version) → fls -r (file tree; deleted files marked `*`).
2. Look for: user profiles, desktop, documents, bash history, browser history, recent files.
3. Carve: binwalk / foremost into a scratch dir (never on the original).
4. Passwords/hints: strings on suspect files.

### Memory
1. `duachuot_mem_probe` — info (profile) → pslist → filescan per evidence.
2. Look for: clipboard, network connections (netstat), text dumps, processes with odd names, env/command lines.
3. Warning: never jump to a plugin whose profile is not yet evidenced.

### Stego
1. Signature scan (binwalk), steghide info, zsteg for LSB.
2. If a passphrase is needed: watch for hints in the filename, metadata, challenge description.
3. **No brute force on scope** (OPSEC rule 4).

### Windows artifacts (when no Windows host is available)
1. `duachuot_win_probe` — SAM/SYSTEM hive strings, LNK target strings, prefetch.
2. Check RecentDocs, user.config, MS Office recent files.

## Principles

- **Preserve the original**: all analysis/output to `/tmp` or a derived dir; read the original read-only.
- **Carve into scratch**: foremost/binwalk output goes to its own directory.
- **Missing tool ≠ speculation**: if `tshark`/`vol` is missing → return a clear BLOCKER, never guess results.
- **True versions on the wire**: if the challenge asks for a tool version, run the real version argument, do not invent one.
- **Evidence chain**: record file source + command + output excerpt for every fact.

## Evidence recording

- FACT: value + source (tool, offset, file).
- INFERENCE: derivation with support.
- HYPOTHESIS: not enough facts → wait for the next step.
- BLOCKER: missing tool/data that blocks progress → state exactly what is missing.
