#!/usr/bin/env bash
# Launch the ERTERFACE farm UI (with the embedded capture session) from the
# desktop. Double-click this file, or the ERTerface launcher on the Desktop.
# Uses the thesis repo's venv (../.venv); output goes to erterface.log here.
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PYTHON="$HERE/../.venv/bin/python"
LOG="$HERE/erterface.log"

if [[ ! -x "$PYTHON" ]]; then
    msg="Python venv not found at $PYTHON. Create it in the thesis repo (with --system-site-packages on the Pi)."
    echo "$msg" >&2
    command -v zenity >/dev/null && zenity --error --text="$msg"
    exit 1
fi

cd "$HERE"
exec "$PYTHON" app.py "$@" >>"$LOG" 2>&1
