# Handoff

Goal: уникальные карточки de/es/fr/it (одна лемма — одна плитка), примеры не теряются.

Done:
- tools/merge_lang_vocab_cards.py — слияние по лемме: pos_all, merged_slugs, все уникальные examples (дедуп по тексту).
- Прогон --write: JSON plugins de/es/fr/it, vocab.sqlite (--sqlite). Напр. FR A1 1826→585 карточек; примеры 9000→2859 (убраны копии одних и тех же фраз на разных slug).
- build_lang_vocab_all.py в конце уровня вызывает merge_vocab_payload.
- tests/test_merge_lang_vocab_cards.py — зелёный.

Next: перезапуск Star Typing — сетка без повторов леммы. При пересборке Tatoeba: build_lang_vocab_all.py уже сливает сам. Поручения Nemotron — docs/tasks/*.md.

Decisions:
- Главная карточка: лучший POS (noun>verb>…) и rank; slug остаётся от неё.
- В sqlite остаёт одна строка на лемму в полосе; остальное в JSON examples.

Problems:
- Коммит не сделан. .pre-merge.bak рядом с vocab_*.json — откат вручную.
