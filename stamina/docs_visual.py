"""Визуальный вид документа: маркеры Markdown спрятаны везде, кроме строки с курсором.

Как в Typora/Obsidian: «**жирный**» на чужой строке выглядит просто жирным, а
на строке, где стоит курсор, маркеры видны — их можно править. Это тег Tk
`elide` поверх уже найденных подсветкой маркеров (md_mark), текст документа
не меняется: в файле и при экспорте — тот же Markdown.

Честные пределы (они же — в справке):
* строка с курсором раскрывается целиком, поэтому при переходе на неё она
  может стать чуть шире и перенестись иначе;
* выделение и копирование через несколько строк берут текст с маркерами
  (это исходный Markdown);
* маркеры списков («- », «1. ») не прячутся — по ним видно, что это список;
* в очень больших документах (> HL_SYNC_LINES строк) прячется по мере
  фоновой подсветки — на долю секунды маркеры могут мелькнуть.
Выключается кнопкой «👁» / Ctrl+Shift+M (настройка docs_visual).
"""
from __future__ import annotations


class VisualMixin:
    def setup_visual(self) -> None:
        t = self.text
        t.tag_configure("md_hide", elide=True)
        t.tag_raise("md_hide")
        self._shown_line: int | None = None
        for seq in ("<KeyRelease>", "<ButtonRelease-1>", "<FocusIn>"):
            t.bind(seq, lambda _e: self.reveal_cursor_line(), add="+")

    # -- настройка ------------------------------------------------------------------
    def visual_on(self) -> bool:
        st = self._settings()
        if st is None:
            return getattr(self, "_visual_mem", True)
        return bool(st.get("docs_visual", True))

    def set_visual(self, on: bool | None = None) -> None:
        on = (not self.visual_on()) if on is None else bool(on)
        st = self._settings()
        if st is not None:
            st["docs_visual"] = on
            self._save_settings()
        else:
            self._visual_mem = on
        b = getattr(self, "fmt_buttons", {}).get("visual")
        if b is not None:
            b.set_active(on)
        self._shown_line = None
        self.apply_hide(1, int(self.text.index("end-1c").split(".")[0]))
        self.reveal_cursor_line()

    # -- спрятать / показать ------------------------------------------------------
    def apply_hide(self, first: int, last: int) -> None:
        """Спрятать маркеры (md_mark) в строках first..last, кроме строки курсора."""
        t = self.text
        a, b = f"{first}.0", f"{last}.end+1c"
        t.tag_remove("md_hide", a, b)
        if not self.visual_on():
            return
        rng = t.tag_nextrange("md_mark", a, b)
        while rng:
            t.tag_add("md_hide", *rng)
            rng = t.tag_nextrange("md_mark", rng[1], b)
        cur = int(t.index("insert").split(".")[0])
        if first <= cur <= last:
            t.tag_remove("md_hide", f"{cur}.0", f"{cur}.end")
        self._shown_line = cur

    def reveal_cursor_line(self) -> None:
        """Курсор перешёл на другую строку: прежнюю спрятать, новую показать."""
        if not self.visual_on():
            return
        t = self.text
        cur = int(t.index("insert").split(".")[0])
        old = self._shown_line
        if old == cur:
            return
        self._shown_line = cur
        t.tag_remove("md_hide", f"{cur}.0", f"{cur}.end")
        if old is not None and int(t.index("end-1c").split(".")[0]) >= old:
            rng = t.tag_nextrange("md_mark", f"{old}.0", f"{old}.end")
            while rng:
                t.tag_add("md_hide", *rng)
                rng = t.tag_nextrange("md_mark", rng[1], f"{old}.end")
