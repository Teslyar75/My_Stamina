"""Скачать русскую модель Vosk (Apache 2.0, ~45 МБ) в папку models/ проекта.

Запуск:  python tools/voice_input/get_model.py
Модель нужна только голосовому вводу (tools/voice_input/voice_input.py) —
сама программа Star Typing её не использует, у неё своя английская модель.

Другая модель:  python tools/voice_input/get_model.py vosk-model-small-ru-0.42
Список моделей: https://alphacephei.com/vosk/models
"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_NAME = "vosk-model-small-ru-0.22"
MODELS = Path(__file__).resolve().parents[2] / "models"


def download(name: str = DEFAULT_NAME) -> int:
    target = MODELS / name
    if (target / "am").exists():
        print(f"Модель уже есть: {target}")
        return 0
    url = f"https://alphacephei.com/vosk/models/{name}.zip"
    MODELS.mkdir(parents=True, exist_ok=True)
    tmp = MODELS / f"{name}.zip"
    print(f"Скачиваю {url} ...")
    try:
        urllib.request.urlretrieve(url, tmp)
        print("Распаковываю ...")
        with zipfile.ZipFile(tmp) as z:
            z.extractall(MODELS)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"Готово: {target}")
    print("Проверить:  python tools/voice_input/voice_input.py")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    name = argv[0] if argv else DEFAULT_NAME
    try:
        return download(name)
    except Exception as exc:  # noqa: BLE001
        print(f"Не получилось скачать: {exc}")
        print("Скачайте ZIP вручную с https://alphacephei.com/vosk/models "
              f"и распакуйте в {MODELS}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
