# Словарь вкладки «АНГЛИЙСКИЙ»: формат и источники

Файл `stamina/english/data/vocab.json` — массив из 20 000 записей, отсортированный по `rank`. Его собирают наши скрипты из открытых источников (см. ниже); никакие данные сторонних сайтов-тренажёров в нём не используются. Программа читает и `vocab.json.gz`, если файл сжат.

## Наборы

| Набор | Ранги / отбор | Название |
|---|---|---|
| `top-1000` | 1–1000 | Essential 1000 |
| `top-3000` | 1–3000 | Core 3000 |
| `top-10000` | 1–10 000 | Advanced 10 000 |
| `top-20000` | 1–20 000 | Master 20 000 |
| `dev-interview` | тематический (`sets`), файл `vocab_dev.json` | IT Interview (S-DEV) — английский для IT-собеседований |

Тематический набор `dev-interview` не входит в частотные top-* по `rank`. Сборка: `python scripts/build_dev_vocab.py` (источник CodersLingo, CC BY 4.0).

## Поля записи

```ts
interface VocabRecord {
  id: string;               // "w00001" — номер по рангу
  word: string;             // как пишется ("December", "leader")
  slug: string;             // ключ в нижнем регистре; по нему хранится прогресс
  rank: number;             // 1 = самое частое слово (wordfreq)
  level: SetId; sets: SetId[];
  pos: string; pos_all: string[];   // части речи (WordNet / Викисловарь)
  difficulty: "easy" | "medium" | "tricky";  // наше правило, см. ниже
  definition: string;       // определение на английском (WordNet, иначе Викисловарь)
  definition_source: "wordnet" | "wiktionary";
  tags: string[];           // тема из WordNet (lexname): "food", "feeling", "act"…
  ru: string; ru_src: "override" | "wiktionary" | "mt" | "";
  ipa: string | null;       // CMUdict → IPA нашим кодом (американский вариант), иначе IPA из Викисловаря
  respelling: string | null;        // "dih-VEH-luhp-muhnt", ударный слог заглавными (наш код по CMUdict)
  syllables: number; syllable_breakdown: string | null;  // перенос из Викисловаря или слоги respelling
  guide: string | null;     // подсказка по чтению и ударению (наш код, по-русски)
  notes: string[];          // заметки по трудным звукам (наш код, по-русски)
  sounds_like: string[] | null;     // омофоны из CMUdict (засчитываются при проверке произношения)
  example: string | null; example_ru: string | null;
  example_source: "tatoeba" | "generated" | null;
  sentences: { en: string; ru: string | null; source: "tatoeba" | "generated";
               tatoeba_id?: string; context: null; context_ru: null; level: null }[];
}
```

## Как собран

1. **Список слов и ранги** — частотный список `wordfreq` (top-90 000), словоформы сведены к лемме по меткам «form of» Викисловаря (years → year), отброшены имена людей, города, аббревиатуры-мусор, сленг и грубые слова. Оставлены месяцы, дни недели, страны, языки и национальности (с заглавной буквы).
2. **Часть речи и определение** — WordNet 3.0 (частоты смыслов решают основную часть речи); для служебных слов, которых нет в WordNet, — Викисловарь (дамп kaikki.org).
3. **Произношение** — CMUdict; перевод ARPAbet → IPA, деление на слоги (правило максимального начала слога), respelling, подсказки и заметки делает наш код. Омофоны — слова с одинаковой записью в CMUdict.
4. **Сложность** — наше правило: балл = набор (0–3) + лишние слоги + «трудное» написание (gh, ough, kn-, -mb, ps-, ph…) + расхождение букв и звуков + длина ≥ 11. 0–1 → easy, 2–3 → medium, ≥ 4 → tricky.
5. **Русский перевод `ru`** — переводы из Викисловаря, отобранные по частоте русского слова (частотный список hermitdave/FrequencyWords, CC BY-SA 4.0) и по части речи; ручные правки для ~200 слов; остальное — машинный перевод отдельного слова моделью Helsinki-NLP opus-mt-en-ru (Apache 2.0).
6. **Примеры** — реальные пары предложений английский–русский из Tatoeba (до 5 на слово для top-10000, до 3 для Master; выбираются короткие предложения с частыми словами). Если пары нет — одно простое предложение, сгенерированное локальной моделью Qwen2.5-1.5B-Instruct по определению из WordNet, с машинным переводом (`source: "generated"`).

## Лицензии данных

| Источник | Что взято | Лицензия |
|---|---|---|
| [wordfreq](https://github.com/rspeer/wordfreq) | частотный список, ранги | данные CC BY-SA 4.0, код Apache 2.0 |
| [Wiktionary](https://www.wiktionary.org/) через [kaikki.org](https://kaikki.org/) | переводы на русский, части речи, определения служебных слов, переносы, IPA | CC BY-SA 4.0 (и GFDL) |
| [WordNet 3.0](https://wordnet.princeton.edu/) | определения, части речи, темы | WordNet License (Princeton, разрешительная) |
| [CMUdict](https://github.com/cmusphinx/cmudict) | произношение | BSD-2-Clause |
| [Tatoeba](https://tatoeba.org/) | пары предложений EN–RU (`tatoeba_id` — номер английского предложения) | CC BY 2.0 FR |
| [FrequencyWords](https://github.com/hermitdave/FrequencyWords) | частоты русских слов для выбора перевода | CC BY-SA 4.0 |
| [opus-mt-en-ru](https://huggingface.co/Helsinki-NLP/opus-mt-en-ru) | машинный перевод (часть `ru`, переводы сгенерированных примеров) | модель Apache 2.0 |
| [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) | генерация простых примеров | модель Apache 2.0 |
| [CodersLingo](https://coderslingo.com/glossary/) (JSON-дамп) | IT-термины для набора `dev-interview` (`vocab_dev.json`) | CC BY 4.0 |

Так как в словаре есть данные Викисловаря и wordfreq (CC BY-SA 4.0), файл `vocab.json` распространяется на условиях **CC BY-SA 4.0** с указанием источников выше. Файл `vocab_dev.json` — адаптация датасета CodersLingo (**CC BY 4.0**); при распространении указывайте CodersLingo.
