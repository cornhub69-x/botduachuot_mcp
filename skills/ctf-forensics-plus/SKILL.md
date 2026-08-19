---
name: ctf-forensics-plus
description: Deep-dive CTF forensics with evidence-first triage: media metadata, PCAP, disk images, and memory images. Use after initial triage when the challenge is a media/pcap/disk/memory artifact and the technique family is uncertain.
---

# CTF Forensics Plus

Covers: media/photo metadata + GPS, PCAP analysis, disk image analysis, memory forensics, and general artifact triage. Never analyze an artifact without first recording its provenance.

## Per-artifact pipeline

- **Media**: `duachuot_media_probe` → `duachuot_geo_extract` → `duachuot_stego_probe` → `duachuot_ocr_probe`. Inspect thumbnail, comments, Software/Creator, and timestamp gaps (GPSDateTime vs ModifyDate = travel hint).
- **PCAP**: `duachuot_pcap_probe` (conversations, endpoints, DNS). Look for Wi-Fi probe requests (AP MAC/SSID → location hint), NMEA `$GPRMC`/`$GPGGA`, cert CN/SAN in TLS flows, and HTTP payloads. Filter with tshark -Y; never live-capture on scope.
- **Disk image**: `duachuot_disk_probe` (fsstat + fls -r). Note deleted files (`*`), user profiles, history files, browser data. Carve with binwalk/foremost into a scratch directory only.
- **Memory**: `duachuot_mem_probe` (windows.info/linux.info → pslist → filescan). Evidence the profile before trusting plugin output. Look for clipboard, netstat, dumps, unusual processes, command lines.

## Rules

- Preserve originals: read-only access; all derived output to scratch dirs.
- Missing tool → BLOCKER with the exact missing command; never guess results.
- Report every fact with source (file + tool + offset when available).
- GPS found in any artifact: hand off to ctf-geo for coordinate verification.
- Read `knowledge/FORENSICS_PLAYBOOK.md` for the full pipeline and trap table.
