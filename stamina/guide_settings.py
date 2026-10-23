"""Строка «Бортовой гид» в «Настройки → Ещё»: вкл/выкл, интервал, голос, проверка."""
from __future__ import annotations

import tkinter as tk

from stamina import theme
from stamina.guide_idle import DEFAULT_INTERVAL, INTERVALS
from stamina.hud import HudButton
from stamina.i18n import t as _t


def build(scr) -> None:
    px = theme.px
    row = scr._row(_t("Бортовой гид"),
                   _t("Бортовой компьютер без ИИ: время от времени приглушает радио и предлагает анекдот "
                      "или интересный факт (Enter — слушать, Esc — отказаться). Всё записано заранее и "
                      "работает без сети. Shift+F1 в любом окне — гид читает вслух справку этого окна."))
    scr.guide_btns = {}
    b = HudButton(row, _t("ВКЛ"), lambda: _set(scr, "guide_enabled", None), width=64, height=30, font_size=8)
    b.pack(side=tk.LEFT, padx=px(2))
    scr.guide_btns["on"] = b
    for key in INTERVALS:
        b = HudButton(row, _t("{0} мин").format(key.replace("-", "–")),
                      lambda k=key: _set(scr, "guide_interval", k), width=72, height=30, font_size=8)
        b.pack(side=tk.LEFT, padx=px(2))
        scr.guide_btns[key] = b
    row2 = scr._row(_t("Голос гида"), _t("Записи сделаны офлайн-голосами Windows: мужской — Павел, женский — Ирина."))
    for key, name in (("male", _t("МУЖСКОЙ")), ("female", _t("ЖЕНСКИЙ"))):
        b = HudButton(row2, name, lambda k=key: _set(scr, "guide_voice", k), width=90, height=30, font_size=8)
        b.pack(side=tk.LEFT, padx=px(2))
        scr.guide_btns[key] = b
    HudButton(row2, _t("▶ ПРОВЕРИТЬ"), lambda: _test(scr), height=30, font_size=8,
              color=theme.AMBER).pack(side=tk.LEFT, padx=px(6))
    sync(scr)


def _set(scr, key: str, value) -> None:
    st = scr.app.store.settings
    st[key] = (not st.get(key, True)) if value is None else value
    try:
        scr.app.apply_settings()
    except Exception:  # noqa: BLE001
        pass
    guide = getattr(scr.app, "guide", None)
    if guide is not None:
        guide.schedule()
    sync(scr)


def _test(scr) -> None:
    guide = getattr(scr.app, "guide", None)
    if guide is not None:
        guide.fire(force=True)


def sync(scr) -> None:
    st = scr.app.store.settings
    btns = getattr(scr, "guide_btns", {})
    on = bool(st.get("guide_enabled", True))
    if "on" in btns:
        btns["on"].set_text(_t("ВКЛ") if on else _t("ВЫКЛ"))
        btns["on"].set_active(on)
    cur = st.get("guide_interval", DEFAULT_INTERVAL)
    for k in INTERVALS:
        if k in btns:
            btns[k].set_active(k == cur)
    v = st.get("guide_voice", "male")
    for k in ("male", "female"):
        if k in btns:
            btns[k].set_active(k == v)
