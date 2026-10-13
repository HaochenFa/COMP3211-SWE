# Requirements coverage

This report lists which Appendix B user stories, and which requirements in the SRS (version 1.3, `docs/deliverables/SRS.md`, rendered as `SRS.pdf`), the implementation covers. All 11 user stories, all 43 functional requirements (FR-1 – FR-43), and all 10 non-functional requirements (NFR-1 – NFR-10) are implemented, so the "Not implemented" section is empty.

Evidence names the automated tests that check each row. All 336 tests pass with `python3 -m unittest` (25 Sep 2026), and the model unit tests cover 100 % of the countable lines in `model/` (`coverage.txt`).

## User stories and functional requirements

| Story | SRS ids | Requirement (short) | Status | Evidence (tests) |
|--------|----------------|--------------------------------------------|-----------------|-------------------------------------------------------|
| US1 | FR-1, FR-2, FR-3, FR-10, FR-11 | Four PIR types; Ids 1, 2, …; prompted fields; missing values; date-time input | implemented | `tests/unit/test_pim.py`, `tests/unit/test_pir.py` |
| US2 | FR-4 | Create Note (body required, no title) | implemented | `tests/unit/test_pir.py` NoteTests |
| US3 | FR-5 | Create Task (description required, deadline optional) | implemented | `tests/unit/test_pir.py` TaskTests |
| US4 | FR-6, FR-7, FR-8 | Create Event (description and start required, 0..n relative/absolute alarms, alarm range) | implemented | `tests/unit/test_pir.py` EventTests, `tests/unit/test_alarms.py` |
| US5 | FR-9 | Create Contact (name required, address/mobile optional, duplicates allowed) | implemented | `tests/unit/test_pir.py` ContactTests |
| US6 | FR-12 – FR-15 | Modify fields; Id and type unchanged; relative alarms follow start; atomic | implemented | `tests/unit/test_pim.py`, `tests/unit/test_pir.py`, `tests/e2e/test_commands.py` |
| US7 | FR-16 – FR-23 | Search: `type`, `contains`, `<` `>` `=`, `&&` `\|\|` `!`, parentheses; syntax error keeps Current Result | implemented | `tests/unit/test_search.py` |
| US8 | FR-24 – FR-26 | Print one PIR; `print all` prints Current Result (all PIRs when no search) | implemented | `tests/unit/test_app.py`, `tests/e2e/test_user_flows.py` |
| US9 | FR-27, FR-28 | Delete with confirmation; Ids never reused | implemented | `tests/unit/test_pim.py`, `tests/unit/test_persist.py` |
| US10 | FR-29 – FR-33 | Store to `.pim` (UTF-8 JSON, atomic write, `.pim` appended, `~` expanded, absolute path in status, overwrite confirm, OS errors reported) | implemented | `tests/unit/test_persist.py`, `tests/unit/test_app.py`, `tests/integration/test_app.py` |
| US11 | FR-34 – FR-37 | Load from `.pim` (other extensions rejected, `~` expanded, corrupt file keeps memory, dirty load asks) | implemented | `tests/unit/test_persist.py`, `tests/unit/test_app.py`, `tests/e2e/` |
| — (UI) | FR-38, FR-39, FR-40 | Command vocabulary and accelerators (`w` / `W` / `o` for save / save as / load); folder browser for load and save-as paths; screen layout; row vs Id selection | implemented | `tests/unit/test_terminal.py`, `tests/unit/test_keys.py`, `tests/unit/test_file_browser.py`, `tests/unit/test_curses_ui.py`, `tests/e2e/` |
| — (derived from US4) | FR-41 – FR-43 | In-process OVERDUE / SOON Alarm Alert; dismiss in memory only | implemented | `tests/unit/test_alarms.py`, `tests/e2e/test_alerts.py` |

## Non-functional requirements

| SRS requirement id | Requirement (short) | Status | Evidence |
|----------|--------------------------------------------------|-----------------|----------------------------------------|
| NFR-1 | Python standard library only | implemented | imports in `model/`, `view/`, `controller/`, `pim.py` |
| NFR-2 | macOS, Python 3.12+ | implemented | `DEVELOPER.md` |
| NFR-3 | `model` package, no import of `view` / `controller` | implemented | package layout |
| NFR-4 | Failed command: no change, no traceback, no exit, one English message | implemented | unit, integration, and e2e error tests |
| NFR-5 | Atomic save; failed load keeps memory; no silent loss of changes | implemented | `tests/unit/test_persist.py`, e2e quit/load tests |
| NFR-6 | Time-zone-aware instants, HKT default, fixed UTC+8 without a time-zone database | implemented | `tests/unit/test_pir.py` ParseDatetimeTests |
| NFR-7 | 10,000 PIRs: search, alarm check, save, load each under 1 s | implemented | measured 24 Sep 2026: 2 ms, 2 ms, 44 ms, 24 ms |
| NFR-8 | Model unit tests with `unittest`, 100 % line coverage of `model/` | implemented | `coverage.txt` |
| NFR-9 | English prompts and specific error messages | implemented | `USER.md` Errors |
| NFR-10 | No out-of-scope features | implemented | SRS §2.2 |

## Not implemented

None. The following are deliberately out of scope and absent, by product decision: GUI, recurrence, links between PIRs, OS notifications, and third-party TUI libraries.

## How coverage is measured

`python3 coverage_report.py` writes `coverage.txt`. It uses the standard-library `trace` module over `tests/unit` and counts the lines where an AST statement starts in each `model/*.py` file except `__init__.py`. The method is stated at the top of `coverage.txt`.
