# TUFS Basic Vocabulary Wordnets — Release 2026.04.06

## Changes in this release

- **Converted to Global WordNet LMF 1.4** format and repackaged for the `wn`
  Python module, uses `wn_edit` to build.
- **Linked to Open English WordNet (OEWN 2025)** via the Collaborative
  Interlingual Index (ILI), replacing the older Princeton WordNet 3.0 mapping.
- **TUFS-internal synsets preserved**: ~2,274 concepts without an ILI mapping
  now carry English definitions extracted from the original TUFS commentary
  (`【意味】` fields), keeping them visible in the database rather than being
  pruned.
- **Web interface** updated to use Cygnet with a new public landing page at
  <https://omwn.github.io/tufs/>.
- **Japanese hiragana readings** added as `<Form>` variant entries within each
  kanji lemma (e.g. 月曜日 now has げつようび as a variant form tagged `morph:hira`).
- **Per-language synset filtering**: only synsets referenced by at least one
  sense in a given language are written to that language's LMF file (~700–2,000
  synsets per language, down from ~2,900 previously).
- **Build pipeline** modernised: `uv` for environment management, LMF XML
  validated with `python -m wn validate` at build time, release packaging with
  `make-release.sh`.

## Known issues

- Example matching success rates vary by language: Myanmar (~45%), Arabic
  (~11%), and Spanish (~79%) have lower rates due to a combination of
  morphological complexity and shared example pools in the source data where
  some examples do not contain the target word.  These examples are in the LMF
  wordnets, but not the cygnet interface.
- No sense relations or concept relations are included in this release; the
  original TUFS data does not provide them.

## Data

23 languages: Arabic, Assamese, German, English, Spanish, French, Indonesian,
Japanese, Khmer, Korean, Lao, Mongolian, Malay, Burmese, Portuguese (Brazil),
Portuguese, Russian, Thai, Filipino, Turkish, Urdu, Vietnamese, Chinese.

All lexical data is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Using with the `wn` module

```python
import wn

# Download the full collection (all 23 languages)
wn.download("https://github.com/omwn/tufs/releases/latest/download/tufs-2026.04.06.tar.xz")

# Or a single language, e.g. Japanese
wn.download("https://github.com/omwn/tufs/releases/latest/download/tufs-ja-2026.04.06.tar.xz")

# Then query
words = wn.words("会社", lang="ja")
synsets = wn.synsets("company", lang="en")
```

## Citation

Bond, Francis, Hiroki Nomoto, Luis Morgado da Costa and Arthur Bond (2020).
Linking the TUFS Basic Vocabulary to the Open Multilingual Wordnet.
In *Proceedings of LREC 2020*, pp. 3171–3177.
<https://aclanthology.org/2020.lrec-1.389/>
