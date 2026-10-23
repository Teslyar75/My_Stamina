# ALT_SKIN_GUIDE — how to build an alternative UI variant of a skin

A guide for the onboard agent (Orion / opencode). It describes how the alt variants
of **spaceship** and **steampunk** were built, and how to repeat that for the other
skins (`bathyscaphe`, `neon_city`, `old_england`, `scriptorium`, `zen_garden`, …).
The role prompt is in `ALT_UI_AGENT_PROMPT.md`; the change log is in `docs/ALT_UI.md`.

---

## 0. Ground rules (non-negotiable)

- **The classic skin is untouched.** The alt variant is a separate mode
  (`stamina/alt_ui.py`, the `alt` flag in settings). Every change is either inside
  `alt_ui.py` / alt branches, or gated by `getattr(widget.winfo_toplevel(), "_alt_view", None)`.
  Allowed in classic: only bug fixes the pilot has approved.
- Never `git push --force`, `git reset --hard`, `git clean -fd`, or a merge into master.
  `git checkout -- .` only on the pilot's direct order.
- Don't touch the pilot's data (`%APPDATA%\Stamina`). Tests use a temporary
  APPDATA (see `bp_head.py` in §9).
- Don't touch `web_star_typing/**` without a separate instruction.
- Don't commit secrets or personal files. Don't rewrite other people's code "along the way".
- Strings go through `tr_()` / `t()`, colours are theme tokens only, sizes go through `px()`.
- No `update_idletasks()` in `<Configure>` handlers or geometry code (re-entrant layout).

## 1. Template structure of a screen

```
┌ HEADER: [logo] [ICON COMPARTMENT › SECTION] [ОБЗОР ▾]     [Orion][? F1][Slides][≡ F8] 04:33 ┐
│ subtitle line: "onboard computer · ship compartments" (skin vocabulary)                     │
├ NAV (left)          ┌ SkinFrame of the work area (wrap(), profile) ─────────────┐           │
│ ● Bridge            │ hero banner (skin bg image, crop without distortion)      │           │
│ ● English           │ filter panels / tab bar (collapsed into ⋯ КОНСОЛЬ)        │           │
│ …                   │ content in a ScrollViewport                               │           │
│ radar/gauge         └───────────────────────────────────────────────────────────┘           │
└ status line (bottom): the pilot's last action                                                ┘
```

### 1.1 Header and the ОБЗОР button
- The header is a single row. Left: the compartment name in the skin's accent,
  then `›` and the current section in bold.
- The **ОБЗОР ▾** button sits right after the breadcrumbs. It is a DropList of the
  compartment's sections (overview, star maps, scanner, …). Picking an item is the
  same as clicking the matching tab.
- The tabs themselves are not duplicated in the header. When the row is narrow
  they collapse into `⋯ КОНСОЛЬ` (spaceship) / `⚙ ЯЩИК` (steampunk) / `⋯ ЕЩЁ`
  (generic); see `MORE_LABEL` in `alt_ui.py`.
- For a new skin, add a label to `MORE_LABEL` and register the string with `tr_()`.

### 1.2 Breadcrumbs
- Format: `COMPARTMENT › SECTION [› OBJECT]` (e.g. `АНГЛИЙСКИЙ › ЗВЁЗДНЫЕ КАРТЫ › enjoy`).
- Every crumb except the last is clickable and returns you up a level.
- Long object names are cut with `…` to fit the width, and the full text goes in a tooltip.

### 1.3 DropList
- `alt_ui.DropList` is the only dropdown in the alt mode. Don't use
  `tk.OptionMenu` or `ttk.Combobox`.
- It closes on Esc, a click outside, or losing focus, and it doesn't block the event loop.
- Keyboard: ↑/↓/Enter. The wheel scrolls the list (see §6).
- Long lists (>12 items) get a scroll and a search field at the top.

## 2. Independence from classic
- Classic screens are reused as-is. The alt shell (`SkinFrame`, `ScrollViewport`,
  `compact()`, `_shrink_overflow()`) adapts them from the outside, without editing them.
- If a screen does need different behaviour in alt, add a marker attribute instead
  of a fork. Examples:
  - `gridf._alt_responsive = True`: a responsive grid that `_stack_grid` must not touch.
  - `_alt_stacked`: a grid that has already been rebuilt.
- Check: switch the alt flag off, and the classic screen must look as it does on master
  (compare screenshots).

## 3. Palette: soft, with checked contrast
- Each skin has a set of tokens (`BG`, `PANEL`, `TEXT`, `MUTED`, `CYAN/ACCENT`, `AMBER`,
  `RED`, `GREEN`). The alt variant takes them, softened: background 4–8 % lighter, accents
  10–15 % less saturated, no pure #000/#fff.
- **Contrast (WCAG):** `TEXT` on `PANEL` ≥ 4.5:1, `MUTED` on `PANEL` ≥ 3:1, accent buttons ≥ 3:1.
  Check it with a script (relative luminance) and write the numbers in `ALT_UI.md`.
- Banner text sits on a semi-transparent plate, never directly on the photo.
- The progress gradient is shared: #d96a5f → #e39355 → #e6c45c → #aec95e → #6fbf73.

## 4. Performance
- Target: switching a compartment or section **< 300 ms**, one event-loop step ≤ 50 ms
  (measure with `stall_pump`).
- Lists and grids are paged or virtualised: 24 star-map tiles per page, and big lists
  draw only the visible part. Change the layout by **re-gridding existing widgets**,
  not by recreating them (`SetsPage._place`).
- `<Configure>` handlers: compare the new value with the old one and do nothing if nothing changed.
- Images: cache the scaled `PhotoImage` per size. Never rescale on every `<Configure>`.
- Background polling (Orion progress, radio): `after()` at ≥ 1 s intervals, read files by mtime.

## 5. Long text
- Text longer than ~400 characters (descriptions, logs, chat, articles) is chunked:
  paragraphs of ≤ 600 characters, and each chunk is inserted in its own `after(0)` step,
  so the window doesn't freeze.
- Labels longer than 16 characters get `wraplength`, set by `_shrink_overflow`
  automatically. Don't hard-code `wraplength` in pixels; use `px()` or a share of the width.
- Very long blocks (>5,000 characters) get a «Показать полностью» button and initially
  show the first 2–3 chunks.

## 6. Mouse wheel
- One global router: `stamina/wheel_router.py`. `install(app)` is called by `ScrollViewport`.
- The wheel scrolls the **nearest scrollable area under the cursor**:
  Canvas with `yscrollcommand`, Text, Listbox or Treeview. At an edge it passes the
  scroll up to the parent.
- Don't write new `bind_all("<MouseWheel>")` handlers, and don't `unbind_all` on
  Leave: that wipes the router. Your own handling goes in a `bind` on the specific widget
  (zoom, horizontal strip); the router won't touch that widget.
- Test: `widget.event_generate("<MouseWheel>", delta=-120, x=5, y=5)` on the area and on
  a child, then check that `yview()[0]` grew.

## 7. Order of compartments
Do one at a time, with a commit after each:
1. Shell: header, ОБЗОР, breadcrumbs, NAV, SkinFrame, palette.
2. Bridge (missions, cards).
3. English (overview, star maps, scanner, practice, warehouse, lists, log, settings).
4. Speed reading (library, reader).
5. Lounge (`lounge/screen.py`).
6. Radio room.
7. Comm (`comm_screen.py`).
8. Orion (console, progress panel).
9. Settings.
10. Small windows (dialogs, help, slides).

For each compartment:
1. Audit sections and long text.
2. List the problems in `ALT_UI.md`.
3. Make the fixes.
4. Take screenshots of both skins.
5. Run the tests.
6. Commit and report.

## 8. Commit and report protocol
- Branch `agent/<name>/alt-ui-<skin>`. Push only without `--force`, and never merge into master yourself.
- One commit is one compartment or one idea. The message is short, in English or Russian:
  `alt-ui: <compartment>: <what>`.
- Before committing: `git status`. Commit only your own files. Don't commit untracked
  auxiliary files (`docs/UI_MAP.md`, `tools/*probe*`).
- Report to the pilot (in Russian, 5–10 lines):
  - what was done;
  - the commit hash;
  - which checks passed (tests, GUI pass, times in ms);
  - screenshots;
  - what is left or what you are unsure about.

## 9. Testing: checklist and tools
- `python -m pytest tests -q`: run from `tests`, because the repo root picks up
  `web_star_typing`. `test_i18n::test_check_tool` may fail on other people's strings;
  don't break it further with your own.
- New strings go into all four `stamina/i18n/{ru,en,uk,de}.json` files.
- **GUI pass:**
  - a script beginning `exec(open("bp_head.py").read())` gets `app`, `skin`, `tmp` (a
    temporary APPDATA), `pump(s)`, `shot(name)` and `errs`;
  - run it for each skin in a hidden PowerShell;
  - save the results to `bp/<skin>_<pass>.json`.
- Only synthetic events: `event_generate`, `widget.invoke()`. The real mouse and keyboard
  belong to the pilot.
- To get a panel into a screenshot, walk up from the widget and call `yview_moveto` on
  each Canvas ancestor.
- Checklist per compartment:
  - [ ] both skins, plus the classic one unchanged
  - [ ] the window at 1920, 1366 and 900 px wide: nothing is clipped and no button gets 0 px
  - [ ] the wheel works in every area (§6)
  - [ ] long text doesn't freeze the window (§5)
  - [ ] switching < 300 ms
  - [ ] `errs` is empty (no Tk errors in the log)
  - [ ] the strings are translated
  - [ ] contrast checked (§3)

## 10. Progress reporting (task_progress)
The pilot watches the strip on the Orion console. For each compartment:

```bash
python -m stamina.task_progress plan  alt-<skin>-<compartment> "ALT <skin>: <compartment>" "аудит:1" "правки:3" "скриншоты:1" "тесты:1" "коммит:1"
python -m stamina.task_progress step  alt-<skin>-<compartment> аудит
python -m stamina.task_progress finish alt-<skin>-<compartment>
```

Update it at least every 2 minutes during long steps. The legacy fallback,
`_orion/progress.json` v1, is for when the module isn't available
(see `.opencode/agents/orion-commander.md`).
