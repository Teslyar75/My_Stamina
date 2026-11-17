# Handoff

Goal: английский только через «Иностранные языки»; грамматика EGIC C2 — порционная загрузка (след. задача).

Done:
- `stamina/nav.py`: `english` убран из `ZONE_ORDER`; `zone_of("english")` → `languages`;
  крошки `ИНОСТРАННЫЕ ЯЗЫКИ › АНГЛИЙСКИЙ`.
- `stamina/cockpit.py`: при загруженных languages+english убрать `english` из шапки, lazy-экран остаётся.
- `stamina/alt_ui.py`: зона `languages` в COMPARTMENTS (starship/steampunk).
- Тесты: `test_web_nav_port`, `test_alt_ui`.

Next: порционная подгрузка раздела «Грамматика» (не блокировать UI); затем push/PR.

Problems: нет.
