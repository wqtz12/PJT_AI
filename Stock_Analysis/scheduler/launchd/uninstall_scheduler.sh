#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Stock Analysis Scheduler - macOS launchd 제거 스크립트
# ═══════════════════════════════════════════════════════════════

PLIST_NAME="com.stock-analysis.scheduler.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

echo "Stock Analysis Scheduler - Uninstall"
echo ""

if [ -f "${PLIST_DST}" ]; then
    echo "Unloading launchd agent..."
    launchctl unload "${PLIST_DST}" 2>/dev/null || true

    echo "Removing plist file..."
    rm -f "${PLIST_DST}"

    echo ""
    echo "Uninstall complete."
    echo "Note: Scheduler data (history, reports) is preserved."
else
    echo "Scheduler is not installed."
fi
