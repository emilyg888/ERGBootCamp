#!/bin/bash
# ERGBootCamp — install_launchd.sh
# Installs the 06:30 daily WhatsApp brief as a macOS launchd agent.
# Run once after setup: bash scripts/install_launchd.sh

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_SRC="$PROJECT_DIR/launchd/com.ergbootcamp.daily_brief.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.ergbootcamp.daily_brief.plist"

echo "ERGBootCamp launchd installer"
echo "Project: $PROJECT_DIR"

# Patch the plist with the real absolute path
sed "s|/ABSOLUTE/PATH/TO/ERGBootCamp|$PROJECT_DIR|g" "$PLIST_SRC" > "$PLIST_DST"

echo "Plist installed -> $PLIST_DST"

# Unload if already running
launchctl unload "$PLIST_DST" 2>/dev/null || true

# Load the agent
launchctl load "$PLIST_DST"

echo ""
echo "Installed! The daily brief will fire at 06:30 every morning."
echo ""
echo "Useful commands:"
echo "  Trigger now:    launchctl start com.ergbootcamp.daily_brief"
echo "  Check status:   launchctl list | grep ergbootcamp"
echo "  View logs:      tail -f $PROJECT_DIR/logs/daily_brief.log"
echo "  Uninstall:      launchctl unload $PLIST_DST && rm $PLIST_DST"
