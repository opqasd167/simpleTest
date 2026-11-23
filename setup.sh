#!/usr/bin/env sh
# One command to set up everything for testing (macOS / Linux):  ./setup.sh   [--yes] [--offline]
set -e
cd "$(dirname "$0")"
for py in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    exec "$py" scripts/onboard.py "$@"
  fi
done
echo "Python 3.11+ not found. Install it from https://www.python.org/downloads/ and re-run ./setup.sh" >&2
exit 1
