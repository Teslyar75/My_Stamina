"""РАДИОРУБКА: плашки волн — две колонки, полное имя волны и текущая композиция."""
import tkinter as tk
import unittest
from unittest import mock

from stamina.radio import screen as radio_screen


class FakeEng:
    def __init__(self):
        self.data = {"favorites": []}
        self.station = None
        self.track = ""
        self.volume = 50
        self.playing = False
        self.history = []
        self.calls = []
        self.subs = []

    def bind_ui(self, app): pass
    def reload_store(self): pass
    def subscribe(self, cb): self.subs.append(cb)
    def unsubscribe(self, cb):
        if cb in self.subs:
            self.subs.remove(cb)
    def toggle(self): self.calls.append("toggle")
    def stop(self): self.calls.append("stop")
    def next_favorite(self): self.calls.append("next")
    def prev_favorite(self): self.calls.append("prev")
    def set_volume(self, v): self.volume = v
    def play_station(self, st):
        self.calls.append(("play", st.get("uuid")))
        return True


class FakeApp:
    def __init__(self):
        self.status = []

    def open_help(self): pass

    def set_status(self, text, color=None):
        self.status.append(text)


def station(i: int, name: str | None = None) -> dict:
    return {
        "uuid": f"uuid-{i}",
        "name": name or f"Радио {i}",
        "country": "Germany",
        "tags": "pop · hits",
        "bitrate": 128,
        "url": f"http://example/{i}",
    }


class TestRadioCards(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.geometry("1000x600")
        self.eng = FakeEng()
        self.app = FakeApp()
        self.patch_engine = mock.patch.object(radio_screen, "get_engine", return_value=self.eng)
        self.patch_engine.start()
        self.patch_backend = mock.patch.object(radio_screen, "backend_ok", return_value=True)
        self.patch_backend.start()
        self.scr = radio_screen.RadioScreen(self.root, self.app)
        self.scr.pack(fill=tk.BOTH, expand=True)
        self.root.update()

    def tearDown(self):
        self.scr.close()
        self.root.destroy()
        self.patch_backend.stop()
        self.patch_engine.stop()

    def paint(self, stations, width=None):
        if width is not None:                          # ширина в «логических» px, как в окне
            self.scr._list_width = lambda: radio_screen.px(width)
        self.scr._stations = stations
        self.scr._paint_list()
        self.root.update()

    def cards(self):
        return list(self.scr.list_inner.winfo_children())

    def test_two_columns_when_wide(self):
        self.paint([station(i) for i in range(5)], width=1200)
        rows = self.cards()
        self.assertEqual(len(rows), 5)
        cols = [c.grid_info()["column"] for c in rows]
        self.assertEqual(cols, [0, 1, 0, 1, 0])
        self.assertEqual(self.scr._list_cols, 2)

    def test_single_column_when_narrow(self):
        self.paint([station(i) for i in range(4)], width=560)
        self.assertEqual([c.grid_info()["column"] for c in self.cards()], [0, 0, 0, 0])
        self.assertEqual(self.scr._list_cols, 1)

    def test_columns_threshold(self):
        from stamina import theme
        self.assertEqual(self.scr._columns_for(theme.px(1200)), 2)
        self.assertEqual(self.scr._columns_for(theme.px(560)), 1)

    def test_full_station_name_is_kept(self):
        name = "Радио Европа Плюс — Очень Длинное Название Волны Без Обрезки"
        self.paint([station(0, name)], width=1200)
        card = self.cards()[0]
        name_lbl = card.winfo_children()[-1].winfo_children()[0]
        self.assertEqual(name_lbl._full_text, name)
        shown = name_lbl.cget("text")
        self.assertTrue(shown.startswith("Радио Европа") or shown.endswith("…"))
        self.assertNotEqual(shown, name[:48])

    def test_playing_station_shows_track(self):
        st = station(0)
        self.eng.station = st
        self.eng.track = "Mark Ronson — Nothing Breaks Like a Heart"
        self.paint([st, station(1)], width=1200)
        card = self.cards()[0]
        sub = card.winfo_children()[-1].winfo_children()[1]
        self.assertIn("Nothing Breaks", sub._full_text)
        self.assertEqual(card.cget("highlightbackground").upper(), radio_screen.CYAN.upper())

    def test_other_stations_show_meta(self):
        self.paint([station(0)], width=1200)
        sub = self.cards()[0].winfo_children()[-1].winfo_children()[1]
        self.assertIn("Germany", sub._full_text)
        self.assertIn("128 kbps", sub._full_text)

    def test_cards_update_without_rebuild(self):
        st = station(0)
        self.paint([st, station(1)], width=1200)
        before = self.cards()
        self.eng.station = st
        self.eng.track = "New Track — Amazing"
        self.scr._sync_cards()
        self.root.update()
        self.assertEqual(self.cards(), before)          # плашки не пересобирались
        sub = before[0].winfo_children()[-1].winfo_children()[1]
        self.assertIn("Amazing", sub._full_text)

    def test_play_and_favorite_buttons_work(self):
        st = station(3)
        self.paint([st], width=1200)
        buttons = [w for w in self.cards()[0].winfo_children()
                   if isinstance(w, radio_screen.HudButton)]
        self.assertEqual(len(buttons), 2)
        for b in buttons:
            b.command()
        self.assertIn(("play", "uuid-3"), self.eng.calls)
        self.assertEqual(len(self.eng.data["favorites"]), 1)
        self.assertEqual(self.eng.data["favorites"][0]["uuid"], "uuid-3")

    def test_empty_list_message(self):
        self.paint([], width=1200)
        kids = self.cards()
        self.assertEqual(len(kids), 1)
        self.assertEqual(kids[0].winfo_class(), "Label")


if __name__ == "__main__":
    unittest.main()
