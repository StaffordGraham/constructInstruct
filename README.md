# Bridge Instructional Deal Workshop

Build and tweak instructional bridge deals by hand, then export them to the
Declarer Play Tutor in one keystroke. The design is in [SPEC.md](SPEC.md).

```
python bridge_workshop.py              # start empty
python bridge_workshop.py deal.json    # open a workshop or tutor file
python -m unittest discover -s tests -t .
```

Standard library only (Python 3.10+, Tkinter).

## Quick reference

| Do this | How |
|---|---|
| Select cards | click (click again to deselect); `Ctrl+A` selects the unused cards |
| Move selection | `N` `E` `S` `W`, or `P` / `Delete` for the pool |
| Swap two cards | select both, `X` (or Shift-drag one onto the other) |
| Drag | drag any card — from a hand or the pool grid — onto a hand or the pool |
| Type a whole hand | double-click the hand's title, enter `AKJ74.K3.A62.Q85` |
| Command line (`Ctrl+L`) | `DQ E` · `DQ x D7` · `SAKQ N` · `HJ P` · `N: AKJ74.K3.A62.Q85` · `lead DK` |
| Opening lead | right-click a card → *Set as opening lead*, or the Deal panel |
| Undo / redo | `Ctrl+Z` / `Ctrl+Y` |
| Keep a layout | `Ctrl+K` (Versions panel; double-click to restore) |
| Test Hand | `F5` — writes tutor JSON to the target file (asked once) and copies it to the clipboard |

Test → *Set command to run after export…* can launch anything after each export;
`{file}` is replaced by the exported path.
