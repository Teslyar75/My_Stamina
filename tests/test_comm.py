"""ЭФИР: лента сообщений экипажа — слой данных (stamina/comm.py) и экран раздела.

Данные проверяются без Tk; экран — на настоящем Tk во временной папке данных
(как в test_web_nav_port), поэтому без дисплея тесты экрана пропускаются.
"""
import json
import tempfile
import unittest
from pathlib import Path

from stamina import comm, i18n, pilots


class CommDataTest(unittest.TestCase):
    """Общий файл экипажа: отправка, непрочитанное, устойчивость к порче."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))

    def tearDown(self):
        pilots.reset_root()

    def test_file_lives_in_crew_root(self):
        self.assertEqual(comm.path().name, "comm.json")
        self.assertEqual(comm.path().parent, Path(pilots.ROOT_DIR))
        comm.send("p1", "Комета", "тест")
        self.assertEqual(json.loads(comm.path().read_text(encoding="utf-8"))["version"], 1)

    def test_send_and_read_back(self):
        self.assertEqual(comm.messages(), [])
        comm.send("p1", "Комета", "  Привет,\nэкипаж!  ", ts=100.0)
        comm.send("p2", "Вега", "Как дела?", ts=101.0)
        msgs = comm.messages()
        self.assertEqual([m["callsign"] for m in msgs], ["Комета", "Вега"])
        self.assertEqual(msgs[0]["text"], "Привет, экипаж!")   # переносы и лишние пробелы убраны
        self.assertEqual(msgs[0]["ts"], 100.0)
        self.assertTrue(msgs[0]["id"])

    def test_empty_message_is_dropped(self):
        self.assertIsNone(comm.send("p1", "Комета", "   "))
        self.assertIsNone(comm.send("p1", "Комета", "\n\n"))
        self.assertEqual(comm.messages(), [])

    def test_long_message_is_trimmed(self):
        comm.send("p1", "Комета", "x" * (comm.MAX_TEXT + 50))
        self.assertEqual(len(comm.messages()[0]["text"]), comm.MAX_TEXT)

    def test_history_is_capped(self):
        for i in range(comm.MAX_MESSAGES + 5):
            comm.send("p1", "Комета", f"msg {i}", ts=float(i))
        msgs = comm.messages()
        self.assertEqual(len(msgs), comm.MAX_MESSAGES)
        self.assertEqual(msgs[-1]["text"], f"msg {comm.MAX_MESSAGES + 4}")

    def test_unread_counts_others_only(self):
        comm.send("p1", "Комета", "раз", ts=100.0)
        comm.send("p1", "Комета", "два", ts=101.0)
        self.assertEqual(comm.unread("p1"), 0)          # своё прочитано сразу
        self.assertEqual(comm.unread("p2"), 2)
        comm.mark_read("p2")
        self.assertEqual(comm.unread("p2"), 0)
        comm.send("p2", "Вега", "ответ", ts=102.0)
        self.assertEqual(comm.unread("p1"), 1)          # Комета ещё не видела ответ
        self.assertEqual(comm.unread(""), 0)            # без пилота
        comm.mark_read("")
        self.assertNotIn("", comm.load()["read"])

    def test_mark_read_is_monotonic(self):
        comm.send("p1", "Комета", "раз", ts=200.0)
        comm.mark_read("p2")
        self.assertEqual(comm.unread("p2"), 0)
        comm.mark_read("p2", ts=100.0)                  # назад не откатывает
        self.assertEqual(comm.unread("p2"), 0)

    def test_broken_file_is_ignored(self):
        comm.path().write_text("{это не json", encoding="utf-8")
        self.assertEqual(comm.messages(), [])
        self.assertEqual(comm.unread("p1"), 0)
        self.assertIsNotNone(comm.send("p1", "Комета", "снова"))
        self.assertEqual(len(comm.messages()), 1)


class CommScreenTest(unittest.TestCase):
    """Экран раздела: лента видна, отправка из поля ввода попадает в эфир."""

    class _App:
        """Заглушка пульта: экрану нужны пилот, справка и обновление счётчика."""

        def __init__(self):
            self.pilot = None
            self.help_calls = 0
            self.badge_calls = 0

        def open_help(self):
            self.help_calls += 1

        def update_comm_badge(self):
            self.badge_calls += 1

        @staticmethod
        def after(_ms, fn):
            fn()          # без цикла Tk: выполняем сразу

    def setUp(self):
        import tkinter as tk
        from stamina import theme
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        i18n.set_language("ru")
        try:
            self.root = tk.Tk()
        except tk.TclError:
            pilots.reset_root()
            self.skipTest("нет дисплея")
        self.root.withdraw()
        theme.init(self.root)
        self.app = self._App()
        self.app.pilot = pilots.create("Комета", accent="amber")
        from stamina.comm_screen import CommScreen
        self.scr = CommScreen(self.root, self.app)
        self.scr.pack()

    def tearDown(self):
        self.root.destroy()
        i18n.set_language("ru")
        pilots.reset_root()

    def test_empty_state_then_send(self):
        self.scr.refresh()
        self.assertIn("пусто", self.scr.text.get("1.0", "end"))
        self.scr.entry.insert(0, "Привет, экипаж!")
        self.scr._send()
        self.assertEqual(len(comm.messages()), 1)
        self.assertEqual(self.scr.entry.get(), "")          # поле очищено
        body = self.scr.text.get("1.0", "end")
        self.assertIn("Привет, экипаж!", body)
        self.assertIn("Комета", body)
        self.assertIn("▸", body)                            # своё сообщение отмечено
        self.assertEqual(self.app.badge_calls, 1)

    def test_other_pilot_message_is_unread(self):
        comm.send("other", "Вега", "Есть связь?")
        self.assertEqual(comm.unread(self.app.pilot["id"]), 1)
        self.scr.refresh()
        self.assertIn("Есть связь?", self.scr.text.get("1.0", "end"))
        self.assertIn("Новых: 1", self.scr.info.cget("text"))
        self.assertEqual(comm.unread(self.app.pilot["id"]), 0)   # отметили прочитанным

    def test_without_pilot_input_is_disabled(self):
        self.app.pilot = None
        self.scr.refresh()
        self.assertEqual(str(self.scr.entry.cget("state")), "disabled")
        self.assertIn("кабину пилота", self.scr.text.get("1.0", "end"))

    def test_help_key(self):
        self.assertEqual(self.scr.page_help_key(), "comm")


class CommLayoutTest(unittest.TestCase):
    """Строка ввода видна и на низком окне: лента не должна её вытеснять."""

    def setUp(self):
        import tkinter as tk
        from stamina import theme
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        i18n.set_language("ru")
        try:
            self.root = tk.Tk()
        except tk.TclError:
            pilots.reset_root()
            self.skipTest("нет дисплея")
        self.root.geometry("900x360+0+0")     # окно заведомо ниже запроса экрана
        theme.init(self.root)
        app = CommScreenTest._App()
        app.pilot = pilots.create("Комета")
        from stamina.comm_screen import CommScreen
        self.scr = CommScreen(self.root, app)
        self.scr.pack(fill="both", expand=True)
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        i18n.set_language("ru")
        pilots.reset_root()

    def test_input_row_is_visible(self):
        e = self.scr.entry
        self.assertTrue(e.winfo_ismapped(), "поле ввода не показано")
        self.assertGreater(e.winfo_height(), 5)
        self.assertTrue(self.scr.send_btn.winfo_ismapped(), "кнопка «ОТПРАВИТЬ» не показана")
        bottom = e.winfo_rooty() + e.winfo_height()
        self.assertLessEqual(bottom, self.root.winfo_rooty() + self.root.winfo_height())


class CommZoneIntegrationTest(unittest.TestCase):
    """«ЭФИР» в настоящем пульте: раздел загружен, непрочитанное красит кнопку шапки."""

    def setUp(self):
        import tkinter as tk
        self._tmp = tempfile.mkdtemp()
        pilots.reset_root(Path(self._tmp))
        i18n.set_language("ru")
        self.me = pilots.create("Комета")
        pilots.create("Вега", accent="green")
        pilots.activate(self.me["id"])
        try:
            from stamina.cockpit import Cockpit
            self.app = Cockpit()
        except tk.TclError:
            pilots.reset_root()
            self.skipTest("нет дисплея")
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        i18n.set_language("ru")
        pilots.reset_root()

    def test_zone_loaded_and_badge_colours_unread(self):
        from stamina import comm_hook, theme
        self.assertIn(comm_hook.KEY, [s for s, _ in self.app.SCREENS])
        # отсек собирается отложенно (after 120 мс) — на быстрой машине его ещё нет
        self.app._ensure_screen(comm_hook.KEY)
        self.assertIn(comm_hook.KEY, self.app.screens)
        button = self.app.nav_buttons[comm_hook.KEY]
        self.app.show("bridge")
        self.app.update_comm_badge()
        self.assertEqual(button.color.upper(), theme.CYAN.upper())     # непрочитанного нет
        comm.send("vega-id", "Вега", "Есть связь?")                    # писал другой пилот
        self.app.update_comm_badge()
        self.assertEqual(button.color.upper(), theme.AMBER.upper())    # кнопка подсвечена
        self.app.show(comm_hook.KEY)
        self.assertEqual(comm.unread(self.me["id"]), 0)                # открыли — прочитано
        self.assertEqual(button.color.upper(), theme.CYAN.upper())


if __name__ == "__main__":
    unittest.main()
