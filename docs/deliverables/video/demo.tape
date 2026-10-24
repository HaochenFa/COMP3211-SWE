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
# Each caption line is followed by a `# narration: <text>` line: the
# voiceover for that step, spoken by a text-to-speech voice from the moment
# the caption appears. It is written as a presenter would say it while
# demonstrating ("or" for ||, "record" for PIR; the caption carries the story
# number), and must finish before the next step starts; render.py checks this.
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
Set Height 1060
Set Padding 12
Set Framerate 30
Set TypingSpeed 55ms

# caption: Start | Start the PIM. It opens with an empty, untitled collection.
# narration: Hi! Let's take a quick tour of our Personal Information Manager. It opens empty.
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

# caption: US1, US2 | Create a Note: press c, choose Note, and type the text.
# narration: First, a note. I press C, pick Note, and just type what I want to remember.
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

# caption: US3 | Create a Task. Its deadline is picked from a calendar, in Hong Kong time.
# narration: Next, a task. I give it a description, then pick the deadline from this little calendar. All times are in Hong Kong time.
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

# caption: US4 | Create an Event with a start time and two alarms: one relative, one absolute.
# narration: Now an event, for my lecture. After the start time, I'll add two alarms: one that rings a set time before the start, and one at a fixed date and time.
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

# caption: Alarms | An alarm that is due appears in the red bar at the top of the screen.
# narration: And when an alarm comes due, it pops up in this red bar.
Hide
Ctrl+B
Type@1ms `:set -g status-style "bg=#00ff00"`
Enter
Show
Sleep 1.5s
Type "n"
Sleep 5s

# caption: US5 | Create a Contact with a name, an address, and a mobile number.
# narration: Let's add a contact too: a name, an address, and a mobile number.
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

# caption: US7 | Search for Events whose description contains "comp". Only the lecture matches.
# narration: Now let's search. I want events whose description contains "comp"... and there's just the lecture.
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

# caption: US8 | Print the selected Event, including the time each alarm will ring.
# narration: Pressing P prints the event in full, including exactly when each alarm will ring.
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

# caption: US6 | Modify the Event. Enter keeps a field as it is; the start moves one day later.
# narration: Say the lecture moves a day later. Enter keeps each field as it is, so I only change the start.
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

# caption: US6 | The relative alarm moved with the new start. The absolute alarm did not.
# narration: Printing it again: the relative alarm moved along with the start, but the fixed one stayed put.
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

# caption: US7 | Esc clears the search. The next search combines conditions with || and !.
# narration: Escape clears the search. This time I'll combine conditions with "or" and "not": every contact, plus anything that doesn't mention "comp".
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

# caption: Errors | "tomorrow" is not a valid time, so the PIM explains the error and changes nothing.
# narration: What if I type a time it can't understand, like "tomorrow"? It tells me what's wrong, and nothing changes.
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

# caption: US8 | Print all PIRs in the current list.
# narration: Capital P prints every record in the current list, so I can scroll through them all.
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

# caption: US9 | Delete the selected PIR. The PIM asks for confirmation first.
# narration: To delete a record, I select it and press X. It asks me to confirm first.
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

# caption: US10 | Save the PIRs to a .pim file, choosing the folder in a file browser.
# narration: Time to save. A file browser lets me pick the folder, and I'll call the file "coursework".
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

# caption: US11 | Quit, start again, and load the file. The PIRs come back with the same Ids.
# narration: Now I'll quit, start the app again, and open that file. Everything comes back, and each record keeps the same ID it had before.
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

# caption: Ids | A new Note gets Id 5. The Id of a deleted PIR is never reused.
# narration: A new note gets ID five. IDs are never reused, even after a delete.
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

# caption: Unsaved | Quitting with unsaved changes asks whether to save, discard, or cancel.
# narration: If I quit with unsaved changes, it asks whether to save, discard, or cancel. I'll save.
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

# caption: Done | That covers all eleven user stories, US1 to US11.
# narration: And that's all eleven user stories. Thanks for watching!
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
