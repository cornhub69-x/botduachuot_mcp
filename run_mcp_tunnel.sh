#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# shellcheck source=scripts/process_helpers.sh
source ./scripts/process_helpers.sh

SUPERVISOR_PID_FILE="logs/watchdog.pid"
LAUNCHER_PID_FILE="logs/launcher.pid"
SERVER_PID_FILE="logs/server.pid"
TUNNEL_PID_FILE="logs/tunnel.pid"
TUNNEL_URL_FILE="logs/tunnel_url.txt"
LAUNCHER_LOG="logs/launcher.log"

launch_supervisor() {
    mkdir -p logs
    nohup "$ROOT_DIR/scripts/start_tunnel_server.sh" >> "$LAUNCHER_LOG" 2>&1 &
    atomic_write_runtime_file "$LAUNCHER_PID_FILE" "$!"
    echo "[+] Tunnel supervisor launched (PID $!)."
}

action="${1:-status}"
case "$action" in
    start)
        launch_supervisor
        ;;
    stop)
        "$ROOT_DIR/scripts/stop_tunnel_server.sh"
        rm -f "$LAUNCHER_PID_FILE"
        ;;
    restart)
        "$ROOT_DIR/scripts/stop_tunnel_server.sh"
        rm -f "$LAUNCHER_PID_FILE"
        launch_supervisor
        ;;
    status)
        report() {
            local file="$1" kind="$2" label="$3" pid=""
            pid=$(read_pid_file "$file")
            if pid_matches_kind "$pid" "$kind"; then
                echo "[+] $label running (PID $pid)."
            else
                echo "[-] $label not running."
            fi
        }
        report "$SUPERVISOR_PID_FILE" supervisor "Supervisor"
        report "$SERVER_PID_FILE" server "MCP Server"
        report "$TUNNEL_PID_FILE" tunnel "Cloudflare Tunnel"
        if [ -s "$TUNNEL_URL_FILE" ]; then
            echo "[i] Connector URL: $(cat "$TUNNEL_URL_FILE")"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}" >&2
        exit 2
        ;;
esac