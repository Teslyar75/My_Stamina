"""Навигация с клавиатуры: стрелки, Tab → меню, Enter, Esc, скрытые страницы не в счёт."""
import unittest


class KeyNavTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("нет дисплея")
        from stamina import keynav, theme
        from stamina.hud import HudButton
        theme.init(self.root)
        self.root.geometry("600x400+0+0")
        self.log = []
        menu = tk.Frame(self.root)
        menu.pack(fill="x")
        self.menu = []
        for i in range(3):
            b = HudButton(menu, f"M{i}", lambda i=i: self.log.append(f"m{i}"))
            b.nav_menu = True
            b.pack(side="left")
            self.menu.append(b)
        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True, pady=20)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        hidden = tk.Frame(body)
        hidden.grid(row=0, column=0, sticky="nsew")
        self.hidden_btn = HudButton(hidden, "HIDDEN", None)
        self.hidden_btn.pack()
        page = tk.Frame(body)
        page.grid(row=0, column=0, sticky="nsew")
        page.tkraise()
        self.grid = []
        for r in range(2):
            row = []
            for c in range(2):
                b = HudButton(page, f"B{r}{c}", lambda r=r, c=c: self.log.append(f"b{r}{c}"))
                b.grid(row=r, column=c, padx=30, pady=10)
                row.append(b)
            self.grid.append(row)
        keynav.install(self.root, current_menu=lambda: self.menu[1])
        self.keynav = keynav
        self.root.update()

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def key(self, w, sym):
        w.focus_force()
        self.root.update()
        w.event_generate("<KeyPress>", keysym=sym)
        self.root.update()
        return self.root.focus_get()

    def test_hidden_page_excluded(self):
        vis = self.keynav.visible_buttons(self.root)
        self.assertNotIn(self.hidden_btn, vis)
        self.assertEqual(len(vis), 7)

    def test_arrows(self):
        g = self.grid
        self.assertIs(self.key(g[0][0], "Right"), g[0][1])
        self.assertIs(self.key(g[0][1], "Down"), g[1][1])
        self.assertIs(self.key(g[1][1], "Left"), g[1][0])
        self.assertIs(self.key(self.menu[0], "Right"), self.menu[1])
        self.assertIn(self.key(g[0][0], "Up"), self.menu)

    def test_enter_and_escape(self):
        self.key(self.grid[1][0], "Return")
        self.assertEqual(self.log, ["b10"])
        self.key(self.menu[2], "Return")
        self.assertEqual(self.log, ["b10", "m2"])
        self.assertIs(self.root.focus_get(), self.root)       # после меню — фокус разделу
        self.assertIs(self.key(self.grid[0][0], "Escape"), self.root)

    def test_tab_to_menu_and_back(self):
        self.root.focus_force()
        self.root.update()

        class E:
            state = 0
            keysym = "Tab"
        self.keynav.on_tab(self.root, E())
        self.root.update()
        self.assertIs(self.root.focus_get(), self.menu[1])      # меню, вкладка текущего раздела
        self.keynav.on_tab(self.root, E())
        self.root.update()
        self.assertIs(self.root.focus_get(), self.grid[0][0])   # из меню — в раздел
        E.state = 1
        self.keynav.on_tab(self.root, E())
        self.root.update()
        self.assertIs(self.root.focus_get(), self.root)


if __name__ == "__main__":
    unittest.main()
