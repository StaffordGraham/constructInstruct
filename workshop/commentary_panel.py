"""The Commentary and Coaching tabs beside the diagram."""

import tkinter as tk
from tkinter import ttk

from .cards import SEAT_NAMES, card_label
from .commentary import (COACH_SEATS, SHORTCUTS, accept_card_record, card_change_text,
                         card_changes, checkpoint_problems, checkpoint_when, cards_text,
                         markup_spans, rank_order, update_card_record)

# The house suit colours, as in SmallCards
SUIT_FG = {"S": "#274C77", "H": "#d00000", "D": "#008000", "C": "#000000"}
SUIT_BUTTONS = [("♠", "S"), ("♥", "H"), ("♦", "D"), ("♣", "C")]
WARN_FG = "#b26a00"
SUIT_WORDS = ["Spades", "Hearts", "Diamonds", "Clubs"]


class CommentaryPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=6)
        self.app = app
        self.deal = None
        self._loading = False

        self.notes = {}              # author field -> its Text box

        ttk.Label(self, text="Concept — printed under the hand's title",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._note_box(self, "concept", 2, ("Segoe UI", 10, "italic")).pack(fill="x")
        ttk.Label(self, text="Commentary — printed in the book",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 0))

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(4, 2))
        for symbol, suit in SUIT_BUTTONS:
            tk.Button(bar, text=symbol, fg=SUIT_FG[suit], width=2, relief="groove",
                      font=("Segoe UI Symbol", 11),
                      command=lambda s=symbol: self._insert(s)).pack(side="left", padx=1)
        ttk.Button(bar, text="Bold", width=5, command=lambda: self._wrap("**")).pack(side="left", padx=(8, 1))
        ttk.Button(bar, text="Italic", width=5, command=lambda: self._wrap("*")).pack(side="left")
        ttk.Label(self, text="Type !s !h !d !c for ♠ ♥ ♦ ♣.  A blank line starts a new "
                  "paragraph;  - starts a bullet.", foreground="#666", wraplength=340,
                  justify="left").pack(anchor="w")

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, pady=(4, 0))
        self.text = tk.Text(frame, wrap="word", undo=True, width=44, height=14,
                            font=("Segoe UI", 11), relief="solid", borderwidth=1,
                            padx=6, pady=4, spacing1=1, spacing2=1)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        for suit, fg in SUIT_FG.items():
            self.text.tag_configure("card-" + suit, foreground=fg,
                                    font=("Segoe UI Symbol", 11, "bold"))
        self.text.tag_configure("bold", font=("Segoe UI", 11, "bold"))
        self.text.tag_configure("italic", font=("Segoe UI", 11, "italic"))
        self.text.tag_configure("marker", foreground="#aaa")
        self.text.tag_configure("moved", background="#ffd8a8", underline=True)
        self.text.tag_raise("moved")
        self.text.bind("<<Modified>>", self._modified)
        self.text.bind("<KeyRelease>", self._shortcut)

        self.checks = ttk.Frame(self)
        self.checks.pack(fill="x", pady=(6, 0))

        private = ttk.LabelFrame(self, text="Your notes — not printed", padding=4)
        private.pack(fill="x", pady=(6, 0))
        for key, label in (("crucial_play", "Crucial play"),
                           ("failure_mechanism", "Failure mechanism"), ("notes", "Notes")):
            ttk.Label(private, text=label).pack(anchor="w")
            self._note_box(private, key, 2).pack(fill="x")

    def _note_box(self, parent, key, height, font=("Segoe UI", 9)):
        """A text box for one of the hand's author fields (concept, crucial play, ...)."""
        t = tk.Text(parent, height=height, width=44, wrap="word", undo=True, font=font,
                    relief="solid", borderwidth=1)
        t.bind("<<Modified>>", lambda e, k=key: self._note_changed(k))
        self.notes[key] = t
        return t

    def refresh_notes(self):
        """Show the concept and notes again (they were typed somewhere else)."""
        self._loading = True
        for key, t in self.notes.items():
            if t.get("1.0", "end-1c") != getattr(self.deal.author, key):
                t.delete("1.0", "end")
                t.insert("1.0", getattr(self.deal.author, key))
                t.edit_modified(False)
        self._loading = False

    def _note_changed(self, key):
        t = self.notes[key]
        if not t.edit_modified():
            return
        t.edit_modified(False)
        if self._loading or self.deal is None:
            return
        setattr(self.deal.author, key, t.get("1.0", "end-1c"))
        self.app.author_changed()

    # ----- loading and showing ---------------------------------------------
    def refresh(self, deal):
        self.deal = deal
        self._loading = True
        self.text.delete("1.0", "end")
        self.text.insert("1.0", deal.commentary)
        self.text.edit_reset()
        self.text.edit_modified(False)
        for key, t in self.notes.items():
            t.delete("1.0", "end")
            t.insert("1.0", getattr(deal.author, key))
            t.edit_reset()
            t.edit_modified(False)
        self._loading = False
        self.cards_moved()

    def cards_moved(self):
        """The cards or the text changed: recolour and recheck the cards mentioned."""
        self._highlight()
        for child in self.checks.winfo_children():
            child.destroy()
        changes = card_changes(self.deal)
        if not changes:
            return
        ttk.Label(self.checks, text="Check the commentary — cards have moved:",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")
        for change in changes:
            tk.Label(self.checks, text="• " + card_change_text(change), fg=WARN_FG,
                     wraplength=340, justify="left", anchor="w",
                     font=("Segoe UI Symbol", 9)).pack(anchor="w")
        ttk.Button(self.checks, text="The commentary is right for the cards as they are now",
                   command=self._accept).pack(anchor="w", pady=(4, 0))

    def _highlight(self):
        t = self.text
        for tag in ("bold", "italic", "marker", "moved", "card-S", "card-H", "card-D", "card-C"):
            t.tag_remove(tag, "1.0", "end")
        text = t.get("1.0", "end-1c")
        for start, end, kind in markup_spans(text):
            t.tag_add(kind, f"1.0+{start}c", f"1.0+{end}c")
        moved = {c for c, _, _ in card_changes(self.deal)} if self.deal else set()
        if moved:
            from .commentary import card_mentions
            for start, end, c in card_mentions(text):
                if c in moved:
                    t.tag_add("moved", f"1.0+{start}c", f"1.0+{end}c")

    # ----- editing -----------------------------------------------------------
    def _modified(self, event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if self._loading or self.deal is None:
            return
        self.deal.commentary = self.text.get("1.0", "end-1c")
        update_card_record(self.deal)
        self.app.author_changed()
        self.cards_moved()

    def _shortcut(self, event=None):
        before = self.text.get("insert-2c", "insert")
        symbol = SHORTCUTS.get(before.lower())
        if symbol:
            self.text.delete("insert-2c", "insert")
            self.text.insert("insert", symbol)

    def _insert(self, symbol):
        self.text.insert("insert", symbol)
        self.text.focus_set()

    def _wrap(self, marker):
        t = self.text
        try:
            first, last = t.index("sel.first"), t.index("sel.last")
        except tk.TclError:
            t.insert("insert", marker + marker)
            t.mark_set("insert", f"insert-{len(marker)}c")
        else:
            t.insert(last, marker)
            t.insert(first, marker)
        t.focus_set()

    def _accept(self):
        accept_card_record(self.deal)
        self.app.author_changed()
        self.cards_moved()


class CoachingPanel(ttk.Frame):
    """SmallCards' coaching checkpoints: at a key moment, the card South or dummy should
    play, a hint after the first wrong card, and an explanation after the second."""

    def __init__(self, master, app):
        super().__init__(master, padding=6)
        self.app = app
        self.deal = None
        self.editing = None          # index of the checkpoint in the form, or None for new
        self._choices = []           # cards listed in the Correct card(s) box

        ttk.Label(self, text="When a student plays the wrong card at a key moment, SmallCards "
                  "shows the hint; after a second wrong card it names the right card and "
                  "shows the explanation.", wraplength=340, justify="left",
                  foreground="#666").pack(anchor="w")

        self.list = ttk.Treeview(self, columns=("when", "who", "cards"), show="headings",
                                 height=5, selectmode="browse")
        for col, text, width in (("when", "When", 110), ("who", "Player", 70),
                                 ("cards", "Correct", 150)):
            self.list.heading(col, text=text, anchor="w")
            self.list.column(col, width=width, anchor="w")
        self.list.tag_configure("warn", foreground=WARN_FG)
        self.list.pack(fill="x", pady=(6, 0))
        self.list.bind("<<TreeviewSelect>>", self._picked)
        self.problems = ttk.Frame(self)
        self.problems.pack(fill="x")

        form = ttk.LabelFrame(self, text="Checkpoint", padding=6)
        form.pack(fill="both", expand=True, pady=(6, 0))
        self.when = tk.StringVar(value="trick")
        row = ttk.Frame(form)
        row.pack(fill="x")
        ttk.Radiobutton(row, text="Trick", variable=self.when, value="trick").pack(side="left")
        self.trick = ttk.Spinbox(row, from_=1, to=13, width=3)
        self.trick.set(1)
        self.trick.pack(side="left", padx=(2, 10))
        ttk.Radiobutton(row, text="First lead of", variable=self.when,
                        value="suit").pack(side="left")
        self.suit = ttk.Combobox(row, values=SUIT_WORDS, width=9, state="readonly")
        self.suit.current(0)
        self.suit.pack(side="left", padx=2)

        row = ttk.Frame(form)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="Player").pack(side="left")
        self.seat = tk.StringVar(value="S")
        for seat, text in (("S", "South"), ("N", "Dummy (North)")):
            ttk.Radiobutton(row, text=text, variable=self.seat, value=seat,
                            command=self._fill_cards).pack(side="left", padx=4)

        ttk.Label(form, text="Correct card(s) — click to choose; more than one is allowed"
                  ).pack(anchor="w", pady=(4, 0))
        self.cards = tk.Listbox(form, selectmode="multiple", height=5, exportselection=False,
                                font=("Segoe UI Symbol", 10), activestyle="none")
        self.cards.pack(fill="x")
        self.cards.bind("<<ListboxSelect>>", lambda e: self._fill_play())
        row = ttk.Frame(form)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="After two misses, play").pack(side="left")
        self.play = ttk.Combobox(row, width=14, state="readonly", font=("Segoe UI Symbol", 9))
        self.play.pack(side="left", padx=4)

        ttk.Label(form, text="Hint (after the first wrong card)").pack(anchor="w", pady=(4, 0))
        self.hint = tk.Text(form, height=2, width=40, wrap="word", font=("Segoe UI", 9),
                            relief="solid", borderwidth=1)
        self.hint.pack(fill="x")
        ttk.Label(form, text="Explanation (after the second)").pack(anchor="w", pady=(4, 0))
        self.explanation = tk.Text(form, height=3, width=40, wrap="word", font=("Segoe UI", 9),
                                   relief="solid", borderwidth=1)
        self.explanation.pack(fill="x")

        row = ttk.Frame(form)
        row.pack(fill="x", pady=(6, 0))
        self.save_btn = ttk.Button(row, text="Add checkpoint", command=self._save)
        self.save_btn.pack(side="left")
        self.delete_btn = ttk.Button(row, text="Delete", command=self._delete)
        self.delete_btn.pack(side="left", padx=4)
        ttk.Button(row, text="New", command=self._new).pack(side="left")
        self.message = ttk.Label(form, text="", foreground=WARN_FG, wraplength=320)
        self.message.pack(anchor="w", pady=(4, 0))

    # ----- list ----------------------------------------------------------------
    def refresh(self, deal, keep=False):
        """Show a deal's checkpoints. keep=True keeps the form (the cards moved)."""
        self.deal = deal
        self.list.delete(*self.list.get_children())
        for i, cp in enumerate(deal.checkpoints):
            who = {"S": "South", "N": "Dummy"}.get(cp.get("seat"), "?")
            self.list.insert("", "end", iid=str(i), values=(
                checkpoint_when(cp), who, cards_text(cp.get("accept") or [])),
                tags=("warn",) if checkpoint_problems(deal, cp) else ())
        for child in self.problems.winfo_children():
            child.destroy()
        for i, cp in enumerate(deal.checkpoints, start=1):
            for p in checkpoint_problems(deal, cp):
                tk.Label(self.problems, text=f"• Checkpoint {i}: {p}", fg=WARN_FG,
                         font=("Segoe UI Symbol", 9), wraplength=340, justify="left",
                         anchor="w").pack(anchor="w")
        if keep and self.editing is not None and self.editing < len(deal.checkpoints):
            self._fill_cards(keep_selection=True)
            self.list.selection_set(str(self.editing))
        else:
            self._new()

    def _picked(self, event=None):
        sel = self.list.selection()
        if not sel or int(sel[0]) == self.editing:
            return
        self._load(int(sel[0]))

    # ----- form ------------------------------------------------------------------
    def _new(self):
        self.editing = None
        self.list.selection_remove(self.list.selection())
        self.when.set("trick")
        self.trick.set(1)
        self.suit.current(0)
        self.seat.set("S")
        self._set_text(self.hint, "")
        self._set_text(self.explanation, "")
        self._fill_cards()
        self.save_btn.config(text="Add checkpoint")
        self.delete_btn.state(["disabled"])
        self.message.config(text="")

    def _load(self, index):
        cp = self.deal.checkpoints[index]
        self.editing = index
        if isinstance(cp.get("suitLed"), int) and not isinstance(cp.get("trick"), int):
            self.when.set("suit")
            self.suit.current(cp["suitLed"] if 0 <= cp["suitLed"] < 4 else 0)
        else:
            self.when.set("trick")
            self.trick.set(cp.get("trick") if isinstance(cp.get("trick"), int) else 1)
        self.seat.set(cp.get("seat") if cp.get("seat") in COACH_SEATS else "S")
        self._set_text(self.hint, cp.get("hint") or "")
        self._set_text(self.explanation, cp.get("explanation") or "")
        self._fill_cards(chosen=cp.get("accept") or [], play=cp.get("play"))
        self.save_btn.config(text="Save changes")
        self.delete_btn.state(["!disabled"])
        self.message.config(text="")

    def _set_text(self, widget, value):
        widget.delete("1.0", "end")
        widget.insert("1.0", value)

    def _fill_cards(self, chosen=None, play=None, keep_selection=False):
        """List the player's cards (and any chosen card that is no longer there)."""
        if keep_selection:
            chosen = self._chosen()
            play = self._play_card()
        chosen = [c for c in chosen or [] if isinstance(c, int) and 0 <= c < 52]
        hand = self.deal.hand(self.seat.get()) if self.deal else []
        self._choices = rank_order(set(hand) | set(chosen))
        self.cards.delete(0, "end")
        for i, c in enumerate(self._choices):
            self.cards.insert("end", card_label(c) + ("" if c in hand else "   (not in this hand)"))
            if c in chosen:
                self.cards.selection_set(i)
        self._fill_play(play)

    def _chosen(self):
        return [self._choices[i] for i in self.cards.curselection()]

    def _fill_play(self, play=None):
        if play is None:
            play = self._play_card()
        chosen = self._chosen()
        self._play_choices = [None] + chosen
        self.play.config(values=["(the first correct card)"] + [card_label(c) for c in chosen])
        self.play.current(chosen.index(play) + 1 if play in chosen else 0)

    def _play_card(self):
        i = self.play.current()
        choices = getattr(self, "_play_choices", [None])
        return choices[i] if 0 < i < len(choices) else None

    def _save(self):
        chosen = self._chosen()
        if not chosen:
            self.message.config(text="Choose at least one correct card")
            return
        if self.editing is None:
            cp = {}
            self.deal.checkpoints.append(cp)
            self.editing = len(self.deal.checkpoints) - 1
        else:
            cp = self.deal.checkpoints[self.editing]
        cp.pop("trick", None)
        cp.pop("suitLed", None)
        if self.when.get() == "trick":
            try:
                cp["trick"] = max(1, min(13, int(self.trick.get())))
            except ValueError:
                cp["trick"] = 1
        else:
            cp["suitLed"] = self.suit.current()
        cp["seat"] = self.seat.get()
        cp["accept"] = chosen
        play = self._play_card()
        if play is None:
            cp.pop("play", None)
        else:
            cp["play"] = play
        cp["hint"] = self.hint.get("1.0", "end-1c").strip()
        cp["explanation"] = self.explanation.get("1.0", "end-1c").strip()
        self.app.author_changed()
        index = self.editing
        self.refresh(self.deal, keep=True)
        self._load(index)
        self.app.set_status(f"Checkpoint {index + 1} saved — press F5 to try it in SmallCards")

    def _delete(self):
        if self.editing is None:
            return
        self.deal.checkpoints.pop(self.editing)
        self.app.author_changed()
        self.refresh(self.deal)
