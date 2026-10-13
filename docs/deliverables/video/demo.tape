# System video (brief 3d): the demo script from docs/BACKLOG.md, typed into
# the real curses UI. Do not run this tape on its own; render.py runs it,
# adds the caption bar, and writes dist/demo.mp4 (at most 4 minutes):
#
#   brew install vhs            # once; also installs ttyd
#   python3 docs/deliverables/video/render.py   # from the repository root
#
# The PIM runs inside tmux (demo.tmux.conf). Each step starts with a
# `# caption: <tag> | <text>` line, which render.py reads, and flips the
# tmux status line between green and magenta while VHS is hidden. The flips
# tell render.py where each step starts in the recording, so the number of
# caption lines must equal the number of steps. HOME is a throwaway folder
# under /tmp, so the folder browser never shows a real home folder.
#
# Pace: each step waits about 2 s after its caption appears before the
# first key, so the caption can be read before anything moves.

Output dist/demo-raw.mp4

Require tmux
Require python3

Set Shell "bash"
Set FontFamily "Menlo"
Set FontSize 22
Set Width 1920
Set Height 980
Set Padding 12
Set Framerate 30
Set TypingSpeed 55ms

# caption: Start | python3 pim.py opens an empty, untitled collection
Hide
Type@1ms `export BASH_SILENCE_DEPRECATION_WARNING=1; rm -rf /tmp/pim-demo && mkdir -p /tmp/pim-demo/student/Documents && ln -s "$PWD/pim.py" /tmp/pim-demo/student/Documents/pim.py && tmux -L pimdemo -f docs/deliverables/video/demo.tmux.conf new-session -s demo -c /tmp/pim-demo/student/Documents -e HOME=/tmp/pim-demo/student -e PS1='\W $ ' -e BASH_SILENCE_DEPRECATION_WARNING=1 'bash --norc --noprofile'`
Enter
Sleep 1.5s
Type@1ms "clear"
Enter
Sleep 300ms
Show
Sleep 1.8s
Type "python3 pim.py"
Sleep 600ms
Enter
Sleep 4s

# caption: US1 · US2 | Create a Note: press c, pick Note, then type the text
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#ff00ff"`
Enter
Show
Sleep 1.8s
Type "c"
Sleep 1.3s
Type "n"
Sleep 900ms
Type "Shopping: milk, eggs, bread"
Sleep 500ms
Enter
Sleep 3.5s

# caption: US3 | Create a Task: the deadline is picked from a calendar in Hong Kong Time
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Show
Sleep 1.8s
Type "c"
Sleep 900ms
Type "t"
Sleep 700ms
Type "Submit COMP3211 SRS"
Enter
Sleep 1.8s
Down
Sleep 700ms
Down
Sleep 700ms
Tab
Sleep 700ms
Down
Sleep 600ms
Down
Sleep 1.3s
Enter
Sleep 3.5s

# caption: US4 | Create an Event: a start time and two alarms, one relative and one absolute
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#ff00ff"`
Enter
Show
Sleep 1.8s
Type "c"
Sleep 900ms
Type "e"
Sleep 700ms
Type "COMP3211 lecture"
Enter
Sleep 1.8s
Enter
Sleep 1.5s
Type "y"
Sleep 1.2s
Type "r"
Sleep 1.5s
Type "1"
Sleep 1.5s
Type "y"
Sleep 1.2s
Type "a"
Sleep 1.5s
Up
Sleep 1.2s
Enter
Sleep 1.5s

# caption: Alarm Alerts | OVERDUE and SOON alarms show inside the program; d dismisses one
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Show
Sleep 1.5s
Type "n"
Sleep 5s

# caption: US5 | Create a Contact: name, address, and mobile number
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#ff00ff"`
Enter
Show
Sleep 1.8s
Type "c"
Sleep 900ms
Type "c"
Sleep 700ms
Type "Ada Lovelace"
Enter
Sleep 700ms
Type "1 Science Park, Sha Tin"
Enter
Sleep 700ms
Type "91234567"
Enter
Sleep 4s

# caption: US7 | Search: a type test and a contains test joined by &&
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Show
Sleep 1.8s
Type "/"
Sleep 1.3s
Type `type = event && description contains "comp"`
Sleep 800ms
Enter
Sleep 5s

# caption: US8 | Print every field of the selected PIR, with each alarm's effective time
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#ff00ff"`
Enter
Show
Sleep 1.8s
Type "p"
Sleep 7s
Escape
Sleep 1s

# caption: US6 | Modify: Enter keeps a field. Move the start one day later
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Show
Sleep 1.8s
Type "m"
Sleep 1.6s
Enter
Sleep 1.3s
Right
Sleep 1.3s
Enter
Sleep 1.3s
Type "n"
Sleep 1.6s

# caption: US6 | The relative alarm moved with the start; the absolute alarm stayed
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#ff00ff"`
Enter
Show
Sleep 1.5s
Type "p"
Sleep 7s
Escape
Sleep 1s

# caption: US7 | Esc shows every PIR again. Then search with || and !
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Show
Sleep 1.8s
Escape
Sleep 1.6s
Type "/"
Sleep 1s
Type `type = contact || !(contains "comp")`
Sleep 800ms
Enter
Sleep 5s
Escape
Sleep 1s

# caption: Invalid input | One clear error, no crash, nothing changed; the typed criterion stays
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#ff00ff"`
Enter
Show
Sleep 1.8s
Type "/"
Sleep 1s
Type "deadline < tomorrow"
Sleep 600ms
Enter
Sleep 5.5s
Ctrl+U
Sleep 400ms
Escape
Sleep 1s

# caption: US8 | print all: every PIR in the Current Result
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Show
Sleep 1.8s
Type "P"
Sleep 5s
PageDown
Sleep 4s
Escape
Sleep 1s

# caption: US9 | Delete the selected PIR after a Yes / No question
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#ff00ff"`
Enter
Show
Sleep 1.8s
Up 4
Sleep 1.2s
Type "x"
Sleep 1.6s
Type "y"
Sleep 4s

# caption: US10 | Save as a .pim file from the folder browser
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Show
Sleep 1.8s
Type "W"
Sleep 3.5s
Enter
Sleep 1.2s
Type "coursework"
Sleep 600ms
Enter
Sleep 4.5s

# caption: US11 | Quit, start again, and load the file: the same PIRs with the same Ids
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#ff00ff"`
Enter
Show
Sleep 1.8s
Type "q"
Sleep 1.6s
Type "python3 pim.py"
Sleep 400ms
Enter
Sleep 3.5s
Type "o"
Sleep 3.5s
Down
Sleep 1s
Enter
Sleep 5s

# caption: Ids | Ids are never reused: the new Note gets Id 5, not Id 1
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Show
Sleep 1.8s
Type "c"
Sleep 900ms
Type "n"
Sleep 700ms
Type "Buy printer paper"
Enter
Sleep 4.5s

# caption: Unsaved changes | Quit asks Save / Discard / Cancel and never drops changes silently
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#ff00ff"`
Enter
Show
Sleep 1.8s
Type "q"
Sleep 4s
Type "s"
Sleep 3.5s

# caption: US1 – US11 | All shown. Every unit test passes, with 100% line coverage of model
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Sleep 300ms
Type@1ms "clear"
Enter
Show
Sleep 5s

Hide
Type "exit"
Enter
Sleep 500ms
