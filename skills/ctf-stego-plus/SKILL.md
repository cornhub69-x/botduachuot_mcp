---
name: ctf-stego-plus
description: Solve CTF steganography: signature scan (binwalk), LSB/plane analysis (zsteg, channel noise), steghide info, carving (foremost), and payload decoding. Use when a carrier file likely hides a payload or flag.
---

# CTF Stego Plus

Pipeline (follow in order):

1. **Signature scan**: `duachuot_stego_probe` — binwalk + steghide info. Binwalk finds appended/embedded files; steghide confirms passphrase-protected payloads.
2. **LSB / plane analysis**: zsteg for PNG/BMP LSB; channel noise comparison (LSB plane of R/G/B vs random) to detect hidden data; stegsolve manual review when needed.
3. **Carve**: foremost/binwalk -e into a scratch directory (never on the original).
4. **Payload decode**: once carved, strings/xxd/file; apply common encodings (base64, zlib, XOR with hint key).
5. **Passphrase hints**: filename, metadata comments, challenge description, EXIF Software field.

## Rules

- Never brute-force passphrases on scope (OPSEC rule 4).
- If GPS or metadata coords appear, hand off to ctf-geo for verification.
- Missing tool → BLOCKER with exact missing command; never guess.
- Record evidence: carrier file, tool, offset, extracted bytes excerpt.
