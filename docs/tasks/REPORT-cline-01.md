# REPORT cline-01 — irregular verbs, conjugation, reference (Star Typing)

**Branch:** `cline/irregular-verbs` (base `4f6bd3b`)

## git log --oneline 4f6bd3b..
```
cb7afae Reference: glue punctuation to words, three rows of tenses; add screenshots of both skins
1583caa Add verb reference screen (search, modes, 12 tenses, add-to-card) to Verbs tab, F2 hotkey, i18n ru/uk/en/de
8733eb2 Load verb packs, search, gradual unlock of frequent-1000 and add-to-card
f0d0e27 Add verb pack builder and data: 197 irregular + 1000 frequent verbs from Wiktionary/Kaikki, CEFR-J, Tatoeba dumps
63bfc70 Add English conjugation engine: 12 tenses x 5 persons x 3 modes
```
(this report is committed on top of these)

## Changed files
- docs/tasks/img/reference-alt.png
- docs/tasks/img/reference-classic.png
- stamina/english/conjugation.py
- stamina/english/data/verbs/frequent_1000.json
- stamina/english/data/verbs/irregular.json
- stamina/english/pages_reference.py
- stamina/english/pages_verbs.py
- stamina/english/progress.py
- stamina/english/verbs.py
- stamina/i18n/de.json
- stamina/i18n/en.json
- stamina/i18n/ru.json
- stamina/i18n/uk.json
- tests/test_english_conjugation.py
- tests/test_english_reference_ui.py
- tests/test_english_verbs.py
- tools/build_verbs_pack.py

Not touched: `cefr.py`, `data/sets/*`, `quality.py`, `pages_warehouse.py`, `textutil.py`, licenses screen, `pages_setshub.py`, `pages_main.py`. The reference is integrated through `pages_verbs.py` (button **СПРАВОЧНИК** + F2).

## Data (built by `tools/build_verbs_pack.py` from local dumps)
| pack | verbs | Tatoeba examples | incomplete (<5 ex.) | no RU | no IPA |
|---|---|---|---|---|---|
| irregular.json | 197 | 950 | 12 (6.1%) | 6 | 0 |
| frequent_1000.json | 1000 | 2982 | 10 | 92 | 3 |

- 93.9% of irregular verbs have ≥5 examples; the rest are `status: incomplete` with `gaps`.
- Incomplete: behold, thrust, withstand, uphold, oversee, stride, remake, overlay, outgrow, outshine, interweave, retell.
- No RU: spring, repay, slit, overlay, outgrow, outshine (left empty — nothing invented).
- Counts by source: forms/IPA/glosses — Wiktionary via Kaikki.org (CC BY-SA 4.0): 197 + 1000 records; examples — Tatoeba (CC BY 2.0 FR): 950 + 2982, each with `source_id` (+ `ru_source_id`, `url`); frequency — hermitdave/FrequencyWords (CC BY-SA 4.0); CEFR level — CEFR-J 1.5 / Octanove C1–C2. Every record has `source` and `license`; pack header has `sources` and `thanks`.
- **Tatoeba API requests: 0** (official sentence/link dumps). Kaikki: one file download, UA `StarTypingDataBuilder/1.0`, 3 s pause, local cache.

## Features
- `conjugation.py`: 12 tenses × 5 persons × affirmative/negative/question; be/have/do, -ing/-ed spelling rules, irregular-token highlighting.
- `verbs.py`: `load_pack`, `search` (prefix on V1/V2/V3 first, then substring/RU), gradual unlock of frequent-1000: `UNLOCK_START=50`, `UNLOCK_STEP=50`, `UNLOCK_NEED=30` (setting `verbs_unlock_need`), irregular verbs never locked; `add_to_card` stores the form in `progress.data["verb_forms"]` and marks the word known when it is in the dictionary, so it reaches the warehouse via the existing API.
- `pages_reference.py`: live search from 1st char, Enter opens, ↑/↓ in the list, ←/→ tense, ↑/↓ person, Ctrl+Enter "→ в карточку", F2 open/back; V2/V3 and irregular tokens in amber; 🔒 + hint for locked verbs; real Tatoeba example with #id and license.
- i18n: 27 new keys in ru/uk/en/de (Russian literal keys like the rest of the app; dotted keys would show raw in RU). ru.json extended, not regenerated (`--fix-ru` would drop ~150 pre-existing keys).

## Tests
```
python -m pytest tests/test_english_conjugation.py tests/test_english_verbs.py -q
56 passed
python -m pytest tests/test_english_hub_ui.py tests/test_theme_skins.py tests/test_english_reference_ui.py -q
14 passed
python tools/i18n_check.py
de 2170/2170, en 2170/2170, uk 2170/2170, substitution errors 0
```

## Screenshots
- classic: `docs/tasks/img/reference-classic.png`
- alt (`_alt_view`): `docs/tasks/img/reference-alt.png`

## Open questions
1. `strike` and `forecast` didn't make it into the irregular pack (Kaikki entry choice). Add them by hand from Wiktionary, or leave as is?
2. Some RU glosses are imperfect (mean → «предназначать», become → «идти, подходить», hit → «ударяться», deal). Should the user's own `my_tr` override them, or do we curate a list?
3. `be`: s = "is" (am/are come from the conjugator). Is that OK for the card?
4. Unlock thresholds 50/50/30: should they go into the settings UI?
5. The alt skin currently differs only in layout width; it uses the same theme tokens. Does it need its own styling?