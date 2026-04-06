#!/usr/bin/env bash
# make-release.sh
#
# Package TUFS wordnets for release and optionally publish to GitHub.
#
# Usage:
#   bash make-release.sh                # build tarballs + run wn load test
#   bash make-release.sh --pre-release  # above + tag, push, create GitHub pre-release
#   bash make-release.sh --release      # above + promote pre-release (or create full release)
#
# Prerequisites:
#   - bash build.sh must have been run first (build/lmf/tufs-*.xml must exist)
#   - For --pre-release / --release: gh CLI must be authenticated (gh auth login)
#   - For --pre-release / --release: etc/release-notes.md must exist and be non-empty
#   - For --pre-release / --release: working tree must be clean

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(cat "$PROJECT_DIR/VERSION")"
LANGFILE="$PROJECT_DIR/tufsdata/languages.txt"
LMF_DIR="$PROJECT_DIR/build/lmf"
RELEASE_DIR="$PROJECT_DIR/build/release"
TAG="v${VERSION}"

MODE="local"
for arg in "$@"; do
    case "$arg" in
        --pre-release) MODE="pre-release" ;;
        --release)     MODE="release" ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: bash make-release.sh [--pre-release | --release]" >&2
            exit 1
            ;;
    esac
done

# ── 0. Check LMF XMLs exist ───────────────────────────────────────────────────
echo "=== Checking build/lmf/ ==="
missing=0
while IFS='|' read -r local_code _bcp47 _en _native; do
    [[ -z "$local_code" ]] && continue
    if [[ ! -f "$LMF_DIR/tufs-$local_code.xml" ]]; then
        echo "  Missing: build/lmf/tufs-$local_code.xml" >&2
        missing=1
    fi
done < "$LANGFILE"
if [[ $missing -eq 1 ]]; then
    echo "Error: some LMF XMLs are missing — run bash build.sh --lmf-only first." >&2
    exit 1
fi
echo "  All LMF XMLs present."

# ── 1. Pre-flight checks for publish modes ────────────────────────────────────
if [[ "$MODE" != "local" ]]; then
    echo "=== Pre-flight checks ==="

    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "Error: working tree has uncommitted changes — commit or stash first." >&2
        exit 1
    fi
    echo "  Working tree is clean."

    notes="$PROJECT_DIR/etc/release-notes.md"
    if [[ ! -s "$notes" ]]; then
        echo "Error: etc/release-notes.md is missing or empty." >&2
        exit 1
    fi
    echo "  Release notes present."

    if ! gh auth status &>/dev/null; then
        echo "Error: not authenticated with gh — run: gh auth login" >&2
        exit 1
    fi
    echo "  gh CLI authenticated."
fi

# ── 2. Build per-language tarballs ────────────────────────────────────────────
echo "=== Building tarballs ==="
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

COLLECTION_DIR="$RELEASE_DIR/tufs-${VERSION}"
mkdir -p "$COLLECTION_DIR"
cp "$PROJECT_DIR/LICENSE"          "$COLLECTION_DIR/LICENSE.md"
cp "$PROJECT_DIR/README.md"        "$COLLECTION_DIR/README.md"
cp "$PROJECT_DIR/etc/citation.bib" "$COLLECTION_DIR/citation.bib"

while IFS='|' read -r local_code _bcp47 _en _native; do
    [[ -z "$local_code" ]] && continue
    pkg="tufs-${local_code}"
    pkg_dir="$COLLECTION_DIR/${pkg}"
    mkdir -p "$pkg_dir"
    cp "$LMF_DIR/tufs-${local_code}.xml"  "$pkg_dir/${pkg}-${VERSION}.xml"
    cp "$PROJECT_DIR/LICENSE"              "$pkg_dir/LICENSE.md"
    cp "$PROJECT_DIR/README.md"            "$pkg_dir/README.md"
    cp "$PROJECT_DIR/etc/citation.bib"    "$pkg_dir/citation.bib"

    # Per-language tarball
    tar -C "$COLLECTION_DIR" -cJf "$RELEASE_DIR/${pkg}-${VERSION}.tar.xz" "${pkg}"
    echo "  ${pkg}-${VERSION}.tar.xz"
done < "$LANGFILE"

# Collection tarball (all languages)
tar -C "$RELEASE_DIR" -cJf "$RELEASE_DIR/tufs-${VERSION}.tar.xz" "tufs-${VERSION}"
echo "  tufs-${VERSION}.tar.xz"

echo
echo "Tarball sizes:"
du -sh "$RELEASE_DIR"/*.tar.xz | sort -k2

# ── 3. Load test with wn ──────────────────────────────────────────────────────
echo
echo "=== Testing wn load (collection tarball) ==="
WN_TMPDIR="$(mktemp -d)"
trap 'rm -rf "$WN_TMPDIR"' EXIT

# Extract the English sub-package and verify it loads cleanly.
tar -xJf "$RELEASE_DIR/tufs-en-${VERSION}.tar.xz" -C "$WN_TMPDIR"
uv run python - <<PYEOF
import wn
wn.config.data_home = "$WN_TMPDIR"
wn.add("$WN_TMPDIR/tufs-en/tufs-en-${VERSION}.xml")
lexs = wn.lexicons(lang="en")
assert lexs, "No lexicons loaded"
n_words = len(wn.words(lang="en"))
assert n_words > 400, f"Too few words: {n_words}"
print(f"  OK: {len(lexs)} lexicon(s), {n_words} words")
PYEOF
echo "Load test passed."

# ── 4. Publish ────────────────────────────────────────────────────────────────
if [[ "$MODE" == "local" ]]; then
    echo
    echo "Done. Tarballs are in build/release/."
    echo "Run with --pre-release or --release to publish."
    exit 0
fi

if [[ "$MODE" == "release" ]]; then
    # Check if a pre-release already exists for this tag — if so, promote it.
    existing_prerelease="$(gh release view "$TAG" --json isPrerelease \
        -q '.isPrerelease' 2>/dev/null || true)"
    if [[ "$existing_prerelease" == "true" ]]; then
        echo
        echo "=== Promoting $TAG from pre-release to release ==="
        gh release edit "$TAG" --prerelease=false --latest
        echo "Done — $TAG is now a full release."
        exit 0
    fi
fi

# Tag and push (for both --pre-release and a fresh --release)
echo
echo "=== Tagging and pushing ==="
if git rev-parse "$TAG" &>/dev/null; then
    echo "Error: tag $TAG already exists locally." >&2
    echo "If you want to re-release, delete it with: git tag -d $TAG && git push origin :$TAG" >&2
    exit 1
fi

git tag "$TAG"
git push origin master
git push origin "$TAG"
echo "  Pushed tag $TAG"

# Create the GitHub release
echo
if [[ "$MODE" == "pre-release" ]]; then
    echo "=== Creating GitHub pre-release $TAG ==="
    gh release create "$TAG" \
        --title "TUFS Basic Vocabulary ${VERSION}" \
        --notes-file "$PROJECT_DIR/etc/release-notes.md" \
        --prerelease \
        "$RELEASE_DIR"/*.tar.xz
    echo "Pre-release $TAG created."
else
    echo "=== Creating GitHub release $TAG ==="
    gh release create "$TAG" \
        --title "TUFS Basic Vocabulary ${VERSION}" \
        --notes-file "$PROJECT_DIR/etc/release-notes.md" \
        --latest \
        "$RELEASE_DIR"/*.tar.xz
    echo "Release $TAG created."
fi
