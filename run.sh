#!/usr/bin/env bash
# Star Typing — запуск на Linux. Сначала .venv (после install.sh), иначе системный python3.
# Если окно открыть нельзя, причина всё равно будет видна: main.py пишет журнал и
# показывает окно (zenity / kdialog / xmessage). Отчёт о среде: ./run.sh --check
cd "$(dirname "$(readlink -f "$0")")" || exit 1

if [ -x .venv/bin/python ] && .venv/bin/python -c 'import sys' >/dev/null 2>&1; then
  exec .venv/bin/python main.py "$@"
fi
if [ -x .venv/bin/python ]; then
  echo "Star Typing: папка .venv не работает — беру системный Python." >&2
  echo "             пересоздать: rm -rf .venv && bash install.sh" >&2
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 main.py "$@"
fi

MSG="Star Typing: не найден Python 3.
Установите его вместе с окнами Tk:
  sudo apt install python3 python3-tk   (Ubuntu / Debian)
  bash install.sh                       (полная установка)"
echo "$MSG" >&2
if command -v zenity >/dev/null 2>&1; then
  zenity --error --no-wrap --title "Star Typing" --text "$MSG" >/dev/null 2>&1
elif command -v kdialog >/dev/null 2>&1; then
  kdialog --error "$MSG" --title "Star Typing" >/dev/null 2>&1
elif command -v xmessage >/dev/null 2>&1; then
  xmessage -center -title "Star Typing" "$MSG" >/dev/null 2>&1
fi
exit 1
