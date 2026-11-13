"""Calendar date/time picker: HKT, 15-minute slots, ISO-like submit string."""

import unittest
from datetime import date, datetime

from controller.app import App
from model import PIM
from model.pir import HKT, parse_datetime
from view.curses_ui import CursesUI
from view.widgets import DateTimePicker, DATETIME_FORMAT
from tests.unit.test_terminal import make_terminal


def hkt(text: str) -> datetime:
    """Parse a fixture instant in Hong Kong Time."""
    return parse_datetime(text)


class DateTimePickerTests(unittest.TestCase):
    def test_value_is_what_parse_datetime_already_accepts(self):
        """A non-quarter-hour seed rounds up to the next 15-minute slot, and `value()` re-parses as HKT."""
        picker = DateTimePicker("Start", hkt("2026-09-14T18:31:00+08:00"))
        # 18:31 rounds up to 18:45
        self.assertEqual(picker.value(), "2026-09-14 18:45")
        self.assertEqual(parse_datetime(picker.value()), parse_datetime("2026-09-14T18:45:00+08:00"))

    def test_exact_quarter_hour_is_kept(self):
        """A seed already on a 15-minute boundary is not rounded."""
        picker = DateTimePicker("Start", hkt("2026-09-14T18:30:00+08:00"))
        self.assertEqual((picker.hour, picker.minute), (18, 30))

    def test_existing_instant_seeds_the_grid(self):
        """An `initial` instant, not `now`, seeds the picker's day and time (a modify pre-fill)."""
        initial = hkt("2026-11-20T20:00:00+08:00")
        picker = DateTimePicker("Deadline", hkt("2026-09-11T09:00:00+08:00"), initial=initial)
        self.assertEqual(picker.day, date(2026, 11, 20))
        self.assertEqual(picker.value(), "2026-11-20 20:00")

    def test_week_starts_monday(self):
        """The first day of each grid week is a Monday (ISO / Hong Kong convention)."""
        picker = DateTimePicker("Start", hkt("2026-09-14T18:30:00+08:00"))
        week = picker.weeks()[0]
        self.assertEqual(week[0].weekday(), 0)

    def test_move_month_clamps_day(self):
        """Moving from 31 January to February clamps the day to 28, the shorter month's last day."""
        picker = DateTimePicker("Start", hkt("2026-01-31T10:00:00+08:00"), initial=hkt("2026-01-31T10:00:00+08:00"))
        picker.move_month(1)
        self.assertEqual(picker.day, date(2026, 2, 28))

    def test_december_9999_has_blank_spill_cells_and_stays_in_range(self):
        """The last month renders normally, with no dates or navigation into year 10000."""
        instant = hkt("9999-12-31T23:59+08:00")
        picker = DateTimePicker("Deadline", instant, initial=instant)
        self.assertEqual(picker.weeks()[-1][-3:], [date.max, None, None])
        picker.move_day(1)
        picker.move_month(1)
        self.assertEqual(picker.day, date.max)

    def test_move_time_wraps_inside_the_day(self):
        """Moving the clock past 23:50 wraps to 00:05 and leaves the picker's day unchanged."""
        picker = DateTimePicker("Start", hkt("2026-09-14T23:50:00+08:00"), initial=hkt("2026-09-14T23:50:00+08:00"))
        picker.move_time(15)
        self.assertEqual(picker.day, date(2026, 9, 14))
        self.assertEqual((picker.hour, picker.minute), (0, 5))

    def test_summary_is_english_not_iso(self):
        """`month_title` names the month in English and `summary` reads as HKT, not an ISO `T` string."""
        picker = DateTimePicker("Start", hkt("2026-09-14T18:30:00+08:00"), initial=hkt("2026-09-14T18:30:00+08:00"))
        self.assertIn("September", picker.month_title())
        self.assertIn("HKT", picker.summary())
        self.assertNotIn("T18:30", picker.summary())


class DatetimePromptTests(unittest.TestCase):
    def test_modify_enter_preserves_unset_deadline_and_original_offset(self):
        """Enter without moving the picker is a no-op for both kinds of existing deadline."""
        from tempfile import TemporaryDirectory
        from pathlib import Path

        for deadline in (None, "2026-11-13T11:30Z"):
            with self.subTest(deadline=deadline), TemporaryDirectory() as tmp:
                pim = PIM()
                task = pim.create_task("test", deadline)
                pim.save(Path(tmp) / "task.pim")
                app, term, _out = make_terminal(app=App(pim), now=hkt("2026-11-13 19:30"))
                app.select_id(task.id)
                ui = CursesUI(term, object())
                for ch in "m\n\n":
                    ui._handle_key(ch)
                self.assertIs(pim.get(task.id), task)
                self.assertFalse(pim.is_dirty())
                self.assertEqual(app.status, "No changes")
                for ch in "m\nl\n":
                    ui._handle_key(ch)
                self.assertEqual(pim.get(task.id).deadline, hkt("2026-11-14 19:30"))
                self.assertTrue(pim.is_dirty())

    def test_start_prompt_names_the_format_and_zone(self):
        """Creating an Event opens a `start` picker whose prompt names the datetime format and Hong Kong Time."""
        app, term, _out = make_terminal()
        term._handle_line("create event")
        term._handle_line("lecture")
        label = term._prompt_label()
        self.assertIn(DATETIME_FORMAT, label)
        self.assertIn("Hong Kong Time", label)
        self.assertIsNotNone(term.current_picker())

    def test_typed_iso_still_creates_the_event(self):
        """The line UI can type an ISO datetime straight into the `start` picker prompt and still create the Event."""
        app, term, _out = make_terminal()
        term._handle_line("create event")
        term._handle_line("lecture")
        term._handle_line("2026-09-14T18:30:00+08:00")
        term._handle_line("n")
        self.assertEqual(app.calls[-1][0], "create")
        self.assertEqual(app.calls[-1][1], "event")

    def test_picker_enter_submits_hkt_clock(self):
        """Submitting the calendar picker's chosen day and HKT clock sets `start` to that `YYYY-MM-DD HH:MM`."""
        from view.curses_ui import CursesUI

        app, term, _out = make_terminal(now=hkt("2026-09-14T18:30:00+08:00"))
        ui = CursesUI(term, object())
        term._handle_line("create event")
        term._handle_line("lecture")
        picker = term.current_picker()
        picker.day = date(2026, 9, 16)
        picker.hour = 9
        picker.minute = 0
        ui._picker_submit(picker.value())
        # next prompt is add-an-alarm
        self.assertIsNotNone(term.current_chooser())
        term._handle_line("n")
        fields = app.calls[-1][2]
        self.assertEqual(fields["start"], "2026-09-16 09:00")

    def test_optional_deadline_skip_from_picker(self):
        """A Task's `deadline` picker is not `required`; pressing `n` skips it and submits `deadline: none`."""
        from view.curses_ui import CursesUI

        app, term, _out = make_terminal()
        ui = CursesUI(term, object())
        term._handle_line("create task")
        term._handle_line("Inbox")
        picker = term.current_picker()
        self.assertFalse(picker.required)
        ui._handle_picker_key("n")
        kind, type_name, fields = app.calls[-1]
        self.assertEqual(type_name, "task")
        self.assertEqual(fields["description"], "Inbox")
        self.assertEqual(fields.get("deadline"), "none")
