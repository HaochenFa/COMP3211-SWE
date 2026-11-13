"""view.Terminal: command dispatch, wizards, layout, dismiss. App is faked."""

from __future__ import annotations

import io
import os
import unittest
from datetime import datetime

from model import Event, Note, RelativeAlarm
from model.pir import HKT, parse_datetime
from view.terminal import MENU, Terminal


class FakeDue:
    """One due alarm for the banner."""

    def __init__(self, event_id=4, alarm_index=0, status="OVERDUE"):
        self.event_id = event_id
        self.alarm_index = alarm_index
        self.status = status
        self.at = parse_datetime("2026-09-14T18:30:00+08:00")
        self.description = "lecture"

    def key(self):
        """Dismiss identity."""
        return (self.event_id, self.alarm_index)


class FakeApp:
    """App stand-in: records calls, holds list/selection/status."""

    def __init__(self):
        self.status = ""
        self.status_kind = "info"
        self.print_text = ""
        self._dirty = False
        self._bound = None
        self._result = []
        self._selected = None
        self._criterion = False
        self._criterion_line = None
        self._due = []
        self.calls = []
        self.save_ok = True
        self.load_ok = True
        self.overwrite = False
        self.created = None
        self.modified = None
        self.save_raises = None

    def set_status(self, text, kind="info"):
        self.status = text
        self.status_kind = kind

    def bound_path(self):
        return self._bound

    def is_dirty(self) -> bool:
        return self._dirty

    def save_target(self, path) -> str:
        text = str(path)
        return text if text.endswith(".pim") else text + ".pim"

    def would_overwrite(self, path) -> bool:
        return self.overwrite

    def clear_print(self):
        self.print_text = ""

    def current_result(self):
        return list(self._result)

    def selected(self):
        return self._selected

    def selected_id(self):
        return None if self._selected is None else self._selected.id

    def has_criterion(self) -> bool:
        return self._criterion

    def criterion_line(self):
        return self._criterion_line

    def due_alarms(self, now):
        return list(self._due)

    def create(self, type_name, fields):
        self.calls.append(("create", type_name, fields))
        self.status = f"Created {type_name} Id 1"
        return self.created

    def modify(self, fields):
        self.calls.append(("modify", fields))
        self.status = "Modified"
        if self.modified is not None:
            return self.modified
        return self._selected

    def delete_selected(self):
        self.calls.append(("delete",))
        self.status = "Deleted"
        self._selected = None
        return True

    def search(self, line: str):
        self.calls.append(("search", line))
        self._criterion = True
        self._criterion_line = line
        self.status = "1 match(es)"
        self.status_kind = "ok"
        if self._result:
            self._selected = self._result[0]
        return True

    def clear_search(self):
        self.calls.append(("clear",))
        self._criterion = False
        self._criterion_line = None
        self.status = "Search cleared"
        self.status_kind = "info"

    def select_row(self, number):
        self.calls.append(("row", number))
        try:
            index = int(number)
        except (TypeError, ValueError):
            return
        if 1 <= index <= len(self._result):
            self._selected = self._result[index - 1]

    def select_id(self, pir_id):
        self.calls.append(("id", pir_id))

    def print_selected(self):
        self.print_text = "one"
        self.status = "Printed Id 1"
        return self.print_text

    def print_all(self):
        self.print_text = "all"
        self.status = "Printed 0 PIR(s) in Current Result"
        return self.print_text

    def save(self, path=None):
        if self.save_raises:
            raise self.save_raises
        self.calls.append(("save", path))
        if not self.save_ok:
            self.status = "save failed"
            return False
        self._dirty = False
        if path:
            self._bound = str(path)
        self.status = f"Saved {self._bound}"
        return True

    def load(self, path, force=False):
        self.calls.append(("load", path, force))
        if not self.load_ok:
            self.status = "load failed"
            return False
        self._dirty = False
        self._bound = str(path)
        self.status = f"Loaded {path}"
        return True


def make_terminal(app=None, now=None, tty=False):
    """Terminal bound to `app` (or a new FakeApp) writing to StringIO."""
    if app is None:
        app = FakeApp()
    stdout = TtyBuffer() if tty else io.StringIO()
    term = Terminal(app, stdin=io.StringIO(), stdout=stdout, now=now)
    return app, term, stdout


class TtyBuffer(io.StringIO):
    """StringIO that reports as a TTY so render uses ANSI clear."""

    def isatty(self) -> bool:
        return True


def feed(term: Terminal, *lines: str) -> None:
    """Push completed lines through the View without the event loop."""
    for line in lines:
        term._handle_line(line)


class CommandDispatchTests(unittest.TestCase):
    def test_blank_line_is_ignored(self):
        """An empty or whitespace-only line produces no App call and no status."""
        app, term, _out = make_terminal()
        feed(term, "", "   ")
        self.assertEqual(app.calls, [])
        self.assertEqual(app.status, "")

    def test_help_clear_print_and_aliases(self):
        """`help`, `clear`, `print`/`print all`, row and `id` shortcuts, and quit aliases `q`/`exit` all dispatch."""
        app, term, _out = make_terminal()
        feed(term, "help")
        self.assertIn("create", app.status)
        feed(term, "clear")
        self.assertEqual(app.calls[-1], ("clear",))
        feed(term, "print")
        self.assertEqual(app.print_text, "one")
        feed(term, "print all")
        self.assertEqual(app.print_text, "all")
        feed(term, "1")
        self.assertEqual(app.calls[-1], ("row", "1"))
        feed(term, "id 4")
        self.assertEqual(app.calls[-1], ("id", "4"))
        app._dirty = False
        term._running = True
        feed(term, "q")
        self.assertFalse(term._running)
        self.assertNotEqual(app.status, "unknown command: q")
        _, term2, _ = make_terminal()
        term2._running = True
        feed(term2, "exit")
        self.assertFalse(term2._running)

    def test_unknown_command_and_non_print_clears_print_text(self):
        """A non-print command clears the print buffer; an unrecognized command sets "unknown command"."""
        app, term, _out = make_terminal()
        app.print_text = "keep"
        feed(term, "print")
        self.assertEqual(app.print_text, "one")
        feed(term, "help")
        self.assertEqual(app.print_text, "")
        feed(term, "explode")
        self.assertEqual(app.status, "unknown command: explode")

    def test_search_inline_or_prompted(self):
        """`search <criterion>` runs immediately; bare `search` prompts for the criterion line."""
        app, term, _out = make_terminal()
        feed(term, "search type = note")
        self.assertEqual(app.calls[-1], ("search", "type = note"))
        feed(term, "search")
        self.assertEqual(term._prompt_label(), "criterion: ")
        feed(term, "type = task")
        self.assertEqual(app.calls[-1], ("search", "type = task"))


class CreateModifyWizardTests(unittest.TestCase):
    def test_create_prompts_for_type_then_fields(self):
        """Bare `create` prompts for a type, then for its fields, before calling `App.create`."""
        app, term, _out = make_terminal()
        feed(term, "create")
        self.assertIn("type", term._prompt_label())
        feed(term, "note", "Shopping: Milk")
        self.assertEqual(app.calls[-1], ("create", "note", {"text": "Shopping: Milk"}))

    def test_create_unknown_type_sets_status(self):
        """`create series` sets "unknown PIR type: series" without calling `App.create`."""
        app, term, _out = make_terminal()
        feed(term, "create series")
        self.assertEqual(app.status, "unknown PIR type: series")

    def test_create_task_skips_empty_optional_deadline(self):
        """An empty optional `deadline` answer during `create task` is omitted from the submitted fields."""
        app, term, _out = make_terminal()
        feed(term, "create task", "Inbox", "")
        kind, type_name, fields = app.calls[-1]
        self.assertEqual((kind, type_name), ("create", "task"))
        self.assertEqual(fields, {"description": "Inbox"})

    def test_modify_without_selection_fails(self):
        """`modify` with no Selection sets "no PIR selected" without prompting for fields."""
        app, term, _out = make_terminal()
        feed(term, "modify")
        self.assertEqual(app.status, "no PIR selected")

    def test_modify_empty_enter_omits_field(self):
        """Pressing Enter on a `modify` field prompt omits that field from the submitted changes."""
        app, term, _out = make_terminal()
        app._selected = Note(1, "old")
        feed(term, "modify", "")
        self.assertEqual(app.calls[-1], ("modify", {}))

    def test_delete_yes_and_no(self):
        """`delete` cancels on "n" and calls `App.delete_selected` on "y"."""
        app, term, _out = make_terminal()
        app._selected = Note(1, "x")
        feed(term, "delete", "n")
        self.assertEqual(app.status, "delete cancelled")
        self.assertNotIn(("delete",), app.calls)
        feed(term, "delete", "y")
        self.assertIn(("delete",), app.calls)


class AlarmWizardTests(unittest.TestCase):
    def test_create_event_with_relative_and_absolute_alarms(self):
        """Creating an Event can add both a relative and an absolute alarm before answering "n" to stop."""
        app, term, _out = make_terminal()
        feed(
            term,
            "create event",
            "lecture",
            "2026-09-14T18:30:00+08:00",
            "y",
            "r",
            "1",
            "day",
            "y",
            "a",
            "2026-09-13T09:00:00+08:00",
            "n",
        )
        _kind, type_name, fields = app.calls[-1]
        self.assertEqual(type_name, "event")
        self.assertEqual(len(fields["alarms"]), 2)
        self.assertEqual(fields["alarms"][0].amount, 1)

    def test_invalid_alarm_kind_sets_status(self):
        """An alarm kind that is neither "relative" nor "absolute" sets "enter relative or absolute"."""
        app, term, _out = make_terminal()
        feed(
            term,
            "create event",
            "lecture",
            "2026-09-14T18:30:00+08:00",
            "y",
            "nope",
        )
        self.assertEqual(app.status, "enter relative or absolute")

    def test_alarm_kind_amount_and_unit_errors_retry(self):
        """Invalid alarm kind, non-numeric amount, negative amount, and unknown unit each retry the prompt."""
        app, term, _out = make_terminal()
        feed(
            term,
            "create event",
            "lecture",
            "2026-09-14T18:30:00+08:00",
            "y",
            "nope",
            "relative",
            "x",
            "relative",
            "-1",
            "relative",
            "1",
            "fortnight",
            "relative",
            "0",
            "n",
        )
        fields = app.calls[-1][2]
        self.assertEqual(len(fields["alarms"]), 1)
        self.assertEqual(fields["alarms"][0].amount, 0)

    def test_replace_alarms_yes_no_and_invalid(self):
        """The "replace alarms?" prompt retries on an invalid answer; only "y" adds an `alarms` field."""
        app, term, _out = make_terminal()
        app._selected = Event(4, "lecture", "2026-09-14T18:30:00+08:00", [RelativeAlarm(0, "minute")])
        app.modified = app._selected
        feed(term, "modify", "", "", "maybe")
        self.assertEqual(app.status, "enter y or n")
        feed(term, "n")
        self.assertEqual(app.calls[-1][0], "modify")
        feed(term, "modify", "", "", "y", "n")
        self.assertIn("alarms", app.calls[-1][1])

    def test_modify_alarms_forgets_dismissed_for_that_id(self):
        """Replacing an Event's alarms during `modify` clears dismissed-alarm memory for that Id only."""
        app, term, _out = make_terminal()
        event = Event(4, "lecture", "2026-09-14T18:30:00+08:00")
        app._selected = event
        replacement = Event(4, "lecture", "2026-09-14T18:30:00+08:00", [RelativeAlarm(0, "minute")])
        app.modified = replacement
        term.dismissed = {(4, 0), (9, 0)}
        feed(term, "modify", "", "", "y", "n")
        self.assertEqual(term.dismissed, {(9, 0)})

    def test_dismissal_changes_only_when_the_alarm_changes(self):
        """Reentering the same alarm keeps it dismissed; moving its effective time resets it."""
        from controller.app import App
        from model import PIM

        pim = PIM()
        event = pim.create_event("lecture", "2026-09-14 18:30", [RelativeAlarm(0, "minute")])
        app, term, _out = make_terminal(app=App(pim), now=parse_datetime("2026-09-14 19:00"))
        app.select_id(event.id)
        feed(term, "dismiss", "modify", "New description", "", "y", "y", "relative", "0", "n")
        self.assertEqual(term.visible_due(), [])
        feed(term, "modify", "", "2026-09-14 18:45", "n")
        self.assertEqual([item.at for item in term.visible_due()], [parse_datetime("2026-09-14 18:45")])


class BrowserPromptTests(unittest.TestCase):
    """Load and save-as prompts carry a folder browser; the handler still takes a path string."""

    def setUp(self):
        import tempfile

        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = os.path.realpath(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_load_browser_starts_in_the_working_directory_when_untitled(self):
        """`o` with no Bound File browses the folder the PIM was started from."""
        _app, term, _out = make_terminal()
        term.apply_accelerator("load")
        browser = term.current_browser()
        self.assertEqual(browser.mode, "load")
        self.assertEqual(str(browser.cwd), os.getcwd())

    def test_browser_starts_in_the_bound_file_folder(self):
        """With a Bound File, `W` browses that file's folder."""
        app, term, _out = make_terminal()
        app._bound = os.path.join(self.dir, "work.pim")
        term.apply_accelerator("save_as")
        browser = term.current_browser()
        self.assertEqual(browser.mode, "save")
        self.assertEqual(str(browser.cwd), self.dir)

    def test_missing_bound_folder_falls_back_to_working_directory(self):
        """A Bound File whose folder no longer exists starts the browser in the working directory."""
        app, term, _out = make_terminal()
        app._bound = os.path.join(self.dir, "gone", "work.pim")
        term.apply_accelerator("save_as")
        self.assertEqual(str(term.current_browser().cwd), os.getcwd())

    def test_untitled_save_and_dirty_quit_save_both_browse(self):
        """`w` when untitled and "save" in the dirty-quit chooser both open the save browser."""
        _app, term, _out = make_terminal()
        term.apply_accelerator("save")
        self.assertEqual(term.current_browser().mode, "save")
        term.cancel_prompt()
        app, term, _out = make_terminal()
        app._dirty = True
        feed(term, "quit", "save")
        self.assertEqual(term.current_browser().mode, "save")

    def test_load_with_a_path_argument_never_opens_the_browser(self):
        """`load <path>` loads directly; the browser is only for the bare prompt."""
        app, term, _out = make_terminal()
        feed(term, "load /tmp/x.pim")
        self.assertIsNone(term.current_browser())
        self.assertEqual(app.calls[-1], ("load", "/tmp/x.pim", False))

    def test_type_path_instead_keeps_the_prompt_and_drops_the_browser(self):
        """Switching to typing keeps the same handler: the typed path is loaded."""
        app, term, _out = make_terminal()
        term.apply_accelerator("load")
        term.type_path_instead()
        self.assertIsNone(term.current_browser())
        self.assertEqual(term._prompt_label(), "load path: ")
        feed(term, "/tmp/typed.pim")
        self.assertEqual(app.calls[-1], ("load", "/tmp/typed.pim", False))

    def test_browser_helpers_are_none_without_a_prompt(self):
        """No prompt: no browser, and type_path_instead is harmless."""
        _app, term, _out = make_terminal()
        self.assertIsNone(term.current_browser())
        term.type_path_instead()
        self.assertEqual(term._prompts, [])


class SaveLoadQuitTests(unittest.TestCase):
    def test_save_asks_path_when_untitled(self):
        """Bare `save` with no Bound File prompts "save as path: " and then saves the typed path."""
        app, term, _out = make_terminal()
        feed(term, "save")
        self.assertEqual(term._prompt_label(), "save as path: ")
        feed(term, "/tmp/demo")
        self.assertEqual(app.calls[-1], ("save", "/tmp/demo"))

    def test_save_as_empty_path_and_overwrite_cancel(self):
        """`save as` requires a non-empty path, and overwriting an existing file needs "y" confirmation."""
        app, term, _out = make_terminal()
        feed(term, "save as")
        feed(term, "")
        self.assertEqual(app.status, "path is required")
        app.overwrite = True
        feed(term, "save as /tmp/taken.pim", "n")
        self.assertEqual(app.status, "save as cancelled")
        feed(term, "save as /tmp/taken.pim", "y")
        self.assertEqual(app.calls[-1], ("save", "/tmp/taken.pim"))

    def test_load_empty_path_and_dirty_cancel(self):
        """`load` requires a non-empty path, and answering "cancel" on a dirty session cancels the load."""
        app, term, _out = make_terminal()
        feed(term, "load")
        feed(term, "")
        self.assertEqual(app.status, "path is required")
        app._dirty = True
        feed(term, "load /tmp/x.pim", "cancel")
        self.assertEqual(app.status, "load cancelled")

    def test_dirty_quit_save_discard_and_invalid_choice(self):
        """Dirty `quit` retries on an invalid choice; "cancel" keeps running; "discard" quits unsaved."""
        app, term, _out = make_terminal()
        app._dirty = True
        term._running = True
        feed(term, "quit", "maybe")
        self.assertEqual(app.status, "enter save, discard, or cancel")
        feed(term, "cancel")
        self.assertEqual(app.status, "quit cancelled")
        self.assertTrue(term._running)
        feed(term, "quit", "discard")
        self.assertFalse(term._running)

    def test_dirty_quit_save_with_bound_file(self):
        """Dirty `quit` answered "s" saves to the existing Bound File and then quits."""
        app, term, _out = make_terminal()
        app._dirty = True
        app._bound = "/tmp/x.pim"
        term._running = True
        feed(term, "quit", "s")
        self.assertFalse(term._running)
        self.assertEqual(app.calls[-1], ("save", None))

    def test_eof_during_wizard_cancels_command(self):
        """EOF during a `create` wizard cancels the command, clears prompts, and stops the session."""
        app, term, _out = make_terminal()
        term._running = True
        feed(term, "create")
        term._handle_eof()
        self.assertEqual(app.status, "command cancelled")
        self.assertFalse(term._running)
        self.assertEqual(term._prompts, [])

    def test_interrupt_on_clean_session_stops(self):
        """Ctrl-C (interrupt) on a clean session stops the Terminal immediately."""
        app, term, _out = make_terminal()
        term._running = True
        term._handle_interrupt()
        self.assertFalse(term._running)

    def test_eof_on_dirty_non_tty_stops(self):
        """FR-37/NFR-5: redirected input that ends while the dirty-quit prompt is open stops
        the Terminal and prints "input ended: unsaved changes were not saved" before it stops."""
        app, term, out = make_terminal()
        app._dirty = True
        term._running = True
        feed(term, "quit")
        term._handle_eof()
        self.assertFalse(term._running)
        self.assertEqual(app.status, "input ended: unsaved changes were not saved")
        self.assertIn("input ended: unsaved changes were not saved", out.getvalue())

    def test_load_failed_does_not_clear_dismissed(self):
        """A failed `load` leaves dismissed alarms untouched; a successful `load` clears them."""
        app, term, _out = make_terminal()
        term.dismissed.add((1, 0))
        app.load_ok = False
        feed(term, "load /tmp/x.pim")
        self.assertEqual(term.dismissed, {(1, 0)})
        app.load_ok = True
        feed(term, "load /tmp/x.pim")
        self.assertEqual(term.dismissed, set())


class UnexpectedErrorTests(unittest.TestCase):
    """A non-domain exception fails one command; the line loop keeps running."""

    def test_line_loop_reports_unexpected_error_and_continues(self):
        """RuntimeError from App.save becomes `command failed`; the next command still runs."""
        app = FakeApp()
        app.save_raises = RuntimeError("boom")
        stdout = io.StringIO()
        term = Terminal(app, stdin=io.StringIO("save as /tmp/x.pim\nhelp\nquit\n"), stdout=stdout)
        term.run()
        out = stdout.getvalue()
        self.assertIn("command failed", out)
        self.assertNotIn("Traceback", out)
        self.assertNotIn("boom", out)
        self.assertFalse(term._running)


class LayoutAndPaintTests(unittest.TestCase):
    def test_layout_empty_untitled_and_menu(self):
        """`_layout` for an empty, untitled session shows placeholder rows and the menu."""
        _app, term, _out = make_terminal()
        lines = term._layout()
        self.assertTrue(lines[0].startswith("PIM  untitled"))
        self.assertIn("ALARMS", lines)
        self.assertIn("  (none)", lines)
        self.assertIn("    (empty)", lines)
        self.assertIn("  (no selection)", lines)
        self.assertIn(MENU, lines)

    def test_layout_truncates_long_name_and_marks_selection(self):
        """`_layout` truncates a long name, marks a dirty Bound File with `*`, and shows the selected row."""
        app, term, _out = make_terminal()
        note = Note(1, "abcdefghijklmnopqrstuvwxyz extra")
        app._result = [note]
        app._selected = note
        app._dirty = True
        app._bound = "/tmp/demo.pim"
        app.print_text = "printed"
        app._due = [FakeDue()]
        lines = term._layout()
        joined = "\n".join(lines)
        self.assertIn("PIM  /tmp/demo.pim*", joined)
        self.assertIn("OVERDUE", joined)
        self.assertIn("(dismiss)", joined)
        self.assertIn("abc", joined)
        self.assertIn("...", joined)
        self.assertIn(">   1    1  note", joined)
        self.assertIn("PRINT", joined)

    def test_dismiss_first_due_alarm(self):
        """`dismiss` dismisses the first due alarm and reports "no alarm to dismiss" once none remain."""
        app, term, _out = make_terminal()
        app._due = [FakeDue()]
        feed(term, "dismiss")
        self.assertEqual(term.dismissed, {(4, 0)})
        self.assertIn("Dismissed alarm on Id 4", app.status)
        feed(term, "dismiss")
        self.assertEqual(app.status, "no alarm to dismiss")

    def test_paint_skips_unchanged_snapshot(self):
        """`_paint` writes when the snapshot changes and writes nothing when called again unchanged."""
        _app, term, out = make_terminal()
        term.render()
        before = out.getvalue()
        self.assertTrue(term._paint(force=False))
        after_first = out.getvalue()
        self.assertGreater(len(after_first), len(before))
        self.assertFalse(term._paint(force=False))
        self.assertEqual(out.getvalue(), after_first)

    def test_tty_render_writes_ansi_clear(self):
        """On a TTY, `render` writes the ANSI clear-screen and home sequence before the layout."""
        _app, term, out = make_terminal(tty=True)
        term.render()
        self.assertIn("\033[2J\033[H", out.getvalue())

    def test_now_datetime_callable_and_wall_clock(self):
        """`_now_dt` accepts a fixed datetime or a zero-arg callable, else falls back to the wall clock in HKT."""
        instant = parse_datetime("2026-09-14T18:30:00+08:00")
        _app, term, _out = make_terminal(now=instant)
        self.assertEqual(term._now_dt(), instant)
        _app, term2, _out = make_terminal(now=lambda: instant)
        self.assertEqual(term2._now_dt(), instant)
        _app, term3, _out = make_terminal()
        self.assertIsInstance(term3._now_dt(), datetime)
        self.assertEqual(term3._now_dt().tzinfo, HKT)

    def test_interrupt_during_dirty_prompt_asks_again(self):
        """Ctrl-C while the dirty-quit prompt is open re-asks save/discard/cancel instead of quitting."""
        app, term, _out = make_terminal()
        app._dirty = True
        feed(term, "quit")
        term._handle_interrupt()
        self.assertEqual(app.status, "enter save, discard, or cancel")


class AcceleratorAndCursesGateTests(unittest.TestCase):
    def test_arrows_move_selection_in_current_result(self):
        """`select_down`/`select_up`/`select_first`/`select_last` move the Selection through the Current Result."""
        app, term, _out = make_terminal()
        app._result = [Note(1, "a"), Note(2, "b"), Note(3, "c")]
        term.apply_accelerator("select_down")
        self.assertEqual(app.calls[-1], ("row", "1"))
        self.assertEqual(app.selected_id(), 1)
        term.apply_accelerator("select_down")
        self.assertEqual(app.selected_id(), 2)
        term.apply_accelerator("select_up")
        self.assertEqual(app.selected_id(), 1)
        term.apply_accelerator("select_last")
        self.assertEqual(app.selected_id(), 3)
        term.apply_accelerator("select_first")
        self.assertEqual(app.selected_id(), 1)

    def test_empty_result_move_sets_status(self):
        """Moving the selection when the Current Result is empty sets "Current Result is empty"."""
        app, term, _out = make_terminal()
        term.apply_accelerator("select_down")
        self.assertEqual(app.status, "Current Result is empty")

    def test_save_accelerator_asks_path_when_untitled(self):
        """The `save` accelerator with no Bound File prompts for "save as path: " instead of saving."""
        app, term, _out = make_terminal()
        term.apply_accelerator("save")
        self.assertEqual(term._prompt_label(), "save as path: ")
        self.assertNotIn(("save", None), app.calls)

    def test_save_as_accelerator_asks_path_even_with_bound_file(self):
        """`W` asks for a new path instead of rewriting the Bound File."""
        app, term, _out = make_terminal()
        app._bound = "/tmp/old.pim"
        term.apply_accelerator("save_as")
        self.assertEqual(term._prompt_label(), "save as path: ")
        self.assertEqual(app.calls, [])
        feed(term, "/tmp/new")
        self.assertEqual(app.calls[-1], ("save", "/tmp/new"))

    def test_load_accelerator_asks_path_then_loads(self):
        """`o` asks "load path: " and loads the typed path when clean."""
        app, term, _out = make_terminal()
        term.apply_accelerator("load")
        self.assertEqual(term._prompt_label(), "load path: ")
        feed(term, "~/work.pim")
        self.assertEqual(app.calls[-1], ("load", "~/work.pim", False))

    def test_load_accelerator_when_dirty_asks_save_discard_cancel(self):
        """`o` with unsaved changes asks save/discard/cancel before loading; discard forces."""
        app, term, _out = make_terminal()
        app._dirty = True
        term.apply_accelerator("load")
        feed(term, "/tmp/work.pim")
        self.assertIn("unsaved changes", term._prompt_label())
        self.assertNotIn("load", [call[0] for call in app.calls])
        feed(term, "discard")
        self.assertEqual(app.calls[-1], ("load", "/tmp/work.pim", True))

    def test_create_and_search_accelerators_open_prompts(self):
        """`create` and `search` accelerators open their prompts, and `cancel_prompt` cancels a pending one."""
        app, term, _out = make_terminal()
        term.apply_accelerator("create")
        self.assertIn("type", term._prompt_label())
        term.cancel_prompt()
        self.assertEqual(app.status, "command cancelled")
        self.assertEqual(term._prompts, [])
        term.apply_accelerator("search")
        self.assertEqual(term._prompt_label(), "criterion: ")

    def test_slash_verbs_still_work_after_cancel(self):
        """After the `search` accelerator opens a prompt, a typed criterion line still runs the search."""
        app, term, _out = make_terminal()
        term.apply_accelerator("search")
        feed(term, "type = note")
        self.assertEqual(app.calls[-1], ("search", "type = note"))

    def test_use_curses_false_when_not_a_tty(self):
        """`_use_curses` is false when stdin and stdout are not TTYs."""
        _app, term, _out = make_terminal()
        self.assertFalse(term._use_curses())

    def test_use_curses_false_when_env_disables_it(self):
        """`_use_curses` is false when `PIM_NO_CURSES` is set, even though stdin/stdout report as a TTY."""
        import os

        class Tty:
            def isatty(self):
                return True

        app = FakeApp()
        term = Terminal(app, stdin=Tty(), stdout=Tty())
        previous = os.environ.get("PIM_NO_CURSES")
        os.environ["PIM_NO_CURSES"] = "1"
        try:
            self.assertFalse(term._use_curses())
        finally:
            if previous is None:
                os.environ.pop("PIM_NO_CURSES", None)
            else:
                os.environ["PIM_NO_CURSES"] = previous

    def test_esc_on_dirty_prompt_does_not_drop_changes(self):
        """Esc on the dirty-quit prompt keeps the prompt open and the session running, not discarded."""
        app, term, _out = make_terminal()
        app._dirty = True
        term._running = True
        feed(term, "quit")
        term.cancel_prompt()
        self.assertEqual(app.status, "enter save, discard, or cancel")
        self.assertTrue(term._prompts)
        self.assertTrue(term._running)
