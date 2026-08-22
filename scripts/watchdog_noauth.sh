#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

NOAUTH_PORT="${NOAUTH_PORT:-8002}"
MCP_PATH="${MCP_PATH:-/mcp}"
[[ "$MCP_PATH" == /* ]] || MCP_PATH="/$MCP_PATH"
LOOP_PID_FILE="logs/noauth_watchdog.pid"
LOG="logs/noauth_watchdog.log"
CONFIG="${NOAUTH_CONFIG:-$HOME/.config/opencode/opencode.jsonc}"
CONFIG_KEY="botduachuot-host-mcp"
LAST_URL_FILE="logs/noauth_last_url.txt"

mkdir -p logs
echo "$$" > "$LOOP_PID_FILE"

log() { printf '%s [watchdog] %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }

log "watchdog started (pid $$)"

while true; do
    url=$(./gen-link-noauth.sh start 2>/dev/null | grep -o -E 'https://[a-zA-Z0-9-]+\.trycloudflare\.com/mcp' | head -n 1 || true)
    if [ -n "$url" ]; then
        last=""
        [ -f "$LAST_URL_FILE" ] && last=$(cat "$LAST_URL_FILE")
        if [ "$url" != "$last" ]; then
            if [ -f "$CONFIG" ]; then
                if sed -i -E "s#(\"$CONFIG_KEY\"[[:space:]]*:[[:space:]]*\{[^}]*\"url\"[[:space:]]*:[[:space:]]*\")https://[a-zA-Z0-9-]+\.trycloudflare\.com/mcp(\")#\1${url}\2#g" "$CONFIG"; then
                    log "URL updated in config: $url"
                else
                    log "URL changed but config update FAILED: $url"
                fi
            fi
            printf '%s\n' "$url" > "$LAST_URL_FILE"
        fi
    else
        log "no URL obtained from gen-link-noauth.sh"
    fi
    sleep 30
done