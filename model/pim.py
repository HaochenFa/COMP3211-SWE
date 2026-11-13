"""Working Collection: create, modify, delete, search, save, load, due_alarms."""

from __future__ import annotations

import copy
import os
from datetime import datetime, timezone

from model.criterion import Criterion
from model.pimfile import read_pim_file, require_pim_extension, write_pim_file
from model.pir import (
    Contact,
    DueAlarm,
    DirtyLoadError,
    Event,
    NotFound,
    Note,
    PIR,
    SOON_WINDOW,
    AlarmSpec,
    Task,
    ValidationError,
    parse_datetime,
)


class PIM:
    """Working Collection: PIR identity, search, persistence, and due alarms."""

    def __init__(self):
        """Empty collection, next Id 1, not dirty, no Bound File."""
        self._pirs: dict[int, PIR] = {}
        self._next_id = 1
        self._dirty = False
        self._bound_path: str | None = None

    def create_note(self, text: str | None) -> Note:
        """Insert a Note. Raises ValidationError if text is missing. Marks dirty."""
        pir = Note(self._next_id, text)
        return self._insert(pir)

    def create_task(self, description: str | None, deadline: datetime | str | None = None) -> Task:
        """Insert a Task. `deadline` is optional. Marks dirty."""
        pir = Task(self._next_id, description, deadline)
        return self._insert(pir)

    def create_event(
        self,
        description: str | None,
        start: datetime | str | None,
        alarms: list[AlarmSpec] | None = None,
    ) -> Event:
        """Insert an Event. `start` is required; `alarms` default to none. Marks dirty."""
        pir = Event(self._next_id, description, start, alarms)
        return self._insert(pir)

    def create_contact(
        self, name: str | None, address: str | None = None, mobile: str | None = None
    ) -> Contact:
        """Insert a Contact. `name` is required. Marks dirty."""
        pir = Contact(self._next_id, name, address, mobile)
        return self._insert(pir)

    def modify(self, pir_id: int | str, fields: dict[str, object]) -> PIR:
        """Copy-then-replace field updates.

        No mutation if validation fails or JSON is unchanged. Cannot change type.
        Raises NotFound if `pir_id` is missing.
        """
        pir = self.get(pir_id)
        if not isinstance(fields, dict):
            raise ValidationError("fields must be a mapping")
        candidate = copy.copy(pir)
        candidate.modify(fields)
        if candidate.to_json() == pir.to_json():
            return pir
        self._pirs[pir.id] = candidate
        self._dirty = True
        return candidate

    def delete(self, pir_id: int | str) -> None:
        """Remove the PIR. Id is never reused. Raises NotFound if missing."""
        self.get(pir_id)
        del self._pirs[int(pir_id)]
        self._dirty = True

    def get(self, pir_id: int | str) -> PIR:
        """Return the PIR with this Id. Raises NotFound if missing."""
        try:
            key = int(pir_id)
        except (TypeError, ValueError) as exc:
            raise NotFound(f"no PIR with Id {pir_id}") from exc
        pir = self._pirs.get(key)
        if pir is None:
            raise NotFound(f"no PIR with Id {key}")
        return pir

    def all(self) -> list[PIR]:
        """Every PIR in Id order."""
        return [self._pirs[key] for key in sorted(self._pirs)]

    def search(self, criterion: Criterion) -> list[PIR]:
        """PIRs that match `criterion`, in Id order."""
        return [pir for pir in self.all() if criterion.matches(pir)]

    def due_alarms(self, now: datetime | str) -> list[DueAlarm]:
        """OVERDUE and SOON alarms at injected `now`. Does not read the wall clock."""
        instant = parse_datetime(now).astimezone(timezone.utc)
        due: list[DueAlarm] = []
        for pir in self.all():
            if not isinstance(pir, Event):
                continue
            for index, alarm in enumerate(pir.alarms):
                at = alarm.effective(pir.start)
                at_utc = at.astimezone(timezone.utc)
                if at_utc <= instant:
                    status = "OVERDUE"
                elif at_utc - instant <= SOON_WINDOW:
                    status = "SOON"
                else:
                    continue
                due.append(DueAlarm(pir.id, index, at, status, pir.description))
        return due

    def save(self, path: str | os.PathLike[str]) -> None:
        """Write UTF-8 JSON. Appends .pim if omitted. Clears dirty and binds the path."""
        written = write_pim_file(path, self._next_id, self.all())
        self._bound_path = str(written)
        self._dirty = False

    def load(self, path: str | os.PathLike[str], *, force: bool = False) -> None:
        """Replace the collection from a .pim file.

        Rejects any other extension. Raises DirtyLoadError unless `force`.
        A corrupt file does not clobber memory: parse first, then replace.
        """
        require_pim_extension(path)
        if self._dirty and not force:
            raise DirtyLoadError("unsaved changes; save, discard, or cancel")
        next_id, pirs = read_pim_file(path)
        self._pirs = {pir.id: pir for pir in pirs}
        self._next_id = next_id
        self._bound_path = str(require_pim_extension(path))
        self._dirty = False

    def is_dirty(self) -> bool:
        """True if unsaved creates, modifies, or deletes exist."""
        return self._dirty

    def bound_path(self) -> str | None:
        """Path of the last successful save or load, or None."""
        return self._bound_path

    def _insert(self, pir: PIR) -> PIR:
        """Store a newly created PIR, advance the next Id past it, and mark the collection dirty."""
        self._pirs[pir.id] = pir
        self._next_id = pir.id + 1
        self._dirty = True
        return pir
