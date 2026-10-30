"""Классика: Английский > СКАНЕР — компактная панель (слово · произношение · данные) + канал связи.
Проверяем winfo-раскладку на 1024x600 и 1280x720: без прокрутки и обрезки, кнопка микрофона
справа в блоке проверки видна целиком (и в фокус-режиме O), Esc возвращает вид,
а O/T в поле ввода печатаются как буквы."""
import os
import tempfile
import time
import tkinter as tk
import types
import unittest
from pathlib import Path


class ScannerCompactTest(unittest.TestCase):
    def setUp(self):
        if os.name == "nt":
            try:   # реальные пиксели окна, как у самого приложения на Windows
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass
        from stamina import pilots, storage, theme
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        self._appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp
        self._defaults = dict(storage.DEFAULT_SETTINGS)
        storage.DEFAULT_SETTINGS.update(living_space="off", idle_minutes=0, skin="spaceship")
        self._init = theme.init

        def init96(root, _orig=self._init):
            root.tk.call("tk", "scaling", 96 / 72.0)   # логические пиксели, как на экране 100%
            _orig(root)
        theme.init = init96
        try:
            from stamina.cockpit import Cockpit
            self.app = Cockpit()
        except tk.TclError:
            self._restore()
            self.skipTest("нет дисплея")
        try:
            self.app.guide.stop()
        except Exception:
            pass

    def _restore(self):
        from stamina import pilots, storage, theme
        theme.init = self._init
        storage.DEFAULT_SETTINGS.clear()
        storage.DEFAULT_SETTINGS.update(self._defaults)
        pilots.reset_root()
        if self._appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._appdata

    def tearDown(self):
        try:
            self.app.destroy()
        except tk.TclError:
            pass
        self._restore()

    def pump(self, s=0.5):
        t = time.time()
        while time.time() - t < s:
            self.app.update()
            time.sleep(0.02)

    def _open_scanner(self):
        a = self.app
        self.pump(1.5)
        a.show("english")
        self.pump(1.0)
        scr = a.screens["english"]
        t = time.time()
        while not getattr(scr, "_built", True) and time.time() - t < 60:
            self.pump(0.2)
        scr.show("scanner")
        self.pump(1.0)
        page = scr.pages["scanner"]
        page.mic.speech_on = lambda: True          # как с моделью распознавания: кнопка микрофона видна
        page.mic.refresh_mode()
        self.pump(0.3)
        return scr, page

    def _rel(self, w):
        a = self.app
        return w.winfo_rootx() - a.winfo_rootx(), w.winfo_rooty() - a.winfo_rooty()

    def _assert_inside(self, w, what):
        a = self.app
        x, y = self._rel(w)
        self.assertTrue(w.winfo_ismapped(), f"{what}: не показан")
        self.assertGreaterEqual(x, 0, what)
        self.assertGreaterEqual(y, 0, what)
        self.assertLessEqual(x + w.winfo_width(), a.winfo_width() + 1, f"{what}: за правым краем")
        self.assertLessEqual(y + w.winfo_height(), a.winfo_height() + 1, f"{what}: за нижним краем")

    def _squeezed(self, root):
        bad = []

        def walk(w):
            for c in w.winfo_children():
                if not c.winfo_ismapped() or isinstance(c, tk.Toplevel):
                    continue
                cls = c.winfo_class()
                if cls in ("Label", "Button", "Canvas") and c.winfo_width() > 2 \
                        and c.winfo_width() < c.winfo_reqwidth() - 3 \
                        and not (cls == "Label" and int(c.cget("wraplength") or 0) > 0) \
                        and not str(c).endswith("!canvas") and c.winfo_reqwidth() < 3000:
                    bad.append(f"{str(c)[-60:]} {c.winfo_width()}/{c.winfo_reqwidth()}")
                px_ = w.winfo_rootx() + w.winfo_width()
                if c.winfo_width() > 2 and c.winfo_rootx() + c.winfo_width() > px_ + 1:
                    bad.append(f"{str(c)[-60:]} вылезает вправо")
                walk(c)
        walk(root)
        return bad

    def _check_layout(self, page, size):
        sf = page.sf
        self.assertEqual(tuple(sf.canvas.yview()), (0.0, 1.0), f"{size}: нужна прокрутка")
        self.assertEqual(self._squeezed(page), [], f"{size}: обрезано")
        for w, n in ((page.scan_panel, "панель сканера"), (page.chan, "канал связи"),
                     (page.mic.btn, "кнопка микрофона"), (page.sent, "предложение")):
            self._assert_inside(w, f"{size} {n}")
        # три группы — рядом, на всю ширину
        cols = [c for c in page.scan_panel.body.winfo_children() if c.winfo_width() > 20]
        xs = sorted(self._rel(c)[0] for c in cols)
        self.assertGreaterEqual(len(xs), 3, f"{size}: меньше трёх групп")
        # микрофон — справа в блоке проверки
        mx = self._rel(page.mic.btn)[0]
        cx = self._rel(page.chan)[0]
        self.assertGreater(mx, cx + page.chan.winfo_width() // 2, f"{size}: микрофон не справа")

    def test_layout_fits_small_screens_and_focus(self):
        scr, page = self._open_scanner()
        a = self.app
        for w, h in ((1024, 600), (1280, 720)):
            a.state("normal")
            a.minsize(640, 480)
            a.geometry(f"{w}x{h}+0+0")
            self.pump(1.2)
            if (a.winfo_width(), a.winfo_height()) != (w, h):
                continue   # оконный менеджер не дал нужный размер
            size = f"{w}x{h}"
            self._check_layout(page, size)
            ev = types.SimpleNamespace(keysym="o", widget=a, char="o", state=0, keycode=79)
            scr.on_key(ev)
            self.pump(0.6)
            self.assertIsNotNone(page._focus, f"{size}: O не включил фокус")
            self.assertFalse(scr.nav["scanner"].winfo_ismapped(), f"{size}: фокус не скрыл вкладки")
            self._assert_inside(page.mic.btn, f"{size} фокус: кнопка микрофона")
            self.assertEqual(self._squeezed(page), [], f"{size} фокус: обрезано")
            esc = types.SimpleNamespace(keysym="Escape", widget=a, char="", state=0, keycode=27)
            a._on_key(esc)
            self.pump(0.6)
            self.assertIsNone(page._focus, f"{size}: Esc не вышел из фокуса")
            self.assertTrue(scr.nav["scanner"].winfo_ismapped(), f"{size}: вкладки не вернулись")
            self._check_layout(page, size)

    def test_o_and_t_type_in_entry(self):
        scr, page = self._open_scanner()
        e = tk.Entry(page)
        e.place(x=0, y=0)
        e.focus_force()
        self.pump(0.3)
        for ch in "ot":
            ev = types.SimpleNamespace(keysym=ch, widget=e, char=ch, state=0, keycode=ord(ch.upper()))
            res = scr.on_key(ev)
            self.assertNotEqual(res, "break", f"{ch} перехвачен в поле ввода")
        self.assertIsNone(page._focus, "O в поле ввода включил фокус")
