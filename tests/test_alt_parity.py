"""Паритет «классика → alt»: каждый контрол, видимый в классике, доступен в Пульт-кабине
(на экране, в «⋯ ЕЩЁ» или в прокрутке) и не обрезан — для обоих скинов при трёх размерах окна.
Скрытые по состоянию и в классике (кнопки идущего занятия, диалоги Ориона, «перезапустить»
без обновления) исключаются — см. tools/alt_ui_audit.parity. Тест запускает реальные окна
tkinter в подпроцессах (~3 мин). Пропуск: STAMINA_SKIP_UI_AUDIT=1."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import alt_ui_audit as audit  # noqa: E402

pytestmark = pytest.mark.skipif(os.environ.get("STAMINA_SKIP_UI_AUDIT") == "1", reason="UI-аудит отключён")


@pytest.mark.parametrize("skin", ["starship", "steampunk"])
def test_alt_parity(skin):
    classic = audit.run("classic", skin, "1440x800")
    assert classic["controls"], "аудит классики ничего не нашёл"
    for size in audit.SIZES:
        p = audit.parity(classic, audit.run("alt", skin, size))
        assert not p["missing"], f"{skin} {size}: нет в alt: {p['missing'][:10]}"
        cut = [(r["screen"], r["tab"], r["text"], r["why"]) for r in p["cut"]]
        assert not cut, f"{skin} {size}: обрезано: {cut[:10]}"
        assert p["alt_ok"] == p["classic"]
