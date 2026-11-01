# Palamedes — Bridge Writer's Studio

*In Greek legend, Palamedes invented games, among them dice and draughts, to pass the time at the siege of Troy, and taught the Greeks letters and numbers.*

Palamedes is where a bridge book is written. In one window you:

- **build each hand** card by card, with the contract, the opening lead and how the defenders play;
- **organise the book** into sections and chapters, each chapter with its teaching hands and five training hands;
- **write the commentary** for each hand, with the diagram beside you;
- **set up coaching**, so SmallCards corrects a student at the key moment of a hand;
- **play-test** any hand in SmallCards with one key;
- **print** a chapter or the whole book as a Word document, ready for Amazon KDP;
- **make the SmallCards library**, so students can play every hand in the book.

Palamedes is the one place where the book lives. The Word documents and the
SmallCards library are made from it, and are made again whenever you ask. Make every
change in Palamedes, never in the Word documents or the library files.

---

## Contents

1. [Starting the program](#1-starting-the-program)
2. [The window](#2-the-window)
3. [Building a hand](#3-building-a-hand)
4. [Contract, leads, the defence, and the Hand tab](#4-contract-leads-the-defence-and-the-hand-tab)
5. [Saving and opening hands](#5-saving-and-opening-hands)
6. [Play-testing in SmallCards](#6-play-testing-in-smallcards)
7. [Working with the book](#7-working-with-the-book)
8. [Writing the commentary](#8-writing-the-commentary)
9. [Coaching checkpoints](#9-coaching-checkpoints)
10. [Printing: Word and Amazon KDP](#10-printing-word-and-amazon-kdp)
11. [The SmallCards library for students](#11-the-smallcards-library-for-students)
12. [Older library tools](#12-older-library-tools)
13. [Where everything is kept](#13-where-everything-is-kept)
14. [Keys at a glance](#14-keys-at-a-glance)
15. [When something goes wrong](#15-when-something-goes-wrong)

---

## 1. Starting the program

**What it needs:**

- **Python** must be installed.
- **python-docx** is needed for printing to Word. If it's missing, install it once by
  typing `pip install python-docx` in a terminal.
- **SmallCards** should be in the folder next to Palamedes's own folder
  (`C:\Users\sgcam\Projects\SmallCards`). Play-testing uses it.
- **Word** is needed to open the printed chapters and to make the PDF.

**To start:**

1. Open Palamedes's folder, `C:\Users\sgcam\Projects\InstructConstruct`, in VS Code.
   (The folder keeps the program's old name, InstructConstruct.)
2. Open a terminal (**Terminal → New Terminal**).
3. Type `python bridge_workshop.py` and press Enter.

The window opens. If you had a book open last time, it opens again by itself.

To open a single hand file at the same time, add its name after the command:
`python bridge_workshop.py "Hand 1.json"`.

---

## 2. The window

```
┌ toolbar ───────────────────────────────────────────────────────────────────────────────┐
├ book outline ──┬ diagram ───────────────────────────────┬ tabs: Hand, Commentary, …    ┤
│ sections,      │        North                           │  Book, Section, Chapter,     │
│ chapters and   │  West           East                   │  Hand, title; contract,      │
│ hands          │        South                           │  leads, defence              │
│                │  card pool (cards not yet dealt)       │  — or concept, commentary    │
│ details of the │                                        │  — or the coaching           │
│ selected item  │                                        │  — or the versions           │
├────────────────┴────────────────────────────────────────┴──────────────────────────────┤
│ N 13  E 13  S 13  W 13 │ 52/52 assigned │ Missing │ Duplicates │ Ready to test         │
│ status messages                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Toolbar:** New, Open, Save, Undo and Redo, plus the most-used card actions and the
  **▶ Play-test (F5)** button. The **Command** box lets you type moves (section 3).
- **Book outline (left):** appears when a book is open (section 7).
- **Diagram (middle):** the four hands round the table. The **card pool** below them
  holds every card not yet dealt.
- **Tabs (right):**
  - **Hand:** where the hand belongs (Book, Section, Chapter, Hand) and its title, then
    the contract, leads and the defenders' plays (section 4).
  - **Commentary:** the hand's concept and commentary, both printed in the book, and
    your own notes, which are not (section 8).
  - **Coaching:** SmallCards' coaching points (section 9).
  - **Versions:** layouts you have kept (section 3).
- **Check bar (bottom):** shows how many cards each hand has, which cards are missing or
  duplicated, and whether the hand is ready. Red means something needs fixing;
  **✔ Ready to test** means the hand is complete.
- **Status line (very bottom):** tells you what just happened, and why when something
  couldn't be done.

---

## 3. Building a hand

There are several ways to put cards where you want them. Use whichever feels easiest.

**Click and press a letter**

1. Click one or more cards (in the pool or in a hand). Selected cards are highlighted.
   Click again to deselect.
2. Press **N**, **E**, **S** or **W** to send them to that hand. Press **P** (or Delete) to
   send them back to the pool.

**Drag:** drag a card from the pool or a hand onto any hand, or back to the pool.

**Swap two cards:** select both and press **X**, or hold Shift and drag one onto the
other.

**Type a whole hand:** double-click a hand's title (e.g. NORTH) and type it suit by suit,
spades first, with a full stop between suits: `AKJ74.K3.A62.Q85`.

**Command box:** press **Ctrl+L** (or click in the Command box) and type, then Enter:

| Type | Means |
|---|---|
| `DQ E` | ♦Q to East |
| `SAKQ N` | ♠A, ♠K and ♠Q to North |
| `HJ P` | ♥J back to the pool |
| `DQ x D7` | swap ♦Q and ♦7 |
| `N: AKJ74.K3.A62.Q85` | North's whole hand |
| `lead DK` | ♦K is the opening lead |

**Other useful actions:**

- **Ctrl+A** selects every card still in the pool.
- **Complete Deal** deals the remaining pool cards at random to the hands that are short.
  Cards you have already placed stay where they are.
- **Clear Deal** sends every card back to the pool (it asks first).
- **Undo / Redo:** Ctrl+Z and Ctrl+Y, as many steps as you like.
- **Right-click** a card or a hand for a menu of the same actions.

**Versions:** to keep a layout before trying a change, press **Ctrl+K** (or Snapshot in
the Versions tab). Double-click a version to go back to it.

---

## 4. Contract, leads, the defence, and the Hand tab

The contract, leads and defence are on the **Hand** tab, below the hand's place in the
book.

**Contract:** choose the level, the suit and the declarer. SmallCards needs **South** to
be declarer.

**Opening lead:** choose it in the Deal panel, or right-click a card in the leader's hand
→ *Set as opening lead*. The lead shows in the diagram.

**Later leads:** for each defender, add the card they lead at their next chances to
lead (Lead opportunity 1, 2, …).

**Defensive Play Overrides:** use these when a defender must play a particular card.
For example: "the 1st time hearts are led, East plays ♥Q". Choose the player, the suit
led, which time it is led, and the card, then press **Add Override**.

### The Hand tab: Book, Section, Chapter, Hand

The **Hand** tab follows the plan of the book: **Book → Section → Chapter → Hand**. None
of it is shown to students, except through the printed book.

**For a hand in your book** (a book is open and the hand was opened from its outline):

| Line | What it is |
|---|---|
| **Book** | the book's title |
| **Section** | choose the section from the list |
| **Chapter** | choose the chapter of that section; *(not in a chapter)* takes the hand out |
| **Hand** | *Hand* (a teaching hand) or *Training hand*; its number and code are shown beside it, e.g. **Hand 2 (II.2.2)** |
| **Hand title** | the hand's own title, e.g. *Basic Play* |
| **Source** and **page** | where the hand came from, if it came from another book (e.g. *Breakthrough Bridge*, page 49) |

Choosing a Section and Chapter **puts the hand there in the book**, just as the outline
does, and the outline moves it at once. Moving it in the outline updates the Hand tab.

**For a hand on its own** (no book open, or not one of its hands), Book, page, Section
and Chapter are typed in.

The hand's concept and commentary are on the **Commentary** tab (section 8).

---

## 5. Saving and opening hands

- **Save (Ctrl+S)** saves the hand you are working on. The title bar shows **\*** when
  there are unsaved changes.
- **Save as… (Ctrl+Shift+S)** saves a copy under a new name.
- **Open (Ctrl+O)** opens a hand file. **File → Open recent** lists recent ones.
- **New (Ctrl+N)** starts an empty hand.

If you leave a hand with unsaved changes, Palamedes asks whether to save them first.

**Files stay on your computer.** Open and Save always start in a folder on this computer,
never in OneDrive: the folder you last used, or else your **home folder for files**. Set
that with **File → Home folder for files…**; until you do, it is
`C:\Users\sgcam\Projects`. If you choose a OneDrive folder for saving, Palamedes
asks you to confirm.

---

## 6. Play-testing in SmallCards

Press **F5** (or the **▶ Play-test** button). The hand opens in SmallCards, in a window of
its own, exactly as a student will see it. Nothing is saved or exported.

- **Play the hand as South.** SmallCards defends exactly as it will for students.
- **The bar at the top of the SmallCards window:**
  - **Restart** starts the hand again;
  - **Show All Hands** turns East and West face up, so you can watch the defence.
- **Back** takes back a card or trick; **Replay** starts again after the hand is over.
- **After a change**, press **F5** again in Palamedes. The open SmallCards window
  starts the new version within a second.
- **When you finish a hand**, the result comes back to Palamedes and is kept
  with the hand: the status line says, for example, "12 tricks in 4 Spades — made".
  **Test → Play-test results…** lists every play-test of this hand, trick by trick, and
  whether it was played on the current layout or an earlier one.

**F5 refuses a hand SmallCards can't play** and says why on the status line: missing
cards, no contract, South not declarer, or no opening lead from West.

**Test → Set SmallCards folder…** is needed only if SmallCards is not next to
Palamedes.

**Shift+F5** is the older **Test Hand**: it writes the hand to a tutor file and copies it
to the clipboard.

---

## 7. Working with the book

### Starting or opening a book

- **Book → New book…** asks for the title and where to keep the book, and makes a
  folder named after the title there. The book starts empty: plan it with the buttons
  described below.
- **Book → New book from an outline…** does the same, but takes the sections and
  chapters from an outline you have already written: a text file with lines starting
  *Section …* and *Chapter …*, or a Word plan (Heading 1 for sections, Heading 2 for
  chapters). Lines such as *Hand 1*, *Concept* or *Display* are ignored.
- **Book → Open book…** and choose the book's folder (for this book,
  `C:\Users\sgcam\Projects\Book\LearnDeclarerPlay`).
- **Book → Close book** hides the outline.

### The outline

The left side shows the book:

```
Learn Declarer Play
  I    Two Basic Rules                       ← section
     1   Suit Contracts- Draw Trumps         ← chapter
           Hand 1   Basic Play               ← teaching hand
           Hand 2   Hold on To Dummy Trumps
           Training Hand 1   …               ← training hands (up to five)
     2   No Trump Contracts Keep Control
  II   How to Make Tricks
  …
Unplaced hands (10)                          ← in the book, but not yet in a chapter
```

- **Orange** marks something still to do. A chapter turns **green** when it has
  nothing left to do.
- **Click a hand** to open it in the diagram. Edit it as usual and save with **Ctrl+S**.
  The title bar shows where it is in the book, e.g. *Basic Play (I.1.1)*, and the
  **Hand** tab shows its Section, Chapter and Hand, where you can also move it.
- **Click a section, chapter or the book title** to see its details below the outline:
  the title, introduction and notes. These save themselves as you type.
- **A hand that is planned but not yet dealt** is marked *(not dealt yet)*.

### Planning the book: Book, Section, Chapter, Hand

The buttons under the outline build and change the plan. Each one works on what is
selected in the outline, and a new item goes **just after** it.

| Button | Does |
|---|---|
| **+ Section** | adds a section after the selected one |
| **+ Chapter** | adds a chapter to the selected section, after the selected chapter |
| **+ Hand** | adds a teaching hand to the selected chapter |
| **+ Training** | adds a training hand to the selected chapter (up to five) |
| **Rename (F2)** | puts the cursor in the selected item's title, ready to type |
| **Remove (Del)** | removes the selected item (see below) |
| **▲ ▼** | moves the selected item up or down |

After **+ Section**, **+ Chapter** or **+ Hand**, the new item's title is already
selected, so just type its name.

**Planning a hand before it is dealt:** after **+ Hand**, type the hand's title and its
**concept** in the boxes below the outline. They are saved as you type. Deal the cards
whenever you are ready; until then the outline marks the hand *(not dealt yet)*.

**Removing:**

- a section can be removed once it has no chapters;
- removing a chapter asks first, and its hands stay in the book under *Unplaced hands*;
- **Remove** on a hand in a chapter takes it out of the chapter, back to *Unplaced
  hands*;
- **Remove** on an unplaced hand takes it out of the book (it asks first).

**Order:** teaching hands always stay ahead of training hands. A chapter at the end of
a section moves into the next section.

**To see the whole plan on paper**, use **Book → Print the book plan (Word)**. It lists
every section, chapter and hand, with each hand's concept, like your own outline.

### Hand codes

Every hand has a code from its place in the book. **II.3.2** is section II, chapter 3,
Hand 2. **II.3.T4** is that chapter's Training Hand 4. Codes update themselves when
things move. They appear in the title bar and in SmallCards (section 11).

### More, with a right-click

The same things, and a few more, are on the right-click menus in the outline:

| To | Right-click | Choose |
|---|---|---|
| Put an unplaced hand in a chapter | the hand | *Put in chapter as a hand* (or *as a training hand*), then the section and chapter — or choose them on the **Hand** tab |
| …or, from the chapter | the chapter | *Add an unplaced hand* (or *…as a training hand*) |
| Start a new hand in a chapter | the chapter | *New hand* or *New training hand* |
| Take a hand out of its chapter | the hand | *Take out of chapter (back to unplaced)* |
| Add a chapter | a section | *Add chapter* |
| Add a section | the book title | *Add section* |
| Remove a hand, chapter or empty section | it | *Remove…* (it asks first) |

**Nothing removed is lost.** A removed hand or chapter goes into the book's
`removed` folder, not the recycle bin.

### Bringing hands in

- **Book → Bring hands into the book…** takes hand files (`.json`) and libraries
  (`.js`). They arrive under *Unplaced hands*. An exact copy of a hand already in the
  book is skipped.
- **Book → Add this deal to the book** adds the hand that is open now. The original file
  is left as it was, and from then on you are editing the book's copy.

### The To do list

Click a chapter or hand to see what it still needs:

- a teaching hand needs a **concept** and **commentary**;
- each chapter plans **five training hands**;
- every hand must be one SmallCards can play;
- any **card mentioned in the commentary** that has since moved is listed, and so is any
  coaching checkpoint whose card has moved.

A chapter that is all text, such as an introduction, needs no hands.

---

## 8. Writing the commentary

Open a hand, then click the **Commentary** tab. The diagram stays in view while you
write. The tab has three parts:

| Part | Printed in the book? |
|---|---|
| **Concept**: the one idea the hand teaches | yes, under the hand's title |
| **Commentary**: the explanation of the hand | yes, after the diagram |
| **Your notes**: crucial play, failure mechanism and notes | no, they are for you only |

**Suit symbols:** type **!s !h !d !c** for **♠ ♥ ♦ ♣**, or click the coloured suit
buttons. A card written as a suit and a rank (♠5, ♥10, ♦A) appears in its suit colour,
in the printed book as well.

**Layout:**

| Type | You get |
|---|---|
| a blank line | a new paragraph |
| `- ` at the start of a line | a bullet point |
| `**words**` (or select and press **Bold**) | **bold** |
| `*words*` (or select and press **Italic**) | *italic* |

**When cards move:** Palamedes remembers which hand each mentioned card was in.
If you later move that card, say ♠5 from dummy to East, it is highlighted in orange
and listed under the text:

> ♠5 was North's when the commentary mentioned it; it is now East's

Either correct the text, or press **The commentary is right for the cards as they are
now**. The warning also appears in the chapter's To do list.

Save with **Ctrl+S**, as for the cards.

Training hands are printed without commentary, so they don't need any.

---

## 9. Coaching checkpoints

On the **Coaching** tab you set the moments in a hand where SmallCards corrects a
student who plays the wrong card. If the student goes wrong:

1. after the first wrong card, SmallCards shows your **hint** and lets them try again;
2. after the second, it names the right card, shows your **explanation**, and plays the
   right card for them.

**To add a checkpoint:**

1. **When:** a trick number, or *First lead of* a suit.
2. **Player:** South or dummy (North).
3. **Correct card(s):** click one or more. Any of them counts as right.
4. **After two misses, play:** which correct card SmallCards plays for the student
   (optional).
5. Type the **hint** and the **explanation**.
6. Press **Add checkpoint**. Press **F5** to try it straight away.

To change a checkpoint, click it in the list, edit it and press **Save changes**.
**Delete** removes it; **New** clears the form.

If a checkpoint's card is later moved out of that player's hand, the checkpoint is
shown in orange and listed in the To do list.

---

## 10. Printing: Word and Amazon KDP

- **F6** (or right-click a chapter → *Open in Word*) makes the chapter you are working
  on into a Word document and opens it. This is the easiest way to see how a chapter
  will look in print.
- **Book → Export the whole book to Word** makes the whole book: title page, contents,
  every section, chapter, hand and training hand. It opens in Word. When Word asks
  whether to **update fields**, say **Yes**; that fills in the contents.
- **Book → Print the book plan (Word)** writes the plan of the book: sections,
  chapters, hands and their concepts, on A4.
- **Book → Open the book's exports folder** shows where the documents are.

**What a chapter looks like:**

- each chapter starts on a new page, with its title and introduction;
- then each hand: *Hand 1: Basic Play*, the concept in italics, the contract
  (4♠ by South), the diagram with the opening lead above West, and the commentary;
- then *Training Hands*, each a diagram with no commentary;
- the page is 6×9 inches, with page numbers, and margins for binding.

If you export a chapter that still has to-do items, the status line says how many.

**Making the PDF for Amazon KDP:** open the whole-book document in Word and choose
**File → Save As → PDF**. Upload that PDF to KDP, with a colour interior.

**Changing fonts, sizes and colours:** these are set in **template.docx** in the book
folder, which is made the first time you export.

1. Open template.docx in Word.
2. Go to **Home → Styles**, right-click a style and choose **Modify**.
3. Save the template.

Every later export follows the change. The styles are:

| Style | Used for |
|---|---|
| Heading 1 | sections |
| Heading 2 | chapters |
| Heading 3 | hands |
| Heading 4 | training hands |
| Concept | the concept under a hand's title |
| Contract | the contract line |
| Diagram | the hands in the diagram |
| Normal | the commentary text |
| Spades, Hearts, Diamonds, Clubs | the suit symbols and their colours |

**Don't edit the exported documents.** The next export replaces them. Change the book in
Palamedes, or the look in template.docx.

---

## 11. The SmallCards library for students

**Book → Make the SmallCards library** puts every hand in the book, in book order, into
one SmallCards library file.

- **The first time**, it asks where to save. It starts in your deal libraries folder
  and suggests *Learn Declarer Play.js*. After that it updates the same file without
  asking.
- **Book → Make the SmallCards library as…** saves it somewhere else.

**In SmallCards**, choose the file with **Select Deal Library**. Students see:

| Hand | Description | Page |
|---|---|---|
| Hand 1: Basic Play | the hand's concept | I.1.1 |
| Training Hand 1 | Training: *chapter title* | I.1.T1 |

The *Page* column holds the hand code, so a reader can find the same hand in the printed
book. Each hand's commentary and coaching checkpoints go with it.

- **Hands not ready** (no contract, no opening lead, cards missing) are left out, and
  Palamedes lists them.
- **Unplaced hands** are not included.
- **Don't edit the library file:** it is made from the book every time.
- **Your hand-made libraries are protected:** Palamedes asks before replacing
  one.

---

## 12. Older library tools

These work on SmallCards library files directly, outside a book. You'll rarely need them
for the book.

- **Save Deal To Library** (toolbar or File menu) adds the hand you are working on to the
  end of a library file you choose.
- **File → Open From Deal Library…** lists the hands in a library.
  - **Open** loads one into the diagram.
  - **Check Out** loads it and removes it from the library; the library keeps a backup
    copy ending `.bak`.
- **Library Manager** (toolbar or File menu) lists a library's hands.
  - **Delete and reorder:** you can delete hands, change their order and save.
  - **Open a hand:** double-click it.
  - **Save Current Deal** adds the hand you are working on.
- **File → Export to Word…** makes a single hand's diagram into a Word document.

---

## 13. Where everything is kept

| What | Where |
|---|---|
| The program | `C:\Users\sgcam\Projects\InstructConstruct` |
| SmallCards | `C:\Users\sgcam\Projects\SmallCards` |
| The book | `C:\Users\sgcam\Projects\Book\LearnDeclarerPlay` |
| Deal libraries | `C:\Users\sgcam\Projects\DealLibraries` |
| Your settings | `C:\Users\sgcam\.bridge_deal_workshop.json` |

**Inside the book folder:**

| File or folder | Holds |
|---|---|
| `book.json` | the title, author, page size and the sections in order |
| `chapters` | one file per chapter: its introduction and its list of hands |
| `deals` | one file per hand, with cards, contract, leads, concept, commentary, coaching and play-test results |
| `template.docx` | the Word styles (section 10) |
| `exports` | the Word documents made from the book |
| `removed` | anything removed from the book, kept just in case |

Each file in `deals` is an ordinary hand file. You can open it with File → Open even
without the book open.

**Backups:** the book is just a folder of small files, so any backup that copies the
folder keeps everything. Keeping it in its own git repository also keeps a history of
every change.

---

## 14. Keys at a glance

| Key | Does |
|---|---|
| **N E S W** | send the selected cards to that hand |
| **P** or **Delete** | send the selected cards to the pool |
| **X** | swap the two selected cards |
| **Esc** | clear the selection |
| **Ctrl+A** | select every card in the pool |
| **Ctrl+L** | go to the Command box |
| **Ctrl+Z / Ctrl+Y** | undo / redo |
| **Ctrl+K** | keep a version of the layout |
| **Ctrl+N** | new hand |
| **Ctrl+O** | open a hand |
| **Ctrl+S** | save |
| **Ctrl+Shift+S** | save as |
| **F5** | play-test in SmallCards |
| **Shift+F5** | Test Hand (write a tutor file) |
| **F6** | open this chapter in Word |
| **F2** (in the outline) | rename the selected section, chapter or hand |
| **Delete** (in the outline) | remove the selected item |
| **!s !h !d !c** | ♠ ♥ ♦ ♣ (in the commentary) |

While you are typing in a text box, the card keys (N E S W, P, X) type letters as usual.

---

## 15. When something goes wrong

**F5 says the hand can't be play-tested.** The status line says why. Usually a hand is
short of cards, there is no contract, South is not declarer, or there is no opening lead
from West.

**The SmallCards window doesn't come to the front.** Click it on the taskbar. It has
already received the new hand.

**"The document is open in Word, so it can't be replaced."** Close that chapter or book
in Word, then export again.

**"Export to Word needs python-docx."** In a terminal, type `pip install python-docx`,
then try again.

**The contents page in the book is empty.** In Word, right-click the contents and choose
**Update Field**, then **Update entire table**.

**The book won't open.** The message names the file that has a problem. If you edited
that file by hand, undo the edit or put back a copy from your backup.

**A hand seems to have disappeared from the book.** Look under *Unplaced hands*, then in
the book's `removed` folder.

**A file dialog opened somewhere unexpected.** Set your home folder with
**File → Home folder for files…**.
