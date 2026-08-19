#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_DIR="${DUACHUOT_BIN_DIR:-$HOME/.local/bin}"
TARGET="$TARGET_DIR/duachuot"
SOURCE="$ROOT_DIR/bin/duachuot"

if [ ! -e "$TARGET" ] && [ ! -L "$TARGET" ]; then
    echo "[i] duachuot is not installed at $TARGET"
    exit 0
fi

resolved="$(readlink -f "$TARGET" 2>/dev/null || true)"
if [ "$resolved" != "$SOURCE" ]; then
    echo "[-] Refusing to remove unrelated executable: $TARGET -> ${resolved:-unknown}" >&2
    exit 1
fi

rm -f "$TARGET"
echo "[+] Removed duachuot symlink: $TARGET"
