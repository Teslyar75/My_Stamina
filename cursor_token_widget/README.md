# Cursor Token Widget

Автономный каталог. Запускается **вне Star Typing**, без `import stamina`.

Источник реального Cursor usage API **не подтверждён**. Виджет не угадывает
официальный endpoint: он читает любой GET JSON с полями used/limit (и опционально
разбивкой по моделям). Токен хранится только в локальном config-файле
(`~/.cursor-token-widget.json` по умолчанию) и в архив не кладётся.

## Запуск параллельно с Cursor

```bash
python3 widget.py
```

Свой файл настроек:

```bash
python3 widget.py --config /path/to/widget.json
```

## Проверки каталога

```bash
python3 test_quota.py
```

## Содержимое

| Файл | Назначение |
|---|---|
| `widget.py` | окно: прогресс-бар, remaining, модели, автообновление |
| `quota.py` | парсер usage/quota JSON и сохранение настроек |
| `test_quota.py` | целевые тесты парсера/настроек |

Ветка сохранения в том же репозитории (новый repo не публиковался):
`cursor/token-widget-c61e`.
