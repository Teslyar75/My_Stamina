"""Слайдшоу «Старой Англии»: широкий пул тем, случайный порядок без повторов, плавная смена."""
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stamina import theme
from stamina.idle import images


def _items(n_topics=5, per=3):
    return [{"path": f"/x/{t}_{i}.jpg", "url": f"u{t}_{i}", "topic": f"t{t}"}
            for t in range(n_topics) for i in range(per)]


class ShuffleBagTest(unittest.TestCase):
    def test_no_repeat_until_exhausted(self):
        items = _items()
        bag = images.ShuffleBag(items, random.Random(1))
        for _round in range(3):
            got = [bag.next()["path"] for _ in items]
            self.assertEqual(sorted(got), sorted(i["path"] for i in items))

    def test_neighbours_differ_in_topic(self):
        bag = images.ShuffleBag(_items(), random.Random(2))
        seq = [bag.next() for _ in range(15)]
        same = sum(1 for a, b in zip(seq, seq[1:]) if a["topic"] == b["topic"])
        self.assertLessEqual(same, 1)

    def test_order_is_random(self):
        a = [images.ShuffleBag(_items(), random.Random(s)).next()["path"] for s in range(10)]
        self.assertGreater(len(set(a)), 3)

    def test_add_on_the_fly(self):
        bag = images.ShuffleBag(_items(1, 2), random.Random(3))
        bag.next()
        bag.add([{"path": "/new.jpg", "url": "n", "topic": "new"}])
        seen = {bag.next()["path"] for _ in range(2)}
        self.assertIn("/new.jpg", seen)

    def test_empty(self):
        self.assertIsNone(images.ShuffleBag([]).next())


class PoolTest(unittest.TestCase):
    def setUp(self):
        theme.load_theme("old_england", apply_ui=False)
        self.cfg = theme.current()["slideshow"]

    def tearDown(self):
        theme.load_theme("spaceship", apply_ui=False)

    def test_topics_are_broad_buses_minor(self):
        topics = " ".join(self.cfg["topics"]).lower()
        for w in ("tower bridge", "big ben", "westminster abbey", "stonehenge", "bath", "oxford",
                  "cambridge", "cotswolds", "fog", "tea", "cobblestone", "rain", "victorian", "telephone"):
            self.assertIn(w, topics)
        plan = dict(images.plan_topics(self.cfg))
        bus = sum(n for t, n in plan.items() if "bus" in t.lower())
        self.assertLess(bus / sum(plan.values()), 0.05)

    def test_merge_dedupes_and_caps(self):
        a = _items(2, 2)
        out = images.merge_pool(a, a[:1] + [{"url": "z", "path": "/z"}], cap=4)
        self.assertEqual(len(out), 4)
        self.assertEqual(len({i["url"] for i in out}), 4)

    def test_offline_falls_back_to_skin_photos_quickly(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("stamina.storage.DATA_DIR", Path(tmp)), \
                mock.patch.object(images, "fetch_topic", return_value=[]) as ft, \
                mock.patch.object(images, "fetch_gifs", return_value=[]):
            got = []
            items = images.load_images("old_england", self.cfg, on_add=got.extend)
        self.assertTrue(items)
        self.assertEqual(items[0]["source"], "skin")
        self.assertEqual(got, items)
        self.assertLessEqual(ft.call_count, 3)

    def test_cached_pool_served_first_then_fresh(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("stamina.storage.DATA_DIR", Path(tmp)):
            d = images._cache_dir("old_england")
            p = d / "a.jpg"
            p.write_bytes(b"x")
            images._write_index(d, [{"url": "a", "path": str(p), "topic": "t"}])
            fresh = {"url": "b", "topic": "q"}

            def dl(it, _d):
                it["path"] = str(p.with_name("b.jpg"))
                return True
            with mock.patch.object(images, "fetch_topic", return_value=[fresh]), \
                    mock.patch.object(images, "_download", side_effect=dl):
                batches = []
                items = images.load_images("old_england", self.cfg, on_add=batches.append)
        self.assertEqual(batches[0][0]["url"], "a")
        self.assertEqual({i["url"] for i in items}, {"a", "b"})


class CrossfadeTest(unittest.TestCase):
    def test_fit_and_blend(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("no Pillow")
        from stamina.idle.overlay import Slideshow
        a = Slideshow._fit(Image.new("RGB", (1600, 900), "red"), 320, 240)
        b = Slideshow._fit(Image.new("RGB", (900, 1600), "blue"), 320, 240)
        self.assertEqual(a.size, (320, 240))
        mid = Image.blend(a, b, 0.5).getpixel((10, 10))
        self.assertTrue(100 < mid[0] < 160 and 100 < mid[2] < 160)


if __name__ == "__main__":
    unittest.main()
