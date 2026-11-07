#!/usr/bin/env python3
"""Автономный виджет контроля токенов Cursor. Запускается вне Star Typing."""

from __future__ import annotations

import argparse
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import quota  # noqa: E402  — локальный модуль каталога, не stamina


def _human(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", " ")


class TokenWidget(tk.Tk):
    """Плавающее окно мониторинга usage/quota."""

    def __init__(self, *, config: Path = quota.CONFIG_PATH):
        super().__init__()
        self.config_path = config
        self._busy = False
        self._timer_id = ""
        self._last = {}

        self.title("Cursor Token Widget")
        self.geometry("860x580")
        self.minsize(760, 480)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        self._load()
        self.after(200, self._refresh)
        self._schedule()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(3, weight=1)

        ttk.Label(root, text="Usage API URL").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.url_var = tk.StringVar()
        ttk.Entry(root, textvariable=self.url_var).grid(row=0, column=1, columnspan=3, sticky="ew", pady=4)

        ttk.Label(root, text="Bearer token").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.token_var = tk.StringVar()
        ttk.Entry(root, textvariable=self.token_var, show="*").grid(
            row=1, column=1, columnspan=3, sticky="ew", pady=4
        )

        ttk.Label(root, text="Период").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.period_var = tk.StringVar()
        ttk.Entry(root, textvariable=self.period_var).grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(root, text="Fallback limit").grid(row=2, column=2, sticky="w", padx=(10, 8), pady=4)
        self.limit_var = tk.StringVar()
        ttk.Entry(root, textvariable=self.limit_var).grid(row=2, column=3, sticky="ew", pady=4)

        ttk.Label(root, text="Интервал, сек").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.refresh_var = tk.StringVar(value="60")
        ttk.Entry(root, textvariable=self.refresh_var).grid(row=3, column=1, sticky="w", pady=4)
        self.auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(root, text="Автообновление", variable=self.auto_var).grid(
            row=3, column=2, sticky="w", padx=(10, 8), pady=4
        )

        controls = ttk.Frame(root)
        controls.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 6))
        self.save_btn = ttk.Button(controls, text="СОХРАНИТЬ", command=self._save)
        self.save_btn.pack(side="left")
        self.refresh_btn = ttk.Button(controls, text="ОБНОВИТЬ", command=self._refresh)
        self.refresh_btn.pack(side="left", padx=(8, 0))
        self.status_var = tk.StringVar(value="Готово.")
        ttk.Label(controls, textvariable=self.status_var).pack(side="left", padx=(12, 0))

        summary = ttk.LabelFrame(root, text="Сводка", padding=10)
        summary.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=(6, 8))
        summary.columnconfigure(0, weight=1)
        self.bar = ttk.Progressbar(summary, mode="determinate", maximum=100)
        self.bar.grid(row=0, column=0, sticky="ew")
        self.summary_var = tk.StringVar(value="—")
        ttk.Label(summary, textvariable=self.summary_var).grid(row=1, column=0, sticky="w", pady=(6, 2))
        self.last_var = tk.StringVar(value="—")
        ttk.Label(summary, textvariable=self.last_var).grid(row=2, column=0, sticky="w")

        models = ttk.LabelFrame(root, text="По моделям", padding=6)
        models.grid(row=6, column=0, columnspan=4, sticky="nsew")
        root.rowconfigure(6, weight=1)
        models.columnconfigure(0, weight=1)
        models.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(models, columns=("model", "used", "limit", "pct"), show="headings", height=10)
        self.tree.heading("model", text="Модель")
        self.tree.heading("used", text="Использовано")
        self.tree.heading("limit", text="Лимит")
        self.tree.heading("pct", text="%")
        self.tree.column("model", width=320, anchor="w")
        self.tree.column("used", width=140, anchor="e")
        self.tree.column("limit", width=140, anchor="e")
        self.tree.column("pct", width=80, anchor="e")
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar = ttk.Scrollbar(models, orient="vertical", command=self.tree.yview)
        ybar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=ybar.set)

        hint = ttk.Label(
            root,
            text=(
                "Источник реального Cursor usage API не подтверждён. "
                "Укажите GET endpoint, который возвращает usage/quota JSON."
            ),
        )
        hint.grid(row=7, column=0, columnspan=4, sticky="w", pady=(8, 0))

    def _load(self) -> None:
        cfg = quota.load_settings(self.config_path)
        self.url_var.set(str(cfg.get("url") or ""))
        self.token_var.set(str(cfg.get("token") or ""))
        self.period_var.set(str(cfg.get("period") or ""))
        lim = int(cfg.get("limit") or 0)
        self.limit_var.set(str(lim) if lim else "")
        self.refresh_var.set(str(int(cfg.get("refresh") or 60)))

    @staticmethod
    def _num(raw: str, default: int = 0) -> int:
        try:
            return int(str(raw or "").strip())
        except ValueError:
            return default

    def _save(self) -> None:
        refresh = max(10, self._num(self.refresh_var.get(), 60))
        limit = max(0, self._num(self.limit_var.get(), 0))
        quota.save_settings(
            url=self.url_var.get(),
            token=self.token_var.get(),
            period=self.period_var.get(),
            limit=limit,
            refresh=refresh,
            path=self.config_path,
        )
        self.refresh_var.set(str(refresh))
        self.limit_var.set(str(limit) if limit else "")
        self.status_var.set("Сохранено")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.save_btn.configure(state=state)
        self.refresh_btn.configure(state=state)

    def _refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._set_busy(True)
        self.status_var.set("Обновляю…")
        url = self.url_var.get().strip()
        token = self.token_var.get().strip()
        period = self.period_var.get().strip()
        limit = max(0, self._num(self.limit_var.get(), 0))

        def worker():
            snap = quota.fetch_usage(url=url, token=token, limit=limit, period=period, timeout=20.0)
            self.after(0, lambda: self._apply(snap))

        threading.Thread(target=worker, daemon=True).start()

    def _apply(self, snap: dict) -> None:
        self._busy = False
        self._set_busy(False)
        self._last = dict(snap)
        if not snap.get("ok"):
            self.status_var.set(str(snap.get("message") or snap.get("error") or "Ошибка"))
            return
        self.status_var.set("Готово")
        used = snap.get("used")
        limit = snap.get("limit")
        rem = snap.get("remaining")
        pct = snap.get("percent")
        period = str(snap.get("period") or self.period_var.get() or "—")
        self.summary_var.set(
            f"Период: {period} · Использовано: {_human(used)} · Лимит: {_human(limit)} · "
            f"Осталось: {_human(rem)} · {'—' if pct is None else f'{pct:.1f}%'}"
        )
        self.bar["value"] = 0.0 if pct is None else max(0.0, min(100.0, float(pct)))
        when = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(float(snap.get("updated") or time.time())))
        self.last_var.set(f"Обновлено: {when}")
        self._fill_models(snap.get("models") or [])

    def _fill_models(self, rows: list[dict]) -> None:
        self.tree.delete(*self.tree.get_children())
        if not rows:
            self.tree.insert("", "end", values=("—", "—", "—", "—"))
            return
        for row in rows:
            used = row.get("used")
            limit = row.get("limit")
            pct = "—"
            if used is not None and limit is not None and int(limit) > 0:
                pct = f"{(int(used) / int(limit)) * 100.0:.1f}%"
            self.tree.insert(
                "",
                "end",
                values=(str(row.get("model") or ""), _human(used), _human(limit), pct),
            )

    def _schedule(self) -> None:
        refresh = max(10, self._num(self.refresh_var.get(), 60))
        self.refresh_var.set(str(refresh))
        if self.auto_var.get() and not self._busy:
            self._refresh()
        self._timer_id = self.after(refresh * 1000, self._schedule)

    def _on_close(self) -> None:
        if self._timer_id:
            try:
                self.after_cancel(self._timer_id)
            except tk.TclError:
                pass
        self.destroy()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=str(quota.CONFIG_PATH),
        help="Путь к JSON-файлу настроек (по умолчанию ~/.cursor-token-widget.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = TokenWidget(config=Path(args.config).expanduser())
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
