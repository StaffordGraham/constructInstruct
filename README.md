# Bridge Instructional Deal Workshop

Build and tweak instructional bridge deals by hand, then export them to the
Declarer Play Tutor in one keystroke. The design is in [SPEC.md](SPEC.md).

```
python bridge_workshop.py              # start empty
python bridge_workshop.py deal.json    # open a workshop or tutor file
python -m unittest discover -s tests -t .
```

Standard library only (Python 3.10+, Tkinter). File → Export to Word also needs
`pip install python-docx`.

The SmallCards compatibility tests also run SmallCards' own code. They need Node.js and the
SmallCards folder next to this one, and are skipped when either is missing.

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
| Play-test | `F5` — plays the deal in SmallCards, in a window of its own, with no files written. Press `F5` again after a change and the open window starts the new version. Every finished hand is recorded with the deal: Test → *Play-test results…* |
| Test Hand | `Shift+F5` — writes tutor JSON to the target file (asked once) and copies it to the clipboard |
| Add to a library | **Save Deal To Library** (toolbar, or File menu) — pick any `.js` file containing `const libDeals = [`; the deal is appended to the end of the array |

Test → *Set command to run after export…* can launch anything after each export;
`{file}` is replaced by the exported path.

Play-test uses the SmallCards folder next to this one, or asks for it once
(Test → *Set SmallCards folder…*). In the SmallCards window, **Restart** starts the hand
again and **Show All Hands** turns East and West face up. Back and Replay work as usual.

**Files stay on this computer.** Open and Save dialogs always open in a folder on this
computer: the folder last used, or else the home folder for files (File → *Home folder
for files…*; `C:\Users\<you>\Projects` until one is chosen). They never start in
OneDrive, and saving into a OneDrive folder asks first.

## Book projects

A book is a folder of small JSON files: `book.json` (sections in order), one file per
chapter (its hands and training hands), and one file per deal. The format is in SPEC.md §4.4.

**Book → Open book…** shows the book's outline to the left of the deal: sections,
chapters, their hands and training hands, and *Unplaced hands* (hands in the book but
not yet in a chapter). The book reopens by itself next time.

| Do this | How |
|---|---|
| Edit a hand | click it in the outline; its cards and text are saved with `Ctrl+S` as usual |
| Edit a section or chapter | click it: title, introduction and notes appear below the outline and save as you type |
| Put a hand in a chapter | right-click the hand → *Put in chapter…*, or right-click the chapter → *Add an unplaced hand* |
| New hand / training hand | right-click the chapter |
| Reorder | select, then ▲ ▼ (hands stay before training hands; a chapter at the end of a section moves into the next) |
| Add sections and chapters | right-click the book title or a section |
| Bring hands in | Book → *Bring hands into the book…* (deal files or `.js` libraries), or open any deal and Book → *Add this deal to the book* |
| Remove | right-click → *Remove…*; the file goes to the book's `removed` folder, not the bin |

A chapter's **To do** list shows what it still needs: hands with no concept, fewer than
five training hands, and hands SmallCards can't play yet. A chapter with nothing left to
do turns green in the outline.

A project can also be started from a text outline on the command line:

```
python -m workshop.book_import new <folder> --title "Learn Declarer Play" --plan "Book Outline.txt"
python -m workshop.book_import add <folder> "Hand 1.json" dealLibraryBook.js
```
