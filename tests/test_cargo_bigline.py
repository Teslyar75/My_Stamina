"""Cargo: a book as one 566k-char line must not freeze the Tk Text (soft line chunks)."""
import random
import time
import tkinter as tk
import types
import unittest

from stamina import screens


def _book(n=566_564):
    rnd = random.Random(1)
    words, size = [], 0
    while size < n:
        w = "".join(rnd.choice("abcdefghij") for _ in range(rnd.randint(2, 9)))
        words.append(w); size += len(w) + 1
    return " ".join(words)[:n].rstrip()


class TestSoftChunks(unittest.TestCase):
    def test_roundtrip(self):
        for text in (_book(50_000), "a\nb " * 3000, "x" * 5000, "", "one two\n\nthree"):
            parts = screens.soft_chunks(text, 100)
            joined = "".join(c + (" " if soft else "") for c, soft in parts)
            self.assertEqual(joined, text)
            for c, soft in parts:
                if soft:
                    self.assertLessEqual(len(c), 100)


class TestCargoBigLine(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.geometry("900x600+0+0")

    def tearDown(self):
        self.root.destroy()

    def test_566k_single_line_no_stall(self):
        text = _book()
        self.assertNotIn("\n", text)
        self.assertGreaterEqual(len(text), 566_000)
        t = tk.Text(self.root, wrap=tk.WORD)
        t.pack(fill=tk.BOTH, expand=True)
        fake = types.SimpleNamespace(_readonly=False, text=t, _update_preview=lambda: None)
        screens.CargoScreen._set(fake, text)
        worst = 0.0
        for w in (900, 700, 1100, 800, 1000, 900):
            self.root.geometry(f"{w}x600")
            a = time.perf_counter(); self.root.update(); worst = max(worst, time.perf_counter() - a)
            t.yview_moveto(0.5); a = time.perf_counter(); self.root.update(); worst = max(worst, time.perf_counter() - a)
        self.assertLess(worst, 1.0, f"stall {worst:.2f}s")
        got = screens.CargoScreen._get(fake)
        self.assertEqual(got, text)          # engine sees the same text: no extra \n, no Enter
        self.assertNotIn("\n", got)


if __name__ == "__main__":
    unittest.main()
