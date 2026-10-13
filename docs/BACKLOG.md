# Backlog

What is still open before submission (20:00, 20 November 2026), and a short log of what has landed. This file replaces the dated plans that used to be in `docs/plans/`; git history and the merged pull requests keep their full text. Design decisions are in `docs/deliverables/DESIGN.md` §5.

This is not a feature wishlist. Appendix B plus what the SRS specifies is the whole product (`AGENTS.md`, "Non-negotiable scope"), so nothing here adds a feature.

## Open: course deliverables

These belong to the group. An agent must not claim them as done.

| Item | Brief | What is left |
|---|---|---|
| SRS | 1 (6 pts) | Group review of `docs/deliverables/SRS.md`. Add group number, member names, and student ids, then drop "draft" from the title page. |
| Design document | 2 (5 pts) | Group review of `docs/deliverables/DESIGN.md`, same title-page edits. |
| PDF build | 1, 2, 3 | `sh docs/deliverables/build.sh` renders every document and diagram to `dist/`. Rebuild after the last edit to any Markdown source. |
| System video | 3d | Scripted: `vhs docs/deliverables/video/demo.tape` (after `brew install vhs`) types the demo script below into the real curses UI and renders `dist/demo.mp4`, about 3 minutes, with a caption bar naming each user story. Group: watch it, then re-render on the submission Mac so the dates are current. |
| Presentation | 5 (4 pts) | A draft deck with speaker notes exists as a private claude.ai Slides artifact (11 slides, four speaker sections of about 70 seconds; group number, names, and the lesson's own example are placeholders); download it as PDF. Still to do: the recording. Slides as PDF and a recording as MP4, at most 5 minutes. Every member presents at least 1 minute with face and student ID card visible. Content: one create-a-PIR requirement, one criterion requirement, one search requirement, the MVC design (DESIGN §2–3), and one lesson learned (for example: US7 became unit-testable only once the model was separated from input and output). |
| Honour Declaration | required | At the ZIP root. Acknowledge GenAI use honestly (this repository's `AGENTS.md` and history show it) and state the agreed contribution split. Missing or false: up to 30 % penalty. |
| ZIP | all | One archive. SRS, design, and manual PDFs at the root; `REQUIREMENTS.md`/`.pdf` and `coverage.txt`/`coverage.pdf` in the source root next to `pim.py`; the Honour Declaration at the ZIP root. |

## Open: checks by hand

- **Folder browser in Terminal.app** (macOS, real home folder, `python3 pim.py`). Automated tests and a tmux run cover the same steps with a temporary `HOME`.
  1. `c` → create a Note → `W` → "+ New file in this folder…" → type `pimtest` → Enter. The status line reads `Saved /Users/<you>/…/pimtest.pim`.
  2. `q` quits without asking, because nothing is unsaved. Relaunch, press `o`, and open `pimtest.pim`. The Note is back, and the status line reads `Loaded …`.
  3. `o`, then `/`, then type `~/x.json` and Enter: `path must have a .pim extension`.
  4. Create a Note so the collection is dirty, then `o` and pick a `.pim` file: save / discard / cancel appears before anything loads.
  5. `W` → `~` goes home; `⌫` goes up and highlights the folder you came from; Esc cancels and changes nothing.
  6. Confirm no folder named `~` was created anywhere, then delete the test file.
- **Demo script** below, once end to end on the recording machine.

## Demo script

For the system video and the presentation clips, at most 4 minutes. `tests/e2e/test_demo.py` scripts the create, search, modify, print, save, and reload steps.

1. Start `python3 pim.py`: untitled, empty list.
2. Create the six-PIR test fixture (`tests/fixture.py`) or at least one of each type: a Note, a Task without a deadline, an Event with two relative alarms and one absolute alarm, and a Contact.
3. Search `type = event && description contains "COMP"`: the list shows only that Event.
4. Select it and change its start: the relative alarm times move, the absolute one stays.
5. `print` that PIR. Then `clear` and `print all`, so every PIR is shown (SRS FR-25).
6. `save as demo.pim`, quit, start again, and `load demo.pim`: the same Ids are back.
7. If time allows: one search syntax error, one load blocked by unsaved changes, and one Alarm Alert.

Show only features in the SRS: no GUI, no recurrence.

## Known UI gaps (accepted, not scheduled)

These do not break a requirement. Fix only if time allows; each must keep `python3 -m unittest` green.

- **Wizard field titles.** Only search has a titled field (`Search — one criterion`). The other fields show the prompt label itself, for example `deadline [current] (empty keeps, none clears):`.
- **Calendar time list.** With focus on the time list, keys the picker does not use are ignored rather than passed on.

## Done

| Date | Work | Where |
|---|---|---|
| 2026-09-11 | Foundation: `model` / `view` / `controller` / `pim.py`, US1–US11, line interface, in-process Alarm Alerts, `coverage_report.py` | PR #1 (`ef7e800`) |
| 2026-09-11 | Unit, integration, and e2e layers; 100 % `model/` coverage; `hooks/pre-commit` gate | PR #2 (`7618f78`) |
| 2026-09-11 – 09-12 | `curses` interface: panes, selectors, calendar, colour theme, search retry, idle Esc clears the filter | PR #3 (`d99c01b`) |
| 2026-09-23 | Full-marks audit against the brief. Fixed four crash paths (out-of-range alarms, non-list alarms, non-UTF-8 files, uncaught errors), blank and `.pim`-only file names, id and amount checks, OS save errors, type hints, test docstrings. Added the SRS, design document, and PDF build. | PR #3 (`d99c01b`) |
| 2026-09-24 | `~` expanded in PIM File paths; `o` load and `W` save as keys; absolute path in the save and load status | PR #4 (`de9640a`) |
| 2026-09-24 | Folder browser for load and save-as paths | PR #5 (`7f7597f`) |
| 2026-09-24 | Folded the ADRs into decision tables in DESIGN §5 and `docs/plans/` into this file; refreshed the deliverables | PR #6 (`82bbbfe`) |
| 2026-09-24 | Folded PRODUCT.md into the SRS, ARCHITECTURE.md into DESIGN, and ACCEPTANCE.md into the SRS and this file; deleted CONTEXT.md | branch `docs/merge-working-docs` |
| 2026-09-25 | One Esc cancels the typed path field while the path the browser pre-filled is unedited (was two presses) | branch `fix/full-marks-polish` |
| 2026-09-25 | Second audit against the brief: HKT falls back to fixed UTC+8 without a time-zone database; docstrings on every `model` method and every test; typed `Terminal` interface; DESIGN §3.2 tables for every public View and Controller class; a verification line for every SRS requirement; PDFs rebuilt | branch `fix/full-marks-polish` |
| 2026-09-25 | Found while scripting the demo video: the alarm-offset selector's `0`/`1` keys picked the wrong chip; PRINT, HELP, and calendar pop-ups showed the panes behind them; a long title path ran into the clock; Esc waited a full second. Added the VHS demo tape | branch `chore/demo-video-and-slides` |
