"""Extract TUFS vocabulary data from SQL dumps into a combined TSV file.

Intermediate TSV columns (tab-separated, 9 fields):
  1. cid       – TUFS concept ID (may be None for non-mapped words)
  2. lang      – ISO 639-1 language code
  3. wid       – word ID within the language SQL dump
  4. lemma     – semicolon-separated lemma forms (with optional morph tags)
  5. comment   – usage explanation / Japanese gloss
  6. iids      – semicolon-separated instance IDs linked via t_usage_inst_rel
  7. examples  – ;;;-separated example records, each pipe-separated:
                   sentence | reading_or_trans | function_label | token_form
  8. is_basic  – "1" if this usage is in the basic vocabulary (t_usage.selected=1)
  9. scenes    – comma-separated scene/domain labels from t_scene
"""

import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

DATADIR = Path("tufsdata")

# Full mapping for all 23 TUFS languages: ISO 639-1 → (ISO 639-3, English name)
_L2L3: dict[str, tuple[str, str]] = {
    "ar": ("arb", "Arabic"),
    "as": ("apc", "Arabic, Syrian"),
    "de": ("deu", "German"),
    "en": ("eng", "English"),
    "es": ("spa", "Spanish"),
    "fr": ("fra", "French"),
    "id": ("ind", "Indonesian"),
    "ja": ("jpn", "Japanese"),
    "km": ("khm", "Khmer"),
    "ko": ("kor", "Korean"),
    "lo": ("lao", "Lao"),
    "mn": ("mon", "Mongolian"),
    "ms": ("zsm", "Malay"),
    "my": ("mya", "Burmese"),
    "pb": ("por", "Portuguese, Brazilian"),
    "pt": ("por", "Portuguese"),
    "ru": ("rus", "Russian"),
    "th": ("tha", "Thai"),
    "tl": ("fil", "Filipino"),
    "tr": ("tur", "Turkish"),
    "ur": ("urd", "Urdu"),
    "vi": ("vie", "Vietnamese"),
    "zh": ("cmn", "Chinese, Mandarin"),
}



def l2l3(alpha2: str) -> tuple[str, str]:
    """Convert a two-letter language code to (iso639-3, english_name).

    Args:
        alpha2: ISO 639-1 two-letter code (or TUFS project-specific code).

    Returns:
        Tuple of (three-letter code, English language name).

    Examples:
        >>> l2l3('en')
        ('eng', 'English')
        >>> l2l3('ar')
        ('arb', 'Arabic')
    """
    if alpha2 in _L2L3:
        return _L2L3[alpha2]
    return ("unk", alpha2)


def scrub(cell: str) -> Optional[str]:
    """Replace SQL null sentinel with None."""
    return None if cell == r"\N" else cell


def read_tables(datadir: Path, lang: str) -> dict[str, list]:
    """Parse a PostgreSQL dump file into a dict of table → rows.

    The first element of each list is the column-name row; subsequent
    elements are data rows (each a list of strings or None).

    Args:
        datadir: Directory containing ``vmod_{lang}.sql`` files.
        lang: Two-letter language code.

    Returns:
        Mapping of table name to list of rows (header first).
    """
    data: dict[str, list] = defaultdict(list)
    state: Optional[str] = None
    with open(datadir / f"vmod_{lang}.sql") as fh:
        for line in fh:
            if "COPY" in line:
                table, cols = line[5:-14].split(" (", 1)
                state = table
                data[state].append(cols.split(", "))
            elif line.startswith(r"\."):
                state = None
            elif state:
                data[state].append([scrub(c) for c in line.rstrip("\n").split("\t")])
    return data


def get_words(data: dict[str, list]) -> dict[str, dict[str, str]]:
    """Extract word forms keyed by word ID.

    Includes all words that are not explicitly deselected (selected != '0'),
    so that words with selected=None (present in some languages) are retained.

    Args:
        data: Output of :func:`read_tables`.

    Returns:
        Mapping ``{lang: {word_id: form}}``.
    """
    word: dict[str, dict[str, str]] = defaultdict(dict)
    for lang, tables in data.items():
        for row in tables["t_word"][1:]:
            wid, basic, selected, *_ = row
            if selected != "0" and basic:
                word[lang][wid] = basic.strip()
    return word


def get_usage(data: dict[str, list]) -> dict[str, dict[str, tuple]]:
    """Extract all usages (sense-level entries) with a basic-vocabulary flag.

    All usages are returned, not just the basic set, so that non-basic senses
    (t_usage.selected != '1') are available for inclusion in the wordnet.  The
    ``is_basic`` flag distinguishes them.

    Args:
        data: Output of :func:`read_tables`.

    Returns:
        Mapping ``{lang: {usage_id: (word_id, explanation, is_basic)}}``.
    """
    usage: dict[str, dict[str, tuple]] = {}
    for lang, tables in data.items():
        usage[lang] = {}
        for row in tables["t_usage"][1:]:
            usage_id, word_id, explanation, _priority, selected = row
            is_basic = selected == "1"
            explanation = re.sub(r"(\\n)+", ";", str(explanation or "")).strip(";").strip()
            if usage_id in usage[lang]:
                print(
                    f"WARNING: duplicate usage_id {usage_id} for {lang}",
                    file=sys.stderr,
                )
            usage[lang][usage_id] = (word_id, explanation, is_basic)
    return usage


def get_concepts(data: dict[str, list]) -> tuple:
    """Map usage IDs to TUFS concept IDs and extract bunrui metadata.

    Args:
        data: Output of :func:`read_tables`.

    Returns:
        Tuple of (u2t, bunrui_n, bunrui_c, bunrui_u) where:
        - u2t: ``{lang: {usage_id: classified_id}}``
        - bunrui_n: ``{classified_id: midasi (heading)}``
        - bunrui_c: ``{classified_id: bunrui_code}``
        - bunrui_u: ``{classified_id: {lang: [usage_id, ...]}}``
    """
    u2t: dict[str, dict[str, str]] = defaultdict(dict)
    bunrui_n: dict[str, str] = {}
    bunrui_c: dict[str, str] = {}
    bunrui_u: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    for lang, tables in data.items():
        for row in tables["t_usage_classified_rel"][1:]:
            (usage_id, classified_id, bunrui_no, *_, midasi, _hontai, _yomi) = row
            u2t[lang][usage_id] = classified_id
            bunrui_n[classified_id] = midasi
            bunrui_c[classified_id] = str(round(float(bunrui_no), 4)).ljust(6, "0")
            bunrui_u[classified_id][lang].append(usage_id)

    return u2t, bunrui_n, bunrui_c, bunrui_u


def get_instances(data: dict[str, list]) -> tuple:
    """Extract example sentences linked to usages.

    Captures the full instance record including reading/translation (``trans``),
    pragmatic function label, and audio pronunciation where available.

    Args:
        data: Output of :func:`read_tables`.

    Returns:
        Tuple of (inst, usage_inst) where:
        - inst: ``{lang: {instance_id: (sentence, reading_or_trans, function, pronun)}}``
        - usage_inst: ``{lang: {usage_id: [instance_id, ...]}}``
    """
    inst: dict[str, dict[str, tuple]] = defaultdict(dict)
    usage_inst: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    for lang, tables in data.items():
        ic = tables["t_instance"][0]
        for row in tables["t_instance"][1:]:
            iid = row[ic.index("id")]
            target = row[ic.index("targetlanguage")]
            trans = row[ic.index("trans")]
            function = row[ic.index("function")]
            pronun = row[ic.index("pronun")]
            selected = row[ic.index("selected")]

            if selected == "1" and target and target.strip("\\n"):
                inst[lang][iid] = (
                    target.strip("\\n"),
                    (trans or "").strip("\\n"),
                    (function or "").strip() if function and function != "null" else "",
                    (pronun or "").strip(),
                )

        urc = tables["t_usage_inst_rel"][0]
        for row in tables["t_usage_inst_rel"][1:]:
            usage_id = row[urc.index("usage_id")]
            inst_id = row[urc.index("inst_id")]
            if inst_id in inst[lang]:
                usage_inst[lang][usage_id].append(inst_id)

    return inst, usage_inst


def get_word_instances(data: dict[str, list]) -> dict[str, dict[str, list]]:
    """Extract additional examples via t_word_inst_rel (word ↔ instance links).

    This table provides extra examples from the dialogue module that are
    not linked through t_usage_inst_rel.  Only populated for English in
    the current TUFS data.

    Args:
        data: Output of :func:`read_tables`.

    Returns:
        Mapping ``{lang: {word_id: [(inst_id, token)]}}``.
        ``token`` is the surface form of the word in the example sentence.
    """
    word_inst: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for lang, tables in data.items():
        wc = tables["t_word_inst_rel"][0]
        for row in tables["t_word_inst_rel"][1:]:
            wid = row[wc.index("word_id")]
            iid = row[wc.index("inst_id")]
            token = (row[wc.index("token")] or "").strip()
            if wid and iid:
                word_inst[lang][wid].append((iid, token))
    return word_inst


def get_scenes(data: dict[str, list]) -> dict[str, dict[str, list]]:
    """Extract scene/domain labels for each usage.

    Scenes are thematic categories (e.g. 海外旅行, スポーツ, 学校) assigned
    to usages via t_scene/t_usage_scene_rel.

    Args:
        data: Output of :func:`read_tables`.

    Returns:
        Mapping ``{lang: {usage_id: [scene_name, ...]}}``.
    """
    scenes: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for lang, tables in data.items():
        scene_by_id = {r[0]: r[1] for r in tables["t_scene"][1:]}
        for row in tables["t_usage_scene_rel"][1:]:
            usage_id, scene_id = row[0], row[1]
            name = scene_by_id.get(scene_id)
            if name:
                scenes[lang][usage_id].append(name)
    return scenes


def find_token_offset(sentence: str, token: str) -> int:
    """Find the character offset of ``token`` within ``sentence``.

    Case-insensitive, strips trailing whitespace from token.

    Args:
        sentence: The full example sentence.
        token: The surface form of the vocabulary word.

    Returns:
        Zero-based character offset, or ``-1`` if not found.
    """
    return sentence.lower().find(token.lower().strip())


def clean(word: str, lang: str) -> list[tuple[str, str]]:
    """Normalise a raw word form into a list of (lemma, tag) pairs.

    Args:
        word: Raw word form from the database.
        lang: Two-letter language code.

    Returns:
        List of ``(lemma, tag_string)`` pairs.

    Examples:
        >>> clean('hot', 'en')
        [('hot', '')]
        >>> clean('辣\\u3000là', 'zh')
        [('辣', 'orth:pīnyīn là')]
        >>> clean('طيّب (ـين)', 'as')
        [('طيّب', 'morph:pl ـين')]
    """
    if word.endswith("\\n"):
        word = word[:-2]
    word = word.replace("\u200f", "")

    if word in {
        "(…이/가) 되다",
        "sala (de aula)",
        "-arak/-erek (yürü-yerek)",
        "poderia (fazer) …",
    }:
        return [(word, "")]

    cleaned: list[tuple[str, str]] = []
    for part in re.split(r"[/,]\s*", word):
        m = re.match(r"(.+) \((.+?)\)", part)
        if m:
            base, bracketed = m.group(1), m.group(2)
            if lang in ("ar", "as"):
                cleaned.append((base, f"morph:pl {bracketed}"))
            elif lang == "ja":
                cleaned.append((base, ""))
            elif lang == "ms":
                if base[0] == "m":
                    cleaned.append((bracketed, f"morph:meN- {base}"))
                elif base[0] == "b":
                    cleaned.append((bracketed, f"morph:ber- {base}"))
                else:
                    cleaned.append((base, ""))
            else:
                cleaned.append((base, ""))
        elif lang == "zh":
            parts = part.split()
            if len(parts) >= 2:
                cleaned.append((parts[0], f"orth:pīnyīn {parts[1]}"))
            else:
                print(f"WARNING: zh word missing pinyin: {part!r}", file=sys.stderr)
                cleaned.append((parts[0], ""))
        else:
            cleaned.append((part, ""))

    return cleaned


def fetch_data(datadir: Path, langs: list[str]) -> dict[str, dict]:
    """Load raw table data for all requested languages.

    Args:
        datadir: Directory containing ``vmod_{lang}.sql`` files.
        langs: List of two-letter language codes.

    Returns:
        Mapping ``{lang: tables}`` as returned by :func:`read_tables`.
    """
    return {lang: read_tables(datadir, lang) for lang in langs}


def _encode_example(sentence: str, reading: str, function: str, token: str) -> str:
    """Encode a single example as a pipe-separated string.

    Fields: ``sentence | reading_or_trans | function_label | token_form``

    Empty trailing fields are omitted to keep the format compact.
    """
    parts = [
        sentence.replace("\u3000", " "),
        reading.replace("\u3000", " "),
        function,
        token,
    ]
    # Strip trailing empty fields
    while parts and not parts[-1]:
        parts.pop()
    return "|".join(parts)


def print_tsv(filename: str, data: dict[str, dict]) -> None:
    """Write the combined vocabulary TSV consumed by tufs2wn.py.

    Output columns (tab-separated):
        cid, lang, wid, lemma, comment, iids, examples, is_basic, scenes, bunrui

    Each example record is pipe-separated:
        sentence | reading_or_trans | function_label | token_form

    Multiple examples within a row are separated by ;;;.

    Args:
        filename: Output file path.
        data: Output of :func:`fetch_data`.
    """
    word = get_words(data)
    usage = get_usage(data)
    u2t, _bn, bc, _bu = get_concepts(data)
    inst, usage_inst = get_instances(data)
    word_inst = get_word_instances(data)
    scenes_map = get_scenes(data)

    # Build inst lookup for extra-example access
    inst_full: dict[str, dict[str, tuple]] = defaultdict(dict)
    for lang, tables in data.items():
        ic = tables["t_instance"][0]
        for row in tables["t_instance"][1:]:
            iid = row[ic.index("id")]
            target = (row[ic.index("targetlanguage")] or "").strip("\\n")
            trans = (row[ic.index("trans")] or "").strip("\\n")
            function = row[ic.index("function")] or ""
            if function == "null":
                function = ""
            if target:
                inst_full[lang][iid] = (target, trans.strip(), function.strip(), "")

    with open(filename, "w") as out:
        for lang in usage:
            for uid, (word_id, explanation, is_basic) in usage[lang].items():
                w = word[lang].get(word_id, "")
                if not w:
                    continue

                cleaned_parts = []
                for lem, typ in clean(w, lang):
                    cleaned_parts.append(f"{lem} ({typ})" if typ else lem)

                # Usage-level instances (primary examples)
                iids = usage_inst[lang].get(uid, [])
                ex_records: list[str] = []
                for iid in iids:
                    if iid in inst[lang]:
                        s, r, f, _p = inst[lang][iid]
                        ex_records.append(_encode_example(s, r, f, ""))

                # Word-level extra instances from t_word_inst_rel
                existing_iids = set(iids)
                for iid, token in word_inst[lang].get(word_id, []):
                    if iid not in existing_iids:
                        existing_iids.add(iid)
                        iids.append(iid)
                        if iid in inst_full[lang]:
                            s, r, f, _p = inst_full[lang][iid]
                            offset = find_token_offset(s, token) if token else -1
                            tok_field = f"{token}:{offset}" if token and offset >= 0 else token
                            ex_records.append(_encode_example(s, r, f, tok_field))

                tufs_id = u2t[lang].get(uid)
                scene_labels = ",".join(scenes_map[lang].get(uid, []))

                print(
                    tufs_id,
                    lang,
                    word_id,
                    "; ".join(cleaned_parts),
                    explanation,
                    ";".join(iids),
                    ";;;".join(ex_records) if ex_records else "",
                    "1" if is_basic else "0",
                    scene_labels,
                    bc.get(tufs_id, ""),
                    sep="\t",
                    file=out,
                )


def main() -> None:
    """Extract TUFS vocabulary to a combined TSV file (tufs-vocab.tsv)."""
    langs = [
        "ar", "as", "de", "en", "es", "fr", "id", "ja",
        "km", "ko", "lo", "mn", "ms", "my", "pb", "pt",
        "ru", "th", "tl", "tr", "ur", "vi", "zh",
    ]
    data = fetch_data(DATADIR, langs)
    print_tsv("tufs-vocab.tsv", data)


if __name__ == "__main__":
    main()
