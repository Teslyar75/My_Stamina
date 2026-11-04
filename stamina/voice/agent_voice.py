"""Свой голос у каждого агента: ответы Ориона и, например, Star Typing (мост GitHub) звучат по-разному.

Правило (детерминированное, без случайности):
  * поле «ГОЛОС» агента задано — им и говорим;
  * Орион (агент по умолчанию) с пустым полем — голос корабля: тот, что движок выберет сам
    по языку (на Windows — мужской OneCore, обычно Microsoft Pavel);
  * другой агент с пустым полем — первый установленный голос, не совпадающий с голосом Ориона,
    сперва того же языка, потом любой;
  * голос в системе один — говорим им же (то есть голосом Ориона): лучше так, чем молчать.
"""
from __future__ import annotations

from stamina.voice import tts

ORION_ID = "orion"


def _lang_code(lang: str) -> str:
    return (lang or "ru").split("-")[0].lower()


def orion_voice(lang: str = "ru", orion_rec: dict | None = None) -> str:
    """Имя голоса, которым звучит Орион ("" — неизвестно: движок выберет сам)."""
    own = str((orion_rec or {}).get("tts_voice") or "").strip()
    return own or tts.preferred_voice(_lang_code(lang))


def voice_for(rec: dict | None, lang: str = "ru", orion_rec: dict | None = None) -> str:
    """Голос для ответа агента rec; "" — голос по умолчанию (как у Ориона)."""
    rec = rec or {}
    own = str(rec.get("tts_voice") or "").strip()
    if own:
        return own
    if rec.get("id", ORION_ID) == ORION_ID:
        return ""
    ship = orion_voice(lang, orion_rec).lower()
    rows = tts.voice_rows()
    code = _lang_code(lang)
    others = [r for r in rows if not (ship and ship in r[1].lower())]   # и «… Desktop»-двойники
    same_lang = [r for r in others if r[2].lower().startswith(code)]
    pick = (same_lang or others)
    return pick[0][1] if pick else ""


def choices() -> list[str]:
    """Имена голосов для выпадающего списка (без повторов, порядок системы)."""
    seen, out = set(), []
    for r in tts.voice_rows():
        if r[1] and r[1] not in seen:
            seen.add(r[1])
            out.append(r[1])
    return out
