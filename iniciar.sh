#!/bin/sh
# Bildumargi - arranque en Linux y macOS
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 iniciar.py
fi
exec python iniciar.py
