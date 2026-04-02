"""Shared pytest fixtures for TUFS build tests."""

import gzip
import sqlite3
import sys
import tempfile
from pathlib import Path

# Make the repo root importable so tests can import tufs2wn, munge, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

REPO = Path(__file__).parent.parent


def _open_db(gz_path: Path) -> sqlite3.Connection:
    """Decompress a .db.gz file into a temp file and return a connection."""
    with gzip.open(gz_path, "rb") as f:
        data = f.read()
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.write(data)
    tmp.close()
    return sqlite3.connect(tmp.name)


@pytest.fixture(scope="session")
def main_db() -> sqlite3.Connection:
    gz = REPO / "docs" / "tufs.db.gz"
    if not gz.exists():
        pytest.skip("docs/tufs.db.gz not present — run bash build.sh first")
    return _open_db(gz)


@pytest.fixture(scope="session")
def provenance_db() -> sqlite3.Connection:
    gz = REPO / "docs" / "tufs-provenance.db.gz"
    if not gz.exists():
        pytest.skip("docs/tufs-provenance.db.gz not present — run bash build.sh first")
    return _open_db(gz)


@pytest.fixture(scope="session")
def languages() -> list[tuple[str, str, str, str]]:
    """Parse tufsdata/languages.txt → list of (local_code, bcp47, en_name, native)."""
    path = REPO / "tufsdata" / "languages.txt"
    result = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            parts = line.split("|")
            result.append(tuple(parts))
    return result
