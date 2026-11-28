# VIM Trainer UX and controls — 2026-11-28

**Status:** implemented and sent as PR #69 (`agent/orion/vim-controls` → `master`, MERGEABLE), awaiting the pilot's visual check from `D:\tmp\st-pilot\main.py --select` and the final full `pytest` result. Key-interception recon is complete; all four steps below are done in code and covered by targeted tests. The trainer now has 24 lessons (12 foundational + 12 for confident editing), a translated 182-card cheatsheet, free sandbox and progressive hints. PR #68 (scroll/Esc-on-bridge) stays separate; its commits are not in this branch.

## Decisions

| Topic | Decision (2026-11-28) |
|---|---|
| Goal | Fix the regressed controls first, then make the trainer easier to learn. Keep it a targeted UX change, not a new trainer. |
| `Esc` | Always a VIM mode switch inside the trainer: INSERT/VISUAL/COMMAND → NORMAL. While isolation is on (default), it must never close the trainer, open/close Zen, or trigger "double Esc". `F3` disables isolation so two Esc presses within 0.6 s return to the lobby. |
| Movement | `h/j/k/l` and arrows are equivalent in NORMAL and VISUAL; in INSERT typed letters are text and arrows move the caret; in COMMAND characters build the command and `Esc` cancels. Only keys taught by the current lesson are highlighted; unknown keys get a gentle hint, never a silent hard stop. |
| Key ownership | Add an explicit focused-owner check so global `Cockpit`/`keynav`/`zen_mode` handlers step aside while the VIM trainer has focus. Consume trainer keys at the widget level with `return "break"`; let `Ctrl+n`/`Ctrl+p` and the explicit exit action through. |
| Arena | Replace the tiny 8×3 grid with a larger adaptive arena: default 16×8, clamped 12–24 columns and 6–12 rows from the available window size. Keep `@` as cursor, mark the goal on the right edge, show `x,y` and the current mode in a status line. Longer paths are fine because there is no timer or score. |
| Learning flow | Per lesson: one highlighted "next key" on a visible key strip, short why-hint, mistake counter that unlocks a fuller hint after 2 misses, and a "repeat hint" action. Add a free-practice arena after lesson 1. Progress stays saved. |
| Scope guard | Do not touch `%APPDATA%\Stamina`, `_orion/`, `graphify-out/`, protected i18n keys (`ВЫБРАТЬ`/`WÄHLEN`/`PICK`/`ВИБРАТИ`, `{0} out of {1}`), or the working shortcut `D:\tmp\st-pilot\main.py --select`. |

## Order

1. **Controls regression** — trace the actual key chain, add an owner check and widget-level `break` for `Esc`/movement, keep mode semantics from `docs/vim_trainer_guide.md`. Tests for Esc in all modes, `h/j/k/l` and arrows, and for global handlers standing aside. Gate: targeted pytest + `ruff` + `tools/ci_gate.py`.
2. **Larger adaptive arena** — compute grid size from the available area, update rendering/goal/status, keep the lesson goals reachable and progress compatible. Tests for size bounds, resize, and a full lesson path on the big grid. Gate: same.
3. **Simpler learning layer** — visible key strip with the current lesson's keys, progressive hints (`?` and after three stalled keys), mistake-tolerant feedback, free practice, status line. Add F3 Esc isolation, `:help {topic}`, `:keyboard`, macros and the 12 advanced lessons on generated texts. Update `docs/vim_trainer_guide.md` and built-in help. Gate: same plus `tools/i18n_check`.
4. **Review handoff** — rebase/merge with PR #68 as needed, one PR, pilot checks the VIM tile from the shortcut. Update `docs/HANDOFF.md`.

## Out of scope

- Rewriting the original 12-lesson curriculum; the added 12 advanced lessons use the same engine and `expect` checks.
- Changing bridge scroll behavior (PR #68 owns that).
- Changing protected translations, user data locations, or the pilot's launcher.
- Any `git reset --hard`, force push, or checkout that could erase another agent's work.

## Verification notes

- Snapshot before edits: `snap-20261128-0517`, rollback `git checkout snap-20261128-0517`.
- Known pre-existing Windows failures: two `tests/test_scroll_frame.py` cases fail on baseline 40cfbf6 too; do not attribute them to this work.
- The pilot's smoke path: Lounge → VIM tile → move with `h/j/k/l` and arrows → `i` then `Esc` → `v` then `Esc` → `:` then `Esc` → `F2` theory → `F3` twice (Esc isolation off/on) → two Esc (exit only when off) → finish lesson 1 → free practice.
- Lesson simulation (`sim_lessons.py`): all lessons 13–24 complete with their documented key sequences; completion banner survives further commands.
