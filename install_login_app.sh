#!/usr/bin/env bash
# Set up the watcher to start at login via a small app.
#
# The app (not a LaunchAgent) is what macOS grants Downloads access to, so the
# first time it runs you must click Allow on the Downloads prompt.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
APP="$HOME/Applications/DownloadDate Watcher.app"

# ── 1. Set up venv + install watchdog ────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    BASE_PYTHON="$(command -v python3)"
    echo "Creating venv at $VENV using $BASE_PYTHON..."
    "$BASE_PYTHON" -m venv "$VENV"
fi

if ! "$VENV/bin/python3" -c "import watchdog" 2>/dev/null; then
    echo "Installing watchdog..."
    "$VENV/bin/pip" install --quiet watchdog
fi

# ── 2. Build the app ─────────────────────────────────────────────────────────
mkdir -p "$HOME/Applications"
osacompile -o "$APP" "$SCRIPT_DIR/launch_watcher.applescript"
echo "Built $APP"

# ── 3. Add to Login Items (replaces any existing entry) ──────────────────────
osascript -e 'tell application "System Events" to delete (every login item whose name is "DownloadDate Watcher")' 2>/dev/null || true
osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$APP\", hidden:true}"
echo "Added to Login Items."
echo "Open '$APP' once and click Allow on the Downloads prompt."
