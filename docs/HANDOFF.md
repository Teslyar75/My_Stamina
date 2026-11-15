# HANDOFF

Goal:
- Полные словари DE/ES и учебники COERLL подключены к отсеку. Сырьё остаётся локально.

Done:
- База data/vocab_sources/kaikki/vocab.sqlite: немецкий 1347931, испанский 1333294. Ключ (lang, slug). Полосы Goethe/Cervantes A1–C2 и rest. Сводка summary.txt.
- stamina/languages/core/sqlite_vocab.py поверх vocab_a1.json. Набор, миссия с опытом, проверка SM-2, склад. Тесты языков 38 зелёных.
- tools/fetch_open_vocab.py. COERLL ещё качается локально, в git не входит.
- Карта сайта преподавателя: docs/pflege_jaeckels.md. Каталог источников: language_learning_apis.md.

Next:
- Дождаться «done» в data/vocab_sources/fetch_status.txt. В git от этого ничего не добавится.

Decisions:
- При совпадении slug побеждает слово A1 из Tatoeba.
- Миссии идут по открытому набору, иначе по первому частотному.
- Ветка agent/orion/multilang-core, в master не сливать. Снимок snap-20261115-0249.

Problems:
- нет
