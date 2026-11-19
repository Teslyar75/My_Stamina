"""Импорт приложения не читает файлы уроков грамматики."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

IMPORT_PROBE = r'''
import builtins
import sys
from pathlib import Path

hits = []

def is_grammar_data(path) -> bool:
    text = Path(str(path)).as_posix().lower()
    if not text.endswith(".json"):
        return False
    return ("/english/grammar/" in text) or ("/plugins/" in text and "/grammar/" in text)

real_open = builtins.open

def tracked_open(file, mode="r", *args, **kwargs):
    if is_grammar_data(file) and ("r" in str(mode)):
        hits.append(str(file))
    return real_open(file, mode, *args, **kwargs)

_orig_read_text = Path.read_text
_orig_read_bytes = Path.read_bytes

def tr_read_text(self, *args, **kwargs):
    if is_grammar_data(self):
        hits.append(str(self))
    return _orig_read_text(self, *args, **kwargs)

def tr_read_bytes(self, *args, **kwargs):
    if is_grammar_data(self):
        hits.append(str(self))
    return _orig_read_bytes(self, *args, **kwargs)

builtins.open = tracked_open
Path.read_text = tr_read_text
Path.read_bytes = tr_read_bytes

import main  # noqa: E402
import stamina.app  # noqa: E402
import stamina.cockpit  # noqa: E402
import stamina.english_hook  # noqa: E402
import stamina.languages_hook  # noqa: E402
import stamina.screens  # noqa: E402
import stamina.english.screen  # noqa: E402
import stamina.languages.screen  # noqa: E402

blocked = [
    name for name in (
        "stamina.english.pages_grammar",
        "stamina.english.grammar.lessons",
        "stamina.languages.grammar_page",
        "stamina.languages.plugins.de.grammar_engine",
    )
    if name in sys.modules
]
if hits:
    raise SystemExit("grammar data loaded at import: " + "; ".join(hits))
if blocked:
    raise SystemExit("grammar modules imported at startup: " + ", ".join(blocked))
print("OK")
'''


def test_importing_app_and_main_pages_does_not_load_grammar_files() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-c", IMPORT_PROBE],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert proc.returncode == 0, (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert "OK" in (proc.stdout or "")