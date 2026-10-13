"""curses UI helpers that do not need a real TTY."""

import curses
import unittest
from unittest import mock

from view.curses_ui import CursesUI, title_bar_text
from view.keys import CREATE, SEARCH
from tests.unit.test_terminal import make_terminal
from model import Note


class CursesHelperTests(unittest.TestCase):
    def test_character_actions_without_a_screen(self):
        """`_action` maps `c` to `CREATE`, `/` to `SEARCH`, and an unmapped key to None."""
        _app, term, _out = make_terminal()
        ui = CursesUI(term, object())
        self.assertEqual(ui._action("c"), CREATE)
        self.assertEqual(ui._action("/"), SEARCH)
        self.assertIsNone(ui._action("s"))

    def test_type_selector_letter_submits_note(self):
        """Pressing `n` on the create type selector submits `note` and opens the `text` prompt."""
        app, term, _out = make_terminal()
        ui = CursesUI(term, object())
        term.apply_accelerator("create")
        ui._sync_chooser()
        self.assertTrue(ui._handle_chooser_key("n"))
        self.assertEqual(app.calls, [])
        self.assertIn("text", term._prompt_label())
        self.assertIsNone(term.current_chooser())

    def test_type_selector_arrows_then_enter(self):
        """Two right-arrow moves highlight `event`; Enter submits it and opens the `description` prompt."""
        app, term, _out = make_terminal()
        app._result = []
        ui = CursesUI(term, object())
        term.apply_accelerator("create")
        ui._sync_chooser()
        ui._handle_chooser_key("l")
        ui._handle_chooser_key("l")
        chooser = term.current_chooser()
        self.assertEqual(chooser.value_at(ui.choice_index), "event")
        ui._handle_chooser_key("\n")
        self.assertIn("description", term._prompt_label())

    def test_delete_selector_enter_on_default_cancels(self):
        """Enter on the delete confirmation's default option cancels without calling `delete`."""
        app, term, _out = make_terminal()
        app._selected = Note(1, "x")
        ui = CursesUI(term, object())
        term.apply_accelerator("delete")
        ui._sync_chooser()
        ui._handle_chooser_key("\n")
        self.assertEqual(app.status, "delete cancelled")
        self.assertNotIn(("delete",), app.calls)

    def test_escape_clears_typed_command_not_running_flag(self):
        """Esc on a typed command clears the buffer and status but leaves the run loop's `_running` flag set."""
        app, term, _out = make_terminal()
        term._running = True
        ui = CursesUI(term, object())
        ui.buffer = "create"
        ui.cursor = 6
        ui.raw_command = True
        ui._escape()
        self.assertEqual(ui.buffer, "")
        self.assertFalse(ui.raw_command)
        self.assertEqual(app.status, "command cancelled")
        self.assertTrue(term._running)

    def test_search_syntax_error_keeps_the_typed_line(self):
        """A search syntax error re-opens the `criterion:` prompt with the invalid line still typed."""
        app, term, _out = make_terminal()

        def bad_search(line):
            app.calls.append(("search", line))
            app.set_status("search syntax error: type =", "err")
            return False

        app.search = bad_search
        term.ask("criterion: ", lambda value: app.search(value))
        ui = CursesUI(term, object())
        ui.buffer = "type ="
        ui.cursor = 6
        ui._submit()
        self.assertEqual(ui.buffer, "type =")
        self.assertIn("criterion", term._prompt_label())
        self.assertEqual(app.status_kind, "err")

    def test_idle_escape_clears_an_active_search(self):
        """With no prompt open, Esc during an active search calls `clear` and drops the criterion."""
        app, term, _out = make_terminal()
        app._criterion = True
        app._criterion_line = "type = note"
        ui = CursesUI(term, object())
        ui._escape()
        self.assertIn(("clear",), app.calls)
        self.assertFalse(app.has_criterion())

    def test_idle_escape_without_search_does_not_quit(self):
        """With no prompt and no active search, Esc leaves the run loop running and calls no command."""
        app, term, _out = make_terminal()
        term._running = True
        ui = CursesUI(term, object())
        ui._escape()
        self.assertTrue(term._running)
        self.assertNotIn(("clear",), app.calls)

    def test_safe_turns_unexpected_error_into_status(self):
        """CursesUI._safe reports a RuntimeError as `command failed` instead of raising."""
        app, term, _out = make_terminal()
        ui = CursesUI(term, object())

        def boom():
            raise RuntimeError("boom")

        ui._safe(boom)
        self.assertEqual(app.status, "command failed")
        self.assertEqual(app.status_kind, "err")


class FakeScreen:
    """Just enough of a curses window for the snapshot and composer height."""

    def getmaxyx(self):
        return (30, 100)


class BrowserKeyTests(unittest.TestCase):
    """Folder browser keys in the full-screen UI: every answer reaches the prompt as a path."""

    def setUp(self):
        import os
        import tempfile

        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = os.path.realpath(self.tmpdir.name)
        os.mkdir(os.path.join(self.dir, "courses"))
        with open(os.path.join(self.dir, "courses", "comp.pim"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        with open(os.path.join(self.dir, "work.pim"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        self.app, self.term, _out = make_terminal()
        self.app._bound = os.path.join(self.dir, "work.pim")
        self.ui = CursesUI(self.term, FakeScreen())

    def tearDown(self):
        self.tmpdir.cleanup()

    def path(self, *parts):
        import os

        return os.path.join(self.dir, *parts)

    def labels(self):
        return [entry.label() for entry in self.term.current_browser().entries]

    def test_enter_opens_a_folder_then_loads_a_pim_file(self):
        """`o`, down to `courses/`, Enter, down to `comp.pim`, Enter → load that absolute path."""
        self.term.apply_accelerator("load")
        self.assertEqual(self.labels(), ["../", "courses/", "work.pim"])
        self.ui._handle_browser_key("j")
        self.ui._handle_browser_key("\n")
        self.assertEqual(self.labels(), ["../", "comp.pim"])
        self.ui._handle_browser_key(curses.KEY_DOWN)
        self.ui._handle_browser_key("\n")
        self.assertEqual(self.app.calls[-1], ("load", self.path("courses", "comp.pim"), False))
        self.assertIsNone(self.term.current_browser())

    def test_backspace_and_left_go_up_right_opens(self):
        """⌫ / ← go to the parent folder; → opens the highlighted folder."""
        self.term.apply_accelerator("load")
        self.ui._handle_browser_key("j")
        self.ui._handle_browser_key(curses.KEY_RIGHT)
        self.assertEqual(str(self.term.current_browser().cwd), self.path("courses"))
        self.ui._handle_browser_key("\x7f")
        self.assertEqual(str(self.term.current_browser().cwd), self.dir)
        self.assertEqual(self.term.current_browser().current().label(), "courses/")
        self.ui._handle_browser_key("j")
        self.ui._handle_browser_key("l")
        self.assertEqual(str(self.term.current_browser().cwd), self.dir)
        self.ui._handle_browser_key(curses.KEY_LEFT)
        self.assertNotEqual(str(self.term.current_browser().cwd), self.dir)

    def test_navigation_keys_move_the_highlight(self):
        """k/j, PgUp/PgDn, Home/End, g/G move within the list and are consumed."""
        self.term.apply_accelerator("load")
        browser = self.term.current_browser()
        for key, expected in (
            ("G", 2),
            ("k", 1),
            (curses.KEY_UP, 0),
            (curses.KEY_NPAGE, 2),
            (curses.KEY_PPAGE, 0),
            (curses.KEY_END, 2),
            (curses.KEY_HOME, 0),
            ("g", 0),
        ):
            self.assertTrue(self.ui._handle_browser_key(key))
            self.assertEqual(browser.index, expected, key)
        self.assertTrue(self.ui._handle_browser_key("z"))

    def test_slash_and_tab_switch_to_the_typed_field(self):
        """`/` starts an absolute path; Tab pre-fills the current folder; the prompt stays."""
        import os

        self.term.apply_accelerator("load")
        self.ui._handle_browser_key("/")
        self.assertIsNone(self.term.current_browser())
        self.assertEqual(self.ui.buffer, "/")
        self.assertEqual(self.term._prompt_label(), "load path: ")
        self.term.cancel_prompt()
        self.term.apply_accelerator("load")
        self.ui._handle_browser_key("\t")
        self.assertEqual(self.ui.buffer, self.dir + os.sep)
        self.assertEqual(self.ui.cursor, len(self.ui.buffer))

    def test_tilde_opens_home(self):
        """`~` jumps the browser to the home folder."""
        from unittest.mock import patch

        self.term.apply_accelerator("load")
        with patch.dict("os.environ", {"HOME": self.path("courses")}):
            self.ui._handle_browser_key("~")
        self.assertEqual(str(self.term.current_browser().cwd), self.path("courses"))

    def test_save_new_file_row_types_a_name_in_this_folder(self):
        """`W`, Enter on "new file here", type a name, Enter → save as <folder>/<name>."""
        self.term.apply_accelerator("save_as")
        self.assertEqual(self.labels()[0], "+ New file in this folder…")
        self.ui._handle_browser_key("\n")
        self.assertIsNone(self.term.current_browser())
        for ch in "demo":
            self.ui._edit(ch)
        self.ui._submit()
        self.assertEqual(self.app.calls[-1], ("save", self.path("demo")))

    def test_save_on_an_existing_file_asks_to_overwrite(self):
        """Enter on an existing `.pim` in the save browser goes through the overwrite check."""
        self.app.would_overwrite = lambda path: True
        self.app.save_target = lambda path: path
        self.term.apply_accelerator("save_as")
        self.ui._handle_browser_key("G")
        self.ui._handle_browser_key("\n")
        self.assertIn("overwrite", self.term._prompt_label())

    def test_escape_cancels_the_browser_prompt(self):
        """Esc in the browser cancels the load; nothing is loaded."""
        self.term.apply_accelerator("load")
        self.assertTrue(self.ui._handle_browser_key("\x1b"))
        self.assertIsNone(self.term.current_browser())
        self.assertEqual(self.app.status, "command cancelled")
        self.assertNotIn("load", [call[0] for call in self.app.calls])

    def test_one_escape_cancels_an_unedited_prefilled_path(self):
        """After `/` or Tab, one Esc cancels the load while the pre-filled path is unchanged."""
        for key in ("/", "\t"):
            self.term.apply_accelerator("load")
            self.ui._handle_browser_key(key)
            self.ui._handle_key("\x1b")
            self.assertEqual(self.term._prompt_label(), "> ")
            self.assertEqual(self.ui.buffer, "")
            self.assertEqual(self.app.status, "command cancelled")
        self.assertNotIn("load", [call[0] for call in self.app.calls])

    def test_escape_after_editing_the_path_clears_it_first(self):
        """After the typed path is edited, the first Esc clears it and keeps the prompt; the second cancels."""
        self.term.apply_accelerator("load")
        self.ui._handle_browser_key("/")
        self.ui._handle_key("t")
        self.ui._handle_key("\x1b")
        self.assertEqual(self.ui.buffer, "")
        self.assertEqual(self.term._prompt_label(), "load path: ")
        self.ui._handle_key("\x1b")
        self.assertEqual(self.term._prompt_label(), "> ")
        self.assertNotIn("load", [call[0] for call in self.app.calls])

    def test_browser_key_without_a_browser_is_not_consumed(self):
        """With no browser open, the handler leaves the key to the rest of the UI."""
        self.assertFalse(self.ui._handle_browser_key("j"))

    def test_handle_key_routes_to_the_browser(self):
        """The main key handler sends keys to the browser before the text field."""
        self.term.apply_accelerator("load")
        self.ui._handle_key("j")
        self.assertEqual(self.term.current_browser().index, 1)
        self.assertEqual(self.ui.buffer, "")

    def test_snapshot_and_composer_follow_the_browser(self):
        """A browser move changes the redraw snapshot; the composer is three rows."""
        self.term.apply_accelerator("load")
        before = self.ui._snapshot()
        self.ui._handle_browser_key("j")
        self.assertNotEqual(before, self.ui._snapshot())
        self.assertEqual(self.ui._composer_h(), 3)

    def test_ctrl_u_clears_to_the_start_of_the_field(self):
        """Ctrl-U deletes everything before the caret, e.g. a pre-filled folder."""
        self.ui.buffer = "/Users/you/work"
        self.ui.cursor = 11
        self.ui._edit("\x15")
        self.assertEqual(self.ui.buffer, "work")
        self.assertEqual(self.ui.cursor, 0)


class GridScreen:
    """A character grid that records what the UI writes, for drawing tests."""

    def __init__(self, height=20, width=60):
        self.rows = [[" "] * width for _ in range(height)]

    def getmaxyx(self):
        return (len(self.rows), len(self.rows[0]))

    def addstr(self, y, x, text, attr=0):
        for offset, char in enumerate(text):
            if x + offset < len(self.rows[y]):
                self.rows[y][x + offset] = char

    def addch(self, y, x, char, attr=0):
        self.rows[y][x] = char

    def hline(self, y, x, char, count):
        for offset in range(count):
            self.rows[y][x + offset] = char

    def text(self, y):
        return "".join(self.rows[y])


class DrawingTests(unittest.TestCase):
    """Pop-ups and the title bar, drawn onto a fake screen."""

    def setUp(self):
        # ACS line-drawing names exist only after initscr(); plain characters stand in.
        patches = {"ACS_HLINE": "-", "ACS_VLINE": "|", "ACS_ULCORNER": "+", "ACS_URCORNER": "+", "ACS_LLCORNER": "+", "ACS_LRCORNER": "+"}
        for name, char in patches.items():
            patcher = mock.patch.object(curses, name, char, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        _app, term, _out = make_terminal()
        self.screen = GridScreen()
        self.ui = CursesUI(term, self.screen)

    def test_print_popup_blanks_the_panes_behind_it(self):
        """A PRINT box shorter than the text under it shows only its own lines, not the old text."""
        for row in range(20):
            self.screen.addstr(row, 0, "x" * 60)
        self.ui._box(60, 20, "PRINT", ["Id: 3"], box_w=30, box_h=5)
        inside = [self.screen.text(row)[16:44] for row in range(8, 11)]
        self.assertEqual(inside[0].strip(), "Id: 3")
        self.assertEqual(inside[1].strip(), "")
        self.assertNotIn("x", "".join(inside))

    def test_long_title_keeps_the_file_name_and_clears_the_clock(self):
        """A long bound path is trimmed from the left, so `demo.pim*` stays and the text fits its room."""
        title = "PIM  /Users/student/Documents/COMP3211/group/project/demo.pim*"
        fitted = title_bar_text(title, 30)
        self.assertTrue(fitted.startswith("PIM  ..."))
        self.assertTrue(fitted.endswith("demo.pim*"))
        self.assertLessEqual(len(fitted), 30)
        self.assertEqual(title_bar_text("PIM  untitled", 30), "PIM  untitled")
