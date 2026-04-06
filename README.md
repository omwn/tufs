

# Code and paper for matching TUFS basic Vocab to OMW 

---

## Pipeline

```
tufsdata/*.txt  (PostgreSQL dumps from TUFS Open Language Resources)
      │
      ▼  scripts/munge.py
tufs-vocab.tsv  (10-column TSV: cid lang wid lemma comment iids examples is_basic scenes bunrui)
      │
      ▼  scripts/tufs2wn.py
build/lmf/tufs-{lang}.xml  (WN-LMF 1.4, one file per language)
      │
      ▼  Cygnet  (external/cygnet/, auto-cloned on first run)
docs/cygnet/tufs.db.gz  (SQLite for web UI)
```

**`scripts/munge.py`** — parses SQL dumps → flat TSV with columns:
`cid`, `lang`, `wid`, `lemma`, `comment`, `iids`, `examples`, `is_basic`, `scenes`, `bunrui`.

**`scripts/tufs2wn.py`** — reads TSV → LMF XML per language, extracting:
- lemmas and semicolon-separated variant forms
- morphological variants from `(morph:tag)` annotations and Japanese comment patterns
- pronunciations: hiragana readings (`ja-Hira`) as `<Form>` variants, pinyin (`zh-pinyin`), and audio URLs
- synset definitions from `【意味】` comment fields (keeps TUFS-internal synsets alive in the DB)
- span-annotated example sentences, thematic domain labels, basic-vocabulary flags

**ILI mapping**: `tufs-omw-map.tsv` — TUFS concept IDs → Princeton WordNet 3.0 synset IDs.
~644 concepts are ILI-linked; ~2,274 are TUFS-internal with definitions from `【意味】`.

---

## Requirements

- [uv](https://github.com/astral-sh/uv) — Python package manager
- TUFS SQL dumps in `tufsdata/` — from [TUFS Open Language Resources](https://malindo.aa-ken.jp/TUFSOpenLgResources.html)
- Internet access on first run (to clone Cygnet and download OEWN)

Cygnet is auto-cloned to `external/cygnet/` on first build.
A `.venv` virtual environment is created automatically by `uv`.

---

## Build

```bash
bash build.sh              # full build: TSV → LMF XML → Cygnet DB → docs/
bash build.sh --lmf-only   # TSV + LMF XML only (no Cygnet)
bash build.sh --cygnet-only  # Cygnet packaging only (reuses existing XML)
```

### Preview locally

```bash
bash run.sh   # serves docs/ at http://localhost:8000
```

---

## Tests

```bash
uv run pytest tests/
```

Unit tests (`test_tufs2wn.py`, `test_source.py`) cover TSV parsing helpers.
Integration tests (`test_db.py`) check the built `docs/cygnet/tufs.db.gz`.

---

## Release 

The typical workflow is:
```bash
bash build.sh                       # build + validate XMLs
bash make-release.sh                # build tarballs + wn load test (inspect locally)
bash make-release.sh --pre-release  # tag, push, create pre-release on GitHub
# ... test the pre-release, check the web UI, share for review ...
bash make-release.sh --release      # promotes the existing pre-release (no re-upload)
```

If you discover a bug after pre-release that requires rebuilding the
XMLs with a new version number. Then you  bump VERSION,
rebuild, and release under the new version.


---


## Intermediate TSV (`tufs-vocab.tsv`)

 * Francis Bond, Hiroki Nomoto, Luís Morgado da Costa, and Arthur Bond. 2020. [Linking the TUFS Basic Vocabulary to the Open Multilingual Wordnet](https://aclanthology.org/2020.lrec-1.389/). In Proceedings of the Twelfth Language Resources and Evaluation Conference, pages 3181–3188, Marseille, France. European Language Resources Association.
 * Francis Bond. 2025. [Adding Audio to Wordnets](https://github.com/unipv-larl/GWC2025/releases/download/papers/GWC2025_paper_38.pdf).  Proceedings of the 13th International Global Wordnet Conference (GWC2025).  (Note: non-final version)
 * [![DOI](https://zenodo.org/badge/167881062.svg)](https://doi.org/10.5281/zenodo.15490536)

## Contents

#. Read basic vocab from the TUFS database dump
   #. output some stats
   #. format as input to the OMW linker

#. Automatically link to OMW
   #. add Japanese and Chinese synonyms and defitions

#. Hand check linked results
   #. should end with a table of TUFS to OMW links
   #. also fix minor errors in Chinese/Japanese wordnets

#. Use the links to:
   #. evaluate the existing wordnets
   #. create new data for the wordnets (should send)
      synonyms, example sentences, ...

This is the classification of concepts used by TUFS:

`Bunruigoihyou (Word List by Semantic Principle) <https://pj.ninjal.ac.jp/corpus_center/goihyo.html>`_

This contains the PostgreSQL dumps:

`TUFS data <https://malindo.aa-ken.jp/TUFSOpenLgResources.html>`_

This is the link to the Open Multilingual Wordnet:

`OMW <http://compling.hss.ntu.edu.sg/omw/>`_

