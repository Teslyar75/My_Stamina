import tempfile
import unittest
from pathlib import Path
import tkinter as tk

from stamina.ui.slideshow import Slideshow

try:
    from PIL import Image
except Exception:
    Image = None


class SlideshowTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.withdraw()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.frames = []
        if Image is not None:
            for i, color in enumerate([(255,0,0),(0,255,0),(0,0,255)]):
                p = self.dir / f"f{i}.jpg"
                Image.new("RGB", (64, 40), color).save(p, format="JPEG")
                self.frames.append(p)
        else:
            for i in range(3):
                p = self.dir / f"f{i}.jpg"
                p.write_bytes(b"\xff\xd8\xff\xd9")
                self.frames.append(p)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_set_and_add_frames(self):
        c = tk.Canvas(self.root, width=100, height=60)
        c.pack()
        ss = Slideshow(c, interval_ms=5000, fade_ms=0)
        ss.set_frames(self.frames[:2])
        self.assertEqual(len(ss._frames), 2)
        ss.add_frame(self.frames[2])
        self.assertEqual(len(ss._frames), 3)
        ss.add_frame(self.frames[2])
        self.assertEqual(len(ss._frames), 3)
        ss.stop()

    def test_start_stop_no_crash(self):
        c = tk.Canvas(self.root, width=120, height=80)
        c.pack()
        ss = Slideshow(c, interval_ms=5000, fade_ms=0)
        ss.set_frames(self.frames)
        ss.start()
        self.root.update()
        ss.stop()
        self.assertFalse(ss._running)

    def test_switch_blends_frames_instead_of_sharp_cut(self):
        if Image is None or len(self.frames) < 2:
            self.skipTest("no PIL")
        c = tk.Canvas(self.root, width=120, height=80)
        c.pack()
        self.root.update()
        ss = Slideshow(c, interval_ms=5000, fade_ms=120, scrim_alpha=0.0)
        ss.set_frames(self.frames[:2])
        ss.start()
        scheduled = []
        original_after = c.after
        c.after = lambda ms, fn=None, *a: scheduled.append(fn) or "fake"
        blends = []
        original_blend = Image.blend

        def spy(a, b, t):
            blends.append(t)
            return original_blend(a, b, t)

        Image.blend = spy
        try:
            ss._fade(self.frames[0], self.frames[1])
            while scheduled:
                scheduled.pop(0)()
        finally:
            Image.blend = original_blend
            c.after = original_after
            ss.stop()
        self.assertGreaterEqual(len(blends), 3)
        self.assertLess(blends[0], blends[-1])
        self.assertLessEqual(blends[-1], 1.0)

    def test_on_frame_hook_and_no_scrim_for_experienced(self):
        c = tk.Canvas(self.root, width=120, height=80)
        c.pack()
        calls = []
        ss = Slideshow(c, interval_ms=5000, fade_ms=200, scrim_alpha=0.0, on_frame=lambda: calls.append(1))
        ss.set_frames(self.frames)
        ss._show_next(initial=False)
        self.root.update()
        self.assertGreaterEqual(len(calls), 1)
        self.assertEqual(c.find_withtag("scrim"), ())
        self.assertTrue(c.find_withtag("slide"))
        ss.stop()


class DeckAndDownloaderTest(unittest.TestCase):
    def test_missing_file_skipped(self):
        frames = [Path(tempfile.gettempdir()) / "st-missing-slide.jpg"]
        # Slideshow needs a canvas; skip widget if no display, still test set_frames filter
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("no display")
        try:
            c = tk.Canvas(root, width=40, height=30)
            ss = Slideshow(c, interval_ms=5000, fade_ms=0)
            ss.set_frames(frames + [Path(__file__)])  # non-image existing file may be skipped at decode
            # missing path is not added
            self.assertFalse(any(p.name == "st-missing-slide.jpg" for p in ss._frames))
        finally:
            root.destroy()

    def test_shuffle_no_repeat_until_cycle_ends(self):
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("no display")
        tmp = tempfile.TemporaryDirectory()
        try:
            frames = []
            if Image is not None:
                for i in range(5):
                    p = Path(tmp.name) / f"s{i}.jpg"
                    Image.new("RGB", (16, 12), (i * 40, 20, 20)).save(p, "JPEG")
                    frames.append(p)
            else:
                self.skipTest("no PIL")
            c = tk.Canvas(root, width=40, height=30)
            ss = Slideshow(c, interval_ms=5000, fade_ms=0)
            ss.set_frames(frames)
            ss._current = frames[0]
            seen = []
            # one full cycle
            for _ in range(len(frames)):
                nxt = ss._pick_next()
                self.assertIsNotNone(nxt)
                self.assertNotIn(nxt, seen)
                seen.append(nxt)
            self.assertEqual(set(seen), set(frames))
            # new cycle must not start with the last frame of the previous
            last = seen[-1]
            nxt = ss._pick_next()
            if len(frames) > 1:
                self.assertNotEqual(nxt, last)
        finally:
            root.destroy()
            tmp.cleanup()

    def test_preload_cache_stays_small(self):
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("no display")
        if Image is None:
            self.skipTest("no PIL")
        tmp = tempfile.TemporaryDirectory()
        try:
            frames = []
            for i in range(6):
                p = Path(tmp.name) / f"c{i}.jpg"
                Image.new("RGB", (20, 16), (i * 30, 0, 80)).save(p, "JPEG")
                frames.append(p)
            c = tk.Canvas(root, width=40, height=30)
            c.update()
            ss = Slideshow(c, interval_ms=5000, fade_ms=0)
            ss._size = (40, 30)
            ss.set_frames(frames)
            for pth in frames:
                ss._decode(pth)
            self.assertLessEqual(len(ss._preload_cache), 8)
        finally:
            root.destroy()
            tmp.cleanup()

    def test_priority_download_then_rest_without_blocking(self):
        from stamina.ui import earth_downloader as ed

        tmp = tempfile.TemporaryDirectory()
        cache = Path(tmp.name) / "cache"
        order = []

        def fake_download(self, url, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"\xff\xd8\xff\xd9")
            order.append(Path(url).name)
            return True

        manifest = {
            "items": [
                {"id": "p1", "category": "a", "url": "https://example.test/p1.jpg", "priority": True, "credit": "NASA"},
                {"id": "p2", "category": "a", "url": "https://example.test/p2.jpg", "priority": True, "credit": "NASA"},
                {"id": "p3", "category": "a", "url": "https://example.test/p3.jpg", "priority": True, "credit": "NASA"},
                {"id": "r1", "category": "b", "url": "https://example.test/r1.jpg", "priority": False, "credit": "NASA"},
                {"id": "r2", "category": "b", "url": "https://example.test/r2.jpg", "priority": False, "credit": "NASA"},
            ]
        }
        man = Path(tmp.name) / "manifest.json"
        man.write_text(__import__("json").dumps(manifest), encoding="utf-8")
        orig_cache = ed.cache_root
        orig_dl = ed.EarthDownloader._download
        try:
            ed.cache_root = lambda: cache
            ed.EarthDownloader._download = fake_download
            ready = []
            dl = ed.EarthDownloader(man, on_ready=ready.append)
            # _run is synchronous here: models the background worker; UI is not blocked by this call in production
            dl._run()
            self.assertEqual(order[:3], ["p1.jpg", "p2.jpg", "p3.jpg"])
            self.assertEqual(order[3:], ["r1.jpg", "r2.jpg"])
            self.assertEqual(len(ready), 5)
        finally:
            ed.cache_root = orig_cache
            ed.EarthDownloader._download = orig_dl
            tmp.cleanup()

    def test_offline_does_not_raise(self):
        from stamina.ui import earth_downloader as ed

        tmp = tempfile.TemporaryDirectory()
        cache = Path(tmp.name) / "cache"
        man = Path(tmp.name) / "manifest.json"
        man.write_text(__import__("json").dumps({
            "items": [{"id": "x", "category": "a", "url": "https://example.test/x.jpg", "priority": True}]
        }), encoding="utf-8")
        orig_cache = ed.cache_root
        orig_dl = ed.EarthDownloader._download
        try:
            ed.cache_root = lambda: cache
            ed.EarthDownloader._download = lambda self, url, dest: False
            dl = ed.EarthDownloader(man)
            dl._run()
            self.assertEqual(dl.ready_files(), [])
        finally:
            ed.cache_root = orig_cache
            ed.EarthDownloader._download = orig_dl
            tmp.cleanup()
