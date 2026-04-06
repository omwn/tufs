




================
 tufs-vocab.tsv
================

.. csv-table:: Vocabulary and examples
   :header: "cid", "lang", "wid", "lemma", "meaning", "example"
   :delim: @
   :widths: auto

   30521@en@1208@word@語（ご）@Can you please explain the meaning of this word?|この単語の意味を説明してもらえませんか。
   35036@ms@707@lukisan; melukis@【よみ】\\n え\\n\\n【意味】\\n picture@ Warna lukisan ini cantik.|この　絵は　色が　きれいです。
   
cid:
  The shared id of the concept, used to link vocabularies across languages

lang:
  The two letter language code

wid:
  The language internal word (or sense) id this can be used to link to

  * the page at TUFS:
    http://www.coelang.tufs.ac.jp/mt/en/vmod/v_search_detail.php?id=1208
    
  * the pronunciation:
    http://www.coelang.tufs.ac.jp/mt/en/vmod/sound/word/word_1208.mp3

lemma:
  The realization of this concept in this language.
  Sometimes there are multiple lemmas, in which case
  they will be separated by "; ", like in Malay:
  *lukisan; melukis* "picture"

  For some languages, there is extra information in brackets.

  zh:
    the pronunciation in pinyin

  id:
    the root of the word

  ar,as:
    the irregular (broken) plural

meaning:
  notes on the meaning and usage (in Japanese)
  FIXME: add example

example:
  an example of the lemma being used,
  with a gloss in Japanese, seperated by a '|'


================
 bunrui.tsv
================

The codes from the 分類語彙表 https://pj.ninjal.ac.jp/corpus_center/goihyo.html

These are a four level hierarchy for Japanese vocabulary.   Those
starting with 1 are substances (nouns), 2 are events (verbs) 3 are
aspects (adjectives) and 4 are everything else.

Some of the mid levels are translated into four languages in bunrui_names.tsv

.. csv-table:: Example entries of the bunrui_names.tsv
   :header: "code", "English", "Malay", "Myanmar", "Japanese"
   :delim: @
   :widths: auto

   4.11@Connection@Hubungan@ကြားဆက်@接続
   4.30@Emotion@Emosi@စိတ်ခံစားမှု@感動
   4.31@Judgement@Penilaian@ဆုံးဖြတ်@判断
   4.32@Address@Panggilan@ခေါ်ဝေါ်@呼び掛け
   4.33@Greeting@Ucapan@နှုတ်ဆက်@挨拶
   4.50@Animal calls@Bunyi haiwan@တိရစ္တာန်များ၏အော်မြည်သံ@動物の鳴き声

The names for all four levels are avialable from https://pj.ninjal.ac.jp/corpus_center/goihyo.html

For example, teacher 先生 (1.241
体,主体,成員,専門的・技術的職業
