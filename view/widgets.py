"""View widgets: closed-choice selectors and prompt records.

These are data objects. The curses session paints them; the line-oriented
fallback ignores ``chooser`` and still accepts typed answers. That keeps
US1–US11 and the e2e scripts unchanged.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from model.pir import HKT
from view.file_browser import FileBrowser
from view.textwidth import display_width

WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
TIME_STEP = 15
DATETIME_FORMAT = "YYYY-MM-DD HH:MM"


@dataclass(frozen=True)
class Choice:
    """One option in a selector.

    ``value`` is what the existing prompt handler receives (``note``, ``y``,
    ``save``, …). ``key`` is a one-character accelerator. ``tone`` is a
    colour role (``note`` / ``task`` / ``event`` / ``contact`` / ``ok`` /
    ``danger``), or None.
    """

    value: str
    label: str
    key: str | None = None
    tone: str | None = None


@dataclass(frozen=True)
class Chooser:
    """A single-pick selector: arrows move, Enter submits ``value``."""

    title: str
    options: tuple[Choice, ...]
    default: int = 0
    hint: str = "← →  Enter  Esc"

    def clamp(self, index: int) -> int:
        """Keep ``index`` inside the option list."""
        if not self.options:
            return 0
        return max(0, min(len(self.options) - 1, index))

    def move(self, index: int, delta: int) -> int:
        """Move by ``delta`` without wrapping."""
        return self.clamp(index + delta)

    def pick_key(self, char: str) -> int | None:
        """Index for an option ``key``, else a 1-based digit. None if no match.

        An option's own key wins, so the offsets selector's ``0`` (At start)
        and ``1`` (15 minutes) mean what the chips show. Positional digits
        apply only when no option uses a digit as its key.
        """
        if not char:
            return None
        folded = char.casefold()
        for index, option in enumerate(self.options):
            if option.key is not None and option.key.casefold() == folded:
                return index
        digit_keys = any(option.key is not None and option.key.isdigit() for option in self.options)
        if char.isdigit() and not digit_keys:
            number = int(char)
            if 1 <= number <= len(self.options):
                return number - 1
        return None

    def value_at(self, index: int) -> str:
        """Handler payload for the highlighted option."""
        return self.options[self.clamp(index)].value


class DateTimePicker:
    """Month grid + time, like a calendar app. Submit value is ``YYYY-MM-DD HH:MM``.

    Week starts Monday (ISO / Hong Kong). Time steps 15 minutes, with 1-minute
    nudges. The line UI never sees this object — it still types the same string.
    """

    def __init__(self, title: str, now: datetime, *, initial=None, required: bool = True):
        local = now.astimezone(HKT) if now.tzinfo else now.replace(tzinfo=HKT)
        self.today = local.date()
        if initial is not None:
            seed = initial.astimezone(HKT) if initial.tzinfo else initial.replace(tzinfo=HKT)
            self.day = seed.date()
            self.hour = seed.hour
            self.minute = seed.minute
        else:
            self.day, self.hour, self.minute = _next_slot(local)
        self.view = date(self.day.year, self.day.month, 1)
        self.focus = "date"
        self.title = title
        self.required = required

    def value(self) -> str:
        """Instant the field handler already accepts (naive → HKT)."""
        return f"{self.day.isoformat()} {self.hour:02d}:{self.minute:02d}"

    def summary(self) -> str:
        """Readable confirmation, not an input format."""
        weekday = WEEKDAYS[self.day.weekday()]
        month = MONTHS[self.day.month - 1]
        return f"{weekday} {self.day.day} {month} {self.day.year}  {self.hour:02d}:{self.minute:02d}  HKT"

    def month_title(self) -> str:
        """English month name and year for the grid header."""
        return f"{MONTHS[self.view.month - 1]} {self.view.year}"

    def weeks(self) -> list[list[date]]:
        """Six-or-fewer weeks covering ``view``, Monday first, including spill days."""
        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        return cal.monthdatescalendar(self.view.year, self.view.month)

    def move_day(self, days: int) -> None:
        """Move the highlighted day and keep the month view on it."""
        self.day = self.day + timedelta(days=days)
        self.view = date(self.day.year, self.day.month, 1)

    def move_month(self, months: int) -> None:
        """Shift the visible month; clamp the day if the month is shorter."""
        year = self.view.year
        month = self.view.month + months
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        last = calendar.monthrange(year, month)[1]
        self.day = date(year, month, min(self.day.day, last))
        self.view = date(year, month, 1)

    def move_time(self, minutes: int) -> None:
        """Change the clock, wrapping inside the same day."""
        total = (self.hour * 60 + self.minute + minutes) % (24 * 60)
        if total < 0:
            total += 24 * 60
        self.hour = total // 60
        self.minute = total % 60

    def jump_today(self, now: datetime) -> None:
        """Select today's date; keep the chosen clock."""
        local = now.astimezone(HKT) if now.tzinfo else now.replace(tzinfo=HKT)
        self.day = local.date()
        self.view = date(self.day.year, self.day.month, 1)

    def toggle_focus(self) -> None:
        """Tab between the month grid and the time list."""
        self.focus = "time" if self.focus == "date" else "date"

    def time_slots(self, count: int = 7) -> list[tuple[int, int]]:
        """``count`` clock faces around the selection, 15 minutes apart."""
        current = self.hour * 60 + self.minute
        snapped = current - (current % TIME_STEP)
        start = snapped - (count // 2) * TIME_STEP
        slots = []
        hit = False
        for index in range(count):
            total = (start + index * TIME_STEP) % (24 * 60)
            pair = (total // 60, total % 60)
            slots.append(pair)
            if pair == (self.hour, self.minute):
                hit = True
        if not hit and slots:
            slots[count // 2] = (self.hour, self.minute)
        return slots


def _next_slot(local: datetime) -> tuple[date, int, int]:
    """Round *up* to the next 15-minute mark, like a calendar create sheet."""
    total = local.hour * 60 + local.minute
    remainder = total % TIME_STEP
    if remainder:
        total += TIME_STEP - remainder
    day = local.date()
    if total >= 24 * 60:
        day = day + timedelta(days=1)
        total = 0
    return day, total // 60, total % 60


@dataclass
class Prompt:
    """One stacked ask(): label, callback, optional dirty kind, optional widgets.

    At most one of ``chooser``, ``picker``, or ``browser`` is set.
    """

    label: str
    handler: Callable[[str], object]
    kind: str | None = None
    chooser: Chooser | None = None
    picker: DateTimePicker | None = None
    browser: FileBrowser | None = None


def type_chooser() -> Chooser:
    """PIR type for create. Values are the four type names."""
    return Chooser(
        title="New PIR — pick a type",
        options=(
            Choice("note", "Note", "n", "note"),
            Choice("task", "Task", "t", "task"),
            Choice("event", "Event", "e", "event"),
            Choice("contact", "Contact", "c", "contact"),
        ),
        hint="← →  1-4 or n t e c  Enter  Esc",
    )


def yes_no_chooser(title: str, *, prefer_yes: bool = False) -> Chooser:
    """Confirm. Values ``y`` / ``n`` match the existing handlers."""
    return Chooser(
        title=title,
        options=(
            Choice("y", "Yes", "y", "ok"),
            Choice("n", "No", "n", "danger"),
        ),
        default=0 if prefer_yes else 1,
        hint="← →  y / n  Enter  Esc",
    )


def alarm_kind_chooser() -> Chooser:
    """Relative or absolute. Values ``relative`` / ``absolute``."""
    return Chooser(
        title="Alarm kind",
        options=(
            Choice("relative", "Relative — before start", "r", "event"),
            Choice("absolute", "Absolute — a date and time", "a", "event"),
        ),
        hint="← →  r / a  Enter  Esc",
    )


def alarm_unit_chooser() -> Chooser:
    """Relative duration unit. Values are the model unit names."""
    return Chooser(
        title="How long before start?",
        options=(
            Choice("minute", "Minute", "m", None),
            Choice("hour", "Hour", "h", None),
            Choice("day", "Day", "d", None),
            Choice("week", "Week", "w", None),
        ),
        default=2,
        hint="← →  m h d w  Enter  Esc",
    )


def dirty_chooser(title: str) -> Chooser:
    """Unsaved changes. Values ``save`` / ``discard`` / ``cancel``."""
    return Chooser(
        title=title,
        options=(
            Choice("save", "Save", "s", "ok"),
            Choice("discard", "Discard", "d", "danger"),
            Choice("cancel", "Cancel", "c", None),
        ),
        default=2,
        hint="← →  s / d / c  Enter  Esc",
    )


@dataclass(frozen=True)
class ChipCell:
    """One painted option in a wrapped selector row."""

    text: str
    selected: bool
    tone: str | None


def wrap_chips(chooser: Chooser, index: int, width: int) -> list[list[ChipCell]]:
    """Flow option chips onto as many rows as ``width`` needs. Never drop one."""
    if width <= 0:
        width = 1
    rows: list[list[ChipCell]] = []
    current: list[ChipCell] = []
    used = 0
    for i, option in enumerate(chooser.options):
        key = option.key or str(i + 1)
        body = f" {key} {option.label} "
        w = display_width(body)
        gap = 1 if current else 0
        if current and used + gap + w > width:
            rows.append(current)
            current = []
            used = 0
            gap = 0
        current.append(ChipCell(body, i == index, option.tone))
        used += gap + w
    if current:
        rows.append(current)
    return rows or [[]]


def alarm_amount_chooser() -> Chooser:
    """Common relative offsets. Values the amount handler already understands."""
    return Chooser(
        title="When should it ring?",
        options=(
            Choice("0", "At start", "0", "event"),
            Choice("15 minute", "15 minutes", "1", "event"),
            Choice("1 hour", "1 hour", "h", "event"),
            Choice("1 day", "1 day", "d", "event"),
            Choice("other", "Other…", "o", None),
        ),
        hint="← →  0 1 h d o  Enter  Esc",
    )


def composer_height(
    *,
    chooser: Chooser | None,
    text_prompt: bool,
    picker: DateTimePicker | None = None,
    width: int = 80,
    extra_hint: bool = False,
    browser: FileBrowser | None = None,
) -> int:
    """Rows for the bottom composer: selector, labelled field, or idle hints."""
    if picker is not None or browser is not None:
        return 3
    if chooser is not None:
        inner = max(8, width - 4)
        chip_rows = len(wrap_chips(chooser, 0, inner))
        return 2 + max(1, chip_rows) + 1
    if text_prompt:
        return 4 if extra_hint else 3
    return 2
