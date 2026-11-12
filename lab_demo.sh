#!/usr/bin/env bash
# Демо-режим Лаборатории: искусственные данные, плашка «ДЕМО-ДАННЫЕ».
# Файлы пилота не читаются и не пишутся.
set -euo pipefail
cd "$(dirname "$0")"
export STAMINA_LAB_DEMO=1
if [[ -x venv/bin/python ]]; then
  exec venv/bin/python main.py "$@"
fi
exec python3 main.py "$@"
