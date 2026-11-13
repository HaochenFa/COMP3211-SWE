"""In-process Alarm Alerts: OVERDUE, SOON, dismiss is View memory only."""

from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from queue import Empty
from pathlib import Path
from unittest.mock import patch

from controller.app import App
from model import PIM, parse_datetime
from tests.e2e.harness import clock, run_script
from view import Terminal


class AlarmAlertTests(unittest.TestCase):
    def test_overdue_banner_then_dismiss_is_not_written_to_file(self):
        """An overdue Alarm Alert shows OVERDUE; dismissing it is View-only, so the saved file still reports it due."""
        now = parse_datetime("2026-09-14T18:30:00+08:00")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "alerts.pim"
        app, term, out = run_script(
            [
                "create event",
                "lecture",
                "2026-09-14T18:30:00+08:00",
                "y",
                "relative",
                "0",
                "n",
                "dismiss",
                f"save as {dest}",
                "quit",
            ],
            now=clock(now),
        )
        self.assertIn("OVERDUE", out)
        self.assertIn("Dismissed alarm on Id 1", out)
        self.assertEqual(term.visible_due(), [])
        self.assertIn((1, 0), term.dismissed)
        loaded = PIM()
        loaded.load(dest)
        self.assertEqual(len(loaded.get(1).alarms), 1)
        self.assertTrue(loaded.due_alarms(now))

    def test_soon_banner_within_fifteen_minutes(self):
        """An alarm within fifteen minutes of `now` shows a SOON Alarm Alert, not OVERDUE."""
        now = parse_datetime("2026-09-14T18:30:00+08:00")
        _app, _term, out = run_script(
            [
                "create event",
                "soon",
                "2026-09-14T18:45:00+08:00",
                "y",
                "relative",
                "0",
                "n",
                "quit",
                "discard",
            ],
            now=clock(now),
        )
        self.assertIn("SOON", out)
        self.assertNotIn("OVERDUE", out)

    def test_dismiss_with_no_alarm_reports_status(self):
        """`dismiss` with no Alarm Alert showing reports `no alarm to dismiss`."""
        _app, _term, out = run_script(["dismiss", "quit"])
        self.assertIn("no alarm to dismiss", out)

    def test_idle_alarm_updates_without_using_the_entire_deadline_to_wait(self):
        """An alarm becoming due just after an idle poll is painted within 500 ms."""
        from io import StringIO

        due = parse_datetime("2026-09-14 18:30")
        elapsed = 0.0
        painted = []

        class Output(StringIO):
            def write(self, text):
                if "OVERDUE" in text:
                    painted.append(elapsed)
                return super().write(text)

        class IdleInput:
            def get(self, timeout):
                nonlocal elapsed
                if not elapsed:
                    # Simulate the wait plus a small scheduling and redraw cost.
                    elapsed = timeout + 0.010
                    raise Empty
                return "discard" if term._is_dirty_prompt() else "quit"

        pim = PIM()
        pim.create_event("due just after the poll", due, [{"kind": "absolute", "at": due}])
        term = Terminal(App(pim), stdin=StringIO(), stdout=Output(),
                        now=lambda: due + timedelta(seconds=elapsed - 0.001))
        term.queue = IdleInput()
        with patch("view.terminal.start_stdin_reader"):
            term.run()
        self.assertTrue(painted)
        self.assertLessEqual(painted[0] - 0.001, 0.500)


if __name__ == "__main__":
    unittest.main()
