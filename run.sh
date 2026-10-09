#!/usr/bin/env bash
# Star Typing — запуск на Linux. Есть .venv (после install.sh) — из неё, иначе системный python3.
cd "$(dirname "$(readlink -f "$0")")"
if [ -x .venv/bin/python ]; then exec .venv/bin/python main.py "$@"; fi
if command -v python3 >/dev/null 2>&1 && python3 -c 'import tkinter' 2>/dev/null; then exec python3 main.py "$@"; fi
echo "Star Typing: не найден Python 3 с tkinter. Запустите установку:  bash install.sh"
exit 1
