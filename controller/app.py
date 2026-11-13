"""One completed user action → model.PIM. Holds Current Result and selection."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from controller.errors import message_for
from model import PIM, PIMError, ValidationError, parse_criterion
from model.pimfile import append_pim_extension

if TYPE_CHECKING:
    from model import DueAlarm
    from model.pir import PIR


def format_pir(pir: PIR) -> str:
    """One PIR as `key: value` lines for print."""
    return "\n".join(f"{key}: {value}" for key, value in pir.detail_lines())


STATUS_INFO = "info"
STATUS_OK = "ok"
STATUS_ERR = "err"


_CREATE = {
    "note": lambda pim, fields: pim.create_note(fields.get("text")),
    "task": lambda pim, fields: pim.create_task(fields.get("description"), fields.get("deadline")),
    "event": lambda pim, fields: pim.create_event(
        fields.get("description"), fields.get("start"), fields.get("alarms")
    ),
    "contact": lambda pim, fields: pim.create_contact(
        fields.get("name"), fields.get("address"), fields.get("mobile")
    ),
}


class App:
    """One completed user action → `model.PIM`. Holds Current Result and selection."""

    def __init__(self, pim: PIM):
        """Bind to an empty or existing Working Collection."""
        self.pim = pim
        self._criterion = None
        self._criterion_line = None
        self._result = []
        self._selected_id = None
        self.status = ""
        self.status_kind = STATUS_INFO
        self.print_text = ""
        self._refresh()

    def set_status(self, text: str, kind: str = STATUS_INFO) -> None:
        """Set the status line and its tone. ``kind`` is info, ok, or err."""
        self.status = text
        if kind in {STATUS_INFO, STATUS_OK, STATUS_ERR}:
            self.status_kind = kind
        else:
            self.status_kind = STATUS_INFO

    def bound_path(self) -> str | None:
        """Bound File path, or None if untitled."""
        return self.pim.bound_path()

    def is_dirty(self) -> bool:
        """True if the Working Collection has unsaved changes."""
        return self.pim.is_dirty()

    def save_target(self, path: str | os.PathLike[str]) -> str:
        """Path that save would write, with `.pim` appended if omitted.

        Raises ValidationError if the path has no file name (blank or `.pim`).
        """
        return str(append_pim_extension(path))

    def would_overwrite(self, path: str | os.PathLike[str]) -> bool:
        """True if `save as` would replace a file that is not the Bound File.

        An invalid path is not an overwrite; `save` then reports why it failed.
        """
        try:
            target = Path(self.save_target(path))
        except PIMError:
            return False
        bound = self.pim.bound_path()
        # Match os.replace: it replaces the directory entry, even a dangling link.
        if not os.path.lexists(target):
            return False
        if bound is None:
            return True
        bound = Path(bound)
        try:
            return (target.parent.resolve(), target.name) != (bound.parent.resolve(), bound.name)
        except OSError:
            return target != bound

    def clear_print(self) -> None:
        """Drop the last print buffer."""
        self.print_text = ""

    def current_result(self) -> list[PIR]:
        """PIRs in the current list (search hits, or the whole collection)."""
        return list(self._result)

    def selected(self) -> PIR | None:
        """The selected PIR, or None if none / it left Current Result."""
        if self._selected_id is None:
            return None
        try:
            return self.pim.get(self._selected_id)
        except PIMError:
            self._selected_id = None
            return None

    def selected_id(self) -> int | None:
        """Id of the selection, or None."""
        pir = self.selected()
        return None if pir is None else pir.id

    def has_criterion(self) -> bool:
        """True when Current Result is a search hit list."""
        return self._criterion is not None

    def criterion_line(self) -> str | None:
        """Source text of the current search, or None when unfiltered."""
        return self._criterion_line

    def due_alarms(self, now: datetime) -> list[DueAlarm]:
        """Due alarms at injected `now`."""
        return self.pim.due_alarms(now)

    def create(self, type_name: str, fields: dict[str, object]) -> PIR | None:
        """Create one PIR. On failure, status is set and the collection is unchanged."""
        factory = _CREATE.get(type_name)
        if factory is None:
            self.set_status(f"unknown PIR type: {type_name}", STATUS_ERR)
            return None
        return self._create(lambda: factory(self.pim, fields), type_name.capitalize())

    def modify(self, fields: dict[str, object]) -> PIR | None:
        """Modify the selection. Empty `fields` is a no-op and does not mark dirty."""
        pir = self.selected()
        if pir is None:
            self.set_status("no PIR selected", STATUS_ERR)
            return None
        if not fields:
            self.set_status("No changes", STATUS_INFO)
            return pir
        try:
            updated = self.pim.modify(pir.id, fields)
        except PIMError as exc:
            self.set_status(message_for(exc), STATUS_ERR)
            return None
        if updated is pir:
            self.set_status("No changes", STATUS_INFO)
            return pir
        self._refresh()
        self.set_status(f"Modified Id {updated.id}", STATUS_OK)
        return updated

    def delete_selected(self) -> bool:
        """Delete the selection after the View has confirmed. False if none selected."""
        pir = self.selected()
        if pir is None:
            self.set_status("no PIR selected", STATUS_ERR)
            return False
        try:
            self.pim.delete(pir.id)
        except PIMError as exc:
            self.set_status(message_for(exc), STATUS_ERR)
            return False
        self._selected_id = None
        self._refresh()
        self.set_status(f"Deleted Id {pir.id}", STATUS_OK)
        return True

    def search(self, line: str) -> bool:
        """Replace Current Result with matches. Syntax error leaves the list unchanged.

        Returns True on success. On parse or search failure returns False,
        keeps Current Result, and does not store the criterion line.
        A successful search with hits selects the first row.
        """
        try:
            criterion = parse_criterion(line)
            hits = self.pim.search(criterion)
        except PIMError as exc:
            self.set_status(message_for(exc), STATUS_ERR)
            return False
        self._criterion = criterion
        self._criterion_line = line
        self._result = hits
        self._selected_id = hits[0].id if hits else None
        self.set_status(f"{len(hits)} match(es)", STATUS_OK)
        return True

    def clear_search(self) -> None:
        """Restore Current Result to the whole collection."""
        self._criterion = None
        self._criterion_line = None
        self._refresh()
        self.set_status("Search cleared", STATUS_INFO)

    def select_row(self, number: int | str) -> None:
        """Select by 1-based row of Current Result. Row numbers are not identity."""
        try:
            index = int(number)
        except (TypeError, ValueError):
            self.set_status("row number must be an integer", STATUS_ERR)
            return
        if index < 1 or index > len(self._result):
            self.set_status(f"no row {index} in Current Result", STATUS_ERR)
            return
        self._selected_id = self._result[index - 1].id
        self.set_status(f"Selected Id {self._selected_id}", STATUS_INFO)

    def select_id(self, pir_id: int | str) -> None:
        """Select by Id. Status names NotFound if missing."""
        try:
            pir = self.pim.get(pir_id)
        except PIMError as exc:
            self.set_status(message_for(exc), STATUS_ERR)
            return
        self._selected_id = pir.id
        self.set_status(f"Selected Id {pir.id}", STATUS_INFO)

    def print_selected(self) -> str | None:
        """Fill print_text with every field of the selection."""
        pir = self.selected()
        if pir is None:
            self.set_status("no PIR selected", STATUS_ERR)
            return None
        self.print_text = format_pir(pir)
        self.set_status(f"Printed Id {pir.id}", STATUS_OK)
        return self.print_text

    def print_all(self) -> str:
        """Fill print_text with every PIR in Current Result, not the unfiltered collection."""
        if not self._result:
            self.print_text = "(Current Result is empty)"
        else:
            self.print_text = "\n\n".join(format_pir(pir) for pir in self._result)
        self.set_status(f"Printed {len(self._result)} PIR(s) in Current Result", STATUS_OK)
        return self.print_text

    def save(self, path: str | os.PathLike[str] | None = None) -> bool:
        """Write the Bound File, or `path` for save as. False on domain or OS failure.

        On success the status names the absolute path that was written.

        An OSError (permission denied, disk full) becomes one status line that
        names the `.pim` target; the collection stays dirty.
        """
        try:
            if path is None:
                path = self.pim.bound_path()
                if not path:
                    raise ValidationError("no file name; use save as")
            self.pim.save(path)
        except PIMError as exc:
            self.set_status(message_for(exc), STATUS_ERR)
            return False
        except OSError as exc:
            # exc.filename may be the hidden temp file; show the user's target instead.
            reason = exc.strerror or str(exc)
            self.set_status(f"cannot save {os.path.abspath(self.save_target(path))}: {reason}", STATUS_ERR)
            return False
        # Absolute, so a relative or `~` path shows where the file really went.
        self.set_status(f"Saved {os.path.abspath(self.pim.bound_path())}", STATUS_OK)
        return True

    def load(self, path: str | os.PathLike[str], force: bool = False) -> bool:
        """Replace the collection. `force` discards unsaved changes. False on failure.

        On success the status names the absolute path that was read.
        """
        try:
            self.pim.load(path, force=force)
        except PIMError as exc:
            self.set_status(message_for(exc), STATUS_ERR)
            return False
        self._criterion = None
        self._criterion_line = None
        self._selected_id = None
        self.print_text = ""
        self._refresh()
        self.set_status(f"Loaded {os.path.abspath(self.pim.bound_path())}", STATUS_OK)
        return True

    def _create(self, factory, label: str) -> PIR | None:
        try:
            pir = factory()
        except PIMError as exc:
            self.set_status(message_for(exc), STATUS_ERR)
            return None
        self._selected_id = pir.id
        self._refresh()
        self.set_status(f"Created {label} Id {pir.id}", STATUS_OK)
        return pir

    def _refresh(self) -> None:
        if self._criterion is None:
            self._result = self.pim.all()
        else:
            self._result = self.pim.search(self._criterion)
        if self._selected_id is not None and all(pir.id != self._selected_id for pir in self._result):
            if self._criterion is not None:
                self._selected_id = None
            elif self._selected_id not in {pir.id for pir in self.pim.all()}:
                self._selected_id = None


HELP = (
    "Commands: create [note|task|event|contact] | search <criterion> | clear | "
    "<row> | id <n> | modify | print | print all | delete | save | save as <path> | "
    "load <path> | dismiss | help | quit"
)
