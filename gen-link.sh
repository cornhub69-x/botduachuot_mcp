#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

source ./scripts/process_helpers.sh

TUNNEL_URL_FILE="logs/tunnel_url.txt"
MCP_PATH="$(.venv/bin/python - <<'PY' 2>/dev/null || true
from dotenv import dotenv_values
print(dotenv_values('.env').get('MCP_PATH') or '/mcp')
PY
)"
MCP_PATH="${MCP_PATH:-/mcp}"
[[ "$MCP_PATH" == /* ]] || MCP_PATH="/$MCP_PATH"

if ! pid_matches_kind "$(read_pid_file logs/watchdog.pid)" supervisor; then
    echo "[*] Starting tunnel..." >&2
    ./run_mcp_tunnel.sh start >/dev/null
fi

for _ in $(seq 1 120); do
    url=$(head -n 1 "$TUNNEL_URL_FILE" 2>/dev/null || true)
    if [[ "$url" =~ ^https://[a-zA-Z0-9-]+\.trycloudflare\.com/?$ ]]; then
        printf '%s\n' "${url%/}${MCP_PATH}"
        exit 0
    fi
    sleep 0.5
done

echo "[-] Timeout waiting for tunnel URL. Check logs/launcher.log and logs/cloudflared.log." >&2
exit 1