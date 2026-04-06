# TUFS Basic Vocabulary Wordnets — Release notes

## Changes in this release

- 

## Known issues

-

## Data

23 languages: Arabic, Assamese, German, English, Spanish, French, Indonesian,
Japanese, Khmer, Korean, Lao, Mongolian, Malay, Burmese, Portuguese (Brazil),
Portuguese, Russian, Thai, Filipino, Turkish, Urdu, Vietnamese, Chinese.

## Using with the `wn` module

```python
import wn
wn.download("file:tufs-VERSION.tar.xz")   # collection (all languages)
# or per-language, e.g.:
wn.download("file:tufs-en-VERSION.tar.xz")

en = wn.words("company", lang="en")
```

## Citation

Bond, Francis, Hiroki Nomoto, Luis Morgado da Costa and Arthur Bond (2020).
Linking the TUFS Basic Vocabulary to the Open Multilingual Wordnet.
In *Proceedings of LREC 2020*, pp. 3171–3177.
https://aclanthology.org/2020.lrec-1.389/
