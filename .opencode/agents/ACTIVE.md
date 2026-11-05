# Кто чем занят

> Перед правкой допиши строку: агент, тема, файлы, время начала.
> Закончил — убери свою строку. Пустая таблица — значит, никто ничего не держит.

| Агент | Что делает | Файлы | Начато |
|---|---|---|---|
| Орион (командир) | предложения из `docs/ORION_PROPOSALS_2026-10-20.md`: дисциплина агентов (2.1–2.3) | `AGENTS.md`, `tools/snapshot.ps1`, `.opencode/agents/ACTIVE.md` | 2026-10-20 12:40 |
| Qoder | P0 по внешнему аудиту: канал обновлений + конвейер качества. Ветку `agent/qoder/desktop-fixes` не сливаю, `master` не тронут. Отчёт: `.opencode/agents/QODER_DESKTOP_CHANGES_2026-11-05.md` | `stamina/updater.py`, `tests/test_updater.py`, `tools/ci_gate.py`, `tools/dep_audit.py`, `pyproject.toml`, `requirements-dev.txt`, `.github/workflows/quality-gate.yml`, `.github/workflows/release.yml`, `AGENTS.md`, `.gitignore` | 2026-11-05 10:40 |

## Правила

- Одна строка — одна тема. Две темы — две строки.
- Файлы перечисляй те, которые реально правишь, а не весь проект.
- Если работа прервалась больше часа назад — строку убери, чтобы не пугала.
