"""Tests for the built Cygnet SQLite databases in docs/."""

import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent

# Expected BCP 47 codes from languages.txt (second column)
EXPECTED_BCP47 = {
    "ar", "as", "de", "en", "es", "fr", "id", "ja",
    "km", "ko", "lo", "mn", "zsm", "my", "pt-BR", "pt",
    "ru", "th", "fil", "tr", "ur", "vi", "zh",
}

# Conservative lower bound for TUFS-specific languages (non-OEWN)
MIN_TUFS_ENTRIES = 300


def _lang_entry_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT l.code, COUNT(e.rowid)
        FROM languages l
        LEFT JOIN entries e ON e.language_rowid = l.rowid
        GROUP BY l.code
        """
    ).fetchall()
    return dict(rows)


class TestMainDB:
    def test_all_languages_present(self, main_db):
        codes = {
            row[0]
            for row in main_db.execute("SELECT code FROM languages").fetchall()
        }
        missing = EXPECTED_BCP47 - codes
        assert not missing, f"Missing languages in DB: {missing}"

    def test_no_extra_unexpected_languages(self, main_db):
        codes = {
            row[0]
            for row in main_db.execute("SELECT code FROM languages").fetchall()
        }
        extra = codes - EXPECTED_BCP47
        assert not extra, f"Unexpected language codes in DB: {extra}"

    def test_tufs_languages_have_sufficient_entries(self, main_db):
        counts = _lang_entry_counts(main_db)
        sparse = {
            lang: n
            for lang, n in counts.items()
            if lang != "en" and n < MIN_TUFS_ENTRIES
        }
        assert not sparse, (
            f"TUFS language(s) below {MIN_TUFS_ENTRIES} entries: {sparse}"
        )

    def test_synset_count(self, main_db):
        (n,) = main_db.execute("SELECT COUNT(*) FROM synsets").fetchone()
        assert n > 100_000, f"Too few synsets: {n}"

    def test_sense_count(self, main_db):
        (n,) = main_db.execute("SELECT COUNT(*) FROM senses").fetchone()
        assert n > 150_000, f"Too few senses: {n}"

    def test_arasaac_populated(self, main_db):
        (n,) = main_db.execute("SELECT COUNT(*) FROM arasaac").fetchone()
        assert n > 5_000, f"ARASAAC table unexpectedly sparse: {n} rows"

    def test_definitions_present(self, main_db):
        (n,) = main_db.execute("SELECT COUNT(*) FROM definitions").fetchone()
        assert n > 100_000, f"Too few definitions: {n}"

    def test_no_language_without_senses(self, main_db):
        rows = main_db.execute(
            """
            SELECT l.code
            FROM languages l
            WHERE NOT EXISTS (
                SELECT 1 FROM entries e
                JOIN senses s ON s.entry_rowid = e.rowid
                WHERE e.language_rowid = l.rowid
            )
            """
        ).fetchall()
        empty = [r[0] for r in rows]
        assert not empty, f"Language(s) with no senses: {empty}"

    def test_language_names_populated(self, main_db):
        rows = main_db.execute(
            "SELECT code FROM languages WHERE name IS NULL OR name = ''"
        ).fetchall()
        unnamed = [r[0] for r in rows]
        assert not unnamed, f"Language(s) missing names: {unnamed}"


class TestProvenanceDB:
    def test_provenance_db_non_empty(self, provenance_db):
        tables = {
            r[0]
            for r in provenance_db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert tables, "Provenance DB has no tables"
        total = sum(
            provenance_db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            for t in tables
        )
        assert total > 0, "Provenance DB is empty"
