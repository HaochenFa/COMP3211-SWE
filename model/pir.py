"""PIR types, alarms, and datetime helpers.

Callers use the classes and `parse_datetime` / `format_datetime`. Matching
and persistence stay in sibling modules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _hong_kong_zone() -> tzinfo:
    """Return the `Asia/Hong_Kong` zone, or a fixed UTC+8 zone named HKT.

    `zoneinfo` needs the system time-zone database (or the third-party
    `tzdata` package). Without either, the program would stop at import.
    Hong Kong has had no daylight saving since 1979, so the fixed offset
    gives the same instants for every present-day time.
    """
    try:
        return ZoneInfo("Asia/Hong_Kong")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8), "HKT")


HKT = _hong_kong_zone()
SOON_WINDOW = timedelta(minutes=15)
RELATIVE_UNITS = {
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
}
TYPE_NAMES = ("note", "task", "event", "contact")
CLEAR = "none"
KIND_TEXT = "text"
KIND_DATETIME = "datetime"
KIND_ALARMS = "alarms"


@dataclass(frozen=True)
class FieldSpec:
    """One PIR field: storage key, prompt label, kind, and whether it is required."""

    key: str
    label: str
    kind: str
    required: bool = True


class PIMError(Exception):
    """Domain rule violation. `status_message` is the specific English error."""

    def status_message(self) -> str:
        """English text for this failure."""
        return str(self)


class ValidationError(PIMError):
    """A required field is missing or a value is illegal."""


class NotFound(PIMError):
    """No PIR has this Id."""


class ParseError(PIMError):
    """Search criterion syntax is invalid."""

    def status_message(self) -> str:
        """English text, prefixed `search syntax error:`."""
        return f"search syntax error: {self}"


class DirtyLoadError(PIMError):
    """load while the collection has unsaved changes, without force."""


class FileFormatError(PIMError):
    """The path is not a readable pim/v1 JSON file."""

    def status_message(self) -> str:
        """English text, prefixed `not a PIM file:`."""
        return f"not a PIM file: {self}"


class ExtensionError(PIMError):
    """The path does not use the .pim extension."""


def is_blank(value: object) -> bool:
    """True for None or a whitespace-only string (a missing value)."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def is_positive_int(value: object) -> bool:
    """True for an `int` greater than zero (`bool` is not an int here)."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def require_text(value: object, field: str) -> str:
    """Return a stripped required string. Raises ValidationError if blank."""
    if is_blank(value):
        raise ValidationError(f"{field} is required")
    if not isinstance(value, str):
        raise ValidationError(f"{field} is required")
    return _utf8_text(value.strip(), field)


def optional_text(value: object, field: str = "text") -> str | None:
    """Strip an optional string; blank becomes None."""
    if is_blank(value):
        return None
    if not isinstance(value, str):
        return str(value)
    return _utf8_text(value.strip(), field)


def _utf8_text(value: str, field: str) -> str:
    """Reject lone surrogates, including those decoded from JSON escape sequences."""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{field} is not valid UTF-8 text") from exc
    return value


def minute_floor(dt: datetime) -> datetime:
    """Truncate to minute. Raises ValidationError if naive."""
    if dt.tzinfo is None:
        raise ValidationError("datetime must be timezone-aware")
    return dt.replace(second=0, microsecond=0)


def parse_datetime(value: datetime | str, field: str = "datetime") -> datetime:
    """Parse a timezone-aware instant; default zone is Hong Kong Time.

    `field` names the value in the error raised for a blank or `none` answer,
    for example `start is required`.
    """
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=HKT)
        return require_hkt_range(minute_floor(dt))
    if is_blank(value) or not isinstance(value, str):
        raise ValidationError(f"{field} is required")
    raw = _utf8_text(value.strip(), field)
    if raw.casefold() == CLEAR:
        raise ValidationError(f"{field} is required")
    text = raw
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"invalid datetime: {raw}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=HKT)
    return require_hkt_range(minute_floor(dt))


def require_hkt_range(dt: datetime) -> datetime:
    """Return `dt` if it can be shown in Hong Kong Time; else ValidationError.

    An instant such as 9999-12-31T23:59-10:00 parses, but converting it to
    HKT or UTC overflows the datetime range, so it could not be displayed
    or saved and loaded back.
    """
    try:
        # astimezone(HKT) is a no-op when tzinfo is already HKT, so also go
        # through UTC: a value that cannot be expressed there would save but
        # not load back (it is stored with a fixed offset).
        dt.astimezone(timezone.utc)
        dt.astimezone(HKT)
    except OverflowError as exc:
        raise ValidationError("datetime out of range") from exc
    return dt


def parse_optional_datetime(value: datetime | str | None) -> datetime | None:
    """Parse an optional instant; blank or `none` is None."""
    if is_blank(value):
        return None
    if isinstance(value, str) and value.strip().casefold() == CLEAR:
        return None
    return parse_datetime(value)


def format_datetime(dt: datetime) -> str:
    """ISO 8601 at second resolution, timezone-aware."""
    return minute_floor(dt).isoformat(timespec="seconds")


def parse_alarm(spec: AlarmSpec) -> RelativeAlarm | AbsoluteAlarm:
    """Build a RelativeAlarm or AbsoluteAlarm from an object or JSON dict."""
    if isinstance(spec, (RelativeAlarm, AbsoluteAlarm)):
        return spec
    if not isinstance(spec, dict):
        raise ValidationError("invalid alarm")
    kind = spec.get("kind", "")
    kind = kind.casefold() if isinstance(kind, str) else ""
    if kind == "relative":
        return RelativeAlarm(spec.get("amount"), spec.get("unit"))
    if kind == "absolute":
        return AbsoluteAlarm(spec.get("at"))
    raise ValidationError("alarm kind must be relative or absolute")


def parse_alarms(specs: list[AlarmSpec] | tuple | None) -> list[RelativeAlarm | AbsoluteAlarm]:
    """Build an alarm list. None means no alarms; any non-list value is a ValidationError."""
    if specs is None:
        return []
    if not isinstance(specs, (list, tuple)):
        raise ValidationError("alarms must be a list")
    return [parse_alarm(item) for item in specs]


def _alarm_amount(value: object) -> int:
    """Whole-number amount from an int or a decimal-digit string.

    `bool` and `float` are rejected rather than truncated (1.9 is not 1).
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and re.fullmatch(r"\s*-?[0-9]+\s*", value):
        try:
            return int(value)
        except ValueError as exc:
            raise ValidationError("alarm time is out of range") from exc
    raise ValidationError("relative alarm amount must be an integer")


class RelativeAlarm:
    """Alarm at start, or N units before start. Effective time moves when start changes."""

    def __init__(self, amount: int | str, unit: str):
        amount = _alarm_amount(amount)
        if amount < 0:
            raise ValidationError("relative alarm cannot be after start")
        if is_blank(unit) or not isinstance(unit, str):
            raise ValidationError("relative alarm unit is required")
        unit_key = unit.strip().casefold()
        if unit_key.endswith("s") and unit_key[:-1] in RELATIVE_UNITS:
            unit_key = unit_key[:-1]
        if unit_key not in RELATIVE_UNITS:
            raise ValidationError("relative alarm unit must be minute, hour, day, or week")
        self.amount = amount
        self.unit = unit_key

    def effective(self, start: datetime) -> datetime:
        """`start` minus the stored duration (0 = at start)."""
        at = start.astimezone(timezone.utc) - RELATIVE_UNITS[self.unit] * self.amount
        # The stored start keeps its offset on reload, so use that offset for display.
        return at.astimezone(timezone(start.utcoffset()))

    def to_json(self) -> dict:
        """JSON object with kind, amount, and unit."""
        return {"kind": "relative", "amount": self.amount, "unit": self.unit}

    def kind_label(self) -> str:
        """Human-readable relative trigger, e.g. `relative 1 day before start`."""
        if self.amount == 0:
            return "relative at start"
        unit = self.unit if self.amount == 1 else self.unit + "s"
        return f"relative {self.amount} {unit} before start"


class AbsoluteAlarm:
    """Alarm at a stored instant. Changing start does not move it."""

    def __init__(self, at: datetime | str):
        self.at = parse_datetime(at, "alarm time")

    def effective(self, start: datetime) -> datetime:
        """The stored instant; `start` is ignored."""
        return self.at

    def to_json(self) -> dict:
        """JSON object with kind and `at`."""
        return {"kind": "absolute", "at": format_datetime(self.at)}

    def kind_label(self) -> str:
        """Always `absolute`."""
        return "absolute"


def check_alarm_times(start: datetime, alarms: list[RelativeAlarm | AbsoluteAlarm]) -> None:
    """Raise ValidationError if any Effective Alarm Time falls outside the datetime range.

    A huge relative amount, or a start near year 1, makes `start - duration`
    overflow; the Event must then be rejected rather than stored.
    """
    for alarm in alarms:
        try:
            require_hkt_range(alarm.effective(start))
        except (OverflowError, ValidationError) as exc:
            raise ValidationError("alarm time is out of range") from exc



# What an alarm list may hold: alarm objects, or pim/v1 JSON dicts on load.
AlarmSpec = RelativeAlarm | AbsoluteAlarm | dict

class DueAlarm:
    """One OVERDUE or SOON alarm at an injected `now`. `key` is (event Id, alarm index)."""

    def __init__(self, event_id: int, alarm_index: int, at: datetime, status: str, description: str):
        self.event_id = event_id
        self.alarm_index = alarm_index
        self.at = at
        self.status = status
        self.description = description

    def key(self) -> tuple[int, int]:
        """Dismiss identity: (event Id, alarm index)."""
        return (self.event_id, self.alarm_index)


class PIR:
    """One record. Id is identity; type_name is immutable after creation."""

    type_name: str = ""
    FIELDS: tuple[FieldSpec, ...] = ()

    def __init__(self, pir_id: int):
        self.id = pir_id

    def display_field(self, key: str) -> str:
        """Current value of `key` as a prompt hint (`none` if missing)."""
        value = getattr(self, key)
        if value is None:
            return "none"
        if key == "alarms":
            return "none" if not value else f"{len(value)} alarm(s)"
        if isinstance(value, datetime):
            return format_datetime(value)
        return str(value)

    @property
    def display_name(self) -> str:
        """Derived list label: Note first line, Task/Event description, Contact name."""
        raise NotImplementedError

    def text_fields(self) -> list[str]:
        """Text values used by unqualified `contains`."""
        raise NotImplementedError

    def text_value(self, field: str) -> str | None:
        """Named text field, or None if this type has no such field."""
        return None

    def time_values(self, field: str) -> list[datetime]:
        """Instants for a time comparison; empty if the field is missing."""
        return []

    def relevant_time(self) -> datetime | None:
        """Deadline or start for the Current Result table, else None."""
        return None

    def modify(self, fields: dict[str, object]) -> None:
        """Apply updates in place. Raises ValidationError if type would change."""
        if "type" in fields and not is_blank(fields["type"]):
            wanted = str(fields["type"]).strip().casefold()
            if wanted != self.type_name:
                raise ValidationError("PIR type cannot be changed")
        self._apply(fields)

    def _apply(self, fields: dict[str, object]) -> None:
        """Validate every changed field first, then assign them; subclasses implement it."""
        raise NotImplementedError

    def to_json(self) -> dict:
        """pim/v1 object for this PIR, including Id and type."""
        raise NotImplementedError

    def detail_lines(self) -> list[tuple[str, str]]:
        """(label, value) rows for print and the detail pane."""
        raise NotImplementedError


class Note(PIR):
    """PIR whose body is required `text`."""

    type_name = "note"
    FIELDS = (FieldSpec("text", "text", KIND_TEXT, required=True),)

    def __init__(self, pir_id: int, text: str | None):
        super().__init__(pir_id)
        self.text = require_text(text, "text")

    @property
    def display_name(self) -> str:
        """First line of the body text."""
        return self.text.splitlines()[0]

    def text_fields(self) -> list[str]:
        """A Note's only text field is its body."""
        return [self.text]

    def text_value(self, field: str) -> str | None:
        """The body for `text`; None for any other field name."""
        if field == "text":
            return self.text
        return None

    def _apply(self, fields: dict[str, object]) -> None:
        """Validate the changed fields, then assign them, so a bad value changes nothing."""
        new_text = self.text
        if "text" in fields:
            new_text = require_text(fields["text"], "text")
        self.text = new_text

    def to_json(self) -> dict:
        """`pim/v1` object with the Id, type `note`, and text."""
        return {"id": self.id, "type": "note", "text": self.text}

    def detail_lines(self) -> list[tuple[str, str]]:
        """Rows for `print`: Id, type, and the full text."""
        return [("Id", str(self.id)), ("type", "note"), ("text", self.text)]


class Task(PIR):
    """PIR with required `description` and optional `deadline`."""

    type_name = "task"
    FIELDS = (
        FieldSpec("description", "description", KIND_TEXT, required=True),
        FieldSpec("deadline", "deadline", KIND_DATETIME, required=False),
    )

    def __init__(
        self, pir_id: int, description: str | None, deadline: datetime | str | None = None
    ):
        super().__init__(pir_id)
        self.description = require_text(description, "description")
        self.deadline = parse_optional_datetime(deadline)

    @property
    def display_name(self) -> str:
        """The description."""
        return self.description

    def text_fields(self) -> list[str]:
        """A Task's only text field is its description."""
        return [self.description]

    def text_value(self, field: str) -> str | None:
        """The description for `description`; None for any other field name."""
        if field == "description":
            return self.description
        return None

    def time_values(self, field: str) -> list[datetime]:
        """The deadline for `deadline` when it is set; otherwise empty, so comparisons are false."""
        if field == "deadline" and self.deadline is not None:
            return [self.deadline]
        return []

    def relevant_time(self) -> datetime | None:
        """The deadline shown in the list, or None when there is none."""
        return self.deadline

    def _apply(self, fields: dict[str, object]) -> None:
        """Validate the changed fields, then assign them, so a bad value changes nothing."""
        new_description = self.description
        new_deadline = self.deadline
        if "description" in fields:
            new_description = require_text(fields["description"], "description")
        if "deadline" in fields:
            new_deadline = parse_optional_datetime(fields["deadline"])
        self.description = new_description
        self.deadline = new_deadline

    def to_json(self) -> dict:
        """`pim/v1` object; an unset deadline is stored as null."""
        return {
            "id": self.id,
            "type": "task",
            "description": self.description,
            "deadline": format_datetime(self.deadline) if self.deadline else None,
        }

    def detail_lines(self) -> list[tuple[str, str]]:
        """Rows for `print`: Id, type, description, and deadline or `(none)`."""
        deadline = format_datetime(self.deadline) if self.deadline else "(none)"
        return [
            ("Id", str(self.id)),
            ("type", "task"),
            ("description", self.description),
            ("deadline", deadline),
        ]


class Event(PIR):
    """PIR with required `description` and `start`, and zero or more alarms."""

    type_name = "event"
    FIELDS = (
        FieldSpec("description", "description", KIND_TEXT, required=True),
        FieldSpec("start", "start", KIND_DATETIME, required=True),
        FieldSpec("alarms", "alarms", KIND_ALARMS, required=False),
    )

    def __init__(
        self,
        pir_id: int,
        description: str | None,
        start: datetime | str | None,
        alarms: list[AlarmSpec] | None = None,
    ):
        super().__init__(pir_id)
        self.description = require_text(description, "description")
        self.start = parse_datetime(start, "start")
        self.alarms = parse_alarms(alarms)
        # Reject at entry so due_alarms, print, and search never meet an overflow.
        check_alarm_times(self.start, self.alarms)

    @property
    def display_name(self) -> str:
        """The description."""
        return self.description

    def text_fields(self) -> list[str]:
        """An Event's only text field is its description."""
        return [self.description]

    def text_value(self, field: str) -> str | None:
        """The description for `description`; None for any other field name."""
        if field == "description":
            return self.description
        return None

    def time_values(self, field: str) -> list[datetime]:
        """`[start]` for `start`, every Effective Alarm Time for `alarm`, else empty."""
        if field == "start":
            return [self.start]
        if field == "alarm":
            return [alarm.effective(self.start) for alarm in self.alarms]
        return []

    def relevant_time(self) -> datetime | None:
        """The start shown in the list."""
        return self.start

    def effective_alarm_times(self) -> list[datetime]:
        """Effective Alarm Times of every alarm, relative ones using current start."""
        return [alarm.effective(self.start) for alarm in self.alarms]

    def _apply(self, fields: dict[str, object]) -> None:
        """Validate the changed fields, then assign them, so a bad value changes nothing."""
        new_description = self.description
        new_start = self.start
        new_alarms = list(self.alarms)
        if "description" in fields:
            new_description = require_text(fields["description"], "description")
        if "start" in fields:
            new_start = parse_datetime(fields["start"], "start")
        if "alarms" in fields:
            new_alarms = parse_alarms(fields["alarms"])
        # Validate against the new start before any attribute changes (atomic modify).
        check_alarm_times(new_start, new_alarms)
        self.description = new_description
        self.start = new_start
        self.alarms = new_alarms

    def to_json(self) -> dict:
        """`pim/v1` object; each alarm keeps its kind (relative or absolute)."""
        return {
            "id": self.id,
            "type": "event",
            "description": self.description,
            "start": format_datetime(self.start),
            "alarms": [alarm.to_json() for alarm in self.alarms],
        }

    def detail_lines(self) -> list[tuple[str, str]]:
        """Rows for `print`: Id, type, description, start, and each alarm with its kind and Effective Alarm Time."""
        lines = [
            ("Id", str(self.id)),
            ("type", "event"),
            ("description", self.description),
            ("start", format_datetime(self.start)),
        ]
        if not self.alarms:
            lines.append(("alarms", "(none)"))
        else:
            for index, alarm in enumerate(self.alarms):
                at = format_datetime(alarm.effective(self.start))
                lines.append((f"alarm[{index}]", f"{alarm.kind_label()}; effective {at}"))
        return lines


class Contact(PIR):
    """PIR with required `name` and optional `address` and `mobile`."""

    type_name = "contact"
    FIELDS = (
        FieldSpec("name", "name", KIND_TEXT, required=True),
        FieldSpec("address", "address", KIND_TEXT, required=False),
        FieldSpec("mobile", "mobile", KIND_TEXT, required=False),
    )

    def __init__(
        self, pir_id: int, name: str | None, address: str | None = None, mobile: str | None = None
    ):
        super().__init__(pir_id)
        self.name = require_text(name, "name")
        self.address = optional_text(address, "address")
        self.mobile = optional_text(mobile, "mobile")

    @property
    def display_name(self) -> str:
        """The person name."""
        return self.name

    def text_fields(self) -> list[str]:
        """Name, address, and mobile, leaving out unset ones."""
        return [value for value in (self.name, self.address, self.mobile) if value]

    def text_value(self, field: str) -> str | None:
        """The value of `name`, `address`, or `mobile`; None if unset or not a Contact field."""
        if field == "name":
            return self.name
        if field == "address":
            return self.address
        if field == "mobile":
            return self.mobile
        return None

    def _apply(self, fields: dict[str, object]) -> None:
        """Validate the changed fields, then assign them, so a bad value changes nothing."""
        new_name = self.name
        new_address = self.address
        new_mobile = self.mobile
        if "name" in fields:
            new_name = require_text(fields["name"], "name")
        if "address" in fields:
            new_address = optional_text(fields["address"], "address")
            if isinstance(fields["address"], str) and fields["address"].strip().casefold() == CLEAR:
                new_address = None
        if "mobile" in fields:
            new_mobile = optional_text(fields["mobile"], "mobile")
            if isinstance(fields["mobile"], str) and fields["mobile"].strip().casefold() == CLEAR:
                new_mobile = None
        self.name = new_name
        self.address = new_address
        self.mobile = new_mobile

    def to_json(self) -> dict:
        """`pim/v1` object; unset address or mobile is stored as null."""
        return {
            "id": self.id,
            "type": "contact",
            "name": self.name,
            "address": self.address,
            "mobile": self.mobile,
        }

    def detail_lines(self) -> list[tuple[str, str]]:
        """Rows for `print`: Id, type, name, address, and mobile, with `(none)` when unset."""
        return [
            ("Id", str(self.id)),
            ("type", "contact"),
            ("name", self.name),
            ("address", self.address or "(none)"),
            ("mobile", self.mobile or "(none)"),
        ]


def pir_class(type_name: str) -> type[PIR] | None:
    """PIR subclass for `type_name`, or None if unknown."""
    name = type_name.casefold()
    for cls in (Note, Task, Event, Contact):
        if cls.type_name == name:
            return cls
    return None


def pir_from_json(data: dict[str, object]) -> PIR:
    """Reconstruct a PIR from a pim/v1 object. Raises FileFormatError if invalid."""
    if not isinstance(data, dict):
        raise FileFormatError("PIR must be an object")
    pir_id = data.get("id")
    # Ids are positive integers in the file; 1.7, "3", true, and -3 are not coerced.
    if not is_positive_int(pir_id):
        raise FileFormatError("PIR is missing a valid id")
    type_name = data.get("type")
    if not isinstance(type_name, str):
        raise FileFormatError("PIR type must be a string")
    cls = pir_class(type_name)
    if cls is None:
        raise FileFormatError(f"unknown PIR type: {type_name!r}")
    fields = {}
    for spec in cls.FIELDS:
        value = data.get(spec.key)
        if spec.kind == KIND_ALARMS:
            if spec.key in data and not isinstance(value, list):
                raise FileFormatError("alarms must be a list")
        elif value is not None and not isinstance(value, str):
            raise FileFormatError(f"{spec.key} must be a string")
        fields[spec.key] = value
    return cls(pir_id, **fields)
