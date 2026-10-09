# Сборщик словаря вкладки «АНГЛИЙСКИЙ»

Скрипты, которыми собран `stamina/english/data/vocab.json`. Только открытые источники
(лицензии — в [docs/ENGLISH_DATA.md](../../docs/ENGLISH_DATA.md)). Для работы приложения они не нужны.

Нужно: Python 3.11+, `pip install wordfreq nltk cmudict torch transformers sentencepiece sacremoses`,
WordNet для NLTK (`corpora/wordnet.zip` из nltk_data), около 10 ГБ места на время сборки.

Порядок (всё в одной рабочей папке):

1. `python -c "import json,wordfreq; json.dump(wordfreq.top_n_list('en', 90000), open('cand.json','w'))"`
2. `curl -L https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl | python filter_kaikki.py` → `kaikki_en.jsonl`
3. `python build_list.py` → `wordlist.json` (20 000 лемм), `formmap.json` (словоформа → лемма)
4. `python build_vocab.py` → `stage1.json` (часть речи, определение, IPA, respelling, слоги, подсказки, сложность)
5. Скачать `ru_50k.txt` (hermitdave/FrequencyWords, ru) и `python build_ru.py` → `ru_stage.json`, `mt_words.json`;
   `python mt.py mt_words.json` (opus-mt-en-ru) — перевод слов без перевода в Викисловаре.
6. Tatoeba: `eng_sentences.tsv.bz2`, `rus_sentences.tsv.bz2`, `eng-rus_links.tsv.bz2` с
   https://downloads.tatoeba.org/exports/ → `python build_tat.py` → `pairs.json`; `python tat.py` → `tat_best.json`.
7. `python gen_examples.py 20000` (Qwen2.5-1.5B-Instruct) — простой пример для слов без пары в Tatoeba.
8. `python assemble.py --need` → `mt_gen_need.json`; `python mt.py mt_gen_need.json`; `python assemble.py` → `vocab.json`.

`overrides.json` — ручные правки перевода (наши).
