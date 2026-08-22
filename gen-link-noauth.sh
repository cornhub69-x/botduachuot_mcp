#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

source ./scripts/process_helpers.sh

NOAUTH_PORT="${NOAUTH_PORT:-8002}"
MCP_PATH="${MCP_PATH:-/mcp}"
[[ "$MCP_PATH" == /* ]] || MCP_PATH="/$MCP_PATH"
SERVER_LOG="logs/noauth_server.log"
TUNNEL_LOG="logs/noauth_tunnel.log"
SERVER_PID_FILE="logs/noauth_server.pid"
TUNNEL_PID_FILE="logs/noauth_tunnel.pid"
URL_FILE="logs/noauth_url.txt"

start_server() {
    local existing=""
    existing=$(read_pid_file "$SERVER_PID_FILE")
    if pid_matches_kind "$existing" server; then
        return 0
    fi
    rm -f "$SERVER_PID_FILE"
    export PYTHONPATH="$ROOT_DIR"
    export FASTMCP_MESSAGE_PATH="$MCP_PATH"
    export TESSDATA_PREFIX="${TESSDATA_PREFIX:-$HOME/.local/share/tessdata}"
    REQUIRE_AUTH=false nohup .venv/bin/fastmcp run app/main.py \
        --transport streamable-http \
        --host 127.0.0.1 \
        --port "$NOAUTH_PORT" \
        --path "$MCP_PATH" \
        > "$SERVER_LOG" 2>&1 &
    atomic_write_runtime_file "$SERVER_PID_FILE" "$!"
    echo "[*] NoAuth server started (PID $!)." >&2
}

start_tunnel() {
    local existing=""
    existing=$(read_pid_file "$TUNNEL_PID_FILE")
    if pid_matches_kind "$existing" tunnel; then
        return 0
    fi
    rm -f "$TUNNEL_PID_FILE" "$URL_FILE"
    : > "$TUNNEL_LOG"
    nohup cloudflared tunnel --url "http://127.0.0.1:${NOAUTH_PORT}" \
        > "$TUNNEL_LOG" 2>&1 &
    atomic_write_runtime_file "$TUNNEL_PID_FILE" "$!"
    echo "[*] NoAuth tunnel started (PID $!)." >&2
}

stop_all() {
    stop_managed_pid_file "$TUNNEL_PID_FILE" tunnel "NoAuth Tunnel"
    stop_managed_pid_file "$SERVER_PID_FILE" server "NoAuth Server"
    rm -f "$URL_FILE"
}

action="${1:-start}"
case "$action" in
    start)
        ;;
    stop)
        stop_all
        exit 0
        ;;
    *)
        echo "Usage: $0 [start|stop]" >&2
        exit 2
        ;;
esac

start_server
start_tunnel

for _ in $(seq 1 120); do
    url=$(grep -o -E 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -n 1 || true)
    if [ -n "$url" ] && curl -s -o /dev/null --max-time 1 "http://127.0.0.1:${NOAUTH_PORT}/healthz"; then
        printf '%s\n' "${url}${MCP_PATH}"
        exit 0
    fi
    sleep 0.5
done

echo "[-] Timeout waiting for noauth URL. Check $SERVER_LOG and $TUNNEL_LOG." >&2
exit 1