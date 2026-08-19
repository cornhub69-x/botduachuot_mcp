# OSINT Playbook — BotDuaChuot

Standard playbook for **OSINT** tasks. Two modes: `ctf-live` (default, public discovery **blocked** — only local evidence is allowed) and `investigation` (`OSINT_MODE=true` allows public discovery).

## Rules of engagement

- **ctf-live**: no web search, no public discovery (whois/sherlock/maigret/Shodan-style), no online reverse geocoding. Only the evidence in the working directory counts.
- **investigation**: public discovery is allowed but **still gated**: no telemetry hosts (Apple/Google/Microsoft/Amazon...), no brute force, no attacks on the target.
- Every remote request goes through `duachuot_ops_check` first.

## Pipeline

1. **Inventory local evidence** — `duachuot_list_directory` + `duachuot_search_text` over the workspace for: coordinates, IPs, domains, usernames, emails, timestamps.
2. **Match against local datasets**:
   - coordinates → landmarks.json via `duachuot_geo_reverse` / `duachuot_geo_verify`
   - IP/domain → pcap/DNS/HTTP evidence
   - username/email → strings in disk images, chat logs, credentials
3. **Reconcile timelines** — file mtimes, EXIF timestamps, Wi-Fi probe logs; mismatch = lead.
4. **Conclude only with >= 2 independent facts** (e.g., landmark + timezone, username + profile, IP + ASN). Otherwise record a BLOCKER.
5. **Report with provenance** — source + derivation for every conclusion.

## Evidence-first rules

- Never use tools whose output you cannot verify locally.
- Never run discovery tools against the target infrastructure (no port scanning of scope).
- Never submit a flag guessed from incomplete evidence — human-in-the-loop submits.

## Recording

- FACT: value + source.
- INFERENCE: derivation with support.
- HYPOTHESIS: unproven lead.
- BLOCKER: what is missing (tool, mode, data).
