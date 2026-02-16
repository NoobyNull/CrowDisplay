#!/usr/bin/env bash
set -euo pipefail

# Run from project root so Nuitka can resolve "companion.*" imports
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Use project venv if available, else system python
if [ -d "$PROJECT_ROOT/.venv" ]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python3"
    echo "Using venv: $PROJECT_ROOT/.venv"
else
    PYTHON=python3
fi

# Check dependencies
command -v "$PYTHON" >/dev/null || { echo "python3 not found"; exit 1; }
"$PYTHON" -c "import nuitka" 2>/dev/null || { echo "Install nuitka: pip install nuitka"; exit 1; }

"$PYTHON" -m nuitka \
    --standalone \
    --onefile \
    --enable-plugin=pyside6 \
    --include-data-dir=companion/data=companion/data \
    --include-package=companion \
    --include-package=dbus_next \
    --nofollow-import-to=companion.ui.editor_main \
    --output-filename=crowpanel-tray \
    --output-dir=companion/build \
    --remove-output \
    --assume-yes-for-downloads \
    companion/crowpanel_tray.py

echo "Built: companion/build/crowpanel-tray"
