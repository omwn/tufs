#!/usr/bin/env bash
# run.sh
#
# Serves docs/ locally for testing the Cygnet web UI.
#
# Usage: bash run.sh
# Then open the printed URL in a browser.

set -euo pipefail

THIS_DIR="$(cd "$(dirname "$0")" && pwd)"
CYGNET_DIR="$THIS_DIR/external/cygnet"

if [[ ! -d "$CYGNET_DIR" ]]; then
    echo "Error: cygnet not found at $CYGNET_DIR" >&2
    exit 1
fi

exec bash "$CYGNET_DIR/run.sh" "$THIS_DIR/docs/"
