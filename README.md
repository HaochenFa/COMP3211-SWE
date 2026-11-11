# COMP3211 PIM

Command-line Personal Information Management system for PolyU COMP3211 Software Engineering (Fall 2026).

The assignment brief is [`Project Description.pdf`](<Project Description.pdf>). Product requirements are in the SRS; the design document records the accepted architecture and design decisions.

## Documents

Document sources are grouped under `docs/` in the same order as the assignment: `01-requirements`, `02-design`, `03-implementation`, `04-unit-tests`, and `05-presentation`. The root holds the official brief, submitted PDFs, this README, and `CLAUDE.md`. Run `sh docs/build.sh` to typeset the SRS, design document, manuals, requirements coverage report, and line-coverage report. The brief requires both coverage reports in the source root; those PDFs are `REQUIREMENTS.pdf` and `COVERAGE_REPORT.pdf`. Folders beginning with `_` contain supporting material: diagram sources, typesetting files, the system-video script, and presentation media. The brief is unchanged.

| Source | PDF | What it is |
|---|---|---|
| [`docs/01-requirements/SRS.md`](docs/01-requirements/SRS.md) | [`SRS.pdf`](SRS.pdf) | Software requirements specification (deliverable 1) |
| [`docs/02-design/DESIGN.md`](docs/02-design/DESIGN.md) | [`DESIGN_REPORT.pdf`](DESIGN_REPORT.pdf) | Design document (deliverable 2): architecture, code components, example use, and design decisions |
| [`docs/03-implementation/USER.md`](docs/03-implementation/USER.md) | [`USER_MANUAL.pdf`](USER_MANUAL.pdf) | User manual (deliverable 3) |
| [`docs/03-implementation/DEVELOPER.md`](docs/03-implementation/DEVELOPER.md) | [`DEVELOPER_MANUAL.pdf`](DEVELOPER_MANUAL.pdf) | Developer manual (deliverable 3) |
| [`docs/03-implementation/REQUIREMENTS.md`](docs/03-implementation/REQUIREMENTS.md) | [`REQUIREMENTS.pdf`](REQUIREMENTS.pdf) | Requirements coverage report (deliverable 3; PDF at the source root) |
| [`docs/04-unit-tests/coverage.txt`](docs/04-unit-tests/coverage.txt) | [`COVERAGE_REPORT.pdf`](COVERAGE_REPORT.pdf) | `model/` line coverage (deliverable 4; PDF at the source root) |
| [`docs/05-presentation/`](docs/05-presentation/) | [`Presentation Slides.pdf`](<Presentation Slides.pdf>) | Presentation slides (deliverable 5); source deck is `presentation-slides.pptx` |
| [`CLAUDE.md`](CLAUDE.md) | — | Rules for AI agents: precedence, scope, architecture, gates |

Use the SRS glossary (§3) terms as written. Do not treat **Name** as a title, **Label** as identity, or **Note** as a field name.

## Product in one paragraph

A single-user terminal PIM. The user manages Notes, Tasks, Events, and Contacts in a Working Collection, searches with contains / time comparison / `&&` `||` `!`, and stores the collection in a UTF-8 JSON file with the extension `.pim`. Python 3 and the standard library only. No GUI, no third-party TUI, no recurrence, no network.

## Layout

```
model/                    # required package name; the unit-test surface
view/                     # designed terminal UI and in-process Alarm Alerts
controller/               # one user action → model.PIM
pim.py                    # composition root: python3 pim.py
tests/unit/               # model (100% lines) + controller + view
tests/integration/
tests/e2e/                # includes the scripted demo, test_demo.py
tests/coverage_report.py  # model/ line coverage → docs/04-unit-tests/coverage.txt
hooks/                    # pre-commit: unit + integration + e2e
docs/01-requirements/     # SRS (deliverable 1)
docs/02-design/           # design document (deliverable 2)
docs/03-implementation/   # manuals and requirements coverage (deliverable 3)
docs/04-unit-tests/       # model line-coverage source (deliverable 4)
docs/05-presentation/     # slide source deck and its build script (deliverable 5)
docs/group.yaml           # shared title-page and presentation details
docs/_*/                  # supporting material: diagrams, typesetting, video, media
docs/build.sh             # typesets the PDFs into the root
*.pdf                     # the brief and the submitted PDFs
README.md
CLAUDE.md                 # rules for AI agents
```

Run with `python3 pim.py`. Tests: `python3 -m unittest`. Coverage: `python3 tests/coverage_report.py` (must be 100% of `model/`). Enable the commit gate: `git config core.hooksPath hooks`. See the [developer manual](docs/03-implementation/DEVELOPER.md) and the [user manual](docs/03-implementation/USER.md). Story coverage: [`REQUIREMENTS.md`](docs/03-implementation/REQUIREMENTS.md).

## Constraints that affect every commit

- Importable top-level package named `model`
- Standard library only (no pip dependencies)
- Default timezone: Hong Kong Time (`Asia/Hong_Kong`)
- Failed commands do not mutate data, dump a traceback, or exit
- Unit tests target `model/` with `unittest` at 100% line coverage; integration and e2e suites also run under `unittest`; line-coverage report (`COVERAGE_REPORT.pdf`) at the source root

## Submission

One ZIP by **20:00, 20 November 2026**: SRS, design document, source, manuals, ≤4 min system video, requirements coverage table, model tests and coverage report, presentation PDF and ≤5 min recording, Honour Declaration at the ZIP root.

The demo script runs end to end as [`tests/e2e/test_demo.py`](tests/e2e/test_demo.py).
