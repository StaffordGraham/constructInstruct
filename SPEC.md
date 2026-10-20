# Bridge Instructional Deal Workshop — Specification

A Tkinter desktop tool for **building and adjusting** instructional bridge deals by hand.
It never generates or suggests deals. The author places every card; the workshop
makes placing, moving, swapping, checking and test-exporting those cards fast.

---

## 1. Application specification

### 1.1 Scope

| In scope | Out of scope |
|---|---|
| Manual placement of all 52 cards | Random / constrained deal generation |
| Drag-and-drop, click-select, keyboard and typed entry | Double-dummy analysis, "AI" suggestions |
| One-step swap of two cards | Bidding sequences |
| Live validation and hand statistics | Databases, web technology |
| Author notes per deal | Multi-deal book management (see §9) |
| Named "versions" of a layout inside one file | |
| Save / load workshop JSON | |
| **Test Hand** export to the Declarer Play Tutor JSON | |
| Import of existing tutor / DealCreator JSON files | |

### 1.2 Core data rules

* Every card has exactly **one location**: North, East, South, West or the Pool.
  Because of that, the app cannot create a duplicate. Duplicates can only arrive
  from a file. On load they are detected, kept in the first hand listed, and
  reported in the validation bar.
* Card numbering matches the existing tutor and DealCreator:
  `number = suit × 13 + rank`, where suit 0–3 = ♠ ♥ ♦ ♣ and rank 0–12 = 2…A.
* A deal is **complete** when each hand holds 13 cards and the pool is empty.

### 1.3 Functional requirements

**Card handling**

| # | Requirement | How |
|---|---|---|
| C1 | Pool → hand | Drag a card from the pool onto a hand, or select it and press `N` `E` `S` `W` |
| C2 | Hand → hand | Drag onto the other hand, or select it and press the seat key |
| C3 | Hand → pool | Drag onto the pool, or press `P` / `Delete` |
| C4 | **Swap** | Select card A, select card B, press **Swap** (`X`). Or Shift-drag A onto B |
| C5 | Several cards at once | Click to toggle each card into the selection. Dragging any selected card moves the whole selection |
| C6 | Typed entry for a whole hand | Double-click a hand's title and type PBN-style `AKQ7.J94.K5.432` (♠.♥.♦.♣). Listed cards are pulled from wherever they sit; cards no longer listed go to the pool |
| C7 | Command line | Type `DQ E` (move), `DQ x D7` (swap), `SAKQ N` (several cards of one suit), `HJ P` (to pool) |
| C8 | Undo / redo | `Ctrl+Z` / `Ctrl+Y` on every card change, unlimited within the session |
| C9 | Find a card | The pool shows all 52 positions. A card in a hand appears there dimmed, tagged with its seat letter, and can be selected or dragged from the pool too |

**Validation (always visible)**

* Card count per hand (shown red if not 13), total assigned out of 52.
* Missing cards (cards still in the pool), listed when there are 8 or fewer.
* Duplicate cards found at load time.
* The opening lead must be a card held by the opening leader. A warning appears
  as soon as that card is moved away.
* The tutor needs a contract. Leaving it blank produces a warning.

**Statistics (always visible)**

* HCP per hand (A=4 K=3 Q=2 J=1), N-S and E-W totals.
* Shape per hand in ♠-♥-♦-♣ order, e.g. `4-3-5-1`.

**Deal settings**: contract level (1–7), strain (♠ ♥ ♦ ♣ NT), declarer (N/E/S/W),
opening lead, and optional later leads by each defender. These feed the tutor's
`w_leads` / `e_leads`.

**Author information** (author-only, does not affect cards): Chapter, Hand Title,
Concept, Crucial Play, Failure Mechanism, Notes, plus Book and Page. The tutor
library already uses Book and Page, so they are carried into the export.

**Versions**: **Snapshot** (`Ctrl+K`) stores the current layout under a name,
e.g. "Q♦ with East". Double-clicking a version restores it, and the restore can
be undone. Versions are saved in the file.

**Test Hand** (`F5`) writes the current deal as tutor JSON to a remembered
target file, without a dialog after the first use. It also copies the JSON to the
clipboard and can optionally run a configured command, e.g. to open the tutor. If
the deal is incomplete, Test Hand does not write anything and the status bar
explains why.

### 1.4 Non-functional requirements

* Any card operation redraws in well under 50 ms. The whole diagram is about
  200 canvas items, redrawn on every change.
* Dialogs appear only for choosing a file and for "discard unsaved changes?".
  All other feedback goes to the status bar.
* Standard library only (Python 3.10+, Tkinter). Nothing to install.
* The model and storage layers contain no Tkinter code, so they can be unit tested.

---

## 2. User workflow

**Building a new teaching deal**

1. `Ctrl+N`. All 52 cards sit in the pool.
2. Set the contract, declarer and title in the side panel.
3. Build declarer's hand and dummy first. Either double-click the South title and
   type `AKJ74.K3.A62.Q85`, or click cards in the pool and press `S`.
4. Put the key defensive holding in place, e.g. drag ♦KQ to East.
5. With N-S and the key cards fixed, select the rest of the pool and press `W`.
   Then use the seat keys to move cards from West to East until both hands hold 13.
   The counts turn black when correct.
6. Set the opening lead: right-click the card and choose *Set as opening lead*.
7. `F5` Test Hand → load the file in the tutor and play the right line, then the wrong one.

**The experiment loop**

```
 ┌─► click Q♦ (North) ─► click 7♦ (East) ─► X (swap) ─► F5 ─► play in tutor ─┐
 └──────────────────────────── not right yet ◄───────────────────────────────┘
```

* `Ctrl+Z` steps back if an experiment makes things worse.
* `Ctrl+K` keeps a promising layout as a version before trying something radical.
* `Ctrl+S` saves the layout and its versions.

**Adjusting an existing deal**: open a tutor or DealCreator `.json` file
directly. It is imported, and saving writes a workshop file. Any tutor-only
fields, such as special instructions, are kept and re-exported unchanged.

---

## 3. Screen wireframe

```
┌ Bridge Instructional Deal Workshop — ch4_finesse.json * ─────────────────────────────────────┐
│ [New][Open][Save] │ [Undo][Redo] │ [Swap X][To pool P] │ [▶ Test Hand F5] │ Cmd:[DQ x D7   ] │
├──────────────────────────────────────────────────────────────────┬───────────────────────────┤
│                 ┌ NORTH  13 · 11 HCP · 4-3-3-3 ┐                 │ DEAL                      │
│                 │ ♠ A Q 7 2                    │                 │ Contract [4]  [♥]  by [S] │
│                 │ ♥ K 6 3                      │                 │ Opening lead [♦K      ▾]  │
│                 │ ♦ 9 8 4                      │                 │ Later W leads [♦Q      ]  │
│                 │ ♣ A 5 2                      │                 │ Later E leads [        ]  │
│                 └──────────────────────────────┘                 │───────────────────────────│
│ ┌ WEST 13·9·3-3-4-3 ┐  ┌──────────┐  ┌ EAST 13·7·3-2-3-5 ┐       │ AUTHOR                    │
│ │ ♠ J 9 4           │  │    N     │  │ ♠ 8 6 5           │       │ Book [Mendelson] Pg [22]  │
│ │ ♥ 8 7 5           │  │ W  4♥  E │  │ ♥ 4 2             │       │ Chapter    [4           ] │
│ │ ♦ K Q J 10        │  │    S     │  │ ♦ 7 6 5           │       │ Hand title [Hand 12     ] │
│ │ ♣ J 6 3           │  │ Lead ♦K  │  │ ♣ K 10 9 8 7      │       │ Concept    [............] │
│ └───────────────────┘  │ NS 24    │  └───────────────────┘       │ Crucial play [..........] │
│                        │ EW 16    │                              │ Failure mechanism [.....] │
│                        └──────────┘                              │ Notes                     │
│                 ┌ SOUTH  13 · 13 HCP · 3-5-3-2 ┐                 │ [.......................] │
│                 │ ♠ K 10 3                     │                 │───────────────────────────│
│                 │ ♥ A Q J 10 9                 │                 │ VERSIONS                  │
│                 │ ♦ A 3 2                      │                 │ ┌───────────────────────┐ │
│                 │ ♣ Q 4                        │                 │ │ v1 base               │ │
│                 └──────────────────────────────┘                 │ │ v2 ♣K onside          │ │
│ CARD POOL  (solid = unused, dim = in a hand, letter = seat)      │ └───────────────────────┘ │
│ ♠ [A]N [K]S [Q]N [J]W ... [2]N                                   │ [Snapshot][Restore][Del]  │
│ ♥ ...                                                            │                           │
│ ♦ ...                                                            │                           │
│ ♣ ...                                                            │                           │
├──────────────────────────────────────────────────────────────────┴───────────────────────────┤
│ N 13  E 13  S 13  W 13 │ 52/52 assigned │ Missing: none │ Duplicates: none │ ✔ Ready to test  │
│ status: Swapped ♦Q (N) ↔ ♦7 (E)                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

* Selected cards have a gold fill. The opening-lead card has a blue outline.
* While dragging, the hand under the pointer is highlighted. During a Shift-drag
  the card under the pointer is highlighted instead, because it is the swap target.

---

## 4. JSON schemas

### 4.1 Workshop file (`*.json`, `"format": "bidw"`)

```json
{
  "format": "bidw",
  "version": 1,
  "hands": { "N": "AQ72.K63.984.A52", "E": "865.42.765.KT987",
             "S": "KT3.AQJT9.A32.Q4", "W": "J94.875.KQJT.J63" },
  "pool": "",
  "contract": { "level": 4, "strain": "H", "declarer": "S" },
  "opening_lead": 37,
  "later_leads": { "W": [36], "E": [] },
  "author": {
    "book": "Mendelson", "page": "22", "chapter": "4", "title": "Hand 12",
    "concept": "Avoidance", "crucial_play": "Duck the first diamond",
    "failure_mechanism": "East wins the second diamond and returns a club",
    "notes": ""
  },
  "versions": [
    { "name": "base", "created": "2026-10-17T11:42:00",
      "hands": { "N": "...", "E": "...", "S": "...", "W": "..." } }
  ],
  "tutor_extra": { "si_player": 4, "si_pos": 0, "si_suit": 0, "si_action": 0 },
  "saved": "2026-10-17T11:45:10"
}
```

Formal schema (JSON Schema draft 2020-12, abbreviated):

```json
{
  "type": "object",
  "required": ["format", "version", "hands"],
  "properties": {
    "format":  { "const": "bidw" },
    "version": { "const": 1 },
    "hands": {
      "type": "object",
      "properties": { "N": {"$ref": "#/$defs/pbn"}, "E": {"$ref": "#/$defs/pbn"},
                      "S": {"$ref": "#/$defs/pbn"}, "W": {"$ref": "#/$defs/pbn"} }
    },
    "pool": { "$ref": "#/$defs/pbn" },
    "contract": {
      "type": "object",
      "properties": {
        "level":    { "type": ["integer", "null"], "minimum": 1, "maximum": 7 },
        "strain":   { "enum": ["S", "H", "D", "C", "N", ""] },
        "declarer": { "enum": ["N", "E", "S", "W"] }
      }
    },
    "opening_lead": { "$ref": "#/$defs/cardOrNull" },
    "later_leads": {
      "type": "object",
      "properties": { "W": { "type": "array", "items": {"$ref": "#/$defs/card"} },
                      "E": { "type": "array", "items": {"$ref": "#/$defs/card"} } }
    },
    "author":   { "type": "object", "additionalProperties": { "type": "string" } },
    "versions": { "type": "array", "items": {
        "type": "object", "required": ["name", "hands"],
        "properties": { "name": {"type": "string"}, "created": {"type": "string"},
                        "hands": {"type": "object"} } } },
    "tutor_extra": { "type": "object" }
  },
  "$defs": {
    "pbn":  { "type": "string", "pattern": "^$|^[AKQJT2-9]*\\.[AKQJT2-9]*\\.[AKQJT2-9]*\\.[AKQJT2-9]*$" },
    "card": { "type": "integer", "minimum": 0, "maximum": 51 },
    "cardOrNull": { "type": ["integer", "null"], "minimum": 0, "maximum": 51 }
  }
}
```

The hands are stored as PBN strings so that a saved file stays readable and can
be edited by hand. The `pool` field is redundant because it can be derived from
the hands. It is still written so that a partly built deal is easy to read.

### 4.2 Test Hand export (Declarer Play Tutor format)

The export is the same superset that DealCreator now writes, e.g. `1a Mendelson7.json`.
It includes both the old and new field names, so the older Bridge_Declarer Web App
loader and the newer BWARepo `Deal` class can both read it.

```json
{
  "name": "Hand 12", "description": "Avoidance", "book": "Mendelson", "page": "22",
  "reference": "", "all_cards": [[], [], [], []],
  "south_cards": [11, 8, 1, 25, 23, 22, 21, 20, 38, 27, 26, 49, 41],
  "west_cards":  [...], "north_cards": [...], "east_cards": [...],
  "contract": "4 Hearts", "contract_level": "4", "contract_trump": "H",
  "declarer": "S",
  "w_leads": [37, 36], "e_leads": [],
  "west_leads": [37, 36], "east_leads": [],
  "si_player": 4, "si_pos": 0, "si_position": 0, "si_suit": 0, "si_action": 0,
  "commentary": ""
}
```

Mapping rules:

* Cards are sorted ♠ ♥ ♦ ♣, high to low within each suit, which matches the existing files.
* The contract is written as DealCreator writes it: `"1 Spade"`, `"4 Hearts"`, `"3 NoTrumps"`.
* The leader's leads are the opening lead followed by that defender's later leads.
  The other defender's leads are just their later leads. The tutor leads from `w_leads`
  and `e_leads`, so it assumes South declares. If the declarer is not South, the
  workshop warns before exporting.
* Fields from an imported file that the workshop does not manage are kept in
  `tutor_extra` and written back unchanged. Examples are `si_*`, `commentary`,
  `reference` and auto-play lists.

### 4.2a Defensive play overrides

The workshop file, the Test Hand export and each deal-library entry all carry a
top-level `defensiveOverrides` array (empty when there are none). Each record means
"the Nth time `suitLed` is led, `player` must play `cardToPlay`":

```json
"defensiveOverrides": [
  { "player": "East", "suitLed": "S", "occurrence": 1, "cardToPlay": 12 },
  { "player": "West", "suitLed": "H", "occurrence": 2, "cardToPlay": 23 }
]
```

`player` is `East` or `West`, `suitLed` is `S`/`H`/`D`/`C`, `occurrence` starts at 1,
and `cardToPlay` is a card number (never a code such as `"SA"`), even in the workshop
file. Files without the field load with no overrides, and malformed records are skipped.

### 4.2b Open From Deal Library

File → Open From Deal Library… lists the `libDeals` entries of a `.js` library. Each entry
is in the tutor format, so it is loaded exactly like an imported tutor file.

* **Open** loads the deal and leaves the library alone.
* **Check Out** loads the deal, then removes its entry from the library. The entry is cut
  out of the original text, so other entries, comments and line endings stay as they were.
  Nothing is written unless every other deal reads back unchanged and the file has not
  changed since it was read. The original is copied to `<name>.js.bak`, then replaced in
  one step. A checked-out deal is marked unsaved, so closing the app asks to save it.

### 4.3 Settings (`~/.bridge_deal_workshop.json`)

```json
{ "test_target": "C:/Users/.../BWARepo/workshop_test.json",
  "test_command": "", "recent_files": ["..."], "last_dir": "...",
  "four_colour": false }
```

---

## 5. Class design

```
workshop/
  cards.py     pure functions and constants: card ids, names, parsing, HCP
  model.py     Deal, Contract, AuthorInfo, Version, History (undo/redo)
  storage.py   workshop JSON save/load, tutor import/export, Settings
  commands.py  command-line parser ("DQ x D7") → operations on Deal
  diagram.py   DiagramCanvas: draws hands, centre, pool; selection; drag-and-drop
  panels.py    DealPanel, AuthorPanel, VersionsPanel (ttk forms)
  app.py       WorkshopApp: window, toolbar, menus, keys, status, wiring
bridge_workshop.py   entry point
tests/         unit tests for cards, model, storage, commands
```

**`cards`**: `SUITS="SHDC"`, `RANKS="23456789TJQKA"`, `SEATS="NESW"`,
`card(suit, rank) -> int`, `suit_of`, `rank_of`, `card_code(c) -> "DQ"`,
`card_label(c) -> "♦Q"`, `parse_card(text) -> int` (accepts `DQ`, `QD`, `♦Q`, `10D`),
`hcp(cards)`, `shape(cards) -> (s, h, d, c)`, `to_pbn(cards)`, `from_pbn(text)`.

**`model.Deal`**: the single source of truth.

| Member | Purpose |
|---|---|
| `location: dict[int, str or None]` | card → `"N"/"E"/"S"/"W"` or `None` (pool) |
| `contract: Contract` | level, strain, declarer |
| `opening_lead: int or None`, `later_leads: {"W": [...], "E": [...]}` | |
| `author: AuthorInfo` | dataclass of author strings |
| `versions: list[Version]` | named layouts |
| `tutor_extra: dict` | passthrough fields |
| `load_warnings: list[str]` | duplicate and other problems found on import |
| `hand(seat)`, `pool()` | sorted card lists |
| `move(cards, dest)`, `swap(a, b)`, `set_hand(seat, cards)` | **all card changes go through these**; each records undo |
| `validation() -> Validation` | counts, missing, problems, `complete` |
| `stats(seat) -> (hcp, shape)` | |
| `undo()`, `redo()` | via `History` |
| `on_change` callback | the UI redraws when it is called |

**`model.History`**: stacks of snapshots of `(location, opening_lead, later_leads)`.
A snapshot is 52 small entries, so whole-state copies are simpler and safer than
recording inverse operations.

**`storage`**: `save_workshop(deal, path)`, `load_any(path) -> Deal` (detects the
workshop or tutor format), `to_tutor_dict(deal)`, `export_tutor(deal, path)`, `Settings`.

**`diagram.DiagramCanvas(tk.Canvas)`**: owns the layout geometry and
`selection: set[int]`. It reads the `Deal` and asks it to make changes. It never
changes `location` directly.

**`app.WorkshopApp`**: builds the window and implements the actions (`new`,
`open`, `save`, `test_hand`, `swap_selected`, `move_selected(seat)`…).
The toolbar, menus, keys and context menus all call these same actions.

---

## 6. Tkinter widget layout

```
Tk root
├── Menu bar: File (New, Open, Save, Save As, Recent, Exit)
│             Edit (Undo, Redo, Swap, To pool, Clear selection, Select pool)
│             Test (Test Hand, Set test target…, Set test command…)
│             View (Four-colour suits)
├── ttk.Frame toolbar (row 0): ttk.Buttons + ttk.Entry "command"
├── ttk.PanedWindow (row 1, horizontal, expands)
│   ├── DiagramCanvas (tk.Canvas, ~920×700, scales with window)
│   └── ttk.Frame side panel (fixed ~320 px)
│       ├── DealPanel   (ttk.LabelFrame "Deal")    Spinbox level, Combobox strain/declarer/lead, Entries for later leads
│       ├── AuthorPanel (ttk.LabelFrame "Author")  Entries + small tk.Text boxes (undo=True)
│       └── VersionsPanel (ttk.LabelFrame "Versions") Listbox + 3 Buttons
├── ttk.Frame validation bar (row 2): Labels, red when there is a problem
└── ttk.Label status line (row 3)
```

Hands and pool are drawn on **one canvas**, not built from separate widgets.
That makes cross-hand dragging trivial, with no coordinate translation between
widgets. Each card is a rounded rectangle plus a text item, both tagged
`card`, `c<N>`.

Key bindings are attached to the root window. A handler ignores the key when the
focused widget is an Entry, Text, Spinbox or Combobox, so typing notes never
moves cards.

| Key | Action | Key | Action |
|---|---|---|---|
| `N` `E` `S` `W` | move selection to seat | `X` / `Space` | swap two selected |
| `P` / `Delete` | selection → pool | `Esc` | clear selection |
| `Ctrl+Z` / `Ctrl+Y` | undo / redo | `F5` | Test Hand |
| `Ctrl+S` / `Ctrl+O` / `Ctrl+N` | save / open / new | `Ctrl+K` | snapshot version |
| `Ctrl+L` | focus command line | `Ctrl+A` | select all pool cards |

---

## 7. Drag-and-drop implementation

Tkinter's built-in drag-and-drop works between applications and is awkward to
use. This app needs dragging only within its own canvas, which plain mouse
events handle cleanly.

1. **`<ButtonPress-1>`**: hit-test with `find_overlapping` and read the card id
   from the item's tags. Record `press_card`, the press position and the Shift
   state. No visual change happens yet.
2. **`<B1-Motion>`**: once the pointer has moved more than 5 px, start the drag:
   * the cards being dragged are the selection if `press_card` is in it,
     otherwise just `press_card`;
   * create a floating "ghost" group: a card face, plus "+n" if several cards
     are dragged, tagged `drag`, and move it with the pointer;
   * hit-test the drop target and highlight it: a hand box, the pool, or a card
     during a Shift-drag.
3. **`<ButtonRelease-1>`**:
   * *No drag happened* → a click, which toggles `press_card` in the selection.
   * *Dropped on a hand* → `deal.move(cards, seat)`.
   * *Dropped on the pool* → `deal.move(cards, None)`.
   * *Shift-drop on a card in another location* → `deal.swap(press_card, target)`.
   * *Anywhere else* → cancel.
   * Delete the ghost, clear the highlight and redraw.

Drop targets are tested against the stored rectangles of the hand boxes and the
pool, not against canvas items, which is fast and exact. Each change goes
through `Deal`, which records undo and triggers `on_change` → one full redraw.
A full redraw costs about 1–2 ms for this many items, so there is no need for
incremental updates.

Swap without dragging: select exactly two cards that are in different locations
and press `X`. If the two cards share a location, or the selection is not
exactly two cards, the status bar explains why and nothing changes.

---

## 8. Save / load architecture

```
          ┌────────────── Deal (model) ──────────────┐
          │ location · contract · leads · author ·   │
          │ versions · tutor_extra                   │
          └───▲───────────────┬──────────────────────┘
   load_any() │               │ save_workshop()      to_tutor_dict()
   ┌──────────┴───┐     ┌─────▼─────────┐     ┌───────▼──────────────┐
   │ workshop JSON│     │ workshop JSON │     │ tutor JSON (Test Hand)│
   │ tutor JSON   │     │ (atomic write)│     │ + clipboard + command │
   └──────────────┘     └───────────────┘     └──────────────────────┘
```

* **Format detection**: `"format": "bidw"` means a workshop file. A file with
  `south_cards` is a tutor or DealCreator file. Anything else produces a clear
  error in the status bar.
* **Atomic save**: write to `path.tmp`, then `os.replace`, so a crash never
  leaves a half-written file.
* **Dirty tracking**: any change marks the document dirty and adds `*` to the
  title. New, Open and closing the window ask before discarding unsaved changes.
  That is the only confirmation dialog in the app.
* **Importing never overwrites the original**: after opening a tutor file, the
  first `Ctrl+S` asks for a workshop file name.
* **Test Hand target**: chosen once (*Test → Set test target…*, or automatically
  on first use) and remembered in the settings file. Later presses write
  silently. The optional test command runs with `subprocess.Popen` and does not
  block the app.
* **Settings** live in `~/.bridge_deal_workshop.json`. A missing or corrupt
  settings file falls back to defaults.

---

## 9. Future enhancements

1. **Add to dealLibrary.js**: append or replace the deal between the
   `//START DEAL LIST` markers, as DealCreator does.
2. **Built-in play-through**: reuse DealCreator's `Play_Test.PlayTest` rules
   class to play a line inside the workshop, with undo, and record "right line
   makes / wrong line fails".
3. **Double-dummy check**: optional integration with an external solver
   (e.g. DDS) to report the makeable tricks after each change. This is reporting
   only; it never suggests cards.
4. **Book project files**: one file per chapter holding many deals, with a
   navigator and batch export.
5. **Version compare**: highlight the cards that differ between two versions.
6. **Lock cards**: pin the key cards so that broad moves, such as sending a
   whole selection to West, cannot disturb them.
7. **Print / copy diagram**: copy the deal as text or as an image for the manuscript.
8. **Special-instruction editor** for the tutor's `si_*` fields.
9. Losing-trick count and controls count alongside HCP.
10. Adjustable card size and font for high-DPI screens.
