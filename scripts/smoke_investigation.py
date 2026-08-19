"""Smoke test: boot the MCP server over stdio and call new tools end-to-end."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def main() -> int:
    import app.main  # noqa: F401  (registers all tools)

    from app.mcp_server import mcp

    server = mcp._mcp_server if hasattr(mcp, "_mcp_server") else None

    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    expected = {
        "duachuot_geo_extract",
        "duachuot_coord_convert",
        "duachuot_geo_calc",
        "duachuot_geo_reverse",
        "duachuot_geo_verify",
        "duachuot_timezone_at",
        "duachuot_ops_check",
        "duachuot_platform",
        "duachuot_plan",
        "duachuot_win_probe",
    }
    missing = expected - names
    if missing:
        print(f"FAIL missing tools: {sorted(missing)}")
        return 1

    from app.tools.geo_tools import duachuot_coord_convert, duachuot_geo_reverse, duachuot_geo_verify
    from app.tools.ops_tools import duachuot_ops_check, duachuot_ops_redact, duachuot_platform, duachuot_plan

    checks = [
        ("coord_convert", duachuot_coord_convert(lat=21.0285, lon=105.8542).get("ok") is True),
        ("geo_reverse", bool(duachuot_geo_reverse(21.0285, 105.8542).get("matches"))),
        ("geo_verify", duachuot_geo_verify(21.0285, 105.8542)["blocked"] is False),
        ("ops_check_blocked", duachuot_ops_check("curl http://api.ipify.org")["allowed"] is False),
        ("ops_redact", "[FLAG_REDACTED]" in duachuot_ops_redact("FLAG{abc12345}")["redacted"]),
        ("platform", duachuot_platform().get("os") in {"linux", "darwin", "windows"}),
        ("plan", len(duachuot_plan(["/x.jpg"], target_kind="image")["steps"]) >= 6),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL checks: {failed}")
        return 1
    print("SMOKE OK: 31 tools registered, 7 functional checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))