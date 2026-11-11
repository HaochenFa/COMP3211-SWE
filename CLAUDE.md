# CLAUDE.md

Durable instruction set for AI agents working in this repository.

This is not a quick-start and not an implementation snapshot. User-facing overview is `README.md`. Requirements are locked in the SRS (`docs/01-requirements/`) and the design document (`docs/02-design/`). If this file and those documents diverge, fix this file — do not silently “improve” the product.

## Precedence

If anything conflicts, follow this order:

1. `Project Description.pdf` (the COMP3211 brief, at the repository root; cannot be waived)
2. `docs/01-requirements/SRS.md` (requirements and glossary)
3. `docs/02-design/DESIGN.md` (architecture, classes, file format; §5 design decisions)
4. `CLAUDE.md`
5. `README.md`

Do not reopen locked decisions. Do not add decisions that contradict accepted ones. If a genuine conflict with the brief appears, stop and tell the user; do not patch around it.

## Commands (macOS, from the repository root)

```bash
python3 pim.py                                      # curses UI on a TTY
PIM_NO_CURSES=1 python3 pim.py                      # line UI (what tests drive)
python3 -m unittest                                 # all three layers
python3 -m unittest discover -s tests/unit -t .     # or tests/integration, tests/e2e
python3 tests/coverage_report.py                    # writes docs/04-unit-tests/coverage.txt; must be 100% of model/
git config core.hooksPath hooks                     # once per clone: enable the gate
sh docs/build.sh                                    # typeset PDFs into the repository root (needs pandoc, mmdc, Chrome, and xelatex or tectonic)
python3 docs/05-presentation/build_deck.py           # presentation deck (needs python-pptx)
```

## Project intent

This is a **course group project**: a command-line Personal Information Management (PIM) system. The goal is full marks on the brief (SRS, design, implementation, model unit tests, presentation) — not a product beyond Appendix B.

The runnable system must let a user:

- create four PIR types (Note, Task, Event, Contact),
- modify, delete, and print them,
- search with type, contains, time comparison, `&&` `||` `!`,
- save and load a `.pim` file.

Visible demo quality (designed terminal UI, in-process Alarm Alerts) is in scope. Extra features are not.

## Non-negotiable scope

Implement exactly Appendix B (US1–US11) plus the HCI already decided: prompted create/modify, criterion-line search, in-process OVERDUE/SOON alerts, and a curses folder browser for load / save-as paths (DESIGN §5.4).

**Out of scope** (do not implement, suggest, or leave stubs for):

- GUI, Textual, Rich, prompt_toolkit, Click, colour libraries (stdlib `curses` on a TTY is the designed View; DESIGN §5.1)
- any pip / third-party dependency
- networking, multi-user, sync, daemon process, OS notifications (`osascript`, etc.)
- recurring events / Series / RRULE
- links between PIRs
- unique labels, a global title field, fuzzy (edit-distance) search
- changing a PIR’s type after creation
- snooze / postpone, live ringing, background timers as a second process

If a user or another agent asks for an out-of-scope feature, refuse it against this list and the brief’s “no extra credit for additional features” rule.

## Source of truth by topic

| Topic | Read |
|---|---|
| Domain words | SRS §3 Glossary |
| Scope, fields, search grammar, interaction, error rules | SRS §2 and §6 (FR-1 – FR-43, NFR-1 – NFR-10) |
| Packages, `PIM` interface, PIM File JSON, event loop | DESIGN §2–§3 |
| Why a choice was made | DESIGN §5 |
| Which requirement each test covers | `docs/03-implementation/REQUIREMENTS.md`, and the *Verification* lines in the SRS |
| Test fixture | `tests/fixture.py` |
| Demo script | `tests/e2e/test_demo.py` (the scripted demo session) |

Use the SRS glossary terms as written. Forbidden substitutions:

- **Name** is the Contact person name only — not a title on other types
- **Label** is not a concept in this product
- **Note** is a PIR type, not a field; the Note body field is `text`
- **Id** is the only unique identity; row numbers and Display Name are not

## Architecture rules

- Pattern: **MVC**. Composition root is `pim.py`: `PIM()` → `App(pim)` → `Terminal(app)` → `run()`.
- Top-level packages named `model`, `view`, `controller`. Not `pim.model`.
- `model` is a **deep module**. Callers and tests use `PIM` plus Criterion constructors. Matching, JSON codec, and validation stay inside `model`.
- `model` must not import `view` or `controller`. No threads, stdin, ANSI, or curses in `model`.
- `parse_criterion` lives in `model` so US7 is unit-testable without the View.
- Persistence is JSON in a `.pim` file via `PIM.save` / `PIM.load`. Tests use a temp file. Do not add a one-implementation `Storage` port.
- `due_alarms(now)` is a pure query; **inject `now`**. `model` must not read the wall clock.
- View owns the event loop. TTY: stdlib `curses` `get_wch` + `timeout(500)`. Non-TTY / tests: daemon stdin-reader thread + `Queue.get(timeout=0.5)`. Only the main thread calls `model`. Redraw on change, not every tick.
- Dismissed alerts are View memory, not part of the PIM File.

## Implementation guardrails

- Python 3, **standard library only**. No `requirements.txt` of third-party packages.
- Default timezone: IANA `Asia/Hong_Kong` (HKT); `model.pir` falls back to a fixed UTC+8 zone when the tz database is missing, so never build `ZoneInfo` elsewhere. All datetimes timezone-aware. Compare instants.
- Failed commands are atomic: no mutation, no traceback to the user, no process exit. One specific English status-line error.
- Whitespace-only strings are missing values. Missing required fields fail the command.
- Ids are monotonic integers, persisted, never reused after delete.
- Relative alarms: at start or before start only. Search `alarm` is existential over Effective Alarm Times.
- contains: `str.casefold()` substring, not locale and not fuzzy.
- A time comparison on a missing field is false.
- Save appends `.pim` if omitted; load rejects other extensions.
- Dirty load/quit: save / discard / cancel — never silent drop.
- `print all` prints **Current Result**, not the unfiltered collection.
- Developer manual platform: macOS.
- User-facing strings and error messages: English.
- Course artefacts this agent writes (SRS, design text, comments that explain behaviour): English.

## Testing rules

- Framework: `unittest` (the brief’s example). Automatically executable, all passing.
- Three layers, all stdlib:
  - **Unit** (`tests/unit`): `model` (graded surface), `controller` (App/errors with a mocked PIM), and `view` (Terminal/stdin_reader with a fake App). `tests/coverage_report.py` must report **100%** of countable `model/` lines.
  - **Integration** (`tests/integration`): `controller.App` against `model.PIM`; `view.Terminal` against App+PIM on one thread (no stdin reader).
  - **E2E** (`tests/e2e`): scripted stdin through `Terminal.run()` with injected `stdin` / `stdout` / `now`.
- Each test must state the behaviour it exercises (name or comment) and assert expected results.
- Cover: four types create/validate/modify/delete; Id stability; contains / unqualified contains / missing-field time / and-or-not / multi-alarm; save/load round-trip; `due_alarms` with injected `now`; dirty flag; corrupt file does not clobber memory.
- Prefer the shared fixture in `tests/fixture.py`.
- `python3 tests/coverage_report.py` writes the line-coverage report for `model/` to `docs/04-unit-tests/coverage.txt`. Its typeset copy, `COVERAGE_REPORT.pdf`, is the report the brief requires at the source root.
- Pre-commit (`hooks/pre-commit`): unit tests at 100% `model/` coverage, then integration, then e2e, or the commit is refused. `git config core.hooksPath hooks`. Bypass: `git commit --no-verify`.

## Agent working rules

- Implement the locked design. Do not “simplify” by collapsing MVC, swapping JSON for pickle, or blocking on `input()`.
- Do not start coding a new PIR type, a fifth package, or a TUI framework to make the UI “nicer”.
- When implementing, keep `model` the test surface: if a rule cannot be tested through `PIM` / Criterion, it is in the wrong package.
- If you must choose a detail not in the docs (e.g. exact menu keystrokes), pick the smallest option that still satisfies acceptance, and record it as a row in the matching table of `docs/02-design/DESIGN.md` §5 (decision, why, rejected) only if it is hard to reverse, surprising, and a real trade-off.
- Keep the SRS glossary domain-only: no implementation types, file paths, or Python names.
- Do not change a requirement in the SRS or a decision in DESIGN §5 unless the user explicitly changes a product decision. Do keep both documents true to the code: when behaviour, a class, or a public method changes, update the SRS, DESIGN §3, `REQUIREMENTS.md`, and the manuals in the same change.
- Do not add separate product, architecture, acceptance, or glossary files; the SRS and the design document are the only specifications.
- Do not add dated plan files or separate decision records (ADRs).
- Honour Declaration: GenAI use is allowed if acknowledged. Do not invent a false “no GenAI” claim. Contribution splits are the group’s, not the agent’s.
- Every document source lives under `docs/`, grouped in assignment order: SRS in `docs/01-requirements/`, design in `docs/02-design/`, manuals and requirements coverage in `docs/03-implementation/`, line coverage in `docs/04-unit-tests/`, and slides in `docs/05-presentation/`. Shared title-page details are in `docs/group.yaml`; supporting material is in the underscore folders. The root holds only `README.md`, this file, the brief, and the submitted PDFs: `SRS.pdf`, `DESIGN_REPORT.pdf`, `USER_MANUAL.pdf`, `DEVELOPER_MANUAL.pdf`, `REQUIREMENTS.pdf`, `COVERAGE_REPORT.pdf`, and `Presentation Slides.pdf`. The brief requires the requirements coverage report and the line-coverage report in the root folder of the source code; `REQUIREMENTS.pdf` and `COVERAGE_REPORT.pdf` are those. Do not add other documents at the root.
- The SRS, DESIGN, manuals, and `REQUIREMENTS.md` are graded as PDFs. Keep repo-only notes in `<!-- -->` comments (pandoc drops them), and never cite files a grader won't have. After changing a document, rebuild it (`sh docs/build.sh SRS`, named by source file) and look at its PDF at the root: the dash counts in a pipe table's separator row set the column widths. The typeset PDFs are tracked in git; commit them with the Markdown change. The page design lives in `docs/_typeset/`; title-page details (group number, members) are in `docs/group.yaml`.
- `hooks/pre-commit` rewrites `docs/04-unit-tests/coverage.txt`. If it changes, commit it with the change that caused it.
- To stage a file already removed with `git rm`, use `git add -A -- <paths>`. A plain `git add` of that path fails and aborts an `&&` chain.
- To try the curses UI by hand, run it under tmux with `HOME` set to a temporary folder, so the folder browser and `~` paths don't touch your real home folder.

## Commit messages

Every commit message uses Conventional Commits, with a **scope** and a body that is detailed enough that a later reader does not need the diff to know what changed and why.

Format:

```
<type>(<scope>): <short summary>

<body>
```

- **type**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore` (use `feat` for user-visible behaviour, `fix` for defects, `refactor` for structure without behaviour change).
- **scope**: usually `PIM`, or a tighter one when the change is local (`model`, `view`, `controller`, `tests`).
- **summary**: imperative, lowercase after the colon, no trailing period; one line.
- **body**: required unless the change is trivial (typo, path-only). State what changed, which stories or design decisions it serves, and any behaviour a reviewer must not miss. Wrap at ~72 characters.

Examples:

```
feat(PIM): add field-driven create and modify wizards

Replace per-type prompt closures in the View with FieldSpec lists on
each PIR class. Alarms are RelativeAlarm/AbsoluteAlarm objects, not
JSON dicts. Empty modify no longer marks the collection dirty.
```

```
fix(model): keep load from clobbering memory on bad JSON

Parse the whole .pim file before replacing the collection, so a corrupt
file leaves the current records, next Id, and dirty flag untouched and
the status line reports the error.
```

Every commit carries the type/scope prefix; only a trivial change may omit the body.

### Granularity

Each commit has **one job**. Prefer a few medium-sized commits over one dump of everything the agent did in a turn.

When staging, split if any of these is true:

- different **types** (`feat` vs `fix` vs `refactor` vs `docs` vs `test`)
- different **layers** (`model` vs `view`/`controller` vs manuals vs `CLAUDE.md`)
- independent behaviour a reviewer could accept or revert on its own

Do this even when the user said “implement/fix/refactor all of this” in one request, and even when the agent produced every file in one session. Implement together if that is faster; **commit separately**.

Do **not** split a single atomic behaviour across commits (e.g. a `model` change that would fail tests until the matching `tests/` file lands — those stay together). Do not invent tiny commits for whitespace or import reorder.

Order dependent commits so each leaves `python3 -m unittest` green.

### Pull request summary

The PR **title** follows Conventional Commits (`feat(PIM): …`). The PR **body** is the reviewer’s map of the change: detailed enough to understand intent, scope, and risk without reading every hunk; specific enough that a reviewer knows what to try and what is *not* in the PR.

Do not paste the commit list as the whole summary. Do not write a one-line body (`implement PIM`, `see commits`). English, same as other course artefacts this agent writes.

Required sections, in this order:

1. **Summary** — what shipped and why (user stories, design decisions, or the defect). Two to five sentences. Name the user-visible behaviour.
2. **What changed** — bullets by layer (`model`, `view`/`controller`, tests, docs). Call out behaviour a reviewer must not miss (atomic failure, dirty load/quit, Current Result vs `print all`, injected `now`).
3. **How to check** — exact commands (`python3 -m unittest`, `python3 pim.py`, demo steps from the scripted demo in `tests/e2e/test_demo.py`). State the platform if it matters (macOS).
4. **Out of scope** — explicit: extra features not in Appendix B, and course artefacts this PR does not claim (SRS, videos, Honour Declaration) when that applies.

Optional when useful: **Risks / follow-ups** (known gaps, coverage holes, UI edges). **Commits** as a short list only after the summary, not instead of it.

The body must stay true: do not claim tests, manuals, or stories that the diff does not contain. If the PR is a draft, say what still has to land before Ready.

## Comments and docstrings

Code the agent writes or substantially edits must be documented in **English**:

- Every public module, class, and function gets a docstring. Modules: what the file is for. Classes: the type’s role in MVC / the domain. Functions/methods: arguments, return value, and error cases when they are not obvious from the name.
- Add a short line comment at non-obvious points: atomic copy-then-replace, dirty-file rules, EOF vs quit, criterion precedence, why `now` is injected, why a failed command must not mutate.
- Do not narrate the code (`# increment i`). Do not leave commented-out code. Docstrings explain behaviour and invariants, not the history of the change.

## Required gates

Before calling implementation work done:

1. Every FR and NFR in the SRS is met, and `REQUIREMENTS.md` shows no row as not implemented.
2. `python3 -m unittest` is green.
3. `python3 pim.py` can run the demo scripted in `tests/e2e/test_demo.py` on macOS with stdlib only.
4. No third-party imports anywhere in the submitted source.

SRS, typeset design document, videos, and Honour Declaration are separate deliverables. Do not claim those are done when only code is done.

## Decision rule

When uncertain:

**assignment compliance > locked product/architecture > testability of `model` > terminal polish**

If a change makes the UI prettier but violates “standard library only”, or adds a feature Appendix B does not ask for, reject it.
