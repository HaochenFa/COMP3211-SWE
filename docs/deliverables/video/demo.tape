# System video (brief 3d): the demo script from docs/BACKLOG.md, typed into
# the real curses UI and rendered to dist/demo.mp4 (at most 4 minutes).
#
#   brew install vhs            # once; also installs ttyd
#   vhs docs/deliverables/video/demo.tape   # from the repository root
#
# The PIM runs inside tmux (demo.tmux.conf) so its status line can carry a
# caption. Each caption is set while VHS is hidden. HOME is a throwaway
# folder under /tmp, so the folder browser never shows a real home folder.

Output dist/demo.mp4

Require tmux
Require python3

Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 22
Set Width 1920
Set Height 1080
Set Padding 12
Set Framerate 30
Set TypingSpeed 45ms

Hide
Type@1ms `export BASH_SILENCE_DEPRECATION_WARNING=1; rm -rf /tmp/pim-demo && mkdir -p /tmp/pim-demo/student/Documents && ln -s "$PWD/pim.py" /tmp/pim-demo/student/Documents/pim.py && tmux -L pimdemo -f docs/deliverables/video/demo.tmux.conf new-session -s demo -c /tmp/pim-demo/student/Documents -e HOME=/tmp/pim-demo/student -e PS1='\W $ ' -e BASH_SILENCE_DEPRECATION_WARNING=1 'bash --norc --noprofile'`
Enter
Sleep 1.5s
Ctrl+B
Type@1ms `:set -g status-left " COMP3211 PIM  ·  a command-line Personal Information Manager  ·  Python 3.12, standard library only "`
Enter
Type@1ms "clear"
Enter
Sleep 300ms
Show

Sleep 1.5s
Type "python3 pim.py"
Sleep 400ms
Enter
Sleep 4.5s

# --- US1, US2: Note ---------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 1/17  US1, US2  ·  Create a Note: press c, then n, then type the text "`
Enter
Show
Sleep 1s
Type "c"
Sleep 1.2s
Type "n"
Sleep 600ms
Type "Shopping: milk, eggs, bread"
Sleep 400ms
Enter
Sleep 3.5s

# --- US3: Task with a deadline ---------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 2/17  US3  ·  Create a Task: the deadline is picked from a calendar in Hong Kong Time "`
Enter
Show
Sleep 800ms
Type "c"
Sleep 800ms
Type "t"
Sleep 500ms
Type "Submit COMP3211 SRS"
Enter
Sleep 1.5s
Down
Sleep 600ms
Down
Sleep 600ms
Tab
Sleep 500ms
Down
Sleep 400ms
Down
Sleep 1s
Enter
Sleep 3.5s

# --- US4: Event with two alarms ----------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 3/17  US4  ·  Create an Event: a start time and two alarms, one relative and one absolute "`
Enter
Show
Sleep 800ms
Type "c"
Sleep 800ms
Type "e"
Sleep 500ms
Type "COMP3211 lecture"
Enter
Sleep 1.5s
Enter
Sleep 1.2s
Type "y"
Sleep 1s
Type "r"
Sleep 1.2s
Type "1"
Sleep 1.2s
Type "y"
Sleep 1s
Type "a"
Sleep 1.2s
Up
Sleep 1s
Enter
Sleep 1.2s
Hide
Ctrl+B
Type@1ms `:set -g status-left " 4/17  Alarm Alerts  ·  OVERDUE and SOON alarms show in the program itself; d dismisses one "`
Enter
Show
Type "n"
Sleep 5.5s

# --- US5: Contact ------------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 5/17  US5  ·  Create a Contact: name, address, and mobile number "`
Enter
Show
Sleep 800ms
Type "c"
Sleep 800ms
Type "c"
Sleep 500ms
Type "Ada Lovelace"
Enter
Sleep 500ms
Type "1 Science Park, Sha Tin"
Enter
Sleep 500ms
Type "91234567"
Enter
Sleep 4s

# --- US7: search --------------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 6/17  US7  ·  Search: a type test and a contains test joined by && "`
Enter
Show
Sleep 800ms
Type "/"
Sleep 1.2s
Type `type = event && description contains "comp"`
Sleep 600ms
Enter
Sleep 4.5s

# --- US8: print ---------------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 7/17  US8  ·  Print every field of the selected PIR, with each alarm's effective time "`
Enter
Show
Sleep 800ms
Type "p"
Sleep 6.5s
Escape
Sleep 1s

# --- US6: modify --------------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 8/17  US6  ·  Modify: Enter keeps a field. Move the start one day later "`
Enter
Show
Sleep 800ms
Type "m"
Sleep 1.5s
Enter
Sleep 1.2s
Right
Sleep 1s
Enter
Sleep 1.2s
Type "n"
Sleep 1.5s
Hide
Ctrl+B
Type@1ms `:set -g status-left " 9/17  US6  ·  The relative alarm moved with the start; the absolute alarm stayed "`
Enter
Show
Type "p"
Sleep 7s
Escape
Sleep 1s

# --- US7: || and ! ------------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 10/17  US7  ·  Esc shows every PIR again. Then search with || and ! "`
Enter
Show
Sleep 800ms
Escape
Sleep 1.5s
Type "/"
Sleep 1s
Type `type = contact || !(contains "comp")`
Sleep 600ms
Enter
Sleep 5s
Escape
Sleep 1s

# --- invalid input ------------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 11/17  Invalid input  ·  one clear error, no crash, nothing changed; the typed criterion stays "`
Enter
Show
Sleep 800ms
Type "/"
Sleep 1s
Type "deadline < tomorrow"
Sleep 500ms
Enter
Sleep 5s
Ctrl+U
Sleep 400ms
Escape
Sleep 1s

# --- US8: print all -----------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 12/17  US8  ·  print all: every PIR in the Current Result "`
Enter
Show
Sleep 800ms
Type "P"
Sleep 5.5s
PageDown
Sleep 4.5s
Escape
Sleep 1s

# --- US9: delete --------------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 13/17  US9  ·  Delete the selected PIR after a Yes / No question "`
Enter
Show
Sleep 800ms
Up 4
Sleep 1s
Type "x"
Sleep 1.5s
Type "y"
Sleep 4s

# --- US10: save ---------------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 14/17  US10  ·  Save as a .pim file from the folder browser "`
Enter
Show
Sleep 800ms
Type "W"
Sleep 3.5s
Enter
Sleep 1s
Type "coursework"
Sleep 500ms
Enter
Sleep 4.5s

# --- US11: quit, start again, load ---------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 15/17  US11  ·  Quit, start again, and load the file: the same PIRs with the same Ids "`
Enter
Show
Sleep 800ms
Type "q"
Sleep 1.5s
Type "python3 pim.py"
Sleep 300ms
Enter
Sleep 3.5s
Type "o"
Sleep 3.5s
Down
Sleep 800ms
Enter
Sleep 5s

Hide
Ctrl+B
Type@1ms `:set -g status-left " 16/17  Ids are never reused: the new Note gets Id 5, not Id 1 "`
Enter
Show
Sleep 800ms
Type "c"
Sleep 800ms
Type "n"
Sleep 500ms
Type "Buy printer paper"
Enter
Sleep 4.5s

# --- dirty quit ---------------------------------------------------------------
Hide
Ctrl+B
Type@1ms `:set -g status-left " 17/17  Unsaved changes: quit asks Save / Discard / Cancel and never drops them silently "`
Enter
Show
Sleep 800ms
Type "q"
Sleep 4s
Type "s"
Sleep 3.5s

Hide
Ctrl+B
Type@1ms `:set -g status-left " US1 - US11 shown  ·  python3 -m unittest: every test passes, 100%% line coverage of the model package "`
Enter
Sleep 300ms
Type@1ms "clear"
Enter
Show
Sleep 5.5s

Hide
Type "exit"
Enter
Sleep 500ms
