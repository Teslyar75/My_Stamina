"""Контекстная справка текущей страницы: F1 / кнопка «?»."""
from __future__ import annotations

from stamina.i18n import t as _t

import tkinter as tk
from tkinter import ttk

from stamina import theme
from stamina.hud import HudButton
from stamina.theme import AMBER, BG, BG2, CYAN, LINE, MUTED, PANEL, PANEL_HI, TEXT, px

# Ключ → (заголовок, текст). Текст с переносами; маркеры • для списков.
PAGES: dict[str, tuple[str, str]] = {
    "bridge": (
        _t("МОСТИК"),
        _t(
            "Главный тренажёр печати.\n\n"
            "• Печатайте строку в иллюминаторе — корабль летит вперёд.\n"
            "• Esc — пауза; F5 — начать упражнение заново.\n"
            "• Зелёные/красные зоны на клавиатуре подсказывают пальцы.\n"
            "• После миссии смотрите отчёт: скорость, точность, слабые клавиши."
        ),
    ),
    "missions": (
        _t("МИССИИ"),
        _t(
            "Курс из 20 миссий на раскладку (EN / RU).\n\n"
            "• Открывайте миссии по порядку — следующие открываются после цели.\n"
            "• «Ремонт систем» тренирует буквы, на которых вы чаще ошибаетесь.\n"
            "• Цель миссии: нужная скорость при точности ≥ порога."
        ),
    ),
    "cargo": (
        _t("СВОЙ ТЕКСТ"),
        _t(
            "Доставка вашего текста в тренажёр.\n\n"
            "• Вставьте или введите текст слева; справа — опции (регистр, пунктуация…).\n"
            "• «Применить» готовит текст; «На мостик» — старт печати.\n"
            "• Прогресс сохраняется: можно закрыть программу и продолжить.\n"
            "• Тот же текст попадает в библиотеку скорочтения."
        ),
    ),
    "log": (
        _t("БОРТЖУРНАЛ"),
        _t(
            "История полётов: миссии, свой текст, статистика.\n\n"
            "• Смотрите скорость, точность и опыт (XP).\n"
            "• Можно повторить недавнее упражнение."
        ),
    ),
    "settings": (
        _t("НАСТРОЙКИ"),
        _t(
            "Бортовые системы всего пульта.\n\n"
            "• Язык интерфейса — после смены нажмите «Перезапустить».\n"
            "• Звук, громкость, звёздное поле, «живой космос».\n"
            "• UPLINK — перевод предложений своего текста / книг в сети.\n"
            "• Размер шрифта строки и всего интерфейса."
        ),
    ),
    "help": (
        _t("СПРАВКА"),
        _t(
            "Полная инструкция (файл ИНСТРУКЦИЯ.md).\n\n"
            "• Слева по главам; F1 на любой странице открывает краткую справку "
            "именно этой страницы.\n"
            "• Кнопка «?» в шапке — то же, что F1."
        ),
    ),
    "honor": (
        _t("ДОСКА ПОЧЁТА"),
        _t(
            "Экипаж и достижения пилотов.\n\n"
            "• Сравнение прогресса, званий и статистики.\n"
            "• Смена пилота — Ctrl+Shift+P или меню у позывного."
        ),
    ),
    # --- Английский ---------------------------------------------------------
    "english": (
        _t("АНГЛИЙСКИЙ"),
        _t(
            "Модуль изучения слов: карты, сканер, миссии, карточки.\n\n"
            "• Подразделы — верхняя полоса вкладок.\n"
            "• Поиск «Сканировать» — быстрый переход к слову.\n"
            "• F1 — справка текущего подраздела."
        ),
    ),
    "english.overview": (
        _t("АНГЛИЙСКИЙ · ОБЗОР"),
        _t(
            "Сводка прогресса по набору.\n\n"
            "• Выберите звёздную карту (набор частотности).\n"
            "• Быстрые кнопки: сканер, миссии, проверка систем, склад.\n"
            "• Блок «из книги» — предложения из вашей библиотеки."
        ),
    ),
    "english.sets": (
        _t("АНГЛИЙСКИЙ · ЗВЁЗДНЫЕ КАРТЫ"),
        _t(
            "Сетка слов текущего набора.\n\n"
            "• Клик по плитке — сканер слова.\n"
            "• Переворот плитки — перевод / подсказка.\n"
            "• Отметьте «знаю» или положите слово в отсек."
        ),
    ),
    "english.scanner": (
        _t("АНГЛИЙСКИЙ · СКАНЕР"),
        _t(
            "Карточка одного слова.\n\n"
            "• Голос / медленно — озвучка; вкладки IPA, слоги, заметки.\n"
            "• Свой перевод сохраняется при уходе с поля.\n"
            "• «В проверку систем» — очередь SM-2; «В отсек» — списки.\n"
            "• Внизу: случайная / говорение / чтение / вопросы по этому слову.\n"
            "• «Канал связи» — практика предложений с микрофоном."
        ),
    ),
    "english.practice": (
        _t("АНГЛИЙСКИЙ · МИССИИ"),
        _t(
            "Тренировки по режимам: говорение, чтение, вопросы, случайная.\n\n"
            "• Выберите режим и длительность.\n"
            "• Можно ограничить одним словом из сканера."
        ),
    ),
    "english.review": (
        _t("АНГЛИЙСКИЙ · ПРОВЕРКА СИСТЕМ"),
        _t(
            "Повтор карточек по интервальному алгоритму (SM-2).\n\n"
            "• Число в вкладке — сколько карточек пора повторить.\n"
            "• Оцените ответ: снова / трудно / хорошо / легко."
        ),
    ),
    "english.warehouse": (
        _t("АНГЛИЙСКИЙ · СКЛАД КАРТОЧЕК"),
        _t(
            "Все карточки в очереди проверки.\n\n"
            "• Фильтры и просмотр срока следующего повтора.\n"
            "• Можно убрать карточку или открыть слово в сканере."
        ),
    ),
    "english.book": (
        _t("АНГЛИЙСКИЙ · ИЗ КНИГИ"),
        _t(
            "Предложения из книг библиотеки → учебные карточки.\n\n"
            "• Соберите карточки из текущего текста / книги.\n"
            "• Повторяйте их как обычную проверку систем."
        ),
    ),
    "english.lists": (
        _t("АНГЛИЙСКИЙ · ОТСЕКИ"),
        _t(
            "Ваши списки слов (отсеки).\n\n"
            "• Создавайте отсеки и складывайте туда слова со сканера или карты.\n"
            "• Удобно для тематических наборов к миссиям."
        ),
    ),
    "english.log": (
        _t("АНГЛИЙСКИЙ · ЖУРНАЛ"),
        _t("История занятий английским: сессии, ответы, прогресс по словам."),
    ),
    "english.settings": (
        _t("АНГЛИЙСКИЙ · НАСТРОЙКИ"),
        _t(
            "Параметры модуля: озвучка, распознавание речи, текущий набор и др.\n\n"
            "Общие настройки пульта — во вкладке «Настройки» верхней панели."
        ),
    ),
    # --- Скорочтение --------------------------------------------------------
    "speedread": (
        _t("СКОРОЧТЕНИЕ"),
        _t(
            "Гипердрайв (RSVP), книга, тренажёры глаз, библиотека.\n\n"
            "• Подразделы — полоса вкладок под заголовком.\n"
            "• F1 — справка текущего подраздела."
        ),
    ),
    "speedread.overview": (
        _t("СКОРОЧТЕНИЕ · ОБЗОР"),
        _t(
            "Сводка: активная книга, скорость, быстрый старт гипердрайва и тренажёров.\n\n"
            "• Откройте библиотеку, если текстов ещё нет."
        ),
    ),
    "speedread.reader": (
        _t("СКОРОЧТЕНИЕ · ГИПЕРДРАЙВ"),
        _t(
            "Чтение по одному слову в центре (RSVP).\n\n"
            "• Пробел — старт/пауза; стрелки — скорость и позиция.\n"
            "• Прогресс книги сохраняется; можно продолжить с того же места.\n"
            "• После блока — короткий квиз на понимание (если включён)."
        ),
    ),
    "speedread.book": (
        _t("СКОРОЧТЕНИЕ · КНИГА"),
        _t(
            "Обычное чтение страницами / главами.\n\n"
            "• Та же книга, что в гипердрайве.\n"
            "• Двуязычный режим — параллельные колонки (если книга bilingual).\n"
            "• Полноэкран и сохранение позиции — из панели читалки."
        ),
    ),
    "speedread.exercises": (
        _t("СКОРОЧТЕНИЕ · ТРЕНАЖЁРЫ"),
        _t(
            "Упражнения для периферии и фиксации взгляда: Шульте, пирамида, вспышки.\n\n"
            "• Выберите тренажёр и текст / сетку.\n"
            "• Результаты пишутся в журнал скорочтения."
        ),
    ),
    "speedread.library": (
        _t("СКОРОЧТЕНИЕ · БИБЛИОТЕКА"),
        _t(
            "Ваши тексты и свободные книги.\n\n"
            "• Импорт файла, свой текст, каталог Gutenberg / bilinguis.\n"
            "• Открыть в гипердрайве или в режиме «Книга».\n"
            "• Билингвальные книги помечены бейджем 2ЯЗ."
        ),
    ),
    "speedread.journal": (
        _t("СКОРОЧТЕНИЕ · ЖУРНАЛ"),
        _t("Сессии чтения и тренажёров: скорость (сл/мин), объём, даты."),
    ),
    "speedread.settings": (
        _t("СКОРОЧТЕНИЕ · НАСТРОЙКИ"),
        _t(
            "Скорость старта, размер слова, квиз, поведение гипердрайва.\n\n"
            "Общий вид пульта — во вкладке «Настройки» сверху."
        ),
    ),
    # --- Отдых / радио ------------------------------------------------------
    "lounge": (
        _t("ОТДЫХ"),
        _t(
            "Комната отдыха: короткие игры между полётами.\n\n"
            "• Тетрис, змейка, арканоид — рекорды сохраняются.\n"
            "• В игре: Esc — пауза, R — заново; «← В лобби» — выход."
        ),
    ),
    "radio": (
        _t("РАДИОРУБКА"),
        _t(
            "Интернет-радио на борту.\n\n"
            "• «Эфир» — поиск станций; «Приёмник» — избранное и сейчас играет.\n"
            "• Пробел — пауза; ± — громкость; ←/→ — соседнее избранное.\n"
            "• Мини-приёмник в шапке, пока идёт эфир."
        ),
    ),
    "radio.air": (
        _t("РАДИОРУБКА · ЭФИР"),
        _t(
            "Поиск волн по каталогу.\n\n"
            "• Введите запрос или выберите тег/страну.\n"
            "• Добавьте станцию в избранное — она появится в приёмнике."
        ),
    ),
    "radio.receiver": (
        _t("РАДИОРУБКА · ПРИЁМНИК"),
        _t(
            "Избранные станции и управление воспроизведением.\n\n"
            "• Громкость, пауза, переключение треков избранного."
        ),
    ),
}


def resolve_key(app) -> str:
    """Ключ справки по текущему экрану и подразделу."""
    cur = getattr(app, "current", None) or "bridge"
    if cur == "help":
        return "help"
    scr = (getattr(app, "screens", None) or {}).get(cur)
    if scr is not None and hasattr(scr, "page_help_key"):
        try:
            key = scr.page_help_key()
            if key:
                return str(key)
        except Exception:  # noqa: BLE001
            pass
    sub = getattr(scr, "current", None) if scr is not None else None
    if sub:
        compound = f"{cur}.{sub}"
        if compound in PAGES:
            return compound
    return cur if cur in PAGES else "bridge"


def content_for(key: str) -> tuple[str, str]:
    if key in PAGES:
        return PAGES[key]
    if "." in key:
        base = key.split(".", 1)[0]
        if base in PAGES:
            return PAGES[base]
    return PAGES["bridge"]


class PageHelpDialog(tk.Toplevel):
    """Модальное окно: как работает текущая страница."""

    def __init__(self, app, key: str | None = None) -> None:
        super().__init__(app)
        self.app = app
        self.key = key or resolve_key(app)
        title, body = content_for(self.key)
        self.title(_t("Справка · {0}").format(title))
        self.configure(bg=BG)
        self.transient(app)
        self.resizable(True, True)
        self.minsize(px(420), px(280))
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(px(560), int(sw * 0.9)), min(px(480), int(sh * 0.8))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        head = tk.Frame(self, bg=BG)
        head.pack(fill=tk.X, padx=px(16), pady=(px(14), px(6)))
        tk.Label(head, text="?", bg=BG, fg=AMBER, font=theme.font(18, True)).pack(side=tk.LEFT, padx=(0, px(10)))
        tk.Label(head, text=title, bg=BG, fg=TEXT, font=theme.font(14, True)).pack(side=tk.LEFT)
        tk.Label(head, text=_t("как работает эта страница"), bg=BG, fg=MUTED,
                 font=theme.font(9)).pack(side=tk.LEFT, padx=px(12))

        tk.Frame(self, bg=LINE, height=1).pack(fill=tk.X, padx=px(16))

        box = tk.Frame(self, bg=BG2, highlightthickness=1, highlightbackground=LINE)
        box.pack(fill=tk.BOTH, expand=True, padx=px(16), pady=px(10))
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Hud.Vertical.TScrollbar", background=PANEL_HI, troughcolor=BG2,
                        bordercolor=PANEL, arrowcolor=CYAN, lightcolor=PANEL_HI, darkcolor=PANEL_HI)
        sb = ttk.Scrollbar(box, orient=tk.VERTICAL, style="Hud.Vertical.TScrollbar")
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        t = tk.Text(box, wrap=tk.WORD, bg=BG2, fg=TEXT, relief=tk.FLAT, padx=px(14), pady=px(12),
                    yscrollcommand=sb.set, font=theme.font(11), highlightthickness=0,
                    spacing1=px(2), spacing3=px(3))
        t.pack(fill=tk.BOTH, expand=True)
        sb.configure(command=t.yview)
        t.insert("1.0", body)
        t.configure(state=tk.DISABLED)

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill=tk.X, padx=px(16), pady=(0, px(12)))
        HudButton(foot, _t("ПОЛНАЯ ИНСТРУКЦИЯ"), self._full_help, height=32, font_size=9,
                  color=CYAN).pack(side=tk.LEFT)
        HudButton(foot, _t("ЗАКРЫТЬ  Esc"), self.destroy, height=32, font_size=9,
                  color=AMBER).pack(side=tk.RIGHT)

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<F1>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        self.focus_set()

    def _full_help(self) -> None:
        self.destroy()
        self.app.show("help")
        scr = self.app.screens.get("help")
        if scr is not None and hasattr(scr, "goto"):
            base = (self.key or "").split(".", 1)[0]
            chapter = {
                "english": _t("АНГЛИЙСКИЙ"),
                "speedread": _t("СКОРОЧТЕНИЕ"),
                "lounge": _t("ОТДЫХ"),
                "radio": _t("РАДИОРУБКА"),
                "honor": _t("ЭКИПАЖ"),
                "bridge": _t("МОСТИК"),
                "missions": _t("МИССИИ"),
                "cargo": _t("СВОЙ ТЕКСТ"),
            }.get(base)
            scr.goto(chapter)


def open_page_help(app, key: str | None = None) -> None:
    """Показать модалку; повторный F1 закрывает предыдущую."""
    prev = getattr(app, "_page_help_dlg", None)
    if prev is not None:
        try:
            if prev.winfo_exists():
                prev.destroy()
        except tk.TclError:
            pass
    dlg = PageHelpDialog(app, key)
    app._page_help_dlg = dlg
