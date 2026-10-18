"""Side panel forms: deal settings, author information, versions."""

import tkinter as tk
from tkinter import ttk

from .cards import (SEATS, SEAT_NAMES, SUITS, SUIT_NAMES, rank_of, sorted_cards,
                    suit_of)
from .model import Contract, DefensiveOverride

# Plain words, not suit symbols: ♣ and ♠ are too easy to confuse at a glance.
STRAIN_CHOICES = ["", "Spades", "Hearts", "Diamonds", "Clubs", "No Trump"]
STRAIN_CODES = {"": "", "Spades": "S", "Hearts": "H", "Diamonds": "D", "Clubs": "C",
                "No Trump": "N"}
NO_LEAD = "(none)"


class DealPanel(ttk.LabelFrame):
    def __init__(self, master, app):
        super().__init__(master, text="Deal", padding=6)
        self.app = app
        self._loading = False
        self._lead_cards = []

        ttk.Label(self, text="Contract").grid(row=0, column=0, sticky="w")
        row = ttk.Frame(self)
        row.grid(row=0, column=1, sticky="w", pady=2)
        self.level = ttk.Combobox(row, values=["", "1", "2", "3", "4", "5", "6", "7"],
                                  width=3, state="readonly")
        self.strain = ttk.Combobox(row, values=STRAIN_CHOICES, width=9, state="readonly")
        self.declarer = ttk.Combobox(row, values=list(SEATS), width=3, state="readonly")
        self.level.pack(side="left")
        self.strain.pack(side="left", padx=(4, 0))
        ttk.Label(row, text="by").pack(side="left", padx=6)
        self.declarer.pack(side="left")
        for cb in (self.level, self.strain, self.declarer):
            cb.bind("<<ComboboxSelected>>", self._contract_changed)

        self.lead_label = ttk.Label(self, text="Opening lead")
        self.lead_label.grid(row=1, column=0, sticky="w")
        self.lead = ttk.Combobox(self, width=18, state="readonly")
        self.lead.grid(row=1, column=1, sticky="w", pady=2)
        self.lead.bind("<<ComboboxSelected>>", self._lead_changed)

        self.later = {}
        for r, seat in zip((2, 4), "WE"):
            ttk.Label(self, text=f"{SEAT_NAMES[seat]} later leads").grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
            ed = LaterLeadsEditor(self, app, seat)
            ed.grid(row=r + 1, column=0, columnspan=2, sticky="we", padx=(8, 0))
            self.later[seat] = ed
        self.columnconfigure(1, weight=1)

    def refresh(self, deal, full=False):
        self._loading = True
        c = deal.contract
        if full or self.focus_get() not in (self.level, self.strain, self.declarer):
            self.level.set(str(c.level) if c.level else "")
            self.strain.set({v: k for k, v in STRAIN_CODES.items()}.get(c.strain, ""))
            self.declarer.set(c.declarer)
        leader = c.leader
        self.lead_label.config(text=f"{SEAT_NAMES[leader]} opening lead")
        planned = set(deal.later_leads.get(leader, []))
        self._lead_cards = [x for x in deal.hand(leader) if x not in planned]
        if deal.opening_lead is not None and deal.opening_lead not in self._lead_cards:
            self._lead_cards = [deal.opening_lead] + self._lead_cards
        self.lead["values"] = [NO_LEAD] + [card_words(x) for x in self._lead_cards]
        self.lead.set(card_words(deal.opening_lead) if deal.opening_lead is not None else NO_LEAD)
        for ed in self.later.values():
            ed.refresh(deal)
        self._loading = False

    def _contract_changed(self, event=None):
        if self._loading:
            return
        level = int(self.level.get()) if self.level.get() else None
        self.app.set_contract(Contract(level=level, strain=STRAIN_CODES[self.strain.get()],
                                       declarer=self.declarer.get() or "S"))

    def _lead_changed(self, event=None):
        if self._loading:
            return
        i = self.lead.current()
        self.app.deal.set_opening_lead(None if i <= 0 else self._lead_cards[i - 1])


def planned_leads(deal, seat):
    """Cards already in seat's lead plan: its later leads, plus the opening lead if it leads."""
    cards = set(deal.later_leads.get(seat, []))
    if deal.opening_lead is not None and deal.contract.leader == seat:
        cards.add(deal.opening_lead)
    return cards


class LaterLeadsEditor(ttk.Frame):
    """One defender's later leads: a card dropdown per lead, then a row to add one more.

    Each dropdown offers only the defender's cards that are not already in their
    lead plan, so a card can never be planned twice.
    """

    def __init__(self, master, app, seat):
        super().__init__(master)
        self.app = app
        self.seat = seat
        self._rows = []         # (number label, card dropdown, Delete button) per lead
        self._choices = []      # card numbers behind each row's dropdown
        self._new_cards = []    # card numbers behind the add-row dropdown
        ttk.Style().configure("Row.TButton", padding=0)
        bold = ("Segoe UI", 9, "bold")
        ttk.Label(self, text="Lead opportunity", font=bold).grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(self, text="Card", font=bold).grid(row=0, column=1, sticky="w")
        self.new_num = ttk.Label(self)
        self.new_card = ttk.Combobox(self, width=18, state="readonly")
        self.add_btn = ttk.Button(self, text="Add Lead", command=self._add)

    def refresh(self, deal):
        leads = deal.later_leads[self.seat]
        while len(self._rows) > len(leads):
            for w in self._rows.pop():
                w.destroy()
        while len(self._rows) < len(leads):
            i = len(self._rows)
            cb = ttk.Combobox(self, width=18, state="readonly")
            cb.bind("<<ComboboxSelected>>", lambda e, k=i: self._changed(k))
            row = (ttk.Label(self, text=str(i + 1)), cb,
                   ttk.Button(self, text="Delete", width=6, style="Row.TButton",
                              command=lambda k=i: self._delete(k)))
            for c, w in enumerate(row):
                w.grid(row=i + 1, column=c, sticky="w", pady=1, padx=(4, 0) if c == 2 else 0)
            self._rows.append(row)

        free = set(deal.hand(self.seat)) - planned_leads(deal, self.seat)
        self._choices = []
        for (_, cb, _), card in zip(self._rows, leads):
            self._choices.append(sorted_cards(free | {card}))
            cb["values"] = [card_words(c) for c in self._choices[-1]]
            cb.set(card_words(card))

        i = self.new_card.current()
        keep = self._new_cards[i] if 0 <= i < len(self._new_cards) else None
        self._new_cards = sorted_cards(free)
        self.new_card["values"] = [card_words(c) for c in self._new_cards]
        self.new_card.set(card_words(keep) if keep in self._new_cards else "")
        r = len(leads) + 1
        self.new_num.config(text=str(r))
        self.new_num.grid(row=r, column=0, sticky="w", pady=(2, 0))
        self.new_card.grid(row=r, column=1, sticky="w", pady=(2, 0))
        self.add_btn.grid(row=r, column=2, sticky="w", padx=(4, 0), pady=(2, 0))

    def _set(self, leads):
        self.app.deal.set_later_leads(self.seat, leads)

    def _changed(self, k):
        leads = list(self.app.deal.later_leads[self.seat])
        leads[k] = self._choices[k][self._rows[k][1].current()]
        self._set(leads)

    def _delete(self, k):
        leads = list(self.app.deal.later_leads[self.seat])
        leads.pop(k)
        self._set(leads)

    def _add(self):
        i = self.new_card.current()
        if not 0 <= i < len(self._new_cards):
            self.app.set_status(f"Choose a card for {SEAT_NAMES[self.seat]}'s next lead first",
                                error=True)
            return
        self._set(list(self.app.deal.later_leads[self.seat]) + [self._new_cards[i]])


class AuthorPanel(ttk.LabelFrame):
    SINGLE = [("book", "Book"), ("page", "Page"), ("chapter", "Chapter"), ("title", "Hand title")]
    MULTI = [("concept", "Concept", 2), ("crucial_play", "Crucial play", 2),
             ("failure_mechanism", "Failure mechanism", 2), ("notes", "Notes", 6)]

    def __init__(self, master, app):
        super().__init__(master, text="Author (not exported to the student)", padding=6)
        self.app = app
        self._loading = False
        self.vars = {}
        self.texts = {}

        top = ttk.Frame(self)
        top.pack(fill="x")
        for i, (key, label) in enumerate(self.SINGLE):
            var = tk.StringVar()
            var.trace_add("write", lambda *a, k=key: self._single_changed(k))
            self.vars[key] = var
            if key == "book":
                ttk.Label(top, text=label).grid(row=0, column=0, sticky="w")
                ttk.Entry(top, textvariable=var, width=16).grid(row=0, column=1, sticky="we", pady=2)
            elif key == "page":
                ttk.Label(top, text=label).grid(row=0, column=2, sticky="w", padx=(6, 2))
                ttk.Entry(top, textvariable=var, width=5).grid(row=0, column=3, sticky="w")
            else:
                ttk.Label(top, text=label).grid(row=i - 1, column=0, sticky="w")
                ttk.Entry(top, textvariable=var).grid(row=i - 1, column=1, columnspan=3,
                                                      sticky="we", pady=2)
        top.columnconfigure(1, weight=1)

        for key, label, height in self.MULTI:
            ttk.Label(self, text=label).pack(anchor="w", pady=(4, 0))
            t = tk.Text(self, height=height, width=36, wrap="word", undo=True,
                        font=("Segoe UI", 9), relief="solid", borderwidth=1)
            t.pack(fill="both", expand=(key == "notes"))
            t.bind("<<Modified>>", lambda ev, k=key: self._text_changed(k))
            self.texts[key] = t

    def refresh(self, deal):
        self._loading = True
        for key, var in self.vars.items():
            var.set(getattr(deal.author, key))
        for key, t in self.texts.items():
            t.delete("1.0", "end")
            t.insert("1.0", getattr(deal.author, key))
            t.edit_reset()
            t.edit_modified(False)
        self._loading = False

    def _single_changed(self, key):
        if self._loading:
            return
        setattr(self.app.deal.author, key, self.vars[key].get())
        self.app.author_changed(redraw=(key == "title"))

    def _text_changed(self, key):
        t = self.texts[key]
        if not t.edit_modified():
            return
        t.edit_modified(False)
        if self._loading:
            return
        setattr(self.app.deal.author, key, t.get("1.0", "end-1c"))
        self.app.author_changed()


class VersionsPanel(ttk.LabelFrame):
    def __init__(self, master, app):
        super().__init__(master, text="Versions", padding=6)
        self.app = app
        row = ttk.Frame(self)
        row.pack(fill="x")
        self.name = ttk.Entry(row)
        self.name.pack(side="left", fill="x", expand=True)
        self.name.bind("<Return>", lambda e: self.app.snapshot_version())
        ttk.Button(row, text="Snapshot", command=self.app.snapshot_version).pack(side="left", padx=(4, 0))

        self.listbox = tk.Listbox(self, height=6, activestyle="none", exportselection=False,
                                  font=("Segoe UI Symbol", 9))
        self.listbox.pack(fill="both", expand=True, pady=4)
        self.listbox.bind("<Double-Button-1>", lambda e: self.restore())

        btns = ttk.Frame(self)
        btns.pack(fill="x")
        ttk.Button(btns, text="Restore", command=self.restore).pack(side="left")
        ttk.Button(btns, text="Rename", command=self.rename).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete", command=self.delete).pack(side="left")

    def take_name(self, default):
        name = self.name.get().strip() or default
        self.name.delete(0, "end")
        return name

    def refresh(self, deal):
        self.listbox.delete(0, "end")
        for v in deal.versions:
            when = v.created[11:16] if len(v.created) >= 16 else ""
            self.listbox.insert("end", f"{v.name}   {when}")

    def _selected(self):
        sel = self.listbox.curselection()
        if not sel:
            self.app.set_status("Select a version first", error=True)
            return None
        return sel[0]

    def restore(self):
        i = self._selected()
        if i is not None:
            self.app.deal.restore_version(i)
            self.app.canvas.clear_selection()

    def rename(self):
        i = self._selected()
        if i is None:
            return
        name = self.name.get().strip()
        if not name:
            self.app.set_status("Type the new name in the box above, then press Rename", error=True)
            return
        self.name.delete(0, "end")
        self.app.deal.rename_version(i, name)
        self.app.versions_changed()

    def delete(self):
        i = self._selected()
        if i is not None:
            self.app.deal.delete_version(i)
            self.app.versions_changed()


# ----- defensive play overrides ------------------------------------------------

RANK_WORDS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
OVERRIDE_PLAYERS = ["East", "West"]
_SEAT_BY_NAME = {name: seat for seat, name in SEAT_NAMES.items()}


def card_words(c):
    """'Ace of Spades': words, so clubs and spades can't be confused."""
    return f"{RANK_WORDS[rank_of(c)]} of {SUIT_NAMES[suit_of(c)]}"


class OverridesPanel(ttk.LabelFrame):
    """Dropdown editor above a table of overrides, each row with Edit and Delete."""

    COLUMNS = ["Player", "Suit", "Occurrence", "Card"]

    def __init__(self, master, app):
        super().__init__(master, text="Defensive Play Overrides", padding=6)
        self.app = app
        self._cards = []        # card numbers behind the Card dropdown
        self._editing = None    # index of the override loaded into the editor

        form = ttk.Frame(self)
        form.pack(fill="x")
        self.player = ttk.Combobox(form, values=OVERRIDE_PLAYERS, width=8, state="readonly")
        self.suit = ttk.Combobox(form, values=SUIT_NAMES, width=9, state="readonly")
        self.occurrence = ttk.Spinbox(form, from_=1, to=13, width=4, state="readonly")
        self.card = ttk.Combobox(form, width=18, state="readonly")
        for i, (label, w) in enumerate([("Player", self.player), ("Suit led", self.suit),
                                        ("Occurrence", self.occurrence), ("Card", self.card)]):
            r, c = divmod(i, 2)
            ttk.Label(form, text=label).grid(row=r, column=2 * c, sticky="w", padx=(6 * c, 4))
            w.grid(row=r, column=2 * c + 1, sticky="w", pady=2)
        self.player.set("East")
        self.suit.set("Spades")
        self.occurrence.set(1)
        self.player.bind("<<ComboboxSelected>>", lambda e: self._fill_cards())
        self.suit.bind("<<ComboboxSelected>>", lambda e: self._fill_cards())

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(2, 0))
        self.add_btn = ttk.Button(btns, text="Add Override", command=self._add_or_update)
        self.add_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="Cancel", command=self._cancel_edit)
        self.hint = ttk.Label(self, text="", foreground="#a00")
        self.hint.pack(anchor="w")

        # Fixed column widths, so the panel is as wide as it will ever be from the
        # start and rows never get clipped by the side pane.
        ttk.Style().configure("Row.TButton", padding=0)
        self.table = ttk.Frame(self)
        self.table.pack(fill="x", pady=(4, 0))
        for c, name in enumerate(self.COLUMNS):
            ttk.Label(self.table, text=name, font=("Segoe UI", 9, "bold"),
                      width=17 if name == "Card" else None).grid(
                row=0, column=c, sticky="w", padx=(0, 4))
        for c, (text, width) in enumerate([("Edit", 4), ("Delete", 6)], start=4):
            probe = ttk.Button(self.table, text=text, width=width, style="Row.TButton")
            self.table.columnconfigure(c, minsize=probe.winfo_reqwidth() + 2)
            probe.destroy()
        ttk.Separator(self.table).grid(row=1, column=0, columnspan=6, sticky="we", pady=2)
        self._rows = []

    def refresh(self, deal, full=False):
        if full:
            self._cancel_edit()
        for w in self._rows:
            w.destroy()
        self._rows = []
        if not deal.defensive_overrides:
            self._rows.append(ttk.Label(self.table, text="No overrides", foreground="#666"))
            self._rows[-1].grid(row=2, column=0, columnspan=4, sticky="w")
        for i, o in enumerate(deal.defensive_overrides):
            r = i + 2
            for c, text in enumerate([SEAT_NAMES[o.player], o.suit_led, o.occurrence,
                                      card_words(o.card)]):
                self._rows.append(ttk.Label(self.table, text=text))
                self._rows[-1].grid(row=r, column=c, sticky="w", padx=(0, 4))
            self._rows.append(ttk.Button(self.table, text="Edit", width=4, style="Row.TButton",
                                         command=lambda k=i: self._edit(k)))
            self._rows[-1].grid(row=r, column=4, pady=1)
            self._rows.append(ttk.Button(self.table, text="Delete", width=6, style="Row.TButton",
                                         command=lambda k=i: self._delete(k)))
            self._rows[-1].grid(row=r, column=5, padx=(2, 0))
        self._fill_cards()      # hands may have changed

    def _fill_cards(self, keep=None):
        """Only the chosen player's current cards in the suit led can be picked."""
        if keep is None and 0 <= self.card.current() < len(self._cards):
            keep = self._cards[self.card.current()]
        seat = _SEAT_BY_NAME[self.player.get()]
        suit = SUIT_NAMES.index(self.suit.get())
        self._cards = [c for c in self.app.deal.hand(seat) if suit_of(c) == suit]
        self.card["values"] = [card_words(c) for c in self._cards]
        self.card.set(card_words(keep) if keep in self._cards else "")
        self.hint.config(text="" if self._cards
                         else f"{self.player.get()} holds no {self.suit.get()}")

    def _add_or_update(self):
        i = self.card.current()
        if not 0 <= i < len(self._cards):
            self.hint.config(text="Choose a card to play")
            return
        o = DefensiveOverride(suit_led=SUITS[SUIT_NAMES.index(self.suit.get())],
                              occurrence=int(self.occurrence.get()),
                              player=_SEAT_BY_NAME[self.player.get()], card=self._cards[i])
        overrides = self.app.deal.defensive_overrides
        if any(k != self._editing and (x.player, x.suit_led, x.occurrence)
               == (o.player, o.suit_led, o.occurrence) for k, x in enumerate(overrides)):
            self.hint.config(text=f"{self.player.get()} already has an override for that lead")
            return
        editing = self._editing
        self._cancel_edit()
        self.card.set("")
        if editing is None:
            self.app.deal.add_override(o)
        else:
            self.app.deal.replace_override(editing, o)

    def _edit(self, index):
        o = self.app.deal.defensive_overrides[index]
        self._editing = index
        self.player.set(SEAT_NAMES[o.player])
        self.suit.set(SUIT_NAMES[SUITS.index(o.suit_led)])
        self.occurrence.set(o.occurrence)
        self._fill_cards(keep=o.card)
        self.add_btn.config(text="Update Override")
        self.cancel_btn.pack(side="left", padx=(4, 0))

    def _cancel_edit(self):
        self._editing = None
        self.add_btn.config(text="Add Override")
        self.cancel_btn.pack_forget()

    def _delete(self, index):
        self._cancel_edit()
        self.app.deal.delete_override(index)
