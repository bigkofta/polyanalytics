#!/bin/bash
# Sets up launchd agents so Falcon runs automatically:
#   1. alert_monitor.py — starts on login, restarts if it crashes
#   2. daily_brief.py — runs every morning at 07:00 UTC (adjust to your timezone)
#
# Run once: bash setup_launchd.sh
# To uninstall: bash setup_launchd.sh uninstall

FALCON_DIR="$HOME/falcon"
PYTHON=$(which python3)
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

mkdir -p "$LAUNCH_AGENTS"
mkdir -p "$FALCON_DIR/logs"

if [ "$1" = "uninstall" ]; then
    launchctl unload "$LAUNCH_AGENTS/com.falcon.monitor.plist"   2>/dev/null
    launchctl unload "$LAUNCH_AGENTS/com.falcon.daily.plist"     2>/dev/null
    rm -f "$LAUNCH_AGENTS/com.falcon.monitor.plist"
    rm -f "$LAUNCH_AGENTS/com.falcon.daily.plist"
    echo "Uninstalled."
    exit 0
fi

# ── 1. Alert monitor (persistent, restarts on crash) ────────────────────────────
cat > "$LAUNCH_AGENTS/com.falcon.monitor.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.falcon.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$FALCON_DIR/alert_monitor.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$FALCON_DIR</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$FALCON_DIR/logs/monitor.log</string>
    <key>StandardErrorPath</key>
    <string>$FALCON_DIR/logs/monitor_err.log</string>
</dict>
</plist>
EOF

# ── 2. Daily collection (07:00 UTC = adjust Hour to your preference) ─────────────
cat > "$LAUNCH_AGENTS/com.falcon.daily.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.falcon.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$FALCON_DIR/daily_brief.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$FALCON_DIR</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>7</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$FALCON_DIR/logs/daily.log</string>
    <key>StandardErrorPath</key>
    <string>$FALCON_DIR/logs/daily_err.log</string>
</dict>
</plist>
EOF

# Load both
launchctl unload "$LAUNCH_AGENTS/com.falcon.monitor.plist" 2>/dev/null
launchctl unload "$LAUNCH_AGENTS/com.falcon.daily.plist"   2>/dev/null
launchctl load   "$LAUNCH_AGENTS/com.falcon.monitor.plist"
launchctl load   "$LAUNCH_AGENTS/com.falcon.daily.plist"

echo ""
echo "Falcon launchd agents installed:"
echo "  Monitor:  running now, restarts on crash"
echo "  Daily:    fires every day at 07:00 UTC"
echo ""
echo "Check status:"
echo "  launchctl list | grep falcon"
echo "  tail -f $FALCON_DIR/logs/monitor.log"
echo ""
echo "NOTE: For lid-closed operation, go to:"
echo "  System Settings -> Battery -> Options -> Enable 'Wake for network access'"
echo "  (or keep plugged into power)"
