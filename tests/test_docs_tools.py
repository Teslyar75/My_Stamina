"""Документы: модели диктовки RU/UK/EN, перевод EN/DE с Markdown, проверка у Ориона."""
import io
import os
import tempfile
import threading
import time
import tkinter as tk
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from stamina import book_check, doc_translate, docs, pilots
from stamina.voice import models as vm


def _fake_zip(name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{name}/am/final.mdl", b"x" * 1000)
        z.writestr(f"{name}/conf/model.conf", b"c")
    return buf.getvalue()


class _Resp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class TestModels(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_langs_include_russian(self):
        self.assertEqual(vm.LANGS, ("ru", "uk", "en"))

    def test_download_each_lang_and_detect(self):
        for lang in vm.LANGS:
            name = vm.MODELS[lang][0]
            seen = []
            path = vm.download(lang, root=self.root, progress=lambda d, t: seen.append((d, t)),
                               opener=lambda url, timeout: _Resp(_fake_zip(name)))
            self.assertTrue((path / "am").exists())
            self.assertTrue(seen and seen[-1][0] == seen[-1][1])
            self.assertEqual(vm.model_for(lang, self.root), path)
        self.assertEqual(set(vm.installed(self.root)), {"ru", "uk", "en"})
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith(".")], [])

    def test_no_substitution_and_cancel(self):
        name = vm.MODELS["ru"][0]
        vm.download("ru", root=self.root, opener=lambda u, timeout: _Resp(_fake_zip(name)))
        self.assertIsNone(vm.model_for("uk", self.root))     # чужую модель не подставляем
        ev = threading.Event(); ev.set()
        with self.assertRaises(InterruptedError):
            vm.download("en", root=self.root, cancel=ev,
                        opener=lambda u, timeout: _Resp(_fake_zip(vm.MODELS["en"][0])))
        self.assertIsNone(vm.model_for("en", self.root))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [name])

    def test_url(self):
        self.assertTrue(vm.url_for("uk").startswith("https://alphacephei.com/vosk/models/"))


class TestTranslate(unittest.TestCase):
    def test_markdown_markers_kept(self):
        calls = []

        def eng(lines, sl, tl):
            calls.append((sl, tl))
            return [x.upper() for x in lines]
        src = "# Заголовок\n- пункт\n> цитата\n\n```\nкод\n```\nтекст"
        out = doc_translate.translate_md(src, "en", engine=eng)
        self.assertEqual(out, "# ЗАГОЛОВОК\n- ПУНКТ\n> ЦИТАТА\n\n```\nкод\n```\nТЕКСТ")
        self.assertEqual(calls[0], ("ru", "en"))

    def test_argos_route_pivot(self):
        self.assertEqual(doc_translate.argos_route("ru", "de"), [("ru", "en"), ("en", "de")])
        self.assertEqual(doc_translate.argos_route("uk", "en"), [("uk", "en")])

    def test_net_fallback_mismatch_goes_line_by_line(self):
        from stamina import translator
        with mock.patch.object(translator, "_google", side_effect=lambda t, a, b: t.replace("\n", " ") + "!"), \
                mock.patch.object(translator, "_mymemory", side_effect=OSError):
            self.assertEqual(doc_translate._net_batch(["a", "b"], "ru", "en"), ["a!", "b!"])


class _Root(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._env = mock.patch.dict(os.environ, {"APPDATA": self.tmp,
                                                 "STAR_TYPING_MODELS": str(Path(self.tmp) / "models")})
        self._env.start()
        pilots.reset_root(Path(self.tmp) / "Stamina")
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        self.root.withdraw()
        from stamina.docs_screen import DocsScreen
        self.scr = DocsScreen(self.root, mock.Mock(store=None))
        self.scr.new_doc()

    def tearDown(self):
        self.root.destroy()
        self._env.stop()

    def pump(self, cond, sec=5):
        t0 = time.monotonic()
        while not cond() and time.monotonic() - t0 < sec:
            self.root.update()
            self.scr.poll_tools()
            time.sleep(0.02)


class TestEditorTools(_Root):
    def test_language_picker_ru_uk_en(self):
        s = self.scr
        self.assertEqual(s.dict_lang, "ru")
        self.assertIsNone(s.mic.model_path)
        root = Path(self.tmp) / "models"
        for lang in ("ru", "uk", "en"):
            vm.download(lang, root=root,
                        opener=lambda u, timeout, n=vm.MODELS[lang][0]: _Resp(_fake_zip(n)))
            s.choose_dict_lang(lang)
            self.assertEqual(s.dict_lang, lang)
            self.assertEqual(s.mic.model_path, root / vm.MODELS[lang][0])

    def test_dictation_without_model_downloads(self):
        with mock.patch.object(self.scr, "download_model") as dl:
            self.scr.set_dict_lang("uk")
            self.scr.start_dictation()
            dl.assert_called_once_with("uk")

    def test_translate_to_new_doc(self):
        s = self.scr
        s.title_var.set("Отчёт")
        s.text.insert("1.0", "# Привет\nмир")
        with mock.patch.object(doc_translate, "translate_md", lambda t, tl, **k: t.replace("Привет", "Hello").replace("мир", "world")):
            s.translate("en", "new", wait=True)
        self.assertEqual(s.title_var.get(), "Отчёт (EN)")
        self.assertEqual(s.text.get("1.0", "end-1c"), "# Hello\nworld")
        self.assertEqual(len(docs.list_docs()), 2)

    def test_translate_selection_below(self):
        s = self.scr
        s.text.insert("1.0", "один\nдва")
        s.text.tag_add("sel", "1.0", "1.4")
        with mock.patch.object(doc_translate, "translate_md", lambda t, tl, **k: "eins" if tl == "de" else t):
            s.translate("de", "below", wait=True)
        self.assertEqual(s.text.get("1.0", "end-1c"), "один\n\neins\nдва")

    def test_orion_check_and_apply(self):
        s = self.scr
        s.text.insert("1.0", "Превет, как дила? Превет!")
        made = []
        with mock.patch.object(book_check, "FixesWindow", lambda app, fixes, on_apply: made.append((fixes, on_apply))):
            s.check_text(ask=lambda p: '[{"bad": "Превет", "good": "Привет"}, {"bad": "дила", "good": "дела"}]')
            self.pump(lambda: made)
        self.assertTrue(made)
        fixes, apply = made[0]
        self.assertEqual(fixes, [("Превет", "Привет"), ("дила", "дела")])
        apply(fixes)
        self.assertEqual(s.text.get("1.0", "end-1c"), "Привет, как дела? Привет!")
        self.assertTrue(s.check_btn)


if __name__ == "__main__":
    unittest.main()


class _FakeEngine:
    available = True

    def __init__(self):
        self.said = []
        self._ev = []

    def speak(self, text, **kw):
        self.said.append(text)
        sid = len(self.said)
        return sid

    def poll(self):
        out, self._ev = self._ev, []
        return out

    def __getattr__(self, name):
        return lambda *a, **k: None


class TestReadAloud(_Root):
    def test_speakable_keeps_offsets(self):
        from stamina.docs_tools import speakable
        src = "# Заг\n- **жирный** и [ссылка](http://x)"
        out = speakable(src)
        self.assertEqual(len(out), len(src))
        self.assertNotIn("*", out)
        self.assertIn("жирный", out)

    def test_read_selection_highlights(self):
        from stamina.voice import engine as ve
        s = self.scr
        s.text.insert("1.0", "Первое предложение документа длинное. Второе предложение тоже длинное.")
        s.text.tag_add("sel", "1.38", "end-1c")
        fake = _FakeEngine()
        with mock.patch.object(ve, "make_engine_for", lambda spec="": (fake, "")):
            s.read_toggle()
            s._tts_tick()
            self.assertEqual(s.tts.state, "playing")
            self.assertTrue(fake.said and fake.said[0].startswith("Второе"))
            self.assertEqual(s.text.index("speak.first"), "1.38")
            s.read_toggle()
            self.assertEqual(s.tts.state, "paused")
            s.read_stop()
        self.assertEqual(s.tts.state, "idle")
        self.assertEqual(s.text.tag_ranges("speak"), ())


class TestLongDocs(_Root):
    BOOK = "".join(f"# Глава {n}\nЭто первое длинное предложение главы номер {n}. "
                   f"А это второе длинное предложение той же главы.\n\n" for n in range(1, 4))

    def _read(self):
        from stamina.voice import engine as ve
        fake = _FakeEngine()
        p = mock.patch.object(ve, "make_engine_for", lambda spec="": (fake, ""))
        p.start()
        self.addCleanup(p.stop)
        return fake

    def test_start_from_cursor_and_resume(self):
        s = self.scr
        s.text.insert("1.0", self.BOOK)
        s.save_now()
        fake = self._read()
        s.text.mark_set("insert", "4.0")                      # «# Глава 2»
        s.read_toggle()
        self.assertTrue(fake.said[0].startswith("Глава 2"))
        s.read_chapter(1)                                     # ⏭ — к главе 3
        self.assertTrue(fake.said[-1].startswith("Глава 3"))
        s.read_stop()
        self.assertGreater(s.saved_read_pos(), 0)
        s.text.mark_set("insert", "1.0")                      # курсор в начале — продолжить
        s.read_toggle()
        self.assertTrue(fake.said[-1].startswith("Глава 3"))
        s.read_stop()

    def test_chapter_nav_idle_moves_cursor(self):
        s = self.scr
        s.text.insert("1.0", self.BOOK)
        s.text.mark_set("insert", "1.0")
        s.read_chapter(1)
        self.assertEqual(s.text.index("insert"), "4.0")
        s.read_chapter(-1)
        self.assertEqual(s.text.index("insert"), "1.0")

    def test_big_doc_typing_is_local(self):
        s = self.scr
        s.text.insert("1.0", "**жирный** строка\n" * 6000)
        s.highlight()                                         # большой — видимое сразу, остальное фоном
        self.pump(lambda: "md_b" in s.text.tag_names("5999.3"), sec=20)
        self.assertIn("md_b", s.text.tag_names("5999.3"))
        s.text.mark_set("insert", "3000.0")
        s.text.insert("insert", "# ")
        t0 = time.perf_counter()
        s.schedule_highlight()
        s._run_scheduled_hl()
        self.assertLess(time.perf_counter() - t0, 0.2)
        self.assertIn("md_h1", s.text.tag_names("3000.3"))


class TestFocusMode(_Root):
    def _key(self, sym, char=""):
        return mock.Mock(keysym=sym, char=char, keycode=79, state=0)

    def test_o_toggles_outside_editor_and_esc_exits(self):
        s = self.scr
        self.root.deiconify()
        s.pack(fill=tk.BOTH, expand=True)
        self.root.update()
        self.root.update()
        s.listbox.focus_force()
        self.root.update()
        self.assertEqual(s.on_key(self._key("o", "o")), "break")
        self.assertTrue(s.in_focus())
        self.root.update()
        self.assertFalse(s.left_panel.winfo_ismapped())       # список скрыт
        self.assertTrue(s.right_panel.winfo_ismapped())       # редактор остался
        self.assertEqual(s.on_key(self._key("Escape")), "break")
        self.assertFalse(s.in_focus())
        self.root.update()
        self.assertTrue(s.left_panel.winfo_ismapped())

    def test_cyrillic_shcha_and_typing_untouched(self):
        s = self.scr
        self.root.deiconify()
        s.pack(fill=tk.BOTH, expand=True)
        self.root.update()
        s.listbox.focus_force()
        self.root.update()
        s.on_key(self._key("Cyrillic_shcha", "щ"))
        self.assertTrue(s.in_focus())
        s.toggle_focus(False)
        s.text.focus_force()
        self.root.update()
        self.assertIsNone(s.on_key(self._key("o", "o")))      # в редакторе O — это буква
        self.assertFalse(s.in_focus())

    def test_help_stays_visible_in_focus(self):
        s = self.scr
        self.root.deiconify()
        s.pack(fill=tk.BOTH, expand=True)
        self.root.update()
        s.toggle_help(True)
        s.toggle_focus(True)
        self.root.update()
        self.assertTrue(s.left_panel.winfo_ismapped())
        self.assertTrue(s.right_panel.winfo_ismapped())
        s.toggle_help(False)                                   # справку закрыли — фокус пересобран
        self.root.update()
        self.assertTrue(s.in_focus())
        self.assertFalse(s.left_panel.winfo_ismapped())
        s.toggle_focus(False)


class TestOpenFile(_Root):
    def _png(self):
        import base64
        return base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

    def test_formats_import_and_write_back(self):
        from stamina import docs, docs_import
        d = Path(self.tmp)
        src = docs.Document("Книга", [{"t": "# Глава 1\nТекст **жирный** и *курсив*.\n- пункт\n"},
                                       {"img": "images/1.png", "w": 0}, {"t": "Конец\n"}],
                            {"images/1.png": self._png()})
        docs.export_docx(src, d / "a.docx")
        got = docs_import.import_file(d / "a.docx")
        self.assertEqual(got.title, "Книга")
        self.assertIn("# Глава 1", got.text)
        self.assertIn("**жирный**", got.text)
        self.assertIn("*курсив*", got.text)
        self.assertIn("- пункт", got.text)
        self.assertEqual(sum(1 for s in got.segments if "img" in s), 1)
        self.assertIn("Конец", got.text)
        (d / "b.txt").write_bytes("Привет, борт".encode("cp1251"))
        self.assertEqual(docs_import.import_file(d / "b.txt").text, "Привет, борт")
        p = docs.save(src, d / "c.stdoc")
        st = docs_import.import_file(p)
        self.assertIsNone(st.path)
        self.assertTrue(docs_import.can_write_back(got))
        self.assertFalse(docs_import.can_write_back(st))
        with self.assertRaises(ValueError):
            docs_import.import_file(d / "x.pdf")

    def test_open_edit_read_and_save_back(self):
        d = Path(self.tmp) / "note.md"
        d.write_text("# Заметка\nстрока\n", encoding="utf-8")
        s = self.scr
        with mock.patch.object(s, "preview") as pv:
            s.open_file(d, "edit")
            pv.assert_not_called()
            self.assertEqual(s.doc.title, "Заметка")
            self.assertEqual(Path(s.doc.source), d)
            self.assertIsNotNone(s.doc.path)                       # стал документом в списке
            self.assertTrue(any(it["title"] == "Заметка" for it in s._items))
            s.open_file(d, "read")
            pv.assert_called_once()
        self.assertEqual(s._recent_files(), [str(d)])
        from stamina import docs
        self.assertEqual(docs.load(s.doc.path).source, str(d))     # источник переживает перезагрузку
        s.text.insert("end", "добавка\n")
        s.save_to_source()
        self.assertIn("добавка", d.read_text(encoding="utf-8"))

    def test_dialog_choose_and_modes(self):
        from stamina.docs_open import OpenDocDialog
        f = Path(self.tmp) / "r.txt"
        f.write_text("x", encoding="utf-8")
        dlg = OpenDocDialog(self.root, [str(f), str(Path(self.tmp) / "gone.txt")])
        self.assertEqual(dlg.recent, [str(f)])                      # пропавшие файлы не показываем
        dlg.done("edit")
        self.assertIsNone(dlg.result)                               # без файла не закрывается
        dlg.choose(str(Path(self.tmp) / "a.pdf"))
        self.assertIsNone(dlg.path)
        dlg.listbox.selection_set(0)
        dlg._on_recent()
        dlg.done("read")
        self.assertEqual(dlg.result, (str(f), "read"))
