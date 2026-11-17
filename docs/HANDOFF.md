# Handoff

Goal: грамматика без зависаний; push ветки с навигацией и грамматикой.

Done:
- `GrammarPage`: оболочка сразу, JSON в фоне, темы порциями (`after`), кэш `load_grammar`.
- Убраны `init_grammar_tab` + автопереход на «Грамматика» при входе в английский.
- `tests/test_english_grammar.py`, i18n ключи грамматики (все локали).
- Ранее: english только через «Иностранные языки» (коммит 348d186).

Next: push `agent/orion/english-grammar`, PR в master; дальше — полный контент EGIU по уровням.

Problems: нет.
