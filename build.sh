#!/usr/bin/env bash
# build.sh
#
# Builds TUFS WordNet LMF XML files, then packages them into Cygnet
# databases and deploys the web UI to docs/.
#
# Usage: bash build.sh [--lmf-only] [--cygnet-only]
#   --lmf-only      Build LMF XML only (skip Cygnet packaging)
#   --cygnet-only   Run Cygnet packaging only (skip LMF XML build)

set -euo pipefail

VERSION="2.0"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CYGNET_DIR="$(cd "$PROJECT_DIR/../cygnet" && pwd)"
BLDDIR="$PROJECT_DIR/build/tufs-$VERSION"
CYGNET_WORK="$PROJECT_DIR/build/cygnet-work"
LANGFILE="$PROJECT_DIR/tufsdata/languages.txt"

DO_LMF=true
DO_CYGNET=true

for arg in "$@"; do
    case "$arg" in
        --lmf-only)    DO_CYGNET=false ;;
        --cygnet-only) DO_LMF=false ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: bash build.sh [--lmf-only] [--cygnet-only]" >&2
            exit 1
            ;;
    esac
done

# ── 0. Python environment ────────────────────────────────────────────────────
VENV="$PROJECT_DIR/.venv312"
if [[ ! -d "$VENV" ]]; then
    uv venv --python 3.12 "$VENV"
    uv pip install --quiet -r "$PROJECT_DIR/requirements.txt" \
        -e /home/bond/git/wn_edit \
        --python "$VENV/bin/python"
fi
# shellcheck source=/dev/null
source "$VENV/bin/activate"

# ── 1. Build LMF XML ─────────────────────────────────────────────────────────
if $DO_LMF; then
    echo "=== Building intermediate TSV ==="
    python "$PROJECT_DIR/munge.py"

    echo "=== Building LMF XML ==="
    python "$PROJECT_DIR/tufs2wn.py"
    echo
fi

# ── 2. Stage XMLs and run Cygnet ─────────────────────────────────────────────
if $DO_CYGNET; then
    echo "=== Running Cygnet packaging ==="

    if [[ ! -d "$CYGNET_DIR" ]]; then
        echo "Error: cygnet not found at $CYGNET_DIR" >&2
        echo "Clone it with: git clone https://github.com/globalwordnet/cygnet ../cygnet" >&2
        exit 1
    fi

    mkdir -p "$CYGNET_WORK/bin/raw_wns"
    cp "$PROJECT_DIR/etc/wordnets.toml" "$CYGNET_WORK/wordnets.toml"

    # Pre-stage each language XML so Cygnet skips the download step.
    # Stem matching: URL tufs-{lang}-2.0.tar.xz → stem tufs-{lang} → looks for tufs-{lang}*.xml
    while IFS='|' read -r local_code _bcp47 _en _native; do
        [[ -z "$local_code" ]] && continue
        src="$PROJECT_DIR/build/lmf/tufs-$local_code.xml"
        dst="$CYGNET_WORK/bin/raw_wns/tufs-$local_code.xml"
        if [[ -f "$src" ]]; then
            cp "$src" "$dst"
        else
            echo "Warning: $src not found — Cygnet will attempt to download it." >&2
        fi
    done < "$LANGFILE"

    bash "$CYGNET_DIR/build.sh" --work-dir "$CYGNET_WORK"

    echo
    echo "=== Deploying to docs/ ==="
    mkdir -p "$PROJECT_DIR/docs"
    cp "$CYGNET_DIR/web/index.html"          "$PROJECT_DIR/docs/"
    cp "$CYGNET_DIR/web/relations.json"       "$PROJECT_DIR/docs/"
    cp "$CYGNET_DIR/web/omw-logo.svg"         "$PROJECT_DIR/docs/" 2>/dev/null || true
    cp "$PROJECT_DIR/etc/local.json"          "$PROJECT_DIR/docs/"
    cp "$CYGNET_WORK/web/cygnet.db.gz"        "$PROJECT_DIR/docs/tufs.db.gz"
    cp "$CYGNET_WORK/web/provenance.db.gz"    "$PROJECT_DIR/docs/tufs-provenance.db.gz"
    echo "Done — docs/ is ready for GitHub Pages."
fi
