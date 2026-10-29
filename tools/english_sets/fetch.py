"""Однократная загрузка исходных данных для build_cefr.py — бережно к источникам.

Tatoeba публикует выгрузки раз в неделю; Kaikki — дамп Викисловаря (~0,5 ГБ gz).
Качаем по одному файлу, с паузой и честным User-Agent; уже скачанное не перекачиваем.
Повторять не чаще раза в месяц. Спасибо всем проектам — см. LICENSES.md / «Источники и лицензии».
"""
import sys, time, urllib.request
from pathlib import Path

UA = "StarTypingDataBuilder/1.0 (offline pack build; https://github.com/Teslyar75/My_Stamina)"
FILES = {
    "cefrj-vocabulary-profile-1.5.csv": "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/cefrj-vocabulary-profile-1.5.csv",
    "octanove-vocabulary-profile-c1c2-1.0.csv": "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/octanove-vocabulary-profile-c1c2-1.0.csv",
    "eng_sentences.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2",
    "rus_sentences.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/rus/rus_sentences.tsv.bz2",
    "eng-rus_links.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/eng/eng-rus_links.tsv.bz2",
    "kaikki-en.jsonl.gz": "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl.gz",
}


def main(work="."):
    w = Path(work); w.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dst = w / name
        if dst.exists() and dst.stat().st_size > 0:
            print("есть:", name); continue
        print("качаю:", url)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        time.sleep(3)          # пауза между файлами


if __name__ == "__main__":
    main(*sys.argv[1:])
