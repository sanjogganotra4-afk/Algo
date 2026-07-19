#!/bin/bash
# Double-click to start the copilot + dashboard, then open it in your browser.
cd "$(dirname "$0")/../.." || exit 1
( sleep 3; open "http://127.0.0.1:8000" ) &
./run.sh start
