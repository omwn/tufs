"""Tests for built LMF XML files, wordnets.toml, and local.json config."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent
BUILD_DIR = REPO / "build" / "tufs-2.0"
ETC_DIR = REPO / "etc"
DOCS_DIR = REPO / "docs"


class TestLMFXML:
    def test_all_xml_files_exist(self, languages):
        missing = []
        for local_code, *_ in languages:
            p = BUILD_DIR / f"tufs-{local_code}" / f"tufs-{local_code}.xml"
            if not p.exists():
                missing.append(str(p.relative_to(REPO)))
        assert not missing, f"Missing XML files:\n" + "\n".join(missing)

    def test_xml_files_are_well_formed(self, languages):
        malformed = []
        for local_code, *_ in languages:
            p = BUILD_DIR / f"tufs-{local_code}" / f"tufs-{local_code}.xml"
            if not p.exists():
                continue
            try:
                ET.parse(p)
            except ET.ParseError as exc:
                malformed.append(f"{p.name}: {exc}")
        assert not malformed, "Malformed XML files:\n" + "\n".join(malformed)

    def test_xml_language_attributes_match_bcp47(self, languages):
        mismatches = []
        for local_code, bcp47, en_name, _native in languages:
            p = BUILD_DIR / f"tufs-{local_code}" / f"tufs-{local_code}.xml"
            if not p.exists():
                continue
            tree = ET.parse(p)
            lexicons = tree.findall(".//{http://globalwordnet.github.io/schemas/}Lexicon") or \
                       tree.findall(".//Lexicon")
            for lex in lexicons:
                actual = lex.get("language")
                if actual != bcp47:
                    mismatches.append(
                        f"tufs-{local_code}.xml: expected language='{bcp47}', got '{actual}'"
                    )
        assert not mismatches, "\n".join(mismatches)

    def test_xml_files_have_senses(self, languages):
        empty = []
        for local_code, *_ in languages:
            p = BUILD_DIR / f"tufs-{local_code}" / f"tufs-{local_code}.xml"
            if not p.exists():
                continue
            content = p.read_text()
            if "<Sense " not in content:
                empty.append(f"tufs-{local_code}.xml")
        assert not empty, f"XML files with no senses: {empty}"


class TestWordnetsToml:
    def test_toml_covers_all_languages(self, languages):
        toml_path = ETC_DIR / "wordnets.toml"
        assert toml_path.exists(), "etc/wordnets.toml not found"
        content = toml_path.read_text()
        bcp47_set = {bcp47 for _lc, bcp47, *_ in languages}
        missing = [
            code for code in bcp47_set
            if not re.search(rf"^\s*{re.escape(code)}\s*=", content, re.MULTILINE)
        ]
        assert not missing, f"BCP 47 code(s) missing from wordnets.toml: {missing}"

    def test_en_entry_starts_with_oewn(self):
        toml_path = ETC_DIR / "wordnets.toml"
        content = toml_path.read_text()
        m = re.search(r'^\s*en\s*=\s*\[(.*?)\]', content, re.MULTILINE | re.DOTALL)
        assert m, "No 'en' entry found in wordnets.toml"
        first_url = re.search(r'"([^"]+)"', m.group(1))
        assert first_url, "No URLs in 'en' entry"
        assert "en-word.net" in first_url.group(1) or "english-wordnet" in first_url.group(1), (
            f"First 'en' URL should be OEWN, got: {first_url.group(1)}"
        )


class TestLocalJson:
    def test_local_json_is_valid(self):
        path = ETC_DIR / "local.json"
        assert path.exists(), "etc/local.json not found"
        data = json.loads(path.read_text())
        assert isinstance(data, dict)

    def test_local_json_has_required_fields(self):
        data = json.loads((ETC_DIR / "local.json").read_text())
        assert "databases" in data, "local.json missing 'databases'"
        assert "main" in data["databases"], "local.json missing 'databases.main'"
        assert "provenance" in data["databases"], "local.json missing 'databases.provenance'"
        assert data["databases"]["main"]["filename"].endswith(".db.gz")
        assert data["databases"]["provenance"]["filename"].endswith(".db.gz")

    def test_docs_local_json_matches_etc(self):
        etc_data = json.loads((ETC_DIR / "local.json").read_text())
        docs_path = DOCS_DIR / "local.json"
        if not docs_path.exists():
            pytest.skip("docs/local.json not present — run bash build.sh first")
        docs_data = json.loads(docs_path.read_text())
        assert etc_data == docs_data, (
            "docs/local.json differs from etc/local.json — re-run bash build.sh"
        )

    def test_db_filenames_exist_in_docs(self):
        data = json.loads((ETC_DIR / "local.json").read_text())
        for key in ("main", "provenance"):
            fname = data["databases"][key]["filename"]
            p = DOCS_DIR / fname
            if not p.exists():
                pytest.skip(f"{fname} not in docs/ — run bash build.sh first")
