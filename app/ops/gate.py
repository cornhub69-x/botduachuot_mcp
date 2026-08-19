"""OPSEC Gate — keep the bot invisible and rule-compliant during CTF.

Eight hard rules from the plan:
1. local-first, minimal remote requests
2. human submission gate (never submit flags)
3. sequential requests with jitter (no parallel bursts, no blind retries)
4. no automated attack tools against scope; browser UA on wire
5. zero telemetry / zero outbound except operator tunnel
6. no traces left on challenge servers
7. clean logs (no secrets), auto cleanup after solve
8. never DoS / crash an instance; report BLOCKER honestly
"""

from __future__ import annotations

import random
import re
import time
from typing import Any, Optional

import app.config

_TELEMETRY_HOSTS = re.compile(
    r"(ip-api\.com|api\.ipify\.org|ifconfig\.me|wtfismyip\.com|"
    r"geoip-db\.com|ipinfo\.io|api\.shodan\.io|censys\.io|"
    r"telemetry\..*|analytics\..*)",
    re.IGNORECASE,
)

_SCOPE_HOST = re.compile(r"^[a-zA-Z0-9.-]+:\d+$|^https?://[a-zA-Z0-9.-]+")
_FLAG_MARKERS = re.compile(r"\b(flag|ctf|eno|htb|pico)\{[^}\s]{4,}\}", re.IGNORECASE)

# Tools that must never run automatically against a challenge scope.
_FORBIDDEN_SCOPE_TOOLS = (
    "sqlmap",
    "nikto",
    "nmap",
    "hydra",
    "masscan",
    "ffuf",
    "gobuster",
    "dirb",
    "wpscan",
    "metasploit",
    "msfconsole",
)


class OpsGateError(Exception):
    pass


def jitter_delay() -> float:
    """Human-like delay between remote requests (config bounded)."""
    return random.uniform(app.config.OPSEC_JITTER_MIN_MS, app.config.OPSEC_JITTER_MAX_MS) / 1000.0


def gate_remote_request(
    target: str,
    *,
    mode: str | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """Inspect an outbound request against OPSEC rules before it is sent.

    mode: 'ctf-live' (default) or 'investigation'. dry_run: when True the
    request is described but NOT executed (caller responsibility).
    """
    mode = mode or ("investigation" if app.config.OSINT_MODE else "ctf-live")
    dry_run = app.config.DRY_RUN_DEFAULT if dry_run is None else dry_run

    if not target or not str(target).strip():
        raise OpsGateError("target must not be empty")

    if _TELEMETRY_HOSTS.search(target):
        return _blocked(
            target, "telemetry_host", mode, dry_run,
            "target matches a telemetry/geolocation/OSINT aggregation service; zero-telemetry rule",
        )

    for tool in _FORBIDDEN_SCOPE_TOOLS:
        if re.search(rf"\b{re.escape(tool)}\b", target, re.IGNORECASE):
            return _blocked(
                target, "forbidden_scope_tool", mode, dry_run,
                f"automated attack tool '{tool}' must not be invoked against challenge scope; run manually by the user",
            )

    if mode == "ctf-live":
        if _is_public_discovery(target):
            return _blocked(
                target, "public_discovery_ctf_live", mode, dry_run,
                "public-source discovery is prohibited while a CTF is live; switch to investigation mode for authorized lookups",
            )
        return _allowed(target, mode, dry_run, "ctf-live request within operator scope")

    return _allowed(target, mode, dry_run, "investigation mode; operator is responsible for authorization")


def _is_public_discovery(target: str) -> bool:
    lowered = target.lower()
    discovery = (
        "sherlock",
        "maigret",
        "holehe",
        "theharvester",
        "whois ",
        "dnsrecon",
        "shodan",
        "censys",
        "google.com/search",
        "bing.com/search",
        "duckduckgo.com",
        "github.com/search",
    )
    return any(token in lowered for token in discovery)


def gate_command(command: str, *, mode: str | None = None, dry_run: bool | None = None) -> dict[str, Any]:
    """Inspect a local host command for telemetry/scope/cleanliness violations."""
    mode = mode or ("investigation" if app.config.OSINT_MODE else "ctf-live")
    dry_run = app.config.DRY_RUN_DEFAULT if dry_run is None else dry_run

    if _TELEMETRY_HOSTS.search(command):
        return _blocked(command, "telemetry_host", mode, dry_run,
                        "command references a telemetry/geolocation service")

    for tool in _FORBIDDEN_SCOPE_TOOLS:
        if re.search(rf"\b{re.escape(tool)}\b", command, re.IGNORECASE):
            return _blocked(command, "forbidden_scope_tool", mode, dry_run,
                            f"automated attack tool '{tool}' is not allowed against scope")

    if mode == "ctf-live" and _is_public_discovery(command):
        return _blocked(command, "public_discovery_ctf_live", mode, dry_run,
                        "public-source discovery tools are disabled in ctf-live mode")

    if _FLAG_MARKERS.search(command):
        return _blocked(command, "flag_in_command", mode, dry_run,
                        "command embeds a flag-like string; flags must only be displayed to the human, never submitted programmatically")

    return _allowed(command, mode, dry_run, "command passes OPSEC inspection")


def redact_secrets(text: str) -> str:
    """Redact token/session/flag-like material from logs."""
    redacted = _FLAG_MARKERS.sub("[FLAG_REDACTED]", text)
    redacted = re.sub(
        r"(?i)(bearer\s+)[a-z0-9._-]{16,}", r"\1[TOKEN_REDACTED]", redacted
    )
    redacted = re.sub(
        r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        redacted,
    )
    return redacted


def _blocked(
    subject: str, rule: str, mode: str, dry_run: bool, message: str
) -> dict[str, Any]:
    return {
        "allowed": False,
        "rule": rule,
        "mode": mode,
        "dry_run": dry_run,
        "subject": subject[:500],
        "message": message,
    }


def _allowed(subject: str, mode: str, dry_run: bool, message: str) -> dict[str, Any]:
    return {
        "allowed": True,
        "rule": None,
        "mode": mode,
        "dry_run": dry_run,
        "subject": subject[:500],
        "message": message,
    }


def suggest_jitter_seconds() -> float:
    """Return a concrete jitter delay in seconds for the next remote step."""
    return round(jitter_delay(), 3)