#!/usr/bin/env bash
# build.sh
#
# Builds TUFS WordNet LMF XML files, then packages them into Cygnet
# databases and deploys the web UI to docs/.
#
# Usage: bash build.sh [--lmf-only] [--cygnet-only]
#   --lmf-only      Build LMF XML only (skip Cygnet packaging)
#   --cygnet-only   Run Cygnet packaging only (skip LMF XML build)
#
#  If you want to use a copy of cygnet locally, simlink it external/cygnet
#  otherwise it will download the latest version

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(cat "$PROJECT_DIR/VERSION")"
CYGNET_DIR="$PROJECT_DIR/external/cygnet"
SCRIPT_DIR="$PROJECT_DIR/scripts"
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



# ── 0. Python environment and dependencies ───────────────────────────────────
echo "=== Prepare environment and dependencies ==="
mkdir -p  "$PROJECT_DIR/external"

if [[ ! -d "$PROJECT_DIR/external/wn_edit" ]]; then
    echo "Wn Editor not found at $PROJECT_DIR/external/wn_edit, cloning" >&2
    git clone https://github.com/bond-lab/wn_edit "$PROJECT_DIR/external/wn_edit"
fi

if [[ ! -d "$PROJECT_DIR/external/cili" ]]; then
    echo "CILI not found at $PROJECT_DIR/external/cili, cloning" >&2
    git clone https://github.com/globalwordnet/cili "$PROJECT_DIR/external/cili"
fi


if [[ ! -d .venv ]]; then
    uv venv --python 3.12 
    uv pip install --quiet -r "$PROJECT_DIR/requirements.txt" \
        -e "$PROJECT_DIR/external/wn_edit" 
fi

# ── 1. Build LMF XML ─────────────────────────────────────────────────────────
if $DO_LMF; then
    echo "=== Building intermediate TSV ==="
    uv run python "$SCRIPT_DIR/munge.py"

    echo "=== Building LMF XML ==="
    TUFS_VERSION="$VERSION" uv run python "$SCRIPT_DIR/tufs2wn.py"

    echo "=== Validating LMF XML ==="
    validation_failed=0
    while IFS='|' read -r local_code _bcp47 _en _native; do
        [[ -z "$local_code" ]] && continue
        xml="$PROJECT_DIR/build/lmf/tufs-$local_code.xml"
        if [[ -f "$xml" ]]; then
            uv run python -m wn validate "$xml" || {
                echo "  Warning: validation reported issues for $local_code (see above)" >&2
                validation_failed=1
            }
        fi
    done < "$LANGFILE"
    if [[ $validation_failed -eq 1 ]]; then
        echo "Warning: one or more LMF files have validation issues — continuing anyway." >&2
    fi
    echo
fi

# ── 2. Stage XMLs and run Cygnet ─────────────────────────────────────────────
if $DO_CYGNET; then
    echo "=== Running Cygnet packaging ==="

    if [[ ! -d "$CYGNET_DIR" ]]; then
	echo "Cygnet not found at $CYGNET_DIR, cloning" >&2
	git clone -b issue-17-wordnet-summary-page --single-branch https://github.com/omwn/cygnet "$CYGNET_DIR"
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
    mkdir -p "$PROJECT_DIR/docs/cygnet/img"
    cp "$CYGNET_DIR/web/index.html"            "$PROJECT_DIR/docs/cygnet/"
    cp "$CYGNET_DIR/web/relations.json"        "$PROJECT_DIR/docs/cygnet/"
    cp "$CYGNET_DIR/web/img/"*.svg             "$PROJECT_DIR/docs/cygnet/img/" 2>/dev/null || true
    cp "$PROJECT_DIR/etc/img/"*.svg            "$PROJECT_DIR/docs/cygnet/img/"
    cp "$PROJECT_DIR/etc/local.json"           "$PROJECT_DIR/docs/cygnet/"
    cp "$CYGNET_WORK/web/cygnet.db.gz"         "$PROJECT_DIR/docs/cygnet/tufs.db.gz"
    cp "$CYGNET_WORK/web/provenance.db.gz"     "$PROJECT_DIR/docs/cygnet/tufs-provenance.db.gz"
    echo "Done — docs/ is ready for GitHub Pages."
fi
