#!/bin/bash
# Double-click to run the setup wizard.
cd "$(dirname "$0")/../.." || exit 1
./run.sh setup
echo ""
read -n 1 -s -r -p "Press any key to close…"
