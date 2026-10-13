---
title: "Design Document — Personal Information Management (PIM) System"
subtitle: "COMP3211 Software Engineering, Fall 2026 — Group Project"
date: "Version 1.3 draft, 25 September 2026"
---

<!-- Source-tree note (not rendered): this is the only architecture and
design document in the repository, and Section 5 is the only record of design
decisions. Change it when the design changes. -->

Requirement ids such as FR-16 refer to the Software Requirements Specification (SRS).

# 1. Introduction

This document describes the design of the command-line PIM system:

- **Section 2:** the architecture: which pattern was chosen, why, and how it is instantiated.
- **Section 3:** the main code components: every class with its fields and public methods, and how the classes relate.
- **Section 4:** one example use, *search for records and then update one*, as a sequence diagram.
- **Section 5:** the design decisions, each with its reason and the alternatives rejected.
- **Section 6:** a short assessment of modularity, efficiency, extendibility, and justifiability.

The system is written in Python 3.12 and uses only the standard library. All type names below are Python types. `X | None` means "an X, or nothing"; `list[X]` is a list of X; `dict[K, V]` is a mapping.

# 2. Architecture

## 2.1 Chosen pattern: Model–View–Controller

The system uses the **Model–View–Controller (MVC)** pattern. Each of the three components is a top-level Python package: `model`, `view`, and `controller`.

![Architecture of the PIM system (MVC). Solid arrows are calls; dotted arrows from `pim.py` show object creation; the dotted arrow from the View is read-only use of model value objects.](diagrams/architecture.png){width=100%}

**Why MVC.** Four reasons:

1. **The brief asks for it.** All model code must be in a separate package named `model` so that it can be unit-tested. MVC is the pattern that draws exactly that line: the model holds the data and the rules, and knows nothing about the screen.
2. **It fits an interactive program.** The PIM is a loop: read one user action, change the data, and show the new state. MVC splits that loop into three jobs. The View reads input and draws. The Controller turns one finished action into model calls. The Model applies the rules.
3. **Two front ends share one controller.** On an interactive terminal the View is a full-screen `curses` interface; for scripted input, such as the tests, it is a line-by-line interface. Both call the same `App`, so the behaviour cannot drift between them.
4. **Tests need no screen.** Search (US7), persistence (US10/US11), and alarms can be tested by calling `PIM` directly. The time `now` is passed in, so alarm tests do not depend on the wall clock.

**Alternatives considered.**

- *A layered architecture* (UI → service → storage) would need a separate storage layer and interface. With one JSON file format, that layer would have a single implementation and add indirection for nothing. In this design, persistence is two methods of the model (`save`, `load`).
- *A single procedural script* would mix parsing, input, and screen code, and it would miss the brief's `model`-package requirement.

## 2.2 How the components are instantiated

| Component | Package / class | Responsibility in this system |
|----------------|------------------------------------------------------------|----------------------------------------------------------------------|
| Model | `model.PIM`, the PIR classes, alarms, `Criterion`, `pimfile` | Holds the Working Collection and assigns Ids. Validates every field. Parses and evaluates search criteria. Reads and writes the PIM File. Computes due alarms for a given `now`. Raises a `PIMError` subclass on every rule violation. |
| Controller | `controller.App`, `controller.errors` | Handles one completed user action: create, modify, delete, search, print, save, load. Keeps the Current Result, the search criterion, and the Selection. Turns every model exception into one English status line; it never lets one reach the user as a traceback. |
| View | `view.Terminal`, `view.CursesUI`, helper modules | Owns the event loop (500 ms tick). Reads keys or lines. Asks for fields one at a time. Draws the title, Alarm Alert banner, list, detail, and status line. Remembers which alerts were dismissed. |
| Composition root | `pim.py` | `main()` creates `PIM()`, passes it to `App(pim)`, passes that to `Terminal(app)`, and calls `run()`. |

**Package layout.**

```
pim.py              composition root: python3 pim.py
model/              the unit-test surface; no threads, input, or screen code
  pim.py            PIM: Working Collection, Ids, dirty flag, save/load, due alarms
  pir.py            PIR hierarchy, alarms, field specs, date-time parsing, exceptions
  criterion.py      search criteria (Composite) and parse_criterion
  pimfile.py        PIM File JSON codec and atomic write
controller/
  app.py            App: one user action -> PIM calls; Current Result, Selection
  errors.py         message_for: exception -> one status line
view/
  terminal.py       Terminal: prompts, wizards, Alarm Alerts, line UI loop
  curses_ui.py      CursesUI: full-screen loop on a TTY
  layout.py, widgets.py, file_browser.py, keys.py, theme.py,
  textwidth.py, stdin_reader.py   helpers (Section 3.2)
tests/unit, tests/integration, tests/e2e
```

**Dependency rules.**

- `model` imports nothing from `view` or `controller`.
- `controller` imports `model` only.
- `view` calls `controller.App` for every action. It imports from `model` only value types and helpers: it displays `PIR` and `DueAlarm` objects, builds `RelativeAlarm` / `AbsoluteAlarm` values in the alarm prompts, and uses `HKT` for the clock.
- `view` holds no business rules and does not know the file format; `controller` never reads or writes files itself.
- No module imports anything outside the Python standard library.

**Event loop.** The View runs the loop, and only its main thread calls the model:

- On a TTY, `CursesUI.loop` waits for a key with a 500 ms timeout.
- Otherwise, a daemon thread reads standard input into a `Queue`, and `Terminal` waits on the queue with a 500 ms timeout.

After each input or timeout, the View asks `App.due_alarms(now)` for alerts and redraws only if something changed: the due or dismissed alarms, the collection, the Bound File, the Current Result, the Selection, or the status line. The reader thread only queues lines and never touches the model, so no lock is needed. Dismissed alerts are a set of (Event Id, alarm index) pairs in the View; they are never written to the PIM File.

# 3. Structure of and relationships among the main code components

## 3.1 Model classes

![Model classes, part 1: the Working Collection, the PIR hierarchy, and alarms. Argument types are shortened here; the tables below give the full types.](diagrams/model-pir-classes.png){height=80%}

**Relationships.**

- `PIM` *aggregates* any number of PIRs, keyed by Id.
- `PIR` is an abstract base class with four concrete subclasses. Each subclass declares its fields in `FIELDS`, which the View uses to build the create and modify prompts.
- An `Event` is *composed of* zero or more alarms. Each alarm is a `RelativeAlarm` or an `AbsoluteAlarm`; both provide `effective(start)`.
- `PIM.due_alarms` *creates* `DueAlarm` value objects.

![Model classes, part 2: search criteria (Composite pattern) and the exception hierarchy.](diagrams/model-criterion-classes.png){width=100%}

**Relationships.**

- A search criterion is a tree built with the **Composite** pattern. Leaves (`TypeIs`, `Contains`, `TimeCompare`) test one PIR; `And`, `Or`, and `Not` combine sub-criteria.
- `parse_criterion` builds the tree from one line of text, using a recursive-descent parser whose precedence is `!` > `&&` > `||`. It raises `ParseError` on bad syntax.
- Every model failure is a subclass of `PIMError`. `status_message()` gives the English text that the Controller shows.

### Class `PIM` (module `model.pim`)

The Working Collection: PIR identity, search, persistence, and due alarms.

**Fields (private):**

- `_pirs: dict[int, PIR]`: PIRs keyed by Id.
- `_next_id: int`: the next Id to assign.
- `_dirty: bool`: whether there are unsaved changes.
- `_bound_path: str | None`: the Bound File.

| Return type | Method | Arguments | Exceptions | Description |
|--------------------------|--------------------------|----------------------------------------|----------------------------|----------------------------------------------|
| `Note` | `create_note` | `text: str \| None` | `ValidationError` | Creates and inserts a Note with the next Id; marks the collection dirty. |
| `Task` | `create_task` | `description: str \| None`, `deadline: datetime \| str \| None = None` | `ValidationError` | Creates a Task; the deadline is optional. |
| `Event` | `create_event` | `description: str \| None`, `start: datetime \| str \| None`, `alarms: list[AlarmSpec] \| None = None` | `ValidationError` | Creates an Event; rejects out-of-range alarm times (FR-8). |
| `Contact` | `create_contact` | `name: str \| None`, `address: str \| None = None`, `mobile: str \| None = None` | `ValidationError` | Creates a Contact. |
| `PIR` | `modify` | `pir_id: int \| str`, `fields: dict[str, object]` | `NotFound`, `ValidationError` | Copies the PIR, applies the fields to the copy, and replaces the original only if the copy is valid and different (atomic). |
| `None` | `delete` | `pir_id: int \| str` | `NotFound` | Removes the PIR. Its Id is never reused. |
| `PIR` | `get` | `pir_id: int \| str` | `NotFound` | Returns the PIR with this Id. |
| `list[PIR]` | `all` | — | — | Every PIR in Id order. |
| `list[PIR]` | `search` | `criterion: Criterion` | — | The PIRs for which `criterion.matches(pir)` is true, in Id order. |
| `list[DueAlarm]` | `due_alarms` | `now: datetime \| str` | `ValidationError` | OVERDUE and SOON alarms at the given `now`. Never reads the clock. |
| `None` | `save` | `path: str \| os.PathLike[str]` | `ValidationError`, `OSError` | Writes the PIM File atomically, appending `.pim` if missing and expanding a leading `~`; binds the path and clears the dirty flag. |
| `None` | `load` | `path: str \| os.PathLike[str]`, `force: bool = False` (keyword) | `ExtensionError`, `ValidationError`, `DirtyLoadError`, `FileFormatError` | Replaces the collection from a file. Parses fully before replacing, so a bad file changes nothing. |
| `bool` | `is_dirty` | — | — | True if there are unsaved changes. |
| `str \| None` | `bound_path` | — | — | Path of the last successful save or load. |

### Class `PIR` (abstract) and subclasses (module `model.pir`)

The base class of all records.

**Fields:**

- `id: int`
- `type_name: str` (class constant)
- `FIELDS: tuple[FieldSpec, ...]` (class constant)

| Return type | Method | Arguments | Exceptions | Description |
|------------------------|----------------------|------------------------|--------------------------|------------------------------------------------|
| `str` | `display_name` (property) | — | — | The derived list label (see the SRS glossary). |
| `list[str]` | `text_fields` | — | — | Every text value, used by unqualified `contains`. |
| `str \| None` | `text_value` | `field: str` | — | The named text field, or `None` if this type has no such field. |
| `list[datetime]` | `time_values` | `field: str` | — | The instants of `deadline`, `start`, or `alarm` (Effective Alarm Times); empty if missing. |
| `datetime \| None` | `relevant_time` | — | — | The deadline or start shown in the list. |
| `None` | `modify` | `fields: dict[str, object]` | `ValidationError` | Applies field changes in place. Rejects a change of type. |
| `dict` | `to_json` | — | — | The `pim/v1` JSON object. |
| `list[tuple[str, str]]` | `detail_lines` | — | — | (label, value) rows for `print`. |

The constructors of the subclasses:

| Subclass | Constructor arguments | Extra fields | Exceptions |
|--------------|--------------------------------------------------|--------------------------------------------|--------------------|
| `Note` | `pir_id: int`, `text: str \| None` | `text: str` | `ValidationError` |
| `Task` | `pir_id: int`, `description: str \| None`, `deadline: datetime \| str \| None = None` | `description: str`, `deadline: datetime \| None` | `ValidationError` |
| `Event` | `pir_id: int`, `description: str \| None`, `start: datetime \| str \| None`, `alarms: list[AlarmSpec] \| None = None` | `description: str`, `start: datetime`, `alarms: list[RelativeAlarm \| AbsoluteAlarm]` | `ValidationError` |
| `Contact` | `pir_id: int`, `name: str \| None`, `address: str \| None = None`, `mobile: str \| None = None` | `name: str`, `address: str \| None`, `mobile: str \| None` | `ValidationError` |

`Event` adds one method: `effective_alarm_times() -> list[datetime]`.

### Alarm classes (module `model.pir`)

| Class | Constructor | Fields | Methods |
|---------------------|------------------------------------------------|--------------------|------------------------------------------------|
| `RelativeAlarm` | `amount: int \| str`, `unit: str`. Raises `ValidationError` for a negative or non-integer amount, or a unit other than minute, hour, day, or week. | `amount: int`, `unit: str` | `effective(start: datetime) -> datetime` (start minus the duration); `to_json() -> dict`; `kind_label() -> str` |
| `AbsoluteAlarm` | `at: datetime \| str`. Raises `ValidationError`. | `at: datetime` | `effective(start: datetime) -> datetime` (returns `at`); `to_json() -> dict`; `kind_label() -> str` |
| `DueAlarm` | `event_id: int`, `alarm_index: int`, `at: datetime`, `status: str`, `description: str` | the same | `key() -> tuple[int, int]` (identity used for dismiss) |
| `FieldSpec` (dataclass) | `key: str`, `label: str`, `kind: str`, `required: bool = True` | the same | — |

`AlarmSpec` means `RelativeAlarm | AbsoluteAlarm | dict`. A `dict` is the JSON form read from a file.

### Criterion classes (module `model.criterion`)

| Class | Constructor | Fields | `matches(pir: PIR) -> bool` returns true when … |
|------------------|--------------------------------------------------|------------------------------|--------------------------------------------------|
| `Criterion` (abstract) | — | — | (abstract; raises `NotImplementedError`) |
| `TypeIs` | `type_name: str`. Raises `ParseError`. | `type_name: str` | the PIR's type is `type_name` |
| `Contains` | `field: str \| None`, `needle: str`. Raises `ParseError`. | `field: str \| None`, `needle: str` (case-folded) | the folded field value, or any text field when `field` is `None`, contains `needle` |
| `TimeCompare` | `field: str`, `op: str`, `instant: datetime`. Raises `ParseError`. | `field`, `op`, `instant` | any instant of `field` satisfies `op` against `instant`; false if there is none |
| `And` / `Or` | `left: Criterion`, `right: Criterion` | `left`, `right` | both / either child matches |
| `Not` | `inner: Criterion` | `inner` | the child does not match |

### Module-level functions of `model`

| Return type | Function | Arguments | Exceptions | Description |
|--------------------|------------------------|--------------------------------------|--------------------------|------------------------------------------|
| `Criterion` | `parse_criterion` | `text: str` | `ParseError` | Parses one US7 criterion line (grammar in SRS FR-16). |
| `datetime` | `parse_datetime` | `value: datetime \| str` | `ValidationError` | Parses ISO 8601 or `YYYY-MM-DD HH:MM`; defaults to HKT; floors to the minute. |
| `str` | `format_datetime` | `dt: datetime` | — | ISO 8601 text to the second. |
| `tuple[int, list[PIR]]` | `read_pim_file` | `path: str \| os.PathLike[str]` | `ExtensionError`, `ValidationError`, `FileFormatError` | Parses a PIM File without touching the collection. |
| `Path` | `write_pim_file` | `path: str \| os.PathLike[str]`, `next_id: int`, `pirs: list[PIR]` | `ValidationError`, `OSError` | Writes a temporary file, then atomically replaces the target. |

### Exceptions

All are subclasses of `PIMError(Exception)`, which provides `status_message() -> str`:

- `ValidationError`: a missing or illegal field value.
- `NotFound`: no PIR has this Id.
- `ParseError`: bad criterion syntax.
- `DirtyLoadError`: load with unsaved changes and no force.
- `FileFormatError`: the file is not a valid `pim/v1` PIM File.
- `ExtensionError`: the path does not end in `.pim`.

### PIM File format

A PIM File is UTF-8 JSON. `write_pim_file` writes it; `read_pim_file` checks it completely before `PIM.load` replaces anything (SRS FR-31, FR-36).

```json
{
  "format": "pim/v1",
  "next_id": 5,
  "pirs": [
    { "id": 1, "type": "note", "text": "buy milk" },
    { "id": 2, "type": "task", "description": "submit ZIP",
      "deadline": "2026-11-20T20:00:00+08:00" },
    { "id": 3, "type": "event", "description": "COMP3211 lecture",
      "start": "2026-09-14T18:30:00+08:00",
      "alarms": [
        { "kind": "relative", "amount": 1, "unit": "day" },
        { "kind": "relative", "amount": 0, "unit": "minute" },
        { "kind": "absolute", "at": "2026-09-13T09:00:00+08:00" } ] },
    { "id": 4, "type": "contact", "name": "Ada",
      "address": null, "mobile": "12345678" }
  ]
}
```

- `unit` is `minute`, `hour`, `day`, or `week`; `amount` 0 means at the start.
- An optional field may be `null` or left out; both mean "not set".
- `next_id` is stored so that a deleted Id is never reused after a load. If it is not above the largest Id in the file, the load raises it.

## 3.2 Controller and View classes

![Controller and View classes. Argument types are shortened here; the tables below give the full types.](diagrams/controller-view-classes.png){width=100%}

**Relationships.**

- `CursesUI` drives a `Terminal` when a TTY is available.
- `Terminal` calls `App` for every user action.
- A prompt of `Terminal` may hold one widget: a `Chooser`, a `DateTimePicker`, or a `FileBrowser`. A widget only produces the answer text; the prompt handler checks it exactly like typed input.
- `App` calls `PIM`.

Neither `App` nor `Terminal` stores PIR data of its own. `App` stores only the Current Result (a list of PIR references), the criterion, and the Selected Id, and it re-runs the criterion after every change.

### Class `App` (module `controller.app`)

**Fields:**

- `pim: PIM`
- `status: str` and `status_kind: str` (`info`, `ok`, or `err`)
- `print_text: str`
- private: `_criterion: Criterion | None`, `_criterion_line: str | None`, `_result: list[PIR]`, `_selected_id: int | None`

Constructor: `App(pim: PIM)`. It binds to a Working Collection, which may be empty or already loaded, and shows the whole collection as the Current Result.

The controller does not raise. On a failure it sets `status` to one English line with `status_kind` `err`, and returns `None` or `False`. The only exception is `save_target`, which the View uses to check a path before asking about an overwrite.

| Return type | Method | Arguments | Exceptions | Description |
|----------------------|------------------------------|--------------------------------|--------------------------|----------------------------------------------|
| `PIR \| None` | `create` | `type_name: str`, `fields: dict[str, object]` | none | Creates a PIR and selects it. |
| `PIR \| None` | `modify` | `fields: dict[str, object]` | none | Modifies the selection. Empty `fields` changes nothing. |
| `bool` | `delete_selected` | — | none | Deletes the selection, after the View has confirmed. |
| `bool` | `search` | `line: str` | none | Parses and runs a criterion. On error, keeps the Current Result. |
| `None` | `clear_search` | — | none | Restores the whole collection. |
| `None` | `select_row` | `number: int \| str` | none | Selects by row of the Current Result. |
| `None` | `select_id` | `pir_id: int \| str` | none | Selects by Id. |
| `str \| None` | `print_selected` | — | none | Detail text of the selection. |
| `str` | `print_all` | — | none | Detail text of every PIR in the Current Result. |
| `None` | `clear_print` | — | none | Drops the last printed text. |
| `bool` | `save` | `path: str \| os.PathLike[str] \| None = None` | none | Saves to the Bound File or to `path`; the status names the absolute path. Reports an `OSError` as a status. |
| `bool` | `load` | `path: str \| os.PathLike[str]`, `force: bool = False` | none | Loads and resets the search and the Selection; the status names the absolute path. |
| `str` | `save_target` | `path: str \| os.PathLike[str]` | `ValidationError` | The path `save` would write, with `.pim` appended. |
| `bool` | `would_overwrite` | `path: str \| os.PathLike[str]` | none | Whether `save as` would replace another existing file. |
| `list[DueAlarm]` | `due_alarms` | `now: datetime` | none | Passes through to the model. |
| `None` | `set_status` | `text: str`, `kind: str = "info"` | none | Sets the status line and its tone. |
| `list[PIR]` | `current_result` | — | none | The Current Result, for drawing. |
| `PIR \| None` | `selected` | — | none | The selected PIR. |
| `int \| None` | `selected_id` | — | none | Id of the selected PIR. |
| `bool` | `has_criterion` | — | none | Whether a search is active. |
| `str \| None` | `criterion_line` | — | none | The text of the active search. |
| `str \| None` | `bound_path` | — | none | The Bound File. |
| `bool` | `is_dirty` | — | none | Whether there are unsaved changes. |

`controller.errors.message_for(exc: BaseException) -> str` maps an exception to one status line:

- a `PIMError` → its `status_message()`;
- an `OSError` → its text;
- anything else → `command failed`.

### Class `Terminal` (module `view.terminal`)

**Fields:**

- `app: App`
- `stdin: TextIO`, `stdout: TextIO`
- `queue: Queue`: lines from the stdin reader thread (line UI)
- `dismissed: set[tuple[int, int]]`: dismissed alerts, keyed by (Event Id, alarm index)
- `page_size: int`
- private: `_now: datetime | Callable[[], datetime] | None`, `_prompts: list[Prompt]`

Constructor: `Terminal(app: App, stdin: TextIO | None = None, stdout: TextIO | None = None, now: datetime | Callable[[], datetime] | None = None)`. Tests inject the streams and `now`. Left out, they are the process streams and the HKT wall clock.

None of these methods raises to its caller. Each command is run inside a handler that turns any exception into the status line (NFR-4).

| Return type | Method | Arguments | Description |
|----------------------|--------------------------------|------------------------------------------|------------------------------------------------------------|
| `None` | `run` | — | Starts `CursesUI` on a TTY, or else the line loop. Returns on quit. |
| `list[DueAlarm]` | `visible_due` | — | Due alarms minus the dismissed ones. |
| `Screen` | `screen` | — | The screen model (title, banner, list, detail, status) that both front ends draw. |
| `None` | `render` | — | Draws the line-UI screen. |
| `None` | `ask` | `prompt: str`, `handler: Callable[[str], object]`, `kind: str \| None = None`, `chooser: Chooser \| None = None`, `picker: DateTimePicker \| None = None`, `browser: FileBrowser \| None = None` | Queues a prompt; `handler(answer)` runs when the user answers. At most one widget is set. |
| `None` | `apply_accelerator` | `action: str` | Runs the command bound to a single key. |
| `None` | `cancel_prompt` | — | Esc: drops the current wizard, but not a dirty save / discard / cancel prompt. |
| `None` | `idle_escape` | — | Esc with no wizard: clears an active search. |
| `None` | `retry_search_prompt` | — | Opens the criterion field again after a syntax error (FR-23). |
| `Chooser \| None` | `current_chooser` | — | The selector of the current prompt, if any. |
| `DateTimePicker \| None` | `current_picker` | — | The calendar of the current date-time prompt, if any. |
| `FileBrowser \| None` | `current_browser` | — | The folder browser of the current load or save-as prompt, if any. |
| `None` | `type_path_instead` | — | Drops the browser so the same prompt takes a typed path. |

### Class `CursesUI` (module `view.curses_ui`)

**Fields:**

- `term: Terminal`
- `stdscr`: the curses window
- `theme: Theme`

It has one public method, `loop() -> None`: the full-screen event loop (`get_wch` with a 500 ms timeout, and a 25 ms Esc delay so a lone Esc acts at once). Every command runs through `_safe`, which turns any exception into a status line. It raises no exception to its caller. The module function `title_bar_text(title: str, width: int) -> str` fits the title bar beside the clock, trimming a long file path from the left so the file name stays visible.

### Classes `Chooser` and `Choice` (module `view.widgets`)

A `Chooser` is a closed list of answers, for example Note · Task · Event · Contact, or Yes · No. It is an immutable dataclass. The View keeps the highlighted index, so the methods take and return indexes. The value it submits is the same text a user would type in the line UI.

**Fields:** `title: str`, `options: tuple[Choice, ...]`, `default: int = 0`, `hint: str`. Each `Choice` has `value: str`, `label: str`, `key: str | None` (a one-key shortcut), and `tone: str | None` (a colour role).

| Return type | Method | Arguments | Exceptions | Description |
|----------------------|------------------------------|--------------------------------|--------------------------|----------------------------------------------|
| `int` | `clamp` | `index: int` | none | Keeps `index` inside the option list. |
| `int` | `move` | `index: int`, `delta: int` | none | Moves by `delta` without wrapping. |
| `int \| None` | `pick_key` | `char: str` | none | The option whose key is `char`; else, when no option has a digit key, the option at that 1-based digit; `None` if no match. |
| `str` | `value_at` | `index: int` | none | The value to submit for that option. |

### Class `DateTimePicker` (module `view.widgets`)

A month grid and a time list for date-time prompts on a TTY (FR-11). The week starts on Monday, and the time moves in 15-minute steps. Its submitted value is text in the form `YYYY-MM-DD HH:MM`, which the model parses as HKT.

**Fields:** `title: str`, `required: bool`, `today: date`, `day: date`, `hour: int`, `minute: int`, `view: date` (first day of the shown month), `focus: str` (`date` or `time`).

Constructor: `DateTimePicker(title: str, now: datetime, *, initial: datetime | None = None, required: bool = True)`. It starts on `initial`, or else on the next 15-minute mark after `now`.

| Return type | Method | Arguments | Exceptions | Description |
|----------------------------|----------------------------|------------------------------|--------------------|--------------------------------------------------|
| `str` | `value` | — | none | The text to submit, `YYYY-MM-DD HH:MM`. |
| `str` | `summary` | — | none | A readable confirmation, for example `Mo 14 September 2026  18:30  HKT`. |
| `str` | `month_title` | — | none | Month name and year for the grid header. |
| `list[list[date]]` | `weeks` | — | none | The weeks of the shown month, Monday first. |
| `None` | `move_day` | `days: int` | none | Moves the chosen day and keeps the month in view. |
| `None` | `move_month` | `months: int` | none | Shows another month; clamps the day if the month is shorter. |
| `None` | `move_time` | `minutes: int` | none | Changes the time, wrapping within the day. |
| `None` | `jump_today` | `now: datetime` | none | Chooses today and keeps the time. |
| `None` | `toggle_focus` | — | none | Switches between the grid and the time list. |
| `list[tuple[int, int]]` | `time_slots` | `count: int = 7` | none | `count` times around the chosen one, 15 minutes apart. |

### Class `FileBrowser` (module `view.file_browser`)

The folder browser for load and save-as paths on a TTY (FR-39). It lists one folder: the parent link, subfolders, and `.pim` files. Hidden entries are left out. In save mode it adds a "new file in this folder" row. It returns a path string, so the prompt handler checks it like a typed path (Section 5.4).

**Fields:** `mode: str` (`load` or `save`), `cwd: Path`, `entries: list[Entry]`, `index: int` (the highlighted row), `error: str` (set when the folder cannot be read). Each `Entry` has `kind: str` (parent, folder, file, or new file) and `name: str`.

Constructor: `FileBrowser(mode: str, start: str | os.PathLike[str])`. It reads `start` at once.

| Return type | Method | Arguments | Exceptions | Description |
|----------------------|------------------------------|------------------------------|--------------------|------------------------------------------------------|
| `str` | `title` (property) | — | none | Heading for the overlay. |
| `None` | `refresh` | — | none | Reads `cwd` again. A folder that cannot be read sets `error` instead of raising. |
| `Entry \| None` | `current` | — | none | The highlighted row. |
| `None` | `move` | `delta: int` | none | Moves the highlight without wrapping. |
| `None` | `jump` | `last: bool` | none | Highlights the first or last row. |
| `None` | `go_up` | — | none | Opens the parent folder and highlights the folder just left. |
| `None` | `go_home` | — | none | Opens the home folder. |
| `str \| None` | `activate` | — | none | Opens a folder (returns `None`), or returns the absolute path of a `.pim` file. |
| `str` | `highlighted_path` | — | none | Absolute path of the highlighted folder or file. |
| `bool` | `wants_typing` | — | none | Whether the "new file" row is highlighted. |
| `str` | `typed_start` | — | none | Text to pre-fill when switching to a typed path: the current folder. |
| `tuple` | `state` | — | none | A hashable snapshot, so the screen redraws only on change. |

### View helper modules

| Module | Role |
|-------------------|----------------------------------------------------------------------|
| `view.layout` | Builds the screen model: title, banner, list rows, detail, and menu. |
| `view.widgets` | `Chooser` and `DateTimePicker` (see above), and `Prompt`: one queued question with its handler and at most one widget. |
| `view.file_browser` | `FileBrowser` (see above) and its row type `Entry`. |
| `view.keys` | Maps keys to actions (accelerators), e.g. `w` save, `W` save as, `o` load. |
| `view.theme` | Colour roles for 256-colour, 8-colour, and monochrome terminals. |
| `view.textwidth` | East-Asian-width-aware clipping and padding. |
| `view.stdin_reader` | Daemon thread that feeds lines into the `Queue` in the line UI. |

# 4. Example use: search for records, then update one

![Sequence diagram: searching for Events whose description contains "COMP", then changing the start of the hit.](diagrams/search-update-sequence.png){width=100%}

The numbers in brackets are the message numbers in the diagram.

**Search (messages 1–10).**

- *(1–2)* The user enters a criterion line. `Terminal` passes the raw line to `App.search`.
- *(3–4)* `App` calls `parse_criterion`, which tokenizes the line and builds the tree `And(TypeIs("event"), Contains("description", "comp"))`.
- *(5–8)* `PIM.search` calls `matches` on every PIR in Id order, and `And` evaluates its two children.
- *(9)* `App` stores the criterion and the hits as the Current Result, selects the first hit, and sets the status `1 match(es)`.
- *(10)* The View redraws the list and the detail pane.

A syntax error would raise `ParseError` at message 3. `App` would then leave the Current Result as it was and show `search syntax error: …`.

**Update (messages 11–30).**

- *(11–15)* `modify` asks `App` for the Selection. `Terminal` then prompts field by field, using the Event's `FIELDS`; an empty answer keeps a value.
- *(16–17)* `App.modify` sends only the changed fields to `PIM.modify`.
- *(18–20)* The model uses **copy-then-replace**: it copies the Event and applies the change to the copy. The copy parses the new start and checks that every Effective Alarm Time is still in range.
- *(21–26)* **If the copy is valid:** `PIM` puts the copy in place of the original under the same Id and marks the collection dirty. `App` then re-runs the stored criterion, so the Current Result is up to date, and the View shows the new start and the moved relative alarm times.
- *(27–30)* **If validation fails:** the exception propagates before the original is touched. `App` shows the message, and the data is exactly as before (FR-15, NFR-4).

The diagram shows the main design points of the system:

- the criterion is parsed and evaluated inside the model;
- the Controller holds the Current Result;
- the Id never changes;
- relative alarms follow the start;
- a failed update is atomic.

# 5. Design decisions

Each table below records one group of decisions: what was decided, why, and what was rejected. Section 2.1 covers the choice of MVC itself.

## 5.1 Platform and libraries

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| Python 3.12 with the standard library only. | The brief allows Java or Python and grades use of the standard library only. Python is the language the group knows best. | Java: nothing in the brief favours it. Any pip package, for example Textual, Rich, or pytest. |
| A full-screen `curses` interface on an interactive terminal, and a plain line interface when input or output is redirected (or `PIM_NO_CURSES=1`). | The brief asks for a command-line system and gives no credit for a GUI. `curses` is in the standard library. The line interface lets tests inject `stdin`, `stdout`, and `now`. | A GUI window (tkinter). A third-party terminal library. A line interface only, which would make alarms and selection hard to see. |
| Every time is time-zone aware. A time typed without an offset is Hong Kong Time (`Asia/Hong_Kong`). Comparisons use instants. If the system time-zone database is missing, HKT is a fixed UTC+8 offset. | The same PIM File then means the same instants on every machine. HKT has had no daylight saving since 1979, so the fixed offset gives the same present-day instants, and the program still starts on a computer without the database. | The machine's local zone. Requiring an offset on every input. Stopping at start-up without the database. The third-party `tzdata` package. |

## 5.2 Structure

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| Three top-level packages, `model`, `view`, and `controller`, plus `pim.py` as the composition root (Section 2.2). | The brief requires a package named exactly `model`, and the other components must be easy to identify. | A nested `pim.model`, which is not the required name. View and controller code inside `pim.py`. |
| `model` is one deep module behind a small interface: `PIM`, `parse_criterion`, and the criterion classes. | Validation, matching, and the JSON codec stay inside, so every rule sits in one place and is unit-tested without the screen. | Loose procedural functions. A service class over plain records. A `Storage` interface with a single implementation. |
| The View owns an in-process event loop with a 500 ms tick. The model never reads the clock: `now` is passed in (Section 2.2). | Alarm Alerts appear while the user is idle, without a second process. Alarm tests control time exactly. | Blocking on `input()`. A background process or operating-system notifications. |

## 5.3 Data and rules

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| A PIM File is UTF-8 JSON (`"format": "pim/v1"`). `save` appends `.pim` if it is missing, and `load` rejects any other extension. | The brief fixes only the `.pim` extension. JSON is in the standard library, readable, and easy to test (SRS FR-31). | `pickle`: opaque, and unsafe to load. YAML: needs a third-party parser. A custom text format: extra parser work. |
| A system-assigned integer Id is the only identity. It is stored in the file and never reused. | Row numbers change with every search. Descriptions and Contact names repeat, for example a weekly class. | A unique label chosen by the user. Selecting by row position alone. |
| A PIR's type cannot change. | US6 modifies a PIR's data. The fields of different types do not map onto each other. | Converting a PIR in place. The user deletes it and creates one of the new type. |
| An Event has zero or more alarms. Each is *Relative* (at the start or a whole number of units before it) or *Absolute* (a fixed instant), as in the iCalendar `TRIGGER`. | Several reminders per event is the standard model. Relative alarms move with the start; absolute ones do not. | Exactly one alarm. Relative alarms after the start, which an absolute alarm already covers. The `.ics` file format. |
| No recurring events. | Appendix B does not ask for them. A series needs a second life cycle (one occurrence or the whole series) and earns no credit. | Repeat rules (RRULE). A weekly class is several Events. |
| `contains` is a substring test after `str.casefold()` on both sides. | US7 asks for a substring test. Ignoring case is kinder to the user, and case folding does not depend on the locale. | Fuzzy matching. Locale-dependent comparison. |
| A failed command changes nothing and shows one English status line. | Invalid input is normal at a command line. The model validates a copy (`modify`) or parses the whole file (`load`) before it replaces anything, so each error requirement is testable (SRS NFR-4). | Partial updates. Printing a traceback or ending the program. |

## 5.4 Interaction

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| Create and modify ask for one field at a time. Search takes one criterion line (grammar in SRS FR-16). | Prompts need no syntax to remember. A criterion must be exact to be testable, especially `&&`, `\|\|`, `!`, and time comparisons. | All fields on one command line. A menu-driven query builder. |
| Commands are verbs (`create`, `search`, `modify`, `print`, `delete`, `save`, `load`, …). On a terminal, single keys such as `c`, `/`, `w`, `W`, and `o` are shortcuts for the same verbs. | The verbs map one-to-one onto Appendix B, so the SRS, the user manual, and the screen name one list. | Numbered menus. A separate key-only command language. |
| On a terminal, the load and save-as prompts open a folder browser listing folders and `.pim` files. `/` or Tab switches to a typed path. | Users expect to pick a location, and a bare `path:` field hid how to open a file. The chosen path goes to the same handler as a typed one, so the `.pim` rule, the overwrite question, and unsaved-changes handling stay in one place. | A Finder dialog through `osascript`, or tkinter's file dialog: both are GUI windows. |

## 5.5 Testing

| Decision | Why | Rejected |
|------------------------------------------|------------------------------------------|----------------------------|
| `unittest` in three layers: unit, integration, and end-to-end. Model unit tests cover 100 % of `model/` lines. A `hooks/pre-commit` script refuses a commit unless all three layers pass. | The brief grades the model's unit tests. Integration tests and scripted sessions through `Terminal.run()` catch breaks between packages. `coverage_report.py` measures lines with the standard `trace` module, so everything stays in the standard library. | pytest and `coverage.py` (third-party). Testing the model only. |

# 6. Design quality

**Modularity.**

- Each package has one reason to change: the screen (`view`), the command flow (`controller`), or the rules and data (`model`).
- `model` has a small public interface (`PIM` plus the criterion constructors) and hides the JSON codec and the matching logic behind it.
- 100 % of `model` lines are covered by unit tests that never touch the View.

**Efficiency.**

- Search, the alarm check, and save and load are each linear in the number of PIRs.
- With 10,000 PIRs they take 2 ms, 2 ms, 44 ms, and 24 ms on the development Mac (SRS NFR-7).
- The View redraws only when its screen snapshot changes, so the 500 ms tick does not cause flicker.

**Extendibility.**

- *A new criterion* is a new `Criterion` subclass plus one parser branch.
- *A new PIR type* is a `PIR` subclass with its `FIELDS`, plus its registrations: the type name in `TYPE_NAMES` and `pir_class`, one branch in `pir_from_json`, one `PIM.create_*` method, and one entry in the controller's `_CREATE` table. The View's prompts are generated from `FIELDS`, so the View does not change.
- *A new front end* can reuse `App` unchanged.

**Justifiability.** Section 2.1 explains why the system uses MVC, and Section 5 gives the reason and the rejected alternatives for every other choice that is hard to reverse.
