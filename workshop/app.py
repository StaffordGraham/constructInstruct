"""Main window: toolbar, menus, keys, status, and the actions they all share."""

import os
import re
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .book import BookProject
from .book_import import import_deals
from .book_panel import UNPLACED, BookPanel
from .cards import SEATS, SEAT_NAMES, card_label, from_pbn
from .commands import CommandError, run_command
from .commentary_panel import CoachingPanel, CommentaryPanel
from .diagram import DiagramCanvas
from .library_manager import LibraryManager
from .model import Deal
from .panels import (AuthorPanel, DealPanel, LibraryDealDialog, OverridesPanel,
                     PlayTestLog, VersionsPanel, library_deal_name)
from .playtest import (PlayTestServer, default_smallcards_folder, is_smallcards_folder,
                       open_window, playtest_problems, raise_window)
from .storage import (FileFormatError, Settings, append_to_library, is_cloud_folder,
                      check_out_of_library, deal_from_dict, export_tutor,
                      library_deals, library_names, load_any, read_library,
                      save_workshop, to_library_dict, tutor_json_text)

APP_NAME = "Bridge Instructional Deal Workshop"
JSON_TYPES = [("Deal files", "*.json"), ("All files", "*.*")]
LIBRARY_TYPES = [("JavaScript deal library", "*.js"), ("All files", "*.*")]
IMPORT_TYPES = [("Deal files and libraries", "*.json *.js"), ("All files", "*.*")]
WORD_TYPES = [("Word document", "*.docx"), ("All files", "*.*")]
TEXT_WIDGETS = {"Entry", "TEntry", "Text", "TCombobox", "Spinbox", "TSpinbox"}

OK_FG = "#1b5e20"
BAD_FG = "#c62828"
WARN_FG = "#b26a00"


class WorkshopApp:
    def __init__(self, root, settings=None):
        self.root = root
        self.settings = settings or Settings()
        self.deal = Deal()
        self.path = None           # workshop file being edited (None until saved)
        self.import_name = ""      # name of an imported tutor file, for Save As
        self._library_manager = None
        self._playtest = None          # PlayTestServer, started by the first play-test
        self._playtest_deals = {}      # published version -> the Deal it came from
        self.book = None               # BookProject, when a book is open
        self.book_panel = None
        self.book_deal_id = None       # id of the book hand being edited, if it is one
        self.dirty = False

        root.title(APP_NAME)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        scale = max(1.0, root.winfo_fpixels("1i") / 96.0)

        self._build_menus()
        self._build_toolbar()

        body = ttk.PanedWindow(root, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew")
        self.body = body                # the book pane goes in front when a book is open
        left = ttk.Frame(body)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.canvas = DiagramCanvas(left, self, scale=scale)
        self.canvas.four_colour = bool(self.settings["four_colour"])
        self.canvas.grid(row=0, column=0)       # fixed size, centred in the pane
        body.add(left, weight=1)

        tabs = ttk.Notebook(body)
        self.tabs = tabs
        side = ttk.Frame(tabs, padding=(4, 4, 6, 4))
        self.deal_panel = DealPanel(side, self)
        self.deal_panel.pack(fill="x")
        self.overrides_panel = OverridesPanel(side, self)
        self.overrides_panel.pack(fill="x", pady=(6, 0))
        self.author_panel = AuthorPanel(side, self)
        self.author_panel.pack(fill="both", expand=True, pady=6)
        self.versions_panel = VersionsPanel(side, self)
        self.versions_panel.pack(fill="both")
        tabs.add(side, text="Deal")
        self.commentary_panel = CommentaryPanel(tabs, self)
        tabs.add(self.commentary_panel, text="Commentary")
        self.coaching_panel = CoachingPanel(tabs, self)
        tabs.add(self.coaching_panel, text="Coaching")
        tabs.bind("<<NotebookTabChanged>>", lambda e: self.commentary_panel.refresh_concept())
        body.add(tabs, weight=0)

        self._build_validation_bar()
        self.status = tk.Label(root, anchor="w", padx=8, font=("Segoe UI Symbol", 10))
        self.status.grid(row=3, column=0, sticky="we")
        root.rowconfigure(1, weight=1)
        root.columnconfigure(0, weight=1)

        self._bind_keys()
        self.set_deal(Deal(), path=None)
        self.set_status("Ready. Drag cards from the pool, or click to select and press N E S W.")
        last_book = self.settings["book_dir"]
        if last_book and (Path(last_book) / "book.json").is_file():
            self.open_book(last_book)

    # ----- construction ----------------------------------------------------
    def _build_menus(self):
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=False)
        f.add_command(label="New", accelerator="Ctrl+N", command=self.new)
        f.add_command(label="Open…", accelerator="Ctrl+O", command=self.open)
        self.recent_menu = tk.Menu(f, tearoff=False)
        f.add_cascade(label="Open recent", menu=self.recent_menu)
        f.add_command(label="Open From Deal Library…", command=self.open_from_library)
        f.add_separator()
        f.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        f.add_command(label="Save as…", accelerator="Ctrl+Shift+S", command=self.save_as)
        f.add_separator()
        f.add_command(label="Save deal to library…", command=self.save_to_library)
        f.add_command(label="Export to Word…", command=self.export_word)
        f.add_command(label="Library Manager…", command=self.library_manager)
        f.add_separator()
        f.add_command(label="Home folder for files…", command=self.choose_home_folder)
        f.add_separator()
        f.add_command(label="Exit", command=self.quit)
        m.add_cascade(label="File", menu=f)

        b = tk.Menu(m, tearoff=False)
        b.add_command(label="New book…", command=self.new_book)
        b.add_command(label="Open book…", command=self.open_book)
        b.add_command(label="Close book", command=self.close_book)
        b.add_separator()
        b.add_command(label="Bring hands into the book…", command=self.import_into_book)
        b.add_command(label="Add this deal to the book", command=self.add_deal_to_book)
        b.add_separator()
        b.add_command(label="Open this chapter in Word", accelerator="F6",
                      command=self.export_chapter_word)
        b.add_command(label="Export the whole book to Word", command=self.export_book_word)
        b.add_command(label="Open the book's exports folder", command=self.open_exports_folder)
        m.add_cascade(label="Book", menu=b)

        e = tk.Menu(m, tearoff=False)
        e.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        e.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo)
        e.add_separator()
        e.add_command(label="Swap two selected cards", accelerator="X", command=self.swap_selected)
        for s in SEATS:
            e.add_command(label=f"Move selection to {SEAT_NAMES[s]}", accelerator=s,
                          command=lambda s=s: self.move_selected(s))
        e.add_command(label="Return selection to pool", accelerator="P",
                      command=lambda: self.move_selected(None))
        e.add_separator()
        e.add_command(label="Select all unused cards", accelerator="Ctrl+A", command=self.select_pool)
        e.add_command(label="Clear selection", accelerator="Esc",
                      command=lambda: self.canvas.clear_selection())
        e.add_command(label="Return all cards to pool", command=self.clear_all)
        e.add_separator()
        e.add_command(label="Snapshot version", accelerator="Ctrl+K", command=self.snapshot_version)
        m.add_cascade(label="Edit", menu=e)

        t = tk.Menu(m, tearoff=False)
        t.add_command(label="Play-test in SmallCards", accelerator="F5", command=self.play_test)
        t.add_command(label="Open another play-test window",
                      command=lambda: self.play_test(new_window=True))
        t.add_command(label="Play-test results…", command=self.show_playtests)
        t.add_command(label="Set SmallCards folder…", command=self.choose_smallcards_folder)
        t.add_separator()
        t.add_command(label="Test Hand (export tutor file)", accelerator="Shift+F5",
                      command=self.test_hand)
        t.add_command(label="Set test target file…", command=self.choose_test_target)
        t.add_command(label="Set command to run after export…", command=self.choose_test_command)
        t.add_command(label="Copy tutor JSON to clipboard", command=self.copy_tutor_json)
        m.add_cascade(label="Test", menu=t)

        v = tk.Menu(m, tearoff=False)
        self.four_colour_var = tk.BooleanVar(value=bool(self.settings["four_colour"]))
        v.add_checkbutton(label="Four-colour suits", variable=self.four_colour_var,
                          command=self.toggle_four_colour)
        m.add_cascade(label="View", menu=v)

        self.root.config(menu=m)
        self._refresh_recent()

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(6, 4))
        bar.grid(row=0, column=0, sticky="we")

        def button(text, cmd, **kw):
            b = ttk.Button(bar, text=text, command=cmd, **kw)
            b.pack(side="left", padx=1)
            return b

        def sep():
            ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

        button("New", self.new)
        button("Open", self.open)
        button("Save", self.save)
        button("Save Deal To Library", self.save_to_library)
        button("Library Manager", self.library_manager)     # same command as File menu
        sep()
        self.undo_btn = button("Undo", self.undo)
        self.redo_btn = button("Redo", self.redo)
        sep()
        self.swap_btn = button("Swap  (X)", self.swap_selected)
        button("To pool  (P)", lambda: self.move_selected(None))
        button("Clear Deal", self.clear_deal)
        button("Complete Deal", self.complete_deal)
        sep()
        style = ttk.Style(self.root)
        style.configure("Test.TButton", font=("Segoe UI", 10, "bold"))
        button("▶  Play-test  (F5)", self.play_test, style="Test.TButton")
        sep()
        ttk.Label(bar, text="Command").pack(side="left")
        self.cmd = ttk.Entry(bar, width=28, font=("Consolas", 10))
        self.cmd.pack(side="left", padx=4)
        self.cmd.bind("<Return>", self.run_command_line)
        ttk.Label(bar, text="e.g.  DQ E    DQ x D7    SAKQ N    N: AKJ74.K3.A62.Q85",
                  foreground="#666").pack(side="left", padx=4)

    def _build_validation_bar(self):
        bar = ttk.Frame(self.root, padding=(8, 2))
        bar.grid(row=2, column=0, sticky="we")
        font = ("Segoe UI Symbol", 10, "bold")
        self.count_labels = {}
        for s in SEATS:
            lab = tk.Label(bar, font=font)
            lab.pack(side="left", padx=(0, 8))
            self.count_labels[s] = lab
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        self.assigned_label = tk.Label(bar, font=font)
        self.assigned_label.pack(side="left")
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        self.missing_label = tk.Label(bar, font=("Segoe UI Symbol", 10))
        self.missing_label.pack(side="left")
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        self.dup_label = tk.Label(bar, font=("Segoe UI Symbol", 10))
        self.dup_label.pack(side="left")
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        self.ready_label = tk.Label(bar, font=font, anchor="w")
        self.ready_label.pack(side="left", fill="x", expand=True)

    def _bind_keys(self):
        r = self.root
        r.bind("<Key>", self._on_key)
        globals_ = {
            "<Control-n>": self.new, "<Control-o>": self.open, "<Control-s>": self.save,
            "<Control-S>": self.save_as, "<F5>": self.play_test, "<Shift-F5>": self.test_hand,
            "<F6>": self.export_chapter_word,
            "<Control-k>": self.snapshot_version,
            "<Control-l>": lambda: (self.cmd.focus_set(), self.cmd.select_range(0, "end")),
        }
        for seq, fn in globals_.items():
            r.bind(seq, lambda e, fn=fn: (fn(), "break")[1])
        # These mean something else inside text fields, so only act outside them
        local = {"<Control-z>": self.undo, "<Control-y>": self.redo, "<Control-Z>": self.redo,
                 "<Control-a>": self.select_pool}
        for seq, fn in local.items():
            r.bind(seq, lambda e, fn=fn: None if self._in_text(e) else (fn(), "break")[1])

    def _in_text(self, event):
        try:
            return event.widget.winfo_class() in TEXT_WIDGETS
        except (AttributeError, tk.TclError):
            return False

    def _on_key(self, event):
        if self._in_text(event) or event.state & 0x0004:   # typing, or Ctrl held
            return
        k = event.keysym.lower()
        if k in ("n", "e", "s", "w"):
            self.move_selected(k.upper())
        elif k in ("x", "space"):
            self.swap_selected()
        elif k in ("p", "delete", "backspace"):
            self.move_selected(None)
        elif k == "escape":
            self.canvas.clear_selection()
        else:
            return
        return "break"

    # ----- deal lifecycle --------------------------------------------------
    def set_deal(self, deal, path):
        self.deal = deal
        self.path = path
        self.book_deal_id = self._book_id_for(deal, path)
        deal.add_listener(self.on_deal_change)
        self.canvas.set_deal(deal)
        self.deal_panel.refresh(deal, full=True)
        self.overrides_panel.refresh(deal, full=True)
        self.author_panel.refresh(deal)
        self.versions_panel.refresh(deal)
        self.commentary_panel.refresh(deal)
        self.coaching_panel.refresh(deal)
        self.dirty = False
        self._refresh_validation()
        self._refresh_title()
        self._refresh_buttons()

    def on_deal_change(self, message=""):
        self.dirty = True
        self.canvas.redraw()
        self.deal_panel.refresh(self.deal)
        self.overrides_panel.refresh(self.deal)
        self.commentary_panel.cards_moved()
        self.coaching_panel.refresh(self.deal, keep=True)
        self._refresh_validation()
        self._refresh_title()
        self._refresh_buttons()
        if message:
            self.set_status(message)

    def author_changed(self, redraw=False):
        self.dirty = True
        self._refresh_title()
        if redraw:
            self.canvas.redraw()

    def versions_changed(self):
        self.versions_panel.refresh(self.deal)

    def set_contract(self, contract):
        self.deal.contract = contract
        self.deal.notify(f"Contract: {contract.short_text() or 'none'} by {SEAT_NAMES[contract.declarer]}")

    # ----- status and validation --------------------------------------------
    def set_status(self, text, error=False):
        self.status.config(text=text, fg=BAD_FG if error else "#222")

    def _refresh_title(self):
        if self.book_deal_id:
            label = self.book.hand_code(self.book_deal_id) or "unplaced"
            name = f"{self.book.book.title}: {self.book.deal_title(self.book_deal_id)} ({label})"
        elif self.path:
            name = Path(self.path).name
        elif self.import_name:
            name = f"{self.import_name} (imported)"
        else:
            name = "untitled"
        self.root.title(f"{APP_NAME} — {name}{' *' if self.dirty else ''}")

    def _refresh_buttons(self):
        self.undo_btn.state(["!disabled"] if self.deal.can_undo() else ["disabled"])
        self.redo_btn.state(["!disabled"] if self.deal.can_redo() else ["disabled"])
        self.swap_btn.state(["!disabled"] if len(self.canvas.selection) == 2 else ["disabled"])

    def _refresh_validation(self):
        v = self.deal.validation()
        for s, lab in self.count_labels.items():
            n = v.counts[s]
            lab.config(text=f"{s} {n}", fg=OK_FG if n == 13 else BAD_FG)
        self.assigned_label.config(text=f"{v.assigned}/52 assigned",
                                   fg=OK_FG if v.assigned == 52 else BAD_FG)
        if not v.missing:
            self.missing_label.config(text="Missing: none", fg=OK_FG)
        elif len(v.missing) <= 8:
            self.missing_label.config(text="Missing: " + " ".join(card_label(c) for c in v.missing),
                                      fg=BAD_FG)
        else:
            self.missing_label.config(text=f"Missing: {len(v.missing)} cards", fg=BAD_FG)
        if v.duplicates:
            self.dup_label.config(text="Duplicates: " + " ".join(card_label(c) for c in v.duplicates),
                                  fg=BAD_FG)
        else:
            self.dup_label.config(text="Duplicates: none", fg=OK_FG)
        if v.errors:
            self.ready_label.config(text="✖ " + "; ".join(v.errors), fg=BAD_FG)
        elif v.warnings:
            self.ready_label.config(text="⚠ " + "; ".join(v.warnings), fg=WARN_FG)
        else:
            self.ready_label.config(text="✔ Ready to test", fg=OK_FG)

    # ----- card actions (shared by mouse, keys, menus) -----------------------
    def selection_changed(self):
        self._refresh_buttons()

    def do_move(self, cards, dest):
        if self.deal.move(cards, dest) == 0:
            self.set_status("Already there")
        self.canvas.clear_selection()

    def do_swap(self, a, b):
        if not self.deal.swap(a, b):
            self.set_status(f"{card_label(a)} and {card_label(b)} are in the same place — "
                            "nothing to swap", error=True)
            return
        self.canvas.clear_selection()

    def move_selected(self, dest):
        sel = sorted(self.canvas.selection)
        if not sel:
            self.set_status("Select cards first (click them), then press N, E, S, W or P", error=True)
            return
        self.do_move(sel, dest)

    def swap_selected(self):
        sel = sorted(self.canvas.selection)
        if len(sel) != 2:
            self.set_status(f"Swap needs exactly two selected cards ({len(sel)} selected)", error=True)
            return
        self.do_swap(*sel)

    def select_pool(self):
        self.canvas.set_selection(self.deal.pool())
        self.set_status(f"Selected {len(self.deal.pool())} unused cards — press N E S W to send them")

    def clear_all(self):
        self.deal.clear_all()
        self.canvas.clear_selection()

    def clear_deal(self):
        if not messagebox.askyesno(APP_NAME, "This will remove all cards from every hand and "
                                   "return them to the pool. Continue?", parent=self.root):
            return
        self.canvas.clear_selection()
        if not self.deal.clear_deal():
            self.set_status("Nothing to clear — all 52 cards are already in the pool")

    def complete_deal(self):
        """Deal the pool at random to the hands that are short, leaving placed cards alone."""
        problems = self.deal.completion_problems()
        if problems:
            self.set_status("Deal not completed — " + "; ".join(problems), error=True)
            messagebox.showerror(APP_NAME, "The deal can't be completed, so nothing was changed.\n\n"
                                 + "\n".join(problems), parent=self.root)
            return
        if not self.deal.pool():
            self.set_status("Nothing to deal — every hand already has 13 cards")
            return
        self.canvas.clear_selection()
        self.deal.complete_deal()

    def undo(self):
        if not self.deal.undo():
            self.set_status("Nothing to undo")

    def redo(self):
        if not self.deal.redo():
            self.set_status("Nothing to redo")

    def apply_hand_text(self, seat, text):
        try:
            cards = from_pbn(text)
        except ValueError as e:
            self.set_status(f"{SEAT_NAMES[seat]}: {e}", error=True)
            return False
        self.deal.set_hand(seat, cards)
        return True

    def run_command_line(self, event=None):
        try:
            run_command(self.deal, self.cmd.get())
        except CommandError as e:
            self.set_status(f"Command: {e}", error=True)
            return "break"
        self.cmd.delete(0, "end")
        self.canvas.clear_selection()
        return "break"

    def snapshot_version(self):
        name = self.versions_panel.take_name(f"v{len(self.deal.versions) + 1}")
        self.deal.snapshot_version(name)
        self.versions_changed()

    # ----- context menus -----------------------------------------------------
    def _popup(self, menu, event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def card_menu(self, card, event):
        m = tk.Menu(self.root, tearoff=False)
        where = self.deal.location[card]
        m.add_command(label=f"{card_label(card)}  (in {SEAT_NAMES[where] if where else 'pool'})",
                      state="disabled")
        m.add_separator()
        for s in SEATS:
            m.add_command(label=f"Move to {SEAT_NAMES[s]}", accelerator=s,
                          command=lambda s=s: self.do_move([card], s))
        m.add_command(label="Return to pool", command=lambda: self.do_move([card], None))
        m.add_separator()
        m.add_command(label="Set as opening lead", command=lambda: self.deal.set_opening_lead(card))
        if self.deal.opening_lead is not None:
            m.add_command(label="Clear opening lead", command=lambda: self.deal.set_opening_lead(None))
        sel = self.canvas.selection
        if len(sel) == 1 and card not in sel:
            other = next(iter(sel))
            m.add_separator()
            m.add_command(label=f"Swap with selected {card_label(other)}",
                          command=lambda: self.do_swap(other, card))
        self._popup(m, event)

    def hand_menu(self, seat, event):
        m = tk.Menu(self.root, tearoff=False)
        m.add_command(label=f"Type {SEAT_NAMES[seat]}'s hand…",
                      command=lambda: self.canvas.open_entry(seat))
        m.add_command(label="Select all cards in this hand",
                      command=lambda: self.canvas.set_selection(self.deal.hand(seat)))
        if self.canvas.selection:
            m.add_command(label=f"Move selection here ({len(self.canvas.selection)})",
                          command=lambda: self.move_selected(seat))
        m.add_separator()
        m.add_command(label="Return hand to pool", command=lambda: self.deal.clear_hand(seat))
        self._popup(m, event)

    def pool_menu(self, event):
        m = tk.Menu(self.root, tearoff=False)
        m.add_command(label="Select all unused cards", command=self.select_pool)
        for s in SEATS:
            m.add_command(label=f"Send all unused cards to {SEAT_NAMES[s]}",
                          command=lambda s=s: self.do_move(self.deal.pool(), s))
        self._popup(m, event)

    # ----- files -------------------------------------------------------------
    def confirm_discard(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(APP_NAME, "Save changes to this deal first?",
                                           parent=self.root)
        if answer is None:
            return False
        if answer:
            return self.save()
        if self.book_deal_id:       # the book keeps the hand as last saved
            self.book.reload_deal(self.book_deal_id)
            self.book_panel.hand_saved()
        return True

    def new(self):
        if not self.confirm_discard():
            return
        self.import_name = ""
        self.set_deal(Deal(), path=None)
        self.set_status("New deal — all 52 cards are in the pool")

    def open(self, path=None):
        if not self.confirm_discard():
            return
        if path is None:
            path = filedialog.askopenfilename(parent=self.root, title="Open deal",
                                              initialdir=self.start_folder(),
                                              filetypes=JSON_TYPES)
            if not path:
                return
        try:
            deal, kind = load_any(path)
        except (OSError, FileFormatError) as e:
            self.set_status(f"Could not open {Path(path).name}: {e}", error=True)
            return
        self.settings.add_recent(path)
        self._refresh_recent()
        if kind == "workshop":
            self.import_name = ""
            self.set_deal(deal, path=path)
            self.set_status(f"Opened {Path(path).name}")
        else:
            self.import_name = Path(path).stem
            self.set_deal(deal, path=None)
            self.set_status(f"Imported tutor file {Path(path).name} — Save writes a new workshop file")
        if deal.duplicates:
            self.set_status("Duplicate cards in file (first hand kept): "
                            + " ".join(card_label(c) for c in deal.duplicates), error=True)

    def save(self):
        if not self.path:
            return self.save_as()
        try:
            save_workshop(self.deal, self.path)
        except OSError as e:
            self.set_status(f"Save failed: {e}", error=True)
            return False
        was_book_hand = self.book_deal_id
        self.book_deal_id = self._book_id_for(self.deal, self.path)
        if was_book_hand and not self.book_deal_id:
            # saved as a copy elsewhere: the book keeps its own copy as last saved
            self.book.reload_deal(was_book_hand)
        self.dirty = False
        self._refresh_title()
        if self.book_panel:
            self.book_panel.hand_saved()
        self.set_status(f"Saved {self.book_deal_id and 'the hand in the book' or Path(self.path).name}")
        return True

    def save_as(self):
        suggested = self.import_name or _safe_name(self.deal.author.title) or "deal"
        path = filedialog.asksaveasfilename(parent=self.root, title="Save deal",
                                            initialdir=self.start_folder(),
                                            initialfile=f"{suggested}.json",
                                            defaultextension=".json", filetypes=JSON_TYPES)
        if not path or not self.allow_cloud(path):
            return False
        self.path = path
        self.import_name = ""
        ok = self.save()
        if ok:
            self.settings.add_recent(path)
            self._refresh_recent()
        return ok

    def save_to_library(self):
        """Append the current deal to a libDeals JavaScript file the user picks."""
        v = self.deal.validation()
        if v.errors:
            self.set_status("Not saved to library — " + "; ".join(v.errors), error=True)
            messagebox.showerror(APP_NAME, "This deal can't go into a library yet:\n\n"
                                 + "\n".join(v.errors), parent=self.root)
            return
        if not self.deal.author.title.strip():
            name = simpledialog.askstring(APP_NAME, "Name for this deal in the library "
                                          "(e.g. Hand 12):", parent=self.root)
            if not name or not name.strip():
                return
            self.deal.author.title = name.strip()
            self.author_panel.refresh(self.deal)
            self.author_changed(redraw=True)
        path = filedialog.askopenfilename(
            parent=self.root, title="Save deal to library",
            initialdir=self.start_folder(self.settings["library_dir"]),
            filetypes=LIBRARY_TYPES)
        if not path or not self.allow_cloud(path):
            return
        name = Path(path).name
        try:
            text, had_bom = read_library(path)
        except (OSError, FileFormatError) as e:
            self.set_status(f"Not saved to library: {e}", error=True)
            messagebox.showerror(APP_NAME, f"Could not use {name}:\n\n{e}", parent=self.root)
            return
        title = self.deal.author.title
        if title in library_names(text) and not messagebox.askyesno(
                APP_NAME, f"{name} already has a deal called '{title}'.\n\n"
                "Add this one as well?", parent=self.root):
            return
        try:
            append_to_library(self.deal, path, text=text, had_bom=had_bom)
        except (OSError, FileFormatError) as e:
            self.set_status(f"Library save failed: {e}", error=True)
            messagebox.showerror(APP_NAME, f"Could not save to {name}:\n\n{e}", parent=self.root)
            return
        self.settings["library_dir"] = str(Path(path).parent)
        msg = f"'{title}' added to the end of {name}"
        if v.warnings:
            msg += "   ⚠ " + "; ".join(v.warnings)
        self.set_status(msg)
        messagebox.showinfo(APP_NAME, f"'{title}' was added to the end of\n{path}",
                            parent=self.root)

    def open_from_library(self):
        """Open a libDeals entry, or check it out: open it and remove it from the library."""
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Open from deal library",
            initialdir=self.start_folder(self.settings["library_dir"]),
            filetypes=LIBRARY_TYPES)
        if not path:
            return
        name = Path(path).name
        fail = self._library_error
        try:
            text, had_bom = read_library(path)
            entries = library_deals(text)
        except (OSError, FileFormatError) as e:
            return fail(f"Could not read {name}", e)
        if not entries:
            messagebox.showinfo(APP_NAME, f"{name} has no deals in libDeals.", parent=self.root)
            return
        choice = LibraryDealDialog(self.root, name, entries).result
        if choice is None:
            return
        index, action = choice
        title = self.load_library_entry(entries[index], name)
        if title is None:           # could not load: the library is not touched
            return
        self.settings["library_dir"] = str(Path(path).parent)
        if action == "open":
            self.set_status(f"Opened '{title}' from {name} — the library is unchanged")
            return
        # Checked out: the deal now lives only in the editor until it is saved.
        self.dirty = True
        self._refresh_title()
        try:
            check_out_of_library(path, text, had_bom, index)
        except (OSError, FileFormatError) as e:
            return fail(f"'{title}' is open, but {name} was NOT changed", e)
        self.set_status(f"Checked out '{title}' — removed from {name} (backup {name}.bak). "
                        "Save it to keep it.")

    def load_library_entry(self, entry, library_name):
        """Put a libDeals entry into the editor, as an import. Returns its title, or None
        (after showing why) if it could not be loaded. Callers confirm_discard() first."""
        title = library_deal_name(entry)
        try:
            deal, _ = deal_from_dict(entry)
        except Exception as e:      # any bad entry: report it, change nothing
            self._library_error(f"Could not load '{title}' from {library_name}", e)
            return None
        self.import_name = ""
        self.set_deal(deal, path=None)
        return title

    def _library_error(self, what, e):
        self.set_status(f"{what}: {e}", error=True)
        messagebox.showerror(APP_NAME, f"{what}.\n\n{e}", parent=self.root)

    def library_manager(self):
        if self._library_manager is not None and self._library_manager.winfo_exists():
            self._library_manager.lift()
            self._library_manager.focus_set()
            return
        self._library_manager = LibraryManager(self)

    def export_word(self):
        """Write the deal as a bridge diagram to a .docx file the user names."""
        try:
            from .word_export import export_to_word    # python-docx is optional
        except ImportError as e:
            messagebox.showerror(APP_NAME, "Export to Word needs python-docx.\n\n"
                                 f"Install it with:  pip install python-docx\n\n({e})",
                                 parent=self.root)
            return
        suggested = self.import_name or _safe_name(self.deal.author.title) or "deal"
        path = filedialog.asksaveasfilename(parent=self.root, title="Export to Word",
                                            initialdir=self.start_folder(),
                                            initialfile=f"{suggested}.docx",
                                            defaultextension=".docx", filetypes=WORD_TYPES)
        if not path or not self.allow_cloud(path):
            return
        try:
            export_to_word(self.deal, path)
        except OSError as e:
            self.set_status(f"Export failed: {e}", error=True)
            messagebox.showerror(APP_NAME, f"Could not write {Path(path).name}:\n\n{e}\n\n"
                                 "If it is open in Word, close it and try again.", parent=self.root)
            return
        self.set_status(f"Exported diagram to {Path(path).name}")

    # ----- folders ---------------------------------------------------------------
    def start_folder(self, *candidates):
        """Where a file dialog opens: always a folder on this computer (never OneDrive).
        The folder last used comes after any candidates given."""
        return self.settings.start_folder(*candidates, self.settings["last_dir"])

    def allow_cloud(self, path):
        """Ask before saving into OneDrive. True to go ahead."""
        if not is_cloud_folder(path):
            return True
        return messagebox.askyesno(
            APP_NAME, f"{path}\n\nis in OneDrive, not only on this computer. "
            "Save it there anyway?", icon="warning", parent=self.root)

    def choose_home_folder(self):
        path = filedialog.askdirectory(parent=self.root, title="Home folder for files",
                                       initialdir=self.start_folder())
        if not path:
            return
        if is_cloud_folder(path):
            messagebox.showerror(APP_NAME, "That folder is in OneDrive. Choose a folder on "
                                 "this computer.", parent=self.root)
            return
        self.settings["home_dir"] = str(Path(path))
        self.set_status(f"File dialogs open in {path} when there is no folder to remember")

    def _refresh_recent(self):
        self.recent_menu.delete(0, "end")
        recent = self.settings["recent_files"] or []
        if not recent:
            self.recent_menu.add_command(label="(none)", state="disabled")
        for p in recent:
            self.recent_menu.add_command(label=p, command=lambda p=p: self.open(p))

    def quit(self):
        if self.confirm_discard():
            if self.book_panel:
                self.book_panel.flush()
            if self._playtest:
                self._playtest.close()
            self.root.destroy()

    # ----- book projects ---------------------------------------------------------
    def _book_id_for(self, deal, path):
        """The deal's id if it is a hand of the open book being edited from its file."""
        if self.book and path and deal.id in self.book.deals \
                and Path(path) == self.book.deal_path(deal.id):
            return deal.id
        return None

    def new_book(self):
        folder = filedialog.askdirectory(parent=self.root, title="Choose an empty folder for the "
                                         "new book (make one with the New folder button)",
                                         initialdir=self.start_folder(
                                             Path(self.settings["book_dir"]).parent
                                             if self.settings["book_dir"] else None))
        if not folder or not self.allow_cloud(folder):
            return
        title = simpledialog.askstring(APP_NAME, "Title of the book:", parent=self.root)
        if not title or not title.strip():
            return
        try:
            BookProject.create(folder, title.strip())
        except (OSError, FileExistsError) as e:
            messagebox.showerror(APP_NAME, f"Could not start a book there:\n\n{e}\n\n"
                                 "Choose an empty folder.", parent=self.root)
            return
        self.open_book(folder)

    def open_book(self, folder=None):
        if folder is None:
            folder = filedialog.askdirectory(parent=self.root, title="Open book (its folder)",
                                             initialdir=self.start_folder(
                                                 self.settings["book_dir"]))
            if not folder:
                return False
        try:
            project = BookProject.open(folder)
        except (OSError, FileFormatError) as e:
            self.set_status(f"Could not open the book: {e}", error=True)
            messagebox.showerror(APP_NAME, f"Could not open the book in {folder}:\n\n{e}",
                                 parent=self.root)
            return False
        if self.book and not self.close_book():
            return False
        self.book = project
        self.settings["book_dir"] = str(Path(folder))
        self.book_panel = BookPanel(self.body, self)
        self.body.insert(0, self.book_panel, weight=0)
        self.book_panel.refresh()
        self.book_deal_id = self._book_id_for(self.deal, self.path)
        self._refresh_title()
        notes = project.load_warnings + project.problems()
        self.set_status(f"Opened the book {project.book.title}"
                        + ("   ⚠ " + "; ".join(notes) if notes else ""), error=bool(notes))
        return True

    def close_book(self):
        if not self.book:
            return True
        if self.book_deal_id:
            if not self.confirm_discard():
                return False
            self.set_deal(Deal(), path=None)
        self.book_panel.flush()
        self.body.forget(self.book_panel)
        self.book_panel.destroy()
        self.book = self.book_panel = None
        self.book_deal_id = None
        self.settings["book_dir"] = ""
        self._refresh_title()
        self.set_status("Book closed")
        return True

    def _need_book(self):
        if not self.book:
            self.set_status("Open a book first (Book → Open book…)", error=True)
        return self.book

    def open_book_hand(self, deal_id):
        """Edit one of the book's hands. Returns False if the user kept the current deal."""
        if not self.confirm_discard():
            return False
        deal = self.book.reload_deal(deal_id)
        if deal_id in self.book.unsaved_deals:
            self.book.save()
        self.import_name = ""
        self.set_deal(deal, path=str(self.book.deal_path(deal_id)))
        self.set_status(f"{self.book.hand_label(deal_id) or 'Unplaced hand'}: "
                        f"{self.book.deal_title(deal_id)}")
        return True

    def new_book_hand(self, chapter_id, role):
        if not self.confirm_discard():
            return
        deal = self.book.add_deal(Deal())
        try:
            self.book.place(deal.id, chapter_id, role)
        except ValueError as e:
            self.book.remove_deal(deal.id)
            self.set_status(str(e), error=True)
            return
        self.import_name = ""
        self.book_panel.changed()          # writes the new deal's file too
        self.set_deal(deal, path=str(self.book.deal_path(deal.id)))
        self.book_panel.select(f"d:{deal.id}")
        self.set_status(f"New {self.book.hand_label(deal.id)} in "
                        f"{self.book.chapters[chapter_id].title} — deal its cards")

    def book_deal_moved(self):
        """A hand moved in the book: its code in the title bar may have changed."""
        self._refresh_title()

    def book_deal_removed(self, deal_id):
        if deal_id == self.book_deal_id:
            self.dirty = False
            self.set_deal(Deal(), path=None)

    def current_chapter_id(self):
        """The chapter selected in the outline, or holding the selected or open hand."""
        item = self.book_panel.selected() or ""
        if item.startswith("c:"):
            return item[2:]
        for deal_id in (item[2:] if item.startswith("d:") else None, self.book_deal_id):
            where = deal_id and self.book.placement(deal_id)
            if where:
                return where[0].id
        return None

    def export_chapter_word(self):
        if not self._need_book():
            return
        chapter_id = self.current_chapter_id()
        if not chapter_id:
            self.set_status("Click a chapter (or one of its hands) in the outline first",
                            error=True)
            return
        self._export_word(lambda m: m.export_chapter(self.book, chapter_id), [chapter_id])

    def export_book_word(self):
        if not self._need_book():
            return
        chapters = [c for s in self.book.book.sections for c in s.chapters if c in self.book.chapters]
        self._export_word(lambda m: m.export_book(self.book), chapters)

    def _export_word(self, write, chapter_ids):
        """Write a Word document from the book and open it in Word."""
        try:
            from . import book_export        # python-docx is optional
        except ImportError as e:
            messagebox.showerror(APP_NAME, "Export to Word needs python-docx.\n\n"
                                 f"Install it with:  pip install python-docx\n\n({e})",
                                 parent=self.root)
            return
        if self.dirty and self.book_deal_id:
            answer = messagebox.askyesnocancel(
                APP_NAME, "Save this hand first? (No exports it as it is now, unsaved.)",
                parent=self.root)
            if answer is None or (answer and not self.save()):
                return
        self.book_panel.flush()
        try:
            path = write(book_export)
        except PermissionError:
            messagebox.showerror(APP_NAME, "The document is open in Word, so it can't be "
                                 "replaced. Close it in Word and try again.", parent=self.root)
            return
        except OSError as e:
            self.set_status(f"Export failed: {e}", error=True)
            return
        todo = book_export.export_problems(self.book, chapter_ids)
        self.set_status(f"Exported {path.name}" + (
            f"   ⚠ {len(todo)} to-do item{'s' if len(todo) != 1 else ''} still open — "
            "see the To do lists" if todo else ""), error=bool(todo))
        try:
            os.startfile(path)
        except OSError as e:
            self.set_status(f"Exported {path} but could not open it: {e}", error=True)

    def open_exports_folder(self):
        if not self._need_book():
            return
        folder = self.book.folder / "exports"
        folder.mkdir(exist_ok=True)
        os.startfile(folder)

    def import_into_book(self):
        if not self._need_book():
            return
        paths = filedialog.askopenfilenames(parent=self.root, title="Bring hands into the book",
                                            initialdir=self.start_folder(),
                                            filetypes=IMPORT_TYPES)
        if not paths:
            return
        added, skipped = import_deals(self.book, paths)
        self.book_panel.changed(select=UNPLACED)
        self.set_status(f"{len(added)} hand{'s' if len(added) != 1 else ''} added to "
                        f"Unplaced hands" + (f", {len(skipped)} skipped" if skipped else ""))
        if skipped:
            messagebox.showinfo(APP_NAME, "Not brought in:\n\n" + "\n".join(
                f"{label}: {reason}" for label, reason in skipped), parent=self.root)

    def add_deal_to_book(self):
        if not self._need_book():
            return
        if self.book_deal_id:
            self.set_status("This deal is already in the book")
            return
        deal = self.book.add_deal(self.deal)      # gets a new id if its id is taken
        try:
            self.book.save()
        except OSError as e:
            self.book.deals.pop(deal.id, None)
            self.set_status(f"Not added to the book: {e}", error=True)
            return
        self.import_name = ""
        self.path = str(self.book.deal_path(deal.id))
        self.book_deal_id = deal.id
        self.dirty = False
        self._refresh_title()
        self.book_panel.changed(select=f"d:{deal.id}")
        self.set_status("Added to the book under Unplaced hands. You are now editing the book's "
                        "copy; the original file is unchanged.")

    # ----- play-testing in SmallCards --------------------------------------------
    def play_test(self, new_window=False):
        """Send the deal to SmallCards and show it there. No files are written."""
        problems = playtest_problems(self.deal)
        if problems:
            self.set_status("Not play-tested — " + "; ".join(problems), error=True)
            return
        folder = self.settings["smallcards_dir"]
        if not is_smallcards_folder(folder):
            folder = default_smallcards_folder() or self.choose_smallcards_folder()
            if not folder:
                return
            self.settings["smallcards_dir"] = str(folder)
        if self._playtest is None:
            try:
                self._playtest = PlayTestServer(folder)
            except OSError as e:
                self.set_status(f"Could not start the play-test server: {e}", error=True)
                return
            self.root.after(400, self._poll_playtest)
        entry = to_library_dict(self.deal)
        entry["name"] = entry["name"].strip() or self.import_name or "Untitled deal"
        version = self._playtest.publish(entry)
        self._playtest_deals[version] = self.deal
        if new_window or not self._playtest.page_open():
            open_window(self._playtest.url)
            msg = "Play-test window opened"
        else:
            msg = "Sent to SmallCards" + ("" if raise_window() else " — switch to its window")
        warnings = self.deal.validation().warnings
        self.set_status(msg + ("   ⚠ " + "; ".join(warnings) if warnings else ""))

    def _poll_playtest(self):
        """Collect hands finished in SmallCards (they arrive on the server's thread)."""
        server = self._playtest
        if server is None:
            return
        while not server.results.empty():
            record, data = server.results.get()
            deal = self._playtest_deals.get(data.get("version") if isinstance(data, dict) else None)
            if record is None:
                self.set_status("A play-test result from SmallCards could not be read", error=True)
            elif deal is not self.deal:
                self.set_status("A play-test finished for a deal that is no longer open — "
                                "not recorded", error=True)
            else:
                self.deal.add_playtest(record)
        self.root.after(400, self._poll_playtest)

    def show_playtests(self):
        PlayTestLog(self.root, self.deal)

    def choose_smallcards_folder(self):
        path = filedialog.askdirectory(parent=self.root, title="SmallCards folder",
                                       initialdir=self.start_folder(
                                           self.settings["smallcards_dir"]))
        if not path:
            return None
        if not is_smallcards_folder(path):
            messagebox.showerror(APP_NAME, "That folder does not hold a SmallCards with play-test "
                                 "support (index.html and PlayTest.js).", parent=self.root)
            return None
        self.settings["smallcards_dir"] = path
        if self._playtest and Path(path) != self._playtest.folder:
            self._playtest.close()
            self._playtest = None
        self.set_status(f"SmallCards folder: {path}")
        return path

    # ----- testing -----------------------------------------------------------
    def choose_test_target(self):
        current = self.settings["test_target"]
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Test Hand writes the tutor file here",
            initialdir=self.start_folder(Path(current).parent if current else None),
            initialfile=Path(current).name if current else "workshop_test.json",
            defaultextension=".json", filetypes=JSON_TYPES)
        if path and not self.allow_cloud(path):
            return None
        if path:
            self.settings["test_target"] = path
            self.set_status(f"Test Hand will write to {path}")
        return path

    def choose_test_command(self):
        cmd = simpledialog.askstring(
            APP_NAME, "Command to run after each Test Hand export ({file} = the exported file).\n"
            "Leave empty for none.", initialvalue=self.settings["test_command"], parent=self.root)
        if cmd is not None:
            self.settings["test_command"] = cmd.strip()
            self.set_status("Test command " + ("set" if cmd.strip() else "cleared"))

    def copy_tutor_json(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(tutor_json_text(self.deal))
        self.set_status("Tutor JSON copied to clipboard")

    def test_hand(self):
        v = self.deal.validation()
        if v.errors:
            self.set_status("Not exported — " + "; ".join(v.errors), error=True)
            return
        target = self.settings["test_target"] or self.choose_test_target()
        if not target:
            return
        try:
            export_tutor(self.deal, target)
        except OSError as e:
            self.set_status(f"Test Hand failed: {e}", error=True)
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(tutor_json_text(self.deal))
        msg = f"Test hand written to {target} (and copied to clipboard)"
        cmd = self.settings["test_command"]
        if cmd:
            try:
                subprocess.Popen(cmd.replace("{file}", f'"{target}"'), shell=True)
                msg += " — test command started"
            except OSError as e:
                msg += f" — test command failed: {e}"
        if v.warnings:
            msg += "   ⚠ " + "; ".join(v.warnings)
        self.set_status(msg, error=False)

    def toggle_four_colour(self):
        self.settings["four_colour"] = self.four_colour_var.get()
        self.canvas.four_colour = self.four_colour_var.get()
        self.canvas.redraw()


def _safe_name(text):
    return re.sub(r'[\\/:*?"<>|]+', "", text).strip()
