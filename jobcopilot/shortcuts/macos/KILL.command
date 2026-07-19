#!/bin/bash
# Double-click ANYTIME to instantly pause the copilot (offline fallback).
cd "$(dirname "$0")/../.." || exit 1
echo "stopped" > KILL_SWITCH.flag
echo "🛑 Kill switch engaged — copilot scoring is paused."
echo "   Delete KILL_SWITCH.flag (or press RESUME in the dashboard) to continue."
sleep 2
