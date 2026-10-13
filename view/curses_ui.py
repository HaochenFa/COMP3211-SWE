"""Full-screen stdlib curses UI for an interactive TTY.

The screen is an HKT lecture diary: a quiet page, a vermilion/amber
alarm stamp, Current Result as a timetable, and the selected PIR as a
card. Closed answers use a Chooser; datetimes use a calendar; load and
save-as paths use a folder browser. Free text and every widget answer
still go through ``Terminal._handle_line``. The tick is ``timeout(500)``
so Alarm Alerts appear without a keypress.
"""

from __future__ import annotations

import curses
from datetime import datetime

from controller.errors import message_for
from model import PIMError
from model.pir import HKT
from view.keys import COMMAND, HELP as KEY_HELP, action_for_char, action_for_key_name
from view.layout import (
    EMPTY_INVITE,
    MENU,
    SEARCH_EXAMPLE,
    SEARCH_HINT,
    TYPE_PIN,
    card_fields,
    compute_geometry,
    format_list_header,
    format_list_row,
    idle_hints,
    list_pane_title,
    picker_time_origin,
    picker_weekday_row,
    visible_list_window,
)
from view.theme import (
    ERR,
    OK,
    OVERDUE,
    PAGE,
    PIN_ROLES,
    QUIET,
    RULE,
    SELECT,
    SOON,
    TITLE,
    TONE_ROLES,
    Theme,
    init_theme,
)
from view.file_browser import FILE, FOLDER, PARENT, FileBrowser
from view.textwidth import clip, clip_left, display_width, input_window, wrap
from view.widgets import WEEKDAYS, Chooser, DateTimePicker, composer_height, wrap_chips

HELP_LINES = (
    "Move",
    "  ↑ ↓  j k     Current Result",
    "  PgUp PgDn    page    Home End  first/last",
    "",
    "Act",
    "  /            search (one criterion line)",
    "  Esc          clear search, or cancel a prompt",
    "  c            create     m modify",
    "  p / P        print / print all of Current Result",
    "  x Delete     delete — Yes/No",
    "  d            dismiss the first alarm",
    "",
    "File",
    "  w            save       W save as (asks for a path)",
    "  o            load (open a .pim file)",
    "  in the file browser: ↑↓ Enter open  ⌫ up  ~ home",
    "               / or Tab type a path  Ctrl-U clear it",
    "  q            quit",
    "  :            type a full verb command",
    "  ?            this help",
    "",
    "Selectors: arrows, a letter or number, Enter. Esc cancels.",
    "Dates: month grid + 15-minute times. Do not type ISO.",
    "",
    MENU,
    "",
    "Any key closes this help.",
)


def title_bar_text(title: str, width: int) -> str:
    """Fit ``PIM  <file>`` into ``width`` columns, keeping the end of the path.

    The file name and the unsaved ``*`` matter most, so a long folder path is
    trimmed from the left and never runs into the clock.
    """
    if display_width(title) <= width:
        return title
    head, sep, path = title.partition("  ")
    if not sep:
        return clip(title, width)
    return head + sep + clip_left(path, width - display_width(head + sep))


def run_curses(terminal) -> None:
    """Run the curses session for ``terminal`` until it stops."""
    curses.wrapper(lambda stdscr: CursesUI(terminal, stdscr).loop())


class CursesUI:
    """One curses session bound to a ``Terminal``."""

    def __init__(self, terminal, stdscr):
        self.term = terminal
        self.stdscr = stdscr
        self.buffer = ""
        self.cursor = 0
        # Text the typed path field was pre-filled with, until it is submitted or cancelled.
        self._prefill: str | None = None
        self.raw_command = False
        self.show_help = False
        self.print_open = False
        self.print_scroll = 0
        self.choice_index = 0
        self._chooser_id = None
        self._last_snapshot = None
        self.theme = Theme(has_color=False)

    def loop(self) -> None:
        """Main loop: paint on change, ``get_wch`` with a 500ms timeout."""
        curses.curs_set(1)
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        # ncurses waits a full second after Esc for an escape sequence; arrow
        # keys arrive well inside 25 ms, so a lone Esc cancels at once.
        curses.set_escdelay(25)
        self.stdscr.timeout(500)
        self.theme = init_theme(curses)
        if self.theme.rich:
            try:
                self.stdscr.bkgd(" ", self.theme.attr(PAGE))
            except curses.error:
                pass
        self.term._running = True
        if not self.term.app.status:
            self.term._status("c create   / search   ? help")
        self._paint(force=True)
        while self.term._running:
            self._paint(force=False)
            try:
                ch = self.stdscr.get_wch()
            except curses.error:
                continue
            except KeyboardInterrupt:
                self._safe(self.term._handle_interrupt)
                continue
            self._handle_key(ch)

    def _attr(self, role: str, extra: int = 0) -> int:
        return self.theme.attr(role, extra)

    def _sync_chooser(self) -> Chooser | None:
        """Reset the highlight when a new selector appears."""
        chooser = self.term.current_chooser()
        ident = id(chooser) if chooser is not None else None
        if ident != self._chooser_id:
            self._chooser_id = ident
            self.choice_index = chooser.default if chooser is not None else 0
        if chooser is not None:
            self.choice_index = chooser.clamp(self.choice_index)
        return chooser

    def _is_search_prompt(self) -> bool:
        label = self.term._prompt_label().casefold()
        return "criterion" in label

    def _composer_h(self) -> int:
        chooser = self.term.current_chooser()
        picker = self.term.current_picker()
        text_prompt = bool(self.term._prompts) or self.raw_command or bool(self.buffer)
        _, width = self.stdscr.getmaxyx()
        return composer_height(
            chooser=chooser,
            text_prompt=text_prompt,
            picker=picker,
            width=width,
            extra_hint=self._is_search_prompt(),
            browser=self.term.current_browser(),
        )

    def _snapshot(self):
        height, width = self.stdscr.getmaxyx()
        now = self.term._now_dt()
        clock = now.strftime("%Y-%m-%d %H:%M") if isinstance(now, datetime) else ""
        chooser = self.term.current_chooser()
        picker = self.term.current_picker()
        pick = None
        if picker is not None:
            pick = (picker.day.isoformat(), picker.hour, picker.minute, picker.focus, picker.view.isoformat())
        browser = self.term.current_browser()
        return (
            self.term._snapshot(),
            self.buffer,
            self.cursor,
            self.raw_command,
            self.show_help,
            self.print_open,
            self.print_scroll,
            self.choice_index,
            None if chooser is None else chooser.title,
            pick,
            None if browser is None else browser.state(),
            height,
            width,
            clock,
        )

    def _paint(self, force: bool) -> None:
        snap = self._snapshot()
        if not force and snap == self._last_snapshot:
            return
        self._draw()
        self._last_snapshot = snap

    def _put(self, y: int, x: int, text: str, attr: int = 0, width: int | None = None) -> None:
        height, width_scr = self.stdscr.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width_scr:
            return
        limit = width_scr - x
        if y == height - 1:
            limit = max(0, limit - 1)
        if width is not None:
            limit = min(limit, width)
        if limit <= 0:
            return
        piece = clip(str(text).replace("\t", " "), limit)
        try:
            self.stdscr.addstr(y, x, piece, attr)
        except curses.error:
            pass

    def _fill(self, y: int, attr: int, x: int = 0, width: int | None = None) -> None:
        height, scr_w = self.stdscr.getmaxyx()
        if y < 0 or y >= height:
            return
        span = scr_w - x if width is None else width
        if y == height - 1:
            span = min(span, max(0, scr_w - x - 1))
        if span <= 0:
            return
        try:
            self.stdscr.addstr(y, x, " " * span, attr)
        except curses.error:
            pass

    def _blank(self, y: int, x: int, h: int, w: int) -> None:
        """Clear the inside of an ``h`` by ``w`` box, so a pop-up never shows the panes behind it."""
        for row in range(y + 1, y + h - 1):
            self._fill(row, 0, x + 1, w - 2)

    def _frame(self, y: int, x: int, h: int, w: int, title: str, attr: int = 0) -> None:
        """Titled widget border using ACS line drawing."""
        if h < 2 or w < 2:
            self._put(y, x, clip(title, max(0, w)), attr | curses.A_BOLD)
            return
        try:
            self.stdscr.hline(y, x, curses.ACS_HLINE, w)
            bottom = y + h - 1
            self.stdscr.hline(bottom, x, curses.ACS_HLINE, w)
            for row in range(y + 1, bottom):
                self.stdscr.addch(row, x, curses.ACS_VLINE, attr)
                if x + w - 1 >= 0:
                    self.stdscr.addch(row, x + w - 1, curses.ACS_VLINE, attr)
            self.stdscr.addch(y, x, curses.ACS_ULCORNER, attr)
            self.stdscr.addch(y, x + w - 1, curses.ACS_URCORNER, attr)
            self.stdscr.addch(bottom, x, curses.ACS_LLCORNER, attr)
            self.stdscr.addch(bottom, x + w - 1, curses.ACS_LRCORNER, attr)
        except curses.error:
            pass
        if title:
            label = clip(f" {title} ", max(0, w - 2))
            self._put(y, x + 1, label, attr | curses.A_BOLD)

    def _draw(self) -> None:
        self.stdscr.erase()
        if self.theme.rich:
            try:
                self.stdscr.bkgd(" ", self._attr(PAGE))
            except curses.error:
                pass
        height, width = self.stdscr.getmaxyx()
        chooser = self._sync_chooser()
        picker = self.term.current_picker()
        browser = self.term.current_browser()
        geo = compute_geometry(height, width, self._composer_h())
        self.term.page_size = max(1, geo.list_h - 2)
        if geo.too_small:
            self._put(0, 0, "Widen the terminal to use the PIM.", self._attr(ERR, curses.A_BOLD))
            screen = self.term.screen()
            if screen.alarms:
                self._draw_alarm(geo, screen, width)
            self._put(min(2, height - 1), 0, "q quits.", self._attr(QUIET))
            self.stdscr.move(min(3, height - 1), 0)
            self.stdscr.noutrefresh()
            curses.doupdate()
            return
        screen = self.term.screen()
        now = self.term._now_dt()
        clock = now.astimezone(HKT).strftime("HKT %H:%M") if isinstance(now, datetime) else ""
        bar = self._attr(TITLE)
        self._fill(geo.title_y, bar)
        clock_x = max(0, width - display_width(clock) - 2) if clock else width
        self._put(geo.title_y, 1, title_bar_text(screen.title, clock_x - 3), bar)
        if clock:
            self._put(geo.title_y, clock_x, clock, bar)
        self._draw_alarm(geo, screen, width)
        modal = picker is not None or browser is not None or self.show_help or (self.print_open and screen.print_text)
        if modal:
            self._dim_body(geo, height, width)
        self._draw_panes(geo, screen)
        self._draw_status(geo, screen, width)
        self._draw_composer(geo, screen, chooser, picker, width, browser)
        if picker is not None:
            self._draw_picker(width, height, picker)
        if browser is not None:
            self._draw_browser(width, height, browser)
        if self.print_open and screen.print_text:
            self._draw_overlay(width, height, "PRINT", screen.print_text, self.print_scroll)
        if self.show_help:
            self._draw_overlay(width, height, "HELP", "\n".join(HELP_LINES), 0)
        hide_cursor = bool(chooser) or picker is not None or browser is not None or self.show_help or self.print_open
        if not hide_cursor and not (self.term._prompts or self.raw_command or self.buffer):
            hide_cursor = True
        try:
            curses.curs_set(0 if hide_cursor else 1)
            if not hide_cursor:
                field_w = max(1, width - 4)
                _visible, caret_x = input_window(self.buffer, self.cursor, field_w)
                self.stdscr.move(geo.composer_y + 1, min(width - 2, 2 + caret_x))
        except curses.error:
            pass
        self.stdscr.noutrefresh()
        curses.doupdate()

    def _dim_body(self, geo, height: int, width: int) -> None:
        """Quiet the diary under a modal; the alarm stamp stays loud."""
        quiet = self._attr(QUIET)
        for y in range(geo.list_header_y, geo.composer_y):
            if 0 <= y < height:
                self._fill(y, quiet)

    def _draw_alarm(self, geo, screen, width: int) -> None:
        if not screen.alarms:
            self._fill(geo.alarm_y, self._attr(QUIET))
            self._put(geo.alarm_y, 1, "Alarms  ·  none", self._attr(QUIET))
            return
        first = screen.alarms[0]
        role = OVERDUE if first.status == "OVERDUE" else SOON
        attr = self._attr(role)
        extra = f"  +{len(screen.alarms) - 1} more" if len(screen.alarms) > 1 else ""
        text = (
            f" {first.status}  Id {first.event_id}  {first.description}  "
            f"{first.when}{extra}   d dismiss"
        )
        self._fill(geo.alarm_y, attr)
        self._put(geo.alarm_y, 0, clip(text, width - 1), attr)

    def _draw_panes(self, geo, screen) -> None:
        inner_h = max(1, min(geo.list_h, geo.status_y - geo.list_y) - 1)
        selected = next((i for i, row in enumerate(screen.rows) if row.selected), None)
        scroll = visible_list_window(len(screen.rows), selected, max(1, inner_h - 1))
        list_title = list_pane_title(screen, first=scroll, visible=max(0, inner_h - 1))
        if screen.selected_id is None:
            detail_title = "Detail"
        else:
            kind = screen.detail_kind or ""
            detail_title = f"Detail · Id {screen.selected_id}" + (f" · {kind}" if kind else "")
        rule = self._attr(RULE)
        if geo.stacked:
            list_h = geo.detail_header_y - geo.list_header_y
            detail_h = geo.status_y - geo.detail_header_y
            self._frame(geo.list_header_y, 0, list_h, geo.width, list_title, rule)
            self._frame(geo.detail_header_y, 0, detail_h, geo.width, detail_title, rule)
        else:
            pane_h = geo.status_y - geo.list_header_y
            self._frame(geo.list_header_y, 0, pane_h, geo.list_w, list_title, rule)
            self._frame(geo.detail_header_y, geo.detail_x, pane_h, geo.detail_w, detail_title, rule)
        self._draw_list(geo, screen)
        self._draw_detail(geo, screen)

    def _draw_list(self, geo, screen) -> None:
        inner_x = geo.list_x + 1
        inner_w = max(1, geo.list_w - 2)
        y = geo.list_y
        last = min(geo.list_y + geo.list_h, geo.status_y - 1)
        if y >= last:
            return
        if not screen.rows:
            self._put(y, inner_x, clip(EMPTY_INVITE, inner_w), self._attr(QUIET, curses.A_BOLD))
            return
        self._put(y, inner_x, format_list_header(inner_w, short_time_col=True), self._attr(QUIET))
        y += 1
        height = last - y
        selected = next((i for i, row in enumerate(screen.rows) if row.selected), None)
        scroll = visible_list_window(len(screen.rows), selected, height)
        for offset in range(height):
            index = scroll + offset
            if index >= len(screen.rows):
                break
            row = screen.rows[index]
            self._paint_list_row(y + offset, inner_x, inner_w, row)

    def _paint_list_row(self, y: int, x: int, width: int, row) -> None:
        line = format_list_row(row, width, short_time_col=True)
        if row.selected:
            attr = self._attr(SELECT)
            self._fill(y, attr, x, width)
            self._put(y, x, clip(line, width), attr)
            return
        self._put(y, x, line, 0)
        pin = TYPE_PIN.get(row.type_name, "?")
        pin_x = x + display_width(f"{'>' if row.selected else ' '}{row.index:3d} {row.pir_id:3d} ")
        role = PIN_ROLES.get(row.type_name, QUIET)
        if pin_x < x + width:
            self._put(y, pin_x, pin, self._attr(role, curses.A_BOLD))

    def _draw_detail(self, geo, screen) -> None:
        inner_x = geo.detail_x + 1
        inner_w = max(1, geo.detail_w - 2)
        y = geo.detail_y
        last = min(geo.detail_y + geo.detail_h, geo.status_y - 1)
        if y >= last:
            return
        if not screen.detail:
            self._put(y, inner_x, clip("Select a row to read it here", inner_w), self._attr(QUIET))
            return
        heading = screen.detail_heading or ""
        if heading:
            self._put(y, inner_x, clip(heading, inner_w), curses.A_BOLD)
            y += 1
        label_w = min(14, inner_w)
        for key, value in card_fields(screen.detail):
            if y >= last:
                break
            self._put(y, inner_x, clip(key, label_w), self._attr(QUIET))
            remain = inner_w - label_w
            chunks = wrap(str(value), max(1, remain)) if remain > 0 else []
            if chunks:
                self._put(y, inner_x + label_w, chunks[0], 0)
            y += 1
            for chunk in chunks[1:]:
                if y >= last:
                    break
                self._put(y, inner_x + label_w, chunk, 0)
                y += 1

    def _draw_status(self, geo, screen, width: int) -> None:
        kind = screen.status_kind or "info"
        if kind == "err":
            attr = self._attr(ERR)
        elif kind == "ok":
            attr = self._attr(OK)
        else:
            attr = self._attr(QUIET)
        text = screen.status
        if not text and not screen.rows:
            text = EMPTY_INVITE
            attr = self._attr(QUIET)
        self._fill(geo.status_y, self._attr(PAGE) if self.theme.rich else 0)
        self._put(geo.status_y, 1, clip(text, width - 2), attr)

    def _draw_composer(
        self,
        geo,
        screen,
        chooser: Chooser | None,
        picker: DateTimePicker | None,
        width: int,
        browser: FileBrowser | None = None,
    ) -> None:
        rule = self._attr(TITLE)
        if browser is not None:
            label = self.term._prompt_label().strip().rstrip(":")
            self._frame(geo.composer_y, 0, geo.composer_h, width, label, rule)
            self._put(geo.composer_y + 1, 2, clip_left(browser.highlighted_path(), width - 4), self._attr(SELECT))
            return
        if picker is not None:
            self._frame(geo.composer_y, 0, geo.composer_h, width, picker.title, rule)
            self._put(geo.composer_y + 1, 2, clip(picker.summary(), width - 4), self._attr(SELECT))
            return
        if chooser is not None:
            self._frame(geo.composer_y, 0, geo.composer_h, width, chooser.title, rule)
            self._draw_chips(geo.composer_y + 1, 2, max(1, width - 4), chooser, self.choice_index)
            if geo.composer_h >= 3:
                self._put(
                    geo.composer_y + geo.composer_h - 1,
                    2,
                    clip(chooser.hint, width - 4),
                    self._attr(QUIET),
                )
            return
        if self.term._prompts or self.raw_command or self.buffer:
            label = self._field_title(screen)
            self._frame(geo.composer_y, 0, geo.composer_h, width, label, rule)
            field_w = max(1, width - 4)
            visible, _caret = input_window(self.buffer, self.cursor, field_w)
            if not self.buffer and self._is_search_prompt():
                self._put(geo.composer_y + 1, 2, clip(SEARCH_EXAMPLE, field_w), self._attr(QUIET))
            else:
                self._put(geo.composer_y + 1, 2, clip(visible if visible else " ", field_w), 0)
            if geo.composer_h >= 4 and self._is_search_prompt():
                self._put(geo.composer_y + 2, 2, clip(SEARCH_HINT, field_w), self._attr(QUIET))
            return
        self._fill(geo.composer_y, self._attr(QUIET))
        self._put(geo.composer_y, 1, clip(idle_hints(screen.criterion_line is not None or bool(screen.filter_label != "all")), width - 2), self._attr(QUIET))
        if geo.composer_h > 1:
            self._fill(geo.composer_y + 1, self._attr(QUIET))
            invite = EMPTY_INVITE if not screen.rows else "c create   / search   ? keys"
            self._put(geo.composer_y + 1, 1, clip(invite, width - 2), self._attr(QUIET))

    def _field_title(self, screen) -> str:
        if self.raw_command:
            return "Command"
        label = screen.prompt.rstrip()
        if label.endswith(":"):
            label = label[:-1].strip()
        if self._is_search_prompt():
            return "Search — one criterion"
        return label or "Input"

    def _draw_chips(self, y: int, x: int, width: int, chooser: Chooser, index: int) -> None:
        """Horizontal option chips, wrapping onto following rows."""
        rows = wrap_chips(chooser, index, width)
        for row_i, row in enumerate(rows):
            cursor = x
            for cell in row:
                self._put(y + row_i, cursor, cell.text, self._chip_attr(cell.tone, cell.selected))
                cursor += display_width(cell.text) + 1

    def _chip_attr(self, tone: str | None, selected: bool) -> int:
        role = TONE_ROLES.get(tone or "", TITLE)
        extra = curses.A_REVERSE | curses.A_BOLD if selected else curses.A_BOLD
        return self._attr(role, extra)

    def _draw_picker(self, width: int, height: int, picker: DateTimePicker) -> None:
        """Calendar overlay: month grid (Mon–Sun) and a 15-minute time list."""
        box_w = min(width - 2, 64)
        box_h = min(height - 2, 18)
        y0 = max(0, (height - box_h) // 2)
        x0 = max(0, (width - box_w) // 2)
        self._blank(y0, x0, box_h, box_w)
        self._frame(y0, x0, box_h, box_w, picker.title, self._attr(TITLE))
        inner_w = box_w - 2
        month = f"<  {picker.month_title()}  >"
        month_attr = self._attr(SELECT) if picker.focus == "date" else self._attr(TITLE)
        self._put(y0 + 1, x0 + 2, clip(month, 24), month_attr)
        time_x = x0 + 30
        if time_x + 10 < x0 + box_w:
            time_attr = self._attr(SELECT) if picker.focus == "time" else self._attr(QUIET)
            self._put(y0 + 1, time_x, "Time", time_attr)
        header_y = picker_weekday_row(y0)
        self._put(header_y, x0 + 2, " ".join(WEEKDAYS), self._attr(QUIET))
        for row, week in enumerate(picker.weeks()):
            y = header_y + 1 + row
            if y >= y0 + box_h - 3:
                break
            x = x0 + 2
            for day in week:
                cell = f"{day.day:2d} "
                in_month = day.month == picker.view.month
                selected = day == picker.day
                today = day == picker.today
                if selected and picker.focus == "date":
                    attr = self._attr(SELECT)
                elif today:
                    attr = self._attr(TITLE) | curses.A_UNDERLINE
                elif in_month:
                    attr = 0
                else:
                    attr = self._attr(QUIET)
                self._put(y, x, cell, attr)
                x += 3
        slots = picker.time_slots()
        slot_y0 = picker_time_origin(y0)
        for index, (hour, minute) in enumerate(slots):
            y = slot_y0 + index
            if y >= y0 + box_h - 3:
                break
            label = f"{hour:02d}:{minute:02d}"
            selected = (hour, minute) == (picker.hour, picker.minute)
            if selected and picker.focus == "time":
                attr = self._attr(SELECT)
                label = "▸ " + label
            elif selected:
                attr = self._attr(TITLE)
                label = "· " + label
            else:
                attr = self._attr(QUIET)
                label = "  " + label
            if time_x + 8 < x0 + box_w:
                self._put(y, time_x, label, attr)
        summary_y = y0 + box_h - 3
        self._put(
            summary_y,
            x0 + 2,
            clip("Using  " + picker.summary(), inner_w),
            self._attr(OK),
        )
        skip = "  n skip" if not picker.required else ""
        hint = f"arrows day  Tab time  [ ] month  t today{skip}  Enter  Esc"
        self._put(y0 + box_h - 2, x0 + 2, clip(hint, inner_w), self._attr(QUIET))

    def _draw_browser(self, width: int, height: int, browser: FileBrowser) -> None:
        """Folder browser overlay: current folder, a scrolling list, key hints."""
        box_w = min(width - 2, 72)
        # Folder line, rows, optional error, hint, and borders; at least 10 so the box is steady.
        wanted = len(browser.entries) + (6 if browser.error else 5)
        box_h = min(height - 2, 20, max(10, wanted))
        y0 = max(0, (height - box_h) // 2)
        x0 = max(0, (width - box_w) // 2)
        inner_w = max(1, box_w - 4)
        self._blank(y0, x0, box_h, box_w)
        self._frame(y0, x0, box_h, box_w, browser.title, self._attr(TITLE))
        self._put(y0 + 1, x0 + 2, clip_left(str(browser.cwd), inner_w), self._attr(QUIET))
        list_y = y0 + 2
        list_h = max(1, box_h - 4)
        if browser.error:
            self._put(y0 + box_h - 3, x0 + 2, clip(browser.error, inner_w), self._attr(ERR))
            list_h = max(1, list_h - 1)
        entries = browser.entries
        first = visible_list_window(len(entries), browser.index, list_h)
        if not entries and not browser.error:
            self._put(list_y, x0 + 2, clip("(no folders or .pim files)", inner_w), self._attr(QUIET))
        for offset, entry in enumerate(entries[first : first + list_h]):
            selected = first + offset == browser.index
            marker = "▸ " if selected else "  "
            if selected:
                attr = self._attr(SELECT)
            elif entry.kind == FILE:
                attr = self._attr(OK)
            elif entry.kind in {FOLDER, PARENT}:
                attr = 0
            else:
                attr = self._attr(QUIET)
            self._put(list_y + offset, x0 + 2, clip(marker + entry.label(), inner_w), attr)
        hint = "↑↓ Enter open  ⌫ up  ~ home  / or Tab type  Esc"
        self._put(y0 + box_h - 2, x0 + 2, clip(hint, inner_w), self._attr(QUIET))

    def _draw_overlay(self, width: int, height: int, title: str, body: str, scroll: int) -> None:
        inner_w = min(width - 4, max(40, width * 3 // 4))
        inner_h = min(height - 4, max(8, height * 3 // 4))
        wrapped: list[str] = []
        for raw in body.splitlines() or [""]:
            wrapped.extend(wrap(raw if raw else " ", inner_w - 4) or [" "])
        max_scroll = max(0, len(wrapped) - (inner_h - 2))
        scroll = min(max(0, scroll), max_scroll)
        view = wrapped[scroll : scroll + inner_h - 2]
        shown = f"{title}  {scroll + 1}–{scroll + len(view)} of {len(wrapped)}" if wrapped else title
        self._box(width, height, shown, view, box_w=inner_w, box_h=inner_h)

    def _box(self, width: int, height: int, title: str, lines: list[str], box_w=None, box_h=None) -> None:
        box_w = box_w or min(width - 4, max(36, max((display_width(line) for line in lines), default=20) + 4))
        box_h = box_h or min(height - 2, len(lines) + 2)
        box_w = max(20, min(box_w, width - 2))
        box_h = max(3, min(box_h, height - 2))
        y0 = max(0, (height - box_h) // 2)
        x0 = max(0, (width - box_w) // 2)
        self._blank(y0, x0, box_h, box_w)
        self._frame(y0, x0, box_h, box_w, title, self._attr(TITLE))
        for i, line in enumerate(lines[: box_h - 2]):
            self._put(y0 + 1 + i, x0 + 2, clip(line, box_w - 4), 0)

    def _safe(self, fn) -> None:
        try:
            fn()
        except PIMError as exc:
            self.term._status(message_for(exc), "err")
        except OSError as exc:
            self.term._status(message_for(exc), "err")
        except Exception as exc:
            # Last resort, as in the line loop: fail the command, keep the session.
            self.term._status(message_for(exc), "err")

    def _handle_key(self, ch) -> None:
        if ch == curses.KEY_RESIZE:
            self._paint(force=True)
            return
        if self.show_help:
            self.show_help = False
            return
        if self.print_open:
            if self._handle_print_key(ch):
                return
        if ch in (4, "\x04"):
            self._safe(self.term._handle_eof)
            return
        if ch in (3, "\x03"):
            self._safe(self.term._handle_interrupt)
            return
        self._sync_chooser()
        if self.term.current_browser() is not None:
            if self._handle_browser_key(ch):
                return
        if self.term.current_picker() is not None:
            if self._handle_picker_key(ch):
                return
        if self.term.current_chooser() is not None:
            if self._handle_chooser_key(ch):
                return
        if ch in (curses.KEY_ENTER, 10, 13, "\n", "\r"):
            self._submit()
            return
        if ch in (27, "\x1b"):
            self._escape()
            return
        editing = bool(self.term._prompts) or self.raw_command or bool(self.buffer)
        if not editing:
            action = self._action(ch)
            if action == COMMAND:
                self.raw_command = True
                self.buffer = ""
                self.cursor = 0
                return
            if action == KEY_HELP:
                self.show_help = True
                return
            if action is not None:
                before = self.term.app.print_text
                self._safe(lambda: self.term.apply_accelerator(action))
                if self.term.app.print_text and self.term.app.print_text != before:
                    self.print_open = True
                    self.print_scroll = 0
                return
        self._edit(ch)

    def _handle_picker_key(self, ch) -> bool:
        """True when the calendar consumed the key."""
        picker = self.term.current_picker()
        if picker is None:
            return False
        if ch in (curses.KEY_ENTER, 10, 13, "\n", "\r"):
            self._picker_submit(picker.value())
            return True
        if ch in (27, "\x1b"):
            self._escape()
            return True
        if ch in ("\t", 9) or ch == getattr(curses, "KEY_BTAB", -1):
            picker.toggle_focus()
            return True
        if isinstance(ch, str) and ch in {"t", "T"}:
            picker.jump_today(self.term._now_dt())
            return True
        if isinstance(ch, str) and ch in {"n", "N"} and not picker.required:
            self._picker_submit("none")
            return True
        if ch in ("[", "<") or ch == curses.KEY_PPAGE:
            picker.move_month(-1)
            return True
        if ch in ("]", ">") or ch == curses.KEY_NPAGE:
            picker.move_month(1)
            return True
        if picker.focus == "time":
            if ch in (curses.KEY_UP, "k"):
                picker.move_time(-15)
                return True
            if ch in (curses.KEY_DOWN, "j"):
                picker.move_time(15)
                return True
            if ch in (curses.KEY_LEFT, "h"):
                picker.move_time(-60)
                return True
            if ch in (curses.KEY_RIGHT, "l"):
                picker.move_time(60)
                return True
            if ch in ("-", "_"):
                picker.move_time(-1)
                return True
            if ch in ("+", "="):
                picker.move_time(1)
                return True
            return True
        if ch in (curses.KEY_LEFT, "h"):
            picker.move_day(-1)
            return True
        if ch in (curses.KEY_RIGHT, "l"):
            picker.move_day(1)
            return True
        if ch in (curses.KEY_UP, "k"):
            picker.move_day(-7)
            return True
        if ch in (curses.KEY_DOWN, "j"):
            picker.move_day(7)
            return True
        return True

    def _handle_browser_key(self, ch) -> bool:
        """True when the folder browser consumed the key.

        `/` and Tab leave the browser for the typed path field (pre-filled with
        `/` or the current folder), so any path can still be typed. `~` opens
        the home folder.
        """
        browser = self.term.current_browser()
        if browser is None:
            return False
        if ch in (curses.KEY_ENTER, 10, 13, "\n", "\r"):
            if browser.wants_typing():
                self._type_path(browser.typed_start())
                return True
            path = browser.activate()
            if path is not None:
                self._picker_submit(path)
            return True
        if ch in (27, "\x1b"):
            self._escape()
            return True
        if ch in (curses.KEY_UP, "k"):
            browser.move(-1)
        elif ch in (curses.KEY_DOWN, "j"):
            browser.move(1)
        elif ch == curses.KEY_PPAGE:
            browser.move(-10)
        elif ch == curses.KEY_NPAGE:
            browser.move(10)
        elif ch in (curses.KEY_HOME, "g"):
            browser.jump(last=False)
        elif ch in (curses.KEY_END, "G"):
            browser.jump(last=True)
        elif ch in (curses.KEY_BACKSPACE, 127, 8, "\x7f", "\b", curses.KEY_LEFT, "h"):
            browser.go_up()
        elif ch in (curses.KEY_RIGHT, "l"):
            entry = browser.current()
            if entry is not None and entry.kind in {FOLDER, PARENT}:
                browser.activate()
        elif ch == "~":
            browser.go_home()
        elif ch == "/":
            self._type_path("/")
        elif ch in ("\t", 9):
            self._type_path(browser.typed_start())
        return True

    def _type_path(self, prefill: str) -> None:
        """Close the browser and continue in the typed path field."""
        self.term.type_path_instead()
        self.buffer = prefill
        self.cursor = len(prefill)
        self._prefill = prefill

    def _picker_submit(self, value: str) -> None:
        self.buffer = ""
        self.cursor = 0
        self._safe(lambda: self.term._handle_line(value))

    def _handle_chooser_key(self, ch) -> bool:
        """True when the selector consumed the key."""
        chooser = self.term.current_chooser()
        if chooser is None:
            return False
        if ch in (curses.KEY_ENTER, 10, 13, "\n", "\r"):
            self._chooser_submit(chooser)
            return True
        if ch in (27, "\x1b"):
            self._escape()
            return True
        if ch in (curses.KEY_LEFT, curses.KEY_UP, "h", "k"):
            self.choice_index = chooser.move(self.choice_index, -1)
            return True
        if ch in (curses.KEY_RIGHT, curses.KEY_DOWN, "l", "j"):
            self.choice_index = chooser.move(self.choice_index, 1)
            return True
        if ch in (curses.KEY_HOME,):
            self.choice_index = 0
            return True
        if ch in (curses.KEY_END,):
            self.choice_index = chooser.clamp(len(chooser.options) - 1)
            return True
        if isinstance(ch, str) and len(ch) == 1:
            picked = chooser.pick_key(ch)
            if picked is not None:
                self.choice_index = picked
                self._chooser_submit(chooser)
                return True
        return True

    def _chooser_submit(self, chooser: Chooser) -> None:
        value = chooser.value_at(self.choice_index)
        self.buffer = ""
        self.cursor = 0
        before = self.term.app.print_text
        self._safe(lambda: self.term._handle_line(value))
        if self.term.app.print_text and self.term.app.print_text != before:
            self.print_open = True
            self.print_scroll = 0

    def _action(self, ch) -> str | None:
        if isinstance(ch, str):
            return action_for_char(ch)
        name = curses.keyname(ch)
        if isinstance(name, bytes):
            name = name.decode("ascii", "replace")
        return action_for_key_name(name)

    def _handle_print_key(self, ch) -> bool:
        if ch in (27, "\x1b", "q", "Q", curses.KEY_ENTER, 10, 13, "\n", "\r"):
            self.print_open = False
            return True
        if ch in (curses.KEY_UP, "k"):
            self.print_scroll = max(0, self.print_scroll - 1)
            return True
        if ch in (curses.KEY_DOWN, "j"):
            self.print_scroll += 1
            return True
        if ch == curses.KEY_PPAGE:
            self.print_scroll = max(0, self.print_scroll - 10)
            return True
        if ch == curses.KEY_NPAGE:
            self.print_scroll += 10
            return True
        return False

    def _submit(self) -> None:
        line = self.buffer
        was_search = self._is_search_prompt()
        self._prefill = None
        self.buffer = ""
        self.cursor = 0
        self.raw_command = False
        before = self.term.app.print_text
        self._safe(lambda: self.term._handle_line(line))
        if was_search and getattr(self.term.app, "status_kind", "") == "err":
            self.buffer = line
            self.cursor = len(line)
            self.term.retry_search_prompt()
            return
        if self.term.app.print_text and self.term.app.print_text != before:
            self.print_open = True
            self.print_scroll = 0

    def _escape(self) -> None:
        if self.print_open:
            self.print_open = False
            return
        prefilled = self._prefill is not None and self.buffer == self._prefill
        self._prefill = None
        if prefilled and self.term._prompts:
            # The path the browser pre-filled was never edited, so there is
            # nothing of the user's to clear: one Esc cancels the prompt.
            self.buffer = ""
            self.cursor = 0
            self._safe(self.term.cancel_prompt)
            return
        if self.buffer or self.raw_command:
            self.buffer = ""
            self.cursor = 0
            self.raw_command = False
            self.term._status("command cancelled")
            return
        if self.term._prompts:
            self._safe(self.term.cancel_prompt)
            return
        self._safe(self.term.idle_escape)

    def _edit(self, ch) -> None:
        if ch in (21, "\x15"):
            # Ctrl-U: clear to the start, e.g. a pre-filled folder before typing a new path.
            self.buffer = self.buffer[self.cursor :]
            self.cursor = 0
            return
        if ch in (curses.KEY_BACKSPACE, 127, 8, "\x7f", "\b"):
            if self.cursor > 0:
                self.buffer = self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
                self.cursor -= 1
            return
        if ch == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
            return
        if ch == curses.KEY_RIGHT:
            self.cursor = min(len(self.buffer), self.cursor + 1)
            return
        if ch in (curses.KEY_HOME,):
            self.cursor = 0
            return
        if ch in (curses.KEY_END,):
            self.cursor = len(self.buffer)
            return
        if ch == curses.KEY_DC:
            self.buffer = self.buffer[: self.cursor] + self.buffer[self.cursor + 1 :]
            return
        if isinstance(ch, str) and ch.isprintable():
            self.buffer = self.buffer[: self.cursor] + ch + self.buffer[self.cursor :]
            self.cursor += 1
