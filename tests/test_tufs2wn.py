"""Unit tests for tufs2wn.py parsing helpers."""

import pytest

from tufs2wn import _example_note, _MORPH_RE, _MORPH_TAGS, _CJK_RE, split_lem


class TestSplitLem:
    """Tests for split_lem(), covering all annotation formats."""

    def test_plain_lemma(self):
        assert split_lem("学習") == ("学習", "", "")

    def test_plain_ascii(self):
        assert split_lem("dog") == ("dog", "", "")

    def test_morph_feminine(self):
        assert split_lem("Freundin (morph:f)") == ("Freundin", "morph", "f")

    def test_morph_feminine_french(self):
        assert split_lem("vieille (morph:f)") == ("vieille", "morph", "f")

    def test_morph_compound_tag(self):
        # morph:m:sg must not be split on the second colon
        assert split_lem("vieil (morph:m:sg)") == ("vieil", "morph", "m:sg")

    def test_morph_plural(self):
        assert split_lem("yeux (morph:pl)") == ("yeux", "morph", "pl")

    def test_pinyin(self):
        # orth:pīnyīn has a space separating tag from value
        assert split_lem("去 (orth:pīnyīn qù)") == ("去", "orth:pīnyīn", "qù")

    def test_no_annotation(self):
        # No parenthesised tag at all
        assert split_lem("être") == ("être", "", "")

    def test_unclosed_paren_ignored(self):
        # Parenthesis not at end of string — treated as plain lemma
        assert split_lem("foo (bar") == ("foo (bar", "", "")


class TestMorphRegex:
    """Tests for the morph extraction regex and tag mapping."""

    def test_feminine_form(self):
        com = "きれいな。;＊女性形はbelle。"
        matches = _MORPH_RE.findall(com.replace("\u200f", ""))
        assert ("女性形", "belle") in matches

    def test_plural_form(self):
        com = "動物。;＊複数形はanimaux。"
        matches = _MORPH_RE.findall(com)
        assert ("複数形", "animaux") in matches

    def test_multiple_forms_in_one_note(self):
        com = "きれい。;＊複数形はbeaux、母音または無音のhで始まる男性単数名詞の前ではbel、女性形はbelle。"
        matches = _MORPH_RE.findall(com)
        forms = {tag: lem for tag, lem in matches}
        assert forms.get("複数形", "").strip() == "beaux"
        assert forms.get("女性形", "").strip() == "belle"

    def test_cjk_filter_rejects_japanese(self):
        # The extracted lemma must not contain CJK characters
        com = "否定。;＊ない形で使う。"
        matches = _MORPH_RE.findall(com)
        kept = [l for _tag, l in matches if not _CJK_RE.search(l)]
        assert not kept

    def test_all_tags_known(self):
        # Smoke-test that every tag in _MORPH_TAGS maps to a non-empty code
        for tag, code in _MORPH_TAGS.items():
            assert code, f"Empty code for tag: {tag}"

    def test_hyphenated_form(self):
        com = "＊複数形はpull-overs。"
        matches = _MORPH_RE.findall(com)
        assert any(l.strip() == "pull-overs" for _tag, l in matches)

    def test_premiere_accent(self):
        com = ";＊女性形はpremière。"
        matches = _MORPH_RE.findall(com)
        assert any(l.strip() == "première" for _tag, l in matches)


class TestExampleNote:
    """Tests for _example_note()."""

    def test_empty_fields(self):
        assert _example_note("Hello.", "", "", "") is None

    def test_reading_only(self):
        note = _example_note("犬が走る。", "いぬがはしる。", "", "")
        assert note == "R=いぬがはしる。"

    def test_function_label_generic_skipped(self):
        note = _example_note("Hello.", "", "機能", "")
        assert note is None

    def test_function_label_kept(self):
        note = _example_note("Hello.", "", "あいさつ", "")
        assert note == "F=あいさつ"

    def test_precomputed_span(self):
        note = _example_note("I love cats.", "", "", "cats:7")
        assert note == "S=7:11"

    def test_span_fallback_search(self):
        # No precomputed offset; falls back to case-insensitive substring search
        note = _example_note("I love Cats.", "", "", "cats")
        assert note == "S=7:11"

    def test_span_not_found(self):
        note = _example_note("Hello world.", "", "", "xyz")
        assert note is None

    def test_combined_note(self):
        note = _example_note("犬が走る。", "いぬがはしる。", "描写", "犬:0")
        assert note == "R=いぬがはしる。;F=描写;S=0:1"

    def test_token_with_trailing_newline_not_found(self):
        # rpartition gives off_str="\n" (not a digit), so strip() fallback
        # gives "world:" (colon included) which is not in the sentence
        note = _example_note("Hello world.", "", "", "world:\n")
        assert note is None
