"""MCP adapters — OPSEC gate, platform info, and investigation planner."""

from __future__ import annotations

from typing import Any, Optional

from app.mcp_server import mcp
from app.ops.gate import (
    gate_command,
    gate_remote_request,
    redact_secrets,
    suggest_jitter_seconds,
)
from app.platform import probe_platform, tool_supported
from app.security import format_error_response


@mcp.tool(
    name="duachuot_ops_check",
    description=(
        "Inspect a remote target or host command against OPSEC rules before "
        "execution: telemetry hosts, forbidden automated attack tools, "
        "public-source discovery in ctf-live mode, and flag-like strings. "
        "Returns allowed/blocked with the rule and mode."
    ),
)
def duachuot_ops_check(
    target: str,
    kind: str = "command",
    mode: Optional[str] = None,
    dry_run: Optional[bool] = None,
) -> dict[str, Any]:
    try:
        if kind == "remote":
            result = gate_remote_request(target, mode=mode, dry_run=dry_run)
        else:
            result = gate_command(target, mode=mode, dry_run=dry_run)
        return {"ok": True, **result}
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_ops_jitter",
    description=(
        "Return the suggested human-like delay (seconds) to wait before the next "
        "remote request, so traffic stays sequential and natural."
    ),
)
def duachuot_ops_jitter() -> dict[str, Any]:
    return {
        "ok": True,
        "delay_seconds": suggest_jitter_seconds(),
        "range_ms": [800, 3000],
    }


@mcp.tool(
    name="duachuot_ops_redact",
    description=(
        "Redact secrets, tokens, and flag-like strings from a text/log excerpt "
        "before it is stored or displayed."
    ),
)
def duachuot_ops_redact(text: str) -> dict[str, Any]:
    return {"ok": True, "redacted": redact_secrets(text)}


@mcp.tool(
    name="duachuot_platform",
    description=(
        "Probe the host platform: OS, architecture, distro, shell, and package "
        "managers. Also resolve a single tool's availability and method "
        "(native / WSL / missing) for cross-platform work."
    ),
)
def duachuot_platform(tool: Optional[str] = None) -> dict[str, Any]:
    try:
        probe = probe_platform()
        if tool:
            probe["tool"] = tool_supported(tool)
        return {"ok": True, **probe}
    except Exception as exc:
        return format_error_response(exc)


@mcp.tool(
    name="duachuot_plan",
    description=(
        "Generate a structured investigation plan for a supplied evidence set "
        "(paths, artifact types, hints). Returns ordered steps with the tool to "
        "use per step, aligned with the Geo/forensics pipeline and OPSEC rules."
    ),
)
def duachuot_plan(
    artifact_paths: list[str],
    hints: Optional[list[str]] = None,
    target_kind: str = "image",
) -> dict[str, Any]:
    try:
        hints = hints or []
        steps: list[dict[str, Any]] = []

        pipeline: dict[str, list[dict[str, Any]]] = {
            "image": [
                {"step": "triage", "tool": "duachuot_media_probe", "note": "metadata + format"},
                {"step": "geo_extract", "tool": "duachuot_geo_extract", "note": "GPS cross-checked"},
                {"step": "geo_reverse", "tool": "duachuot_geo_reverse", "note": "offline landmarks"},
                {"step": "geo_verify", "tool": "duachuot_geo_verify", "note": ">=2 facts + confidence"},
                {"step": "stego_probe", "tool": "duachuot_stego_probe", "note": "carved/LSB payload"},
                {"step": "ocr_probe", "tool": "duachuot_ocr_probe", "note": "text + QR coordinates"},
            ],
            "pcap": [
                {"step": "triage", "tool": "duachuot_pcap_probe", "note": "flows + endpoints"},
                {"step": "geo_hints", "tool": "tshark", "note": "Wi-Fi probes / NMEA / GPS"},
                {"step": "carve", "tool": "binwalk", "note": "embedded files"},
            ],
            "disk": [
                {"step": "triage", "tool": "duachuot_disk_probe", "note": "fsstat + fls"},
                {"step": "carve", "tool": "foremost", "note": "deleted files"},
            ],
            "memory": [
                {"step": "triage", "tool": "duachuot_mem_probe", "note": "profile + pslist"},
                {"step": "scan", "tool": "vol", "note": "filescan per evidence"},
            ],
            "windows": [
                {"step": "triage", "tool": "duachuot_win_probe", "note": "hives/LNK/prefetch"},
            ],
        }
        for entry in pipeline.get(target_kind, pipeline["image"]):
            steps.append(
                {
                    "phase": entry["step"],
                    "action": f"call {entry['tool']} on the primary artifact",
                    "tool": entry["tool"],
                    "note": entry["note"],
                }
            )
        if hints:
            steps.append(
                {
                    "phase": "cross_check",
                    "action": "verify hints against extracted facts",
                    "tool": "duachuot_geo_verify",
                    "note": f"hints: {', '.join(hints[:5])}",
                }
            )
        steps.append(
            {
                "phase": "handoff",
                "action": "write solve_log.md + writeup; human reviews and submits",
                "tool": "duachuot_ops_redact",
                "note": "OPSEC: redact secrets; human submission gate",
            }
        )
        return {
            "ok": True,
            "target_kind": target_kind,
            "artifacts": artifact_paths,
            "steps": steps,
            "opsec": {
                "mode": "investigation" if _osint_mode() else "ctf-live",
                "remote_minimal": True,
                "human_submission": True,
            },
        }
    except Exception as exc:
        return format_error_response(exc)


def _osint_mode() -> bool:
    import app.config

    return app.config.OSINT_MODE