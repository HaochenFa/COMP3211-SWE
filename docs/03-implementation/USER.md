---
title: "User Manual"
subtitle: "Personal Information Management (PIM) System"
short-title: "PIM System · User Manual"
version: "1.4"
date: "8 November 2026"
status: "Final"
deliverable: "Deliverable 3: Implementation"
toc: true
---

# 1. Introduction

The PIM is a personal information manager that runs in a terminal. It keeps four kinds of personal information record (PIR) in one place:

| Type | Fields | Required |
|------------|----------------------------------------------------|----------------------------------|
| Note | `text`, the body of the note | `text` |
| Task | `description`, `deadline` | `description` |
| Event | `description`, `start`, and any number of alarms | `description`, `start` |
| Contact | `name`, `address`, `mobile` | `name` |

Every PIR has an **Id**, a number the system assigns when the record is created. The Id never changes, and it is never given to another record, even after a delete. You can save all your records in a file with the extension `.pim` and load them again later.

All times are in **Hong Kong Time (HKT)** unless you type another time-zone offset.

# 2. Starting the program

You need a Mac with Python 3.12 or newer. Open Terminal (or iTerm), go to the folder that contains `pim.py`, and run:

```
python3 pim.py
```

The program selects an interface based on the terminal:

- In an interactive terminal it opens the **full-screen interface**, which you work mostly with single keys, selectors, and a calendar.
- When its input or output is redirected (for example `python3 pim.py < commands.txt`), it uses the **line interface**: it prints the screen as text and reads one command per line. You can also ask for the line interface with `PIM_NO_CURSES=1 python3 pim.py`.

Both interfaces accept the same commands (Section 5). To leave the program, press `q` or type `quit`.

# 3. The screen

The full-screen interface has five areas, from top to bottom:

- **Title bar.** The name of the open file, or `untitled`, followed by `*` when there are unsaved changes, and the current time in HKT on the right.
- **Alarm band.** The first Event alarm that is OVERDUE or SOON, with `+N more` when there are others; `Alarms  ·  none` when nothing is due (Section 9).
- **Current Result** (left). One row per record: the row number `#`, the Id, a type pin (`N`, `T`, `E`, or `C`), the Display Name, and the deadline or start. When a search is active, the pane title shows the criterion.
- **Details** (right). Every field of the selected record. The Id and type are in the pane title.
- **Composer** (bottom). Key hints when nothing is being asked, otherwise the current question: a selector, a calendar, a folder browser, or a text field. The status line, which reports the outcome of every command, sits just above it.

On a terminal narrower than 80 columns, the list is shown above the details. If the window is smaller than about 60 × 12 characters, the program asks you to enlarge it; `q` still quits. On a terminal with 256 colours the interface uses its own dark colour scheme; with fewer colours it uses reverse video for the title and the selected row.

The line interface prints the same information as plain text after every command:

```
PIM  untitled*
----------------------------------------------------------------------------
ALARMS
  OVERDUE  Id 1  COMP3211 lecture  2026-09-13T18:30:00+08:00
  (dismiss)
----------------------------------------------------------------------------
Current Result (all)
    #   Id  Type      Name                      Time
    1    1  event     COMP3211 lecture          2026-09-14T18:30:00+08:00
>   2    2  contact   Ada
----------------------------------------------------------------------------
DETAIL
  Id: 2
  type: contact
  name: Ada
  address: (none)
  mobile: 12345678
----------------------------------------------------------------------------
Created Contact Id 2
create  search  clear  modify  print  print all  delete  save  save as  load  dismiss  help  quit
>
```

The `>` in the list marks the selected row. The line below the last rule is the status line, followed by the list of commands and the prompt.

# 4. Using the full-screen interface

## 4.1 Keys

These keys act at once when no question is open:

| Key | Action |
|----------------------------|----------------------------------------------------------------------|
| `↑` `↓` or `k` `j` | Select the previous or next row of the Current Result |
| `PgUp` `PgDn`, `Home` `End` | Move a page, or to the first or last row |
| `/` | Search: type one criterion line (Section 7). While the field is empty it shows an example. After a syntax error the typed line stays, so you can correct it |
| `c` | Create a record: choose the type, then answer the field questions |
| `m` | Modify the selected record |
| `p` / `P` | Print the selected record / print every record in the Current Result |
| `x` or `Delete` | Delete the selected record (asks Yes or No) |
| `d` | Dismiss the first alarm in the alarm band |
| `w` | Save (asks for a file when the collection has none yet) |
| `W` | Save as: choose a folder and a file name |
| `o` | Load (open) a `.pim` file |
| `:` | Type a full command, such as `id 4` or `save as work` |
| `?` | Show the key help; any key closes it |
| `Esc` | Cancel the current question or typed command; with nothing open, end the active search. It never discards unsaved changes |
| `q` | Quit |

While a text field is open, type your answer and press Enter. On an optional field, Enter alone leaves it empty.

## 4.2 Selectors

When an answer is one of a few fixed values, the composer shows a **selector** instead of a text field, and you do not type the word. Move with `←` `→` (or `↑` `↓`, `Home`, `End`) and press Enter, or press the option's key, which confirms at once.

| Question | Options and keys | Default |
|-------------------------------------|-----------------------------------------------|------------|
| Type of a new record | Note `n` · Task `t` · Event `e` · Contact `c` (or `1`–`4`) | Note |
| Delete, overwrite, add an alarm, replace alarms | Yes `y` · No `n` | No |
| Alarm kind | Relative `r` · Absolute `a` | Relative |
| When a relative alarm rings | At start `0` · 15 minutes `1` · 1 hour `h` · 1 day `d` · Other… `o` | At start |
| Unit (after Other… and a number) | Minute `m` · Hour `h` · Day `d` · Week `w` | Day |
| Unsaved changes | Save `s` · Discard `d` · Cancel `c` | Cancel |

`Esc` cancels a selector, except the unsaved-changes question: there, press `c` to cancel.

## 4.3 Entering dates and times

Event **start**, Task **deadline**, and the time of an **absolute alarm** open a calendar instead of a text field. The month grid on the left starts each week on Monday, and the time list on the right shows Hong Kong Time in 15-minute steps. The line under the grid shows the value that Enter will use, for example `Using  Tu 15 September 2026  18:30  HKT`.

| Key | Action |
|---------------|---------------------------------------------------------|
| `←` `→` | Grid: previous or next day. Time list: one hour earlier or later |
| `↑` `↓` | Grid: previous or next week. Time list: 15 minutes earlier or later |
| `+` `-` | Time list: one minute later or earlier |
| `Tab` | Switch between the grid and the time list |
| `[` `]` (or `PgUp` `PgDn`) | Previous or next month |
| `t` | Jump to today, keeping the time |
| `n` | Leave an optional deadline empty, or clear it during modify |
| `Enter` | Use the highlighted date and time |
| `Esc` | Cancel the whole create or modify command |

During modify, the calendar opens on the current value, so Enter keeps it. A Task without a deadline opens on the next quarter hour; press `n` to keep it without one.

In a **search** there is no calendar: type the time in the criterion, for example `start < 2026-11-20 20:00`.

## 4.4 Choosing a file

`o` (load) and `W` (save as) open a **folder browser**. It starts in the folder of the open file, or else in the folder from which you started the program, and lists the parent folder `../`, the subfolders, and the `.pim` files. Hidden files are not shown.

| Key | Action |
|----------------------------------------------|----------------------------------------------------------------------|
| `↑` `↓` or `k` `j`, `PgUp` `PgDn`, `Home` `End` or `g` `G` | Move the highlight |
| `Enter`, or `→` / `l` on a folder | Open the folder, or choose the highlighted `.pim` file (save as asks before replacing it) |
| `Backspace`, `←`, or `h` | Go up one folder |
| `~` | Go to your home folder |
| `/` or `Tab` | Type a path instead. `Tab` fills in the current folder and `Ctrl-U` clears the field. While the filled-in path is unchanged, `Esc` cancels at once; after you edit it, the first `Esc` clears the text and the second cancels |
| `Esc` | Cancel |

To save under a new name, choose **+ New file in this folder…**, type the name, and press Enter; `.pim` is added for you. The PIM stays inside the terminal and never opens a Finder window.

## 4.5 Reading printed records

`p` and `P` open a PRINT panel over the screen. Scroll it with `↑` `↓` (or `k` `j`) and `PgUp` `PgDn`, and close it with `Esc`, Enter, or `q`. While the panel is open, `q` closes it rather than quitting.

# 5. Commands

You can type every command in the line interface, and after `:` in the full-screen interface.

| Command | Action |
|----------------------------------------------|----------------------------------------------------------------------|
| `create` or `create note\|task\|event\|contact` | Create a record. Without a type, the program asks for one. You are then asked for each field in turn. |
| `search <criterion>` or `search` | Show only the records that match the criterion (Section 7). Without a criterion, the program asks for one. |
| `clear` | End the search and show every record again. |
| `<n>` (a row number) | Select row `n` of the Current Result. Row numbers change with every search; they are not Ids. |
| `id <n>` | Select the record with Id `n`. |
| `modify` | Change the fields of the selected record (Section 6.2). |
| `print` | Print every field of the selected record. |
| `print all` | Print every record in the Current Result: all records when no search is active, otherwise the matches. Use `clear` first to print everything. |
| `delete` | Delete the selected record after you answer `y`. Its Id is not used again. |
| `save` | Save to the open file. With no open file, this works as `save as`. |
| `save as <path>` or `save as` | Save to a new file and keep working with it (Section 8). |
| `load <path>` or `load` | Replace the records in memory with those in a `.pim` file (Section 8). |
| `dismiss` | Hide the first alarm alert (Section 9). |
| `help` | Show the list of commands on the status line. |
| `quit` (also `q` or `exit`) | Leave the program. With unsaved changes, you are asked to save, discard, or cancel first. |

An unknown command is reported as `unknown command: …` and changes nothing.

# 6. Creating and changing records

## 6.1 Creating

`create` asks for the fields of the chosen type one at a time, naming each field and saying whether it is optional. Leading and trailing spaces are removed. An empty answer, or one made only of spaces, leaves an optional field empty; on a required field it makes the create fail with a message such as `description is required`, and nothing is created.

Dates and times can be typed (in the line interface) as `YYYY-MM-DD HH:MM`, for example `2026-11-20 20:00`, or as an ISO 8601 instant such as `2026-11-20T12:00Z`. A time without an offset is Hong Kong Time, and seconds are ignored.

**Alarms.** After the start of an Event, you are asked `Add an alarm?`. Each alarm is one of two kinds:

- a **relative** alarm rings a whole number of minutes, hours, days, or weeks **before** the start, or exactly at the start. When the start changes, it moves with it;
- an **absolute** alarm rings at a fixed date and time, and does not move when the start changes.

After each alarm you are asked whether to add another. An Event may have no alarms at all.

## 6.2 Modifying

`modify` walks through the fields of the selected record and shows each current value in the question:

- press Enter alone to keep a value;
- on an optional field, type `none` (or only spaces) to clear it;
- type a new value to replace it.

For an Event you are asked `Replace alarms?`. Answer No to keep them. Answer Yes to build a new alarm list; answering No at the first `Add an alarm?` removes every alarm.

The Id and the type of a record never change. To turn a Note into a Task, delete the Note and create a Task. If a new value is invalid, the record stays exactly as it was. A modify that changes nothing reports `No changes` and does not count as an unsaved change.

# 7. Searching

A search criterion is one line made of tests, combined with `&&` (and), `||` (or), `!` (not), and parentheses:

```
type = note|task|event|contact
text|description|name|address|mobile contains "..."
contains "..."
deadline|start|alarm  <  |  >  |  =  <date and time>
```

- `contains` ignores upper and lower case and matches any part of the text; it does not do fuzzy matching. Without a field name, `contains` looks in every text field of the record.
- `<` means before, `>` means after, and `=` means at the same minute. Times are compared as instants, so `start = 2026-09-14T10:30Z` finds an Event that starts at 18:30 HKT.
- A comparison on a field that a record does not have, or has left empty, is false. A Task without a deadline never matches `deadline < …`.
- `alarm` matches an Event if **any** of its alarm times matches.
- `!` binds most tightly, then `&&`, then `||`. Use parentheses when in doubt.
- Keywords and field names may be written in any case. Inside quotation marks, write `\"` for a quotation mark and `\\` for a backslash.

Examples:

```
search type = event && description contains "COMP"
search contains "ada"
search type = task && !(deadline < 2026-12-01 00:00)
search alarm < 2026-09-14 12:00 || start > 2026-10-01 00:00
```

A successful search shows the matching records in Id order, selects the first one, and reports `3 match(es)`. A criterion that cannot be read is reported as `search syntax error: …`, and the list stays as it was. `clear`, or `Esc` in the full-screen interface, shows every record again.

# 8. Saving and loading

**Paths.** A path may be absolute (`/Users/you/Documents/work.pim`), start with `~` for your home folder (`~/Desktop/work`), or be relative to the folder from which you started the program. `.pim` is added when you leave it out, and missing folders are created. After a save or load, the status line shows the full path, for example `Saved /Users/you/Desktop/work.pim`.

**Saving.** `save as` replaces an existing file only after you confirm with Yes. The file is written safely: if the save fails, the previous file is left untouched and your changes stay unsaved.

**Loading.** `load` opens only files that end in `.pim`. If the file is not a valid PIM file, the program reports `not a PIM file: …` and keeps the records you had.

**Unsaved changes.** The `*` in the title bar means that some changes are not saved. Loading another file or quitting then asks you to **save**, **discard**, or **cancel**. Ctrl-C and Ctrl-D in an interactive terminal follow the same rule as quit, so you never lose changes without being asked. When the program reads its commands from a redirected file and the file ends while changes are unsaved, nobody can answer the question: the program ends without saving and prints `input ended: unsaved changes were not saved`.

# 9. Alarm alerts

While the program runs, it watches the alarms of every Event. An alarm is **OVERDUE** once its time has passed and **SOON** when it is due within the next 15 minutes. The alarm band shows the Event's Id, its description, and the time the alarm rings; it updates within half a second, even while you are not typing.

The line interface lists every due alarm. The full-screen interface shows the first one and the number of others. `d` or `dismiss` hides the first alarm until you quit the program. An alarm you dismissed appears again after you load a file or change that Event's alarms. Dismissals are not saved in the file.

# 10. Reading the output

Every command ends with one line on the **status line**: what happened (`Created Event Id 1`, `3 match(es)`, `Saved /Users/you/Desktop/work.pim`) or what went wrong (Section 11). In the full-screen interface, a success is shown in green and an error in red.

The **Display Name** in the list is the first line of a Note, the description of a Task or Event, and the name of a Contact. The time column shows a Task's deadline or an Event's start.

`print` and `print all` show every field. Times are ISO 8601 with their offset, where `+08:00` is Hong Kong Time, and an optional field that is not set shows `(none)`. Each Event alarm shows its kind and the **effective** time at which it rings:

```
  Id: 1
  type: event
  description: COMP3211 lecture
  start: 2026-09-14T18:30:00+08:00
  alarm[0]: relative 1 day before start; effective 2026-09-13T18:30:00+08:00
  alarm[1]: absolute; effective 2026-09-13T09:00:00+08:00

  Id: 2
  type: contact
  name: Ada
  address: (none)
  mobile: 12345678
```

# 11. Error messages

An invalid command never changes your records, never shows a program error trace, and never closes the program. The status line names the problem:

| Status line | Meaning and what to do |
|------------------------------------------------------|----------------------------------------------------------------------|
| `text is required` (also `description`, `start`, `name`, `alarm time`) | A required field was left empty. Run the command again and fill it in. |
| `invalid datetime: …` | The value is not a date and time in the form `YYYY-MM-DD HH:MM` or ISO 8601. |
| `datetime out of range` | The time falls outside the years 1–9999 in Hong Kong Time or UTC, for example `0001-01-01 00:10`. |
| `alarm time is out of range` | A relative alarm would ring before the year 1, for example after a huge number of weeks. |
| `relative alarm amount must be an integer` | Enter a whole number such as `15`, not `1.5`. |
| `relative alarm cannot be after start` | A relative alarm needs a number of 0 or more; use an absolute alarm for a time after the start. |
| `relative alarm unit must be minute, hour, day, or week` | The unit was not one of these four. |
| `unknown PIR type: …` | `create` accepts only `note`, `task`, `event`, or `contact`. |
| `no PIR selected` | `modify`, `print`, or `delete` needs a selected record. Select a row first. |
| `no PIR with Id …` | No record has this Id. |
| `no row … in Current Result` | The row number is outside the list on screen. |
| `search syntax error: …` | The criterion could not be read; the list is unchanged. A bad time in a criterion is reported as `search syntax error: invalid datetime: …`. |
| `path is required` | `save as` or `load` was given an empty path. |
| `file name is required` | The path has no file name, for example only `.pim` or a folder ending in `/`. |
| `path must have a .pim extension` | `load` opens only `.pim` files. |
| `not a PIM file: …` | The file is missing, unreadable, or not a valid PIM file. Your records in memory are unchanged. |
| `cannot save …: …` | The operating system refused the write, for example because permission was denied. Your changes stay unsaved. |
| `unknown command: …` | The command does not exist; type `help` for the list. |
| `enter y or n`, `enter relative or absolute`, `enter save, discard, or cancel` | In the line interface, the answer did not match the question. The question is asked again. |
| `command failed` | An unexpected internal error. The command did nothing, and the program keeps running. |

# 12. Example sessions

**Full-screen interface.** Create a Note, find the lecture Event, and change it:

```
c                     open the type selector
n                     choose Note
Shopping: Milk        type the text and press Enter
/                     open the search field
type = event && description contains "COMP"     then Enter
m                     modify the selected Event
```

**Line interface.** The same kind of work as typed commands, one per line (in the full-screen interface, type `:` before each command):

```
create note
Shopping: Milk
create event
COMP3211 lecture
2026-09-14 18:30
y
relative
1 day
n
search type = event && description contains "COMP"
print
clear
print all
save as demo
quit
```

The first answer after `create event` is the description, then the start, then the alarm questions: `y` adds an alarm, `relative` and `1 day` describe it, and `n` stops adding alarms.
