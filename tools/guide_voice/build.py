"""Предзапись бортового гида: тексты → WAV (голоса Windows, офлайн) → MP3 (ffmpeg) + manifest.json.

Запускается разработчиком один раз после правки текстов, НЕ во время работы программы:

    python tools/guide_voice/build.py            # только новые/изменённые фразы
    python tools/guide_voice/build.py --force    # переписать всё
    python tools/guide_voice/build.py --voices male

Источники текста: stamina/guide_content/<lang>.json (заходы, шутки, факты, служебные
фразы) и stamina/page_help.PAGES (справка F1 каждого окна). Голоса — OneCore
(Microsoft Pavel — мужской, Microsoft Irina — женский), без сети. Нужен ffmpeg в PATH.
Результат: stamina/sounds/guide/<lang>/{male,female}/<id>.mp3 и manifest.json.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stamina import guide_idle  # noqa: E402

SYNTH = Path(__file__).resolve().parent / "synth.ps1"
BITRATE = "24k"
SAMPLE_RATE = "16000"
BATCH = 40


def items(lang: str) -> list[tuple[str, str, str]]:
    """(id, kind, text) всех фраз: заходы, служебные, шутки, факты, справка F1."""
    from stamina import page_help
    c = guide_idle.load_content(lang)
    out: list[tuple[str, str, str]] = []
    for group, lst in c["intros"].items():
        out += [(x["id"], "intro_" + group, x["text"]) for x in lst]
    out += [(x["id"], "system", x["text"]) for x in c["system"]]
    out += [(x["id"], "joke", x["text"]) for x in c["jokes"]]
    out += [(x["id"], "fact", x["text"]) for x in c["facts"]]
    for key, (title, text) in page_help.PAGES.items():
        out.append((guide_idle.help_clip_id(key), "help", guide_idle.spoken_help(title, text)))
    return out


def run_batch(jobs: list[dict]) -> None:
    if not jobs:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False)
        path = f.name
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SYNTH),
                        "-Jobs", path], check=True, stdout=subprocess.DEVNULL)
    finally:
        Path(path).unlink(missing_ok=True)


def to_mp3(ffmpeg: str, wav: Path, mp3: Path) -> None:
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-ar", SAMPLE_RATE,
                    "-c:a", "libmp3lame", "-b:a", BITRATE, str(mp3)], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--voices", default=",".join(guide_idle.VOICES))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--tmp", default="", help="папка для WAV (по умолчанию системная временная)")
    a = ap.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg не найден в PATH", file=sys.stderr)
        return 2
    out_dir = guide_idle.SOUND_ROOT / a.lang
    old = guide_idle.load_manifest(a.lang) if not a.force else {}
    old_clips = old.get("clips", {})
    voices = [v for v in a.voices.split(",") if v in guide_idle.VOICES]
    tmp = Path(a.tmp or tempfile.mkdtemp(prefix="guide_voice_"))
    tmp.mkdir(parents=True, exist_ok=True)
    clips: dict[str, dict] = {}
    todo: list[tuple[str, str, Path, Path]] = []
    jobs: list[dict] = []
    for cid, kind, text in items(a.lang):
        if cid in clips or any(t[0] == cid for t in todo):
            continue  # дубликат id — озвучиваем один раз
        h = guide_idle.text_hash(text)
        prev = old_clips.get(cid, {})
        files = {}
        for v in guide_idle.VOICES:
            rel = f"{v}/{cid}.mp3"
            mp3 = out_dir / rel
            keep = prev.get("hash") == h and v in prev.get("files", {}) and mp3.exists()
            if v in voices and not keep:
                mp3.parent.mkdir(parents=True, exist_ok=True)
                wav = tmp / f"{v}_{cid}.wav"
                spec = guide_idle.VOICES[v]
                jobs.append({"text": text, "voice": spec["voice"], "out": str(wav),
                             "rate": spec["rate"], "pitch": spec.get("pitch", ""), "pauses": True})
                todo.append((cid, v, wav, mp3))
                files[v] = rel
            elif keep or mp3.exists() and prev.get("hash") == h:
                files[v] = rel
        clips[cid] = {"kind": kind, "hash": h, "text": text, "files": files}
    print(f"фраз: {len(clips)}, к озвучке: {len(jobs)}")
    for i in range(0, len(jobs), BATCH):
        run_batch(jobs[i:i + BATCH])
        print(f"  синтез {min(i + BATCH, len(jobs))}/{len(jobs)}")
    for _cid, _v, wav, mp3 in todo:
        to_mp3(ffmpeg, wav, mp3)
        wav.unlink(missing_ok=True)
    valid = {f"{v}/{cid}.mp3" for cid, c in clips.items() for v in c["files"]}
    for p in out_dir.glob("*/*.mp3"):
        if f"{p.parent.name}/{p.name}" not in valid:
            p.unlink()
    manifest = {"lang": a.lang, "format": "mp3", "bitrate": BITRATE,
                "voices": {k: v["voice"] for k, v in guide_idle.VOICES.items()}, "clips": clips}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(p.stat().st_size for p in out_dir.rglob("*.mp3"))
    print(f"готово: {out_dir} — {size / 1024 / 1024:.1f} МБ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
