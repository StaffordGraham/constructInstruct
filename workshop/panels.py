"""Side panel forms: deal settings, author information, versions."""

import tkinter as tk
from tkinter import ttk

from .cards import SEATS, SEAT_NAMES, card_label, parse_suit_group
from .model import Contract

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

        ttk.Label(self, text="Opening lead").grid(row=1, column=0, sticky="w")
        self.lead = ttk.Combobox(self, width=12, state="readonly", font=("Segoe UI Symbol", 10))
        self.lead.grid(row=1, column=1, sticky="w", pady=2)
        self.lead.bind("<<ComboboxSelected>>", self._lead_changed)

        self.later = {}
        for r, seat in enumerate("WE", start=2):
            ttk.Label(self, text=f"Later {SEAT_NAMES[seat]} leads").grid(row=r, column=0, sticky="w")
            e = ttk.Entry(self, width=18, font=("Segoe UI Symbol", 10))
            e.grid(row=r, column=1, sticky="we", pady=2)
            e.bind("<Return>", lambda ev, s=seat: self._later_changed(s))
            e.bind("<FocusOut>", lambda ev, s=seat: self._later_changed(s))
            self.later[seat] = e
        ttk.Label(self, text="e.g. DQ C5   (Enter to apply)", foreground="#666").grid(
            row=4, column=1, sticky="w")
        self.columnconfigure(1, weight=1)

    def refresh(self, deal, full=False):
        self._loading = True
        c = deal.contract
        if full or self.focus_get() not in (self.level, self.strain, self.declarer):
            self.level.set(str(c.level) if c.level else "")
            self.strain.set({v: k for k, v in STRAIN_CODES.items()}.get(c.strain, ""))
            self.declarer.set(c.declarer)
        leader = c.leader
        self._lead_cards = deal.hand(leader)
        if deal.opening_lead is not None and deal.opening_lead not in self._lead_cards:
            self._lead_cards = [deal.opening_lead] + self._lead_cards
        self.lead["values"] = [NO_LEAD] + [card_label(x) for x in self._lead_cards]
        self.lead.set(card_label(deal.opening_lead) if deal.opening_lead is not None else NO_LEAD)
        for seat, e in self.later.items():
            if full or self.focus_get() is not e:
                e.delete(0, "end")
                e.insert(0, " ".join(card_label(x) for x in deal.later_leads[seat]))
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

    def _later_changed(self, seat):
        if self._loading:
            return
        cards = []
        try:
            for tok in self.later[seat].get().replace(",", " ").split():
                cards.extend(parse_suit_group(tok))
        except ValueError as e:
            self.app.set_status(f"Later leads: {e}", error=True)
            return
        self.app.deal.set_later_leads(seat, cards)


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
