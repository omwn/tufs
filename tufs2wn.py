"""Build per-language WN-LMF XML files from the TUFS vocabulary TSV.

Uses wn_edit and wn.lmf.dump() directly, bypassing the tsv2lmf.py pipeline.

Output: one XML file per language written to build/lmf/tufs-{lang}.xml.
"""

import re
import sys
import warnings
from collections import defaultdict
from functools import lru_cache
from html.entities import codepoint2name
from pathlib import Path
from typing import Optional

import wn.lmf as wn_lmf
from wn_edit.editor import (
    make_count,
    make_example,
    make_lexical_entry,
    make_lexical_resource,
    make_lemma,
    make_lexicon,
    make_sense,
    make_synset,
)

from munge import l2l3

TUFS_OMW_MAP = "tufs-omw-map.tsv"
TUFS_VOCAB = "tufs-vocab.tsv"
ILI_MAP = Path("etc/cili/ili-map-pwn30.tab")
OUTDIR = Path("build/lmf")

_BUNRUI_POS: dict[str, str] = {'1': 'n', '2': 'v', '3': 'a', '4': 'r'}

_TAG_MORPH = 'morph'
_TAG_PINYIN = 'orth:pīnyīn'
_VAR_PINYIN = 'zh-pinyin'
_VAR_JA_HIRA = 'ja-Hira'

VERSION = "2.0"
EMAIL = "bond@ieee.org"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
BASE_URL = "https://github.com/omwn/tufs/"
AUDIO_BASE = "https://www.coelang.tufs.ac.jp/mt/{lang}/vmod/sound/word/word_{wid}.mp3"

_L2BCP47: dict[str, str] = {
    "ar": "arb", "as": "apc", "de": "de", "en": "en",
    "es": "es", "fr": "fr", "id": "id", "ja": "ja",
    "km": "km", "ko": "ko", "lo": "lo", "mn": "mn",
    "ms": "zsm", "my": "my", "pb": "pt-BR", "pt": "pt",
    "ru": "ru", "th": "th", "tl": "fil", "tr": "tr",
    "ur": "ur", "vi": "vi", "zh": "cmn-Hans",
}

_MORPH_RE = re.compile(
    r"(<女>|[可数名詞双男女性単複]+[性数]形|過去分詞形)"
    r"(?:[は\u200f]|\s*:\s*|\s*：\s*)?"
    # Non-CJK word chars + spaces + Arabic range + hyphens; stop before CJK
    r"([^\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef\u3000-\u303f\u060c\n。；;＊,，]+)"
)
_MORPH_TAGS: dict[str, str] = {
    "複数形": "pl", "<女>": "f", "単数女性形": "f:sg",
    "複数男性形": "m:pl", "男性複数形": "m:pl", "複数女性形": "f:pl",
    "女性複数形": "f:pl", "女性形": "f", "可数名詞単数形": "count:sg",
    "双数形": "du", "男性単数形": "m:sg", "過去分詞形": "VBN",
}

_CJK_RE = re.compile(
    r'[\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef\u3000-\u303f]'
)

_CHAR_ESCAPES: dict[str, str] = {
    ' ': '_', '\u3000': '_', '~': '-tilde-',
    '!': '-excl-', '#': '-num-', '$': '-dollar-',
    '%': '-percnt-', "'": '-apos-', '(': '-lpar-', ')': '-rpar-',
    '*': '-ast-', '+': '-plus-', ',': '-comma-', '-': '--',
    '.': '.', '/': '-sol-', ':': '-colon-', ';': '-semi-',
    '=': '-equals-', '?': '-quest-', '@': '-commat-',
    '[': '-lsqb-', '\\': '-bsol-', ']': '-rsqb-', '^': '-Hat-',
    '_': '_', '`': '-grave-', '{': '-lbrace-', '|': '-vert-',
    '}': '-rbrace-',
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4096)
def escape_lemma(lemma: str) -> str:
    """Escape a lemma string for use as an XML ID component."""
    chars = []
    for c in lemma:
        cp = ord(c)
        if (
            'A' <= c <= 'Z' or 'a' <= c <= 'z' or '0' <= c <= '9'
            or c in '_.·'
            or 0xC0 <= cp <= 0xD6 or 0xD8 <= cp <= 0xF6
            or 0xF8 <= cp <= 0x2FF or 0x370 <= cp <= 0x37D
            or 0x37F <= cp <= 0x1FFF
            or cp in (0x200C, 0x200D, 0x203F, 0x2040)
            or 0x2C00 <= cp <= 0x2FEF or 0x3001 <= cp <= 0xD7FF
            or 0xF900 <= cp <= 0xFDCF or 0xFDF0 <= cp <= 0xFFFD
            or 0x10000 <= cp <= 0xEFFFF
        ):
            chars.append(c)
        elif c in _CHAR_ESCAPES:
            chars.append(_CHAR_ESCAPES[c])
        elif cp in codepoint2name:
            chars.append(codepoint2name[cp])
        else:
            esc = f'-{cp:04X}-'
            warnings.warn(f'no escape for {c!r}; using {esc}')
            chars.append(esc)
    return ''.join(chars)


def load_ili_map(path: Path) -> dict[str, str]:
    """Load PWN 3.0 synset-ID → ILI identifier mapping.

    Args:
        path: Path to ``ili-map-pwn30.tab``.

    Returns:
        Mapping ``{synset_id: ili_id}``.
    """
    ili: dict[str, str] = {}
    with open(path) as fh:
        for line in fh:
            ili_id, ssid = line.strip().split('\t')
            ili[ssid] = ili_id
            if ssid.endswith('-s'):
                ili[ssid[:-2] + '-a'] = ili_id
    return ili


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def syn_to_cid(
    map_filename: str,
    info: dict[str, list],
) -> dict[str, list[str]]:
    """Map synset IDs to TUFS concept IDs, including unmapped concepts.

    Mapped concepts use their PWN synset ID as key (synonym relations only).
    Unmapped concepts get a synthetic key ``{cid}-{pos}`` derived from the
    Bunrui Goihyo category code stored in ``info``.

    Args:
        map_filename: Path to the TUFS–OMW mapping TSV.
        info: Output of :func:`cid_info` (first element).

    Returns:
        Mapping ``{synset_id: [concept_id, ...]}``.

    Examples:
        >>> info, _ = cid_info('tufs-vocab.tsv')
        >>> syns = syn_to_cid('tufs-omw-map.tsv', info)
        >>> syns['10332385-n']
        ['16496', '16507']
    """
    sc: dict[str, list[str]] = defaultdict(list)
    with open(map_filename) as fh:
        for line in fh:
            row = line.strip().split('\t')
            if row[1] == 'synonym':
                sc[row[2]].append(row[0])

    mapped = {cid for cids in sc.values() for cid in cids}
    for cid, entries in info.items():
        if cid in mapped or cid == 'None':
            continue
        bunrui = next((e[7] for e in entries if e[7]), '')
        pos = _BUNRUI_POS.get(bunrui[:1], 'n')
        sc[f'{cid}-{pos}'].append(cid)

    return sc


def cid_info(filename: str) -> tuple[dict[str, list], set[str]]:
    """Load concept entries from the combined vocabulary TSV.

    Args:
        filename: Path to ``tufs-vocab.tsv`` (output of munge.py).

    Returns:
        Tuple of:
        - info: ``{concept_id: [(lang, comment, lemma, exe, wid, is_basic, scenes, bunrui), ...]}``
        - langs: Set of language codes present in the file.

    Examples:
        >>> info, langs = cid_info('tufs-vocab.tsv')
        >>> 'ja' in langs
        True
    """
    info: dict[str, list] = defaultdict(list)
    langs: set[str] = set()

    with open(filename) as fh:
        for line in fh:
            parts = line.rstrip('\n').split('\t')
            cid, lng, wid = parts[0], parts[1], parts[2]
            lem, com = parts[3], parts[4]
            exe = parts[6] if len(parts) > 6 else ''
            is_basic = parts[7] == '1' if len(parts) > 7 else True
            scenes = parts[8] if len(parts) > 8 else ''
            bunrui = parts[9] if len(parts) > 9 else ''
            langs.add(lng)

            matches = _MORPH_RE.findall(com.replace('\u200f', ''))
            if matches:
                known = [
                    f'{l.strip()} (morph:{_MORPH_TAGS[m]})'
                    for m, l in matches
                    if m in _MORPH_TAGS and not _CJK_RE.search(l)
                ]
                if known:
                    lem += '; ' + '; '.join(known)
                unknown = [
                    (l.strip(), m) for m, l in matches
                    if m not in _MORPH_TAGS and not _CJK_RE.search(l)
                ]
                if unknown:
                    print(f'WARNING: unknown morphology {unknown}', file=sys.stderr)

            info[cid].append((
                lng,
                com.replace('\u3000', ' '),
                lem,
                exe.replace('\u3000', ' ') if exe else None,
                wid,
                is_basic,
                scenes,
                bunrui,
            ))

    return info, langs


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def split_lem(lem: str) -> tuple[str, str, str]:
    """Parse a lemma string of the form ``lemma (tag value)``.

    Args:
        lem: Raw lemma string, possibly with a parenthesised tag.

    Returns:
        Triple ``(lemma, tag, value)``.  Tag and value are empty if absent.

    Examples:
        >>> split_lem('Freundin (morph:f)')
        ('Freundin', 'morph', 'f')
        >>> split_lem('学習')
        ('学習', '', '')
    """
    if ' (' in lem and lem.endswith(')'):
        lemma, rest = lem.rstrip(')').split(' (', 1)
        if ' ' in rest:
            tag, var = rest.split(' ', 1)
        else:
            tag, _, var = rest.partition(':')
        return (lemma, tag, var)
    return (lem, '', '')


def _parse_examples(exe: str) -> list[tuple[str, str, str, str]]:
    """Parse the ``;;;``-separated example string into tuples.

    Args:
        exe: Raw example string from the TSV.

    Returns:
        List of ``(sentence, reading_or_trans, function_label, token_field)`` tuples.
    """
    if not exe:
        return []
    records = []
    for ex in exe.strip().split(';;;'):
        fields = ex.split('|')
        sentence = fields[0].replace('\u200f', '')
        reading = fields[1].replace('\u200f', '') if len(fields) > 1 else ''
        function = fields[2] if len(fields) > 2 else ''
        token = fields[3] if len(fields) > 3 else ''
        if sentence:
            records.append((sentence, reading, function, token))
    return records


def _example_note(sentence: str, reading: str, function: str, token: str) -> Optional[str]:
    """Build the ``note`` string for an Example element.

    Encodes:
    - ``R=<reading>``     — hiragana reading (ja) or Japanese translation (zh)
    - ``F=<function>``    — pragmatic function label (omitted if generic ``機能``)
    - ``S=<start>:<end>`` — Unicode character span of the target word in the sentence

    The span is taken from a pre-computed offset stored in ``token`` as
    ``word:offset`` when available; otherwise the word is searched
    case-insensitively in ``sentence``.

    Args:
        sentence: The example sentence text.
        reading: Reading or translation string.
        function: Pragmatic function label.
        token: Token field from the TSV (``word`` or ``word:offset``).

    Returns:
        Semicolon-separated note string, or ``None`` if all fields are empty.
    """
    parts = []
    if reading:
        parts.append(f'R={reading}')
    if function and function != '機能':
        parts.append(f'F={function}')
    if token:
        tok, sep, off_str = token.rpartition(':')
        if sep and tok and off_str.lstrip('-').isdigit():
            token_form, offset = tok, int(off_str)
        else:
            token_form = token.strip()
            offset = sentence.lower().find(token_form.lower())
        if offset >= 0:
            parts.append(f'S={offset}:{offset + len(token_form)}')
    return ';'.join(parts) if parts else None


# ---------------------------------------------------------------------------
# LMF ID formatters
# ---------------------------------------------------------------------------

def _ssid_norm(ssid: str) -> str:
    """Normalise a synset ID (convert -s adjective satellite to -a)."""
    return ssid[:-2] + '-a' if ssid.endswith('-s') else ssid


def _synset_lmf_id(lexid: str, ssid: str) -> str:
    return f'{lexid}-{_ssid_norm(ssid)}'


def _entry_lmf_id(lexid: str, lemma: str, pos: str) -> str:
    return f'{lexid}-{escape_lemma(lemma)}-{pos}'


def _sense_lmf_id(lexid: str, lemma: str, ssid: str, pos: str) -> str:
    return f'{lexid}-{escape_lemma(lemma)}-{_ssid_norm(ssid)[:-2]}-{pos}'


# ---------------------------------------------------------------------------
# LMF construction
# ---------------------------------------------------------------------------

def build_lexicon(
    lang: str,
    syns: dict[str, list[str]],
    info: dict[str, list],
    ili_map: dict[str, str],
) -> dict:
    """Build a wn_edit Lexicon dict for one language.

    Args:
        lang: Two-letter TUFS language code.
        syns: Output of :func:`syn_to_cid`.
        info: Output of :func:`cid_info` (first element).
        ili_map: Output of :func:`load_ili_map`.

    Returns:
        Lexicon dict suitable for ``wn.lmf.dump()``.
    """
    lexid = f'tufs-{lang}'
    _l3, language = l2l3(lang)
    bcp47 = _L2BCP47.get(lang, lang)

    # {(lm, pos): {'audio': ..., 'pron_text': ..., 'pron_variety': ...,
    #              'morph_var': ..., 'senses': [...]}}
    entry_data: dict[tuple[str, str], dict] = {}
    seen_sids: set[str] = set()
    synset_ilis: dict[str, str] = {}

    for ssid, concept_ids in syns.items():
        pos = 'a' if ssid.endswith(('-a', '-s')) else ssid[-1]
        ssid_lmf = _synset_lmf_id(lexid, ssid)
        synset_ilis[ssid_lmf] = ili_map.get(_ssid_norm(ssid), '')

        for cid in concept_ids:
            for lng, com, lem, exe, wid, is_basic, scenes, _bunrui in info.get(cid, []):
                if lng != lang:
                    continue

                # Extract Japanese reading (yomi) from structured comment field
                yomi = ''
                if lang == 'ja' and '【よみ】' in com:
                    yomi = com.split('【よみ】', 1)[1].split('【意味】')[0].strip('; \t')

                ex_parts = _parse_examples(exe)
                all_sentences_lower = ' '.join(s for s, *_ in ex_parts).lower()

                for w in lem.split('; '):
                    lm, tag, var = split_lem(w)
                    lm = lm.replace('\u200f', '')
                    if not lm:
                        continue

                    sid = _sense_lmf_id(lexid, lm, ssid, pos)
                    if sid in seen_sids:
                        continue
                    seen_sids.add(sid)

                    examples = [
                        make_example(
                            sentence,
                            meta={'note': note} if (note := _example_note(sentence, reading, function, token)) else None,
                        )
                        for sentence, reading, function, token in ex_parts
                    ]

                    sense_meta: dict = {}
                    if is_basic:
                        sense_meta['note'] = 'tufs-basic'
                    if scenes:
                        sense_meta['subject'] = scenes

                    freq = all_sentences_lower.count(lm.lower()) if all_sentences_lower else 0

                    sense = make_sense(
                        sid,
                        ssid_lmf,
                        examples=examples or None,
                        counts=[make_count(freq)] if freq > 0 else None,
                        meta=sense_meta or None,
                    )

                    key = (lm, pos)
                    if key not in entry_data:
                        audio = AUDIO_BASE.format(lang=lang, wid=wid)
                        if tag == _TAG_PINYIN:
                            pron_text, pron_variety = var, _VAR_PINYIN
                        elif yomi and not tag:
                            pron_text, pron_variety = yomi, _VAR_JA_HIRA
                        else:
                            pron_text, pron_variety = '', ''
                        entry_data[key] = {
                            'audio': audio,
                            'pron_text': pron_text,
                            'pron_variety': pron_variety,
                            'morph_var': var if tag == _TAG_MORPH else '',
                            'senses': [],
                        }
                    elif tag == _TAG_MORPH and not entry_data[key]['morph_var']:
                        entry_data[key]['morph_var'] = var
                    entry_data[key]['senses'].append(sense)

    # Build LexicalEntry objects
    lmf_entries = []
    for (lm, pos), ed in entry_data.items():
        pron: dict = {'text': ed['pron_text'], 'audio': ed['audio']}
        if ed['pron_variety']:
            pron['variety'] = ed['pron_variety']

        tags = [{'category': 'morph', 'text': ed['morph_var']}] if ed['morph_var'] else None

        lemma = make_lemma(lm, pos, pronunciations=[pron], tags=tags)
        lmf_entries.append(
            make_lexical_entry(
                _entry_lmf_id(lexid, lm, pos),
                lemma,
                senses=ed['senses'],
            )
        )

    # Build minimal Synset shells (ILI links only)
    lmf_synsets = [
        make_synset(ssid_lmf, ssid_lmf[-1], ili=ili or None)
        for ssid_lmf, ili in synset_ilis.items()
    ]

    return make_lexicon(
        id=lexid,
        label=f'TUFS Basic {language} Wordnet',
        language=bcp47,
        email=EMAIL,
        license=LICENSE,
        version=VERSION,
        url=BASE_URL,
        entries=lmf_entries,
        synsets=lmf_synsets,
    )


def write_lmf(lexicon: dict, outdir: Path, lang: str) -> None:
    """Write a single-lexicon WN-LMF XML file.

    Args:
        lexicon: Lexicon dict from :func:`build_lexicon`.
        outdir: Output directory.
        lang: Two-letter language code (used for the filename).
    """
    outdir.mkdir(parents=True, exist_ok=True)
    resource = make_lexical_resource([lexicon])
    wn_lmf.dump(resource, outdir / f'tufs-{lang}.xml')


def main() -> None:
    """Build per-language WN-LMF XML from tufs-vocab.tsv + tufs-omw-map.tsv."""
    langs = [
        'ar', 'as', 'de', 'en', 'es', 'fr', 'id', 'ja',
        'km', 'ko', 'lo', 'mn', 'ms', 'my', 'pb', 'pt',
        'ru', 'th', 'tl', 'tr', 'ur', 'vi', 'zh',
    ]

    info, _langs = cid_info(TUFS_VOCAB)
    syns = syn_to_cid(TUFS_OMW_MAP, info)
    ili_map = load_ili_map(ILI_MAP)

    for lang in langs:
        lexicon = build_lexicon(lang, syns, info, ili_map)
        write_lmf(lexicon, OUTDIR, lang)
        n_entries = len(lexicon['entries'])
        n_synsets = len(lexicon['synsets'])
        print(f'{lang}: {n_entries} entries, {n_synsets} synsets')


if __name__ == '__main__':
    main()
