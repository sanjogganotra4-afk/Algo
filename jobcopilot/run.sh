#!/bin/bash
# Convenience wrapper: create venv if needed, then run a subcommand.
#   ./run.sh setup    -> setup wizard
#   ./run.sh start     -> launch copilot + dashboard (default)
#   ./run.sh parse CV  -> parse a .docx CV
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV="$SCRIPT_DIR/venv"
PY="$VENV/bin/python"

if [ ! -x "$PY" ]; then
    echo "Creating virtual environment…"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
    echo "Dependencies installed."
fi

cd "$SCRIPT_DIR"
case "${1:-start}" in
  setup)  exec "$PY" -m jobcopilot.setup_wizard ;;
  parse)  exec "$PY" -m jobcopilot.resume_parser "$2" ;;
  start)  exec "$PY" -m jobcopilot.orchestrator ;;
  *)      exec "$PY" -m jobcopilot.orchestrator ;;
esac
