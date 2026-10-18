"""The deal being built. No tkinter in here.

Every card has exactly one location: a seat letter or None (the pool).
All card changes go through Deal.move / swap / set_hand / ... so that they
are recorded for undo and listeners are told to redraw.
"""

import copy
from dataclasses import dataclass, field, fields
from datetime import datetime

from .cards import (ALL_CARDS, SEATS, SEAT_NAMES, card_label, hcp, shape_text,
                    sorted_cards)

STRAINS = "SHDCN"
STRAIN_NAMES = {"S": "Spades", "H": "Hearts", "D": "Diamonds", "C": "Clubs",
                "N": "No Trump", "": ""}


def lho(seat):
    """Left-hand opponent: the next seat clockwise (N→E→S→W)."""
    return SEATS[(SEATS.index(seat) + 1) % 4]


@dataclass
class Contract:
    level: int | None = None
    strain: str = ""        # S H D C N, or "" when not set
    declarer: str = "S"

    @property
    def is_set(self):
        return bool(self.level) and self.strain in STRAINS and self.strain != ""

    @property
    def leader(self):
        return lho(self.declarer)

    def short_text(self):
        """Display text, e.g. '4 Spades' or '3 No Trump'."""
        if not self.is_set:
            return ""
        return f"{self.level} {STRAIN_NAMES[self.strain]}"


@dataclass
class AuthorInfo:
    book: str = ""
    page: str = ""
    chapter: str = ""
    title: str = ""
    concept: str = ""
    crucial_play: str = ""
    failure_mechanism: str = ""
    notes: str = ""

    @classmethod
    def field_names(cls):
        return [f.name for f in fields(cls)]


@dataclass
class Version:
    name: str
    hands: dict          # seat -> list of card numbers
    created: str = ""


@dataclass
class Validation:
    counts: dict
    assigned: int
    missing: list
    duplicates: list
    errors: list = field(default_factory=list)     # stop Test Hand
    warnings: list = field(default_factory=list)   # shown, but do not stop it

    @property
    def complete(self):
        return self.assigned == 52 and all(n == 13 for n in self.counts.values())


class History:
    """Undo/redo as whole-state snapshots (the state is tiny)."""

    def __init__(self, limit=500):
        self.undo_stack = []
        self.redo_stack = []
        self.limit = limit

    def record(self, snapshot):
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > self.limit:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()


class Deal:
    def __init__(self):
        self.location = {c: None for c in ALL_CARDS}
        self.contract = Contract()
        self.opening_lead = None
        self.later_leads = {"W": [], "E": []}
        self.author = AuthorInfo()
        self.versions = []
        self.tutor_extra = {}
        self.duplicates = []      # problems found when a file was loaded
        self.history = History()
        self.listeners = []

    # ----- notification -------------------------------------------------
    def add_listener(self, fn):
        self.listeners.append(fn)

    def notify(self, message=""):
        for fn in self.listeners:
            fn(message)

    # ----- queries -------------------------------------------------------
    def hand(self, seat):
        return sorted_cards(c for c, loc in self.location.items() if loc == seat)

    def pool(self):
        return sorted_cards(c for c, loc in self.location.items() if loc is None)

    def hands(self):
        return {s: self.hand(s) for s in SEATS}

    def stats(self, seat):
        h = self.hand(seat)
        return hcp(h), shape_text(h)

    def validation(self):
        counts = {s: 0 for s in SEATS}
        for loc in self.location.values():
            if loc is not None:
                counts[loc] += 1
        assigned = sum(counts.values())
        v = Validation(counts=counts, assigned=assigned, missing=self.pool(),
                       duplicates=list(self.duplicates))
        for s in SEATS:
            if counts[s] != 13:
                v.errors.append(f"{SEAT_NAMES[s]} has {counts[s]} cards")
        if not self.contract.is_set:
            v.errors.append("No contract set")
        if self.opening_lead is not None and self.contract.is_set:
            holder = self.location[self.opening_lead]
            if holder != self.contract.leader:
                where = SEAT_NAMES[holder] if holder else "the pool"
                v.warnings.append(f"Opening lead {card_label(self.opening_lead)} "
                                  f"is in {where}, not {SEAT_NAMES[self.contract.leader]}")
        for seat, leads in self.later_leads.items():
            for c in leads:
                if self.location[c] != seat:
                    v.warnings.append(f"{SEAT_NAMES[seat]} lead {card_label(c)} "
                                      f"is not in {SEAT_NAMES[seat]}'s hand")
        if self.contract.declarer != "S":
            v.warnings.append("The tutor expects South to declare")
        if self.duplicates:
            v.warnings.append("Duplicates in loaded file: "
                              + " ".join(card_label(c) for c in self.duplicates))
        return v

    # ----- undo support ----------------------------------------------------
    def _snapshot(self):
        return (dict(self.location), self.opening_lead, copy.deepcopy(self.later_leads))

    def _restore(self, snap):
        self.location = dict(snap[0])
        self.opening_lead = snap[1]
        self.later_leads = copy.deepcopy(snap[2])

    def _record(self):
        self.history.record(self._snapshot())

    def can_undo(self):
        return bool(self.history.undo_stack)

    def can_redo(self):
        return bool(self.history.redo_stack)

    def undo(self):
        if not self.history.undo_stack:
            return False
        self.history.redo_stack.append(self._snapshot())
        self._restore(self.history.undo_stack.pop())
        self.notify("Undo")
        return True

    def redo(self):
        if not self.history.redo_stack:
            return False
        self.history.undo_stack.append(self._snapshot())
        self._restore(self.history.redo_stack.pop())
        self.notify("Redo")
        return True

    # ----- card operations ---------------------------------------------------
    def move(self, cards, dest):
        """Move cards to a seat letter, or to the pool when dest is None.

        Returns the number of cards that actually moved.
        """
        cards = [c for c in cards if self.location[c] != dest]
        if not cards:
            return 0
        self._record()
        for c in cards:
            self.location[c] = dest
        where = SEAT_NAMES[dest] if dest else "pool"
        names = " ".join(card_label(c) for c in sorted_cards(cards))
        self.notify(f"Moved {names} → {where}")
        return len(cards)

    def swap(self, a, b):
        """Exchange the locations of two cards. Returns False if they share one."""
        la, lb = self.location[a], self.location[b]
        if la == lb:
            return False
        self._record()
        self.location[a], self.location[b] = lb, la

        def name(loc):
            return loc if loc else "pool"
        self.notify(f"Swapped {card_label(a)} ({name(la)}) ↔ {card_label(b)} ({name(lb)})")
        return True

    def set_hand(self, seat, cards):
        """Make seat hold exactly these cards (taken from wherever they are).

        Cards that were in the hand but are not listed go to the pool.
        """
        cards = set(cards)
        before = self._snapshot()
        for c, loc in self.location.items():
            if loc == seat and c not in cards:
                self.location[c] = None
        for c in cards:
            self.location[c] = seat
        if self.location == before[0]:
            return
        self.history.record(before)
        self.notify(f"{SEAT_NAMES[seat]} set to {len(cards)} cards")

    def clear_hand(self, seat):
        self.move(self.hand(seat), None)

    def clear_all(self):
        self.move([c for c in ALL_CARDS if self.location[c] is not None], None)

    def set_opening_lead(self, c):
        if c == self.opening_lead:
            return
        self._record()
        self.opening_lead = c
        self.notify(f"Opening lead: {card_label(c)}" if c is not None else "Opening lead cleared")

    def set_later_leads(self, seat, cards):
        cards = list(cards)
        if cards == self.later_leads[seat]:
            return
        self._record()
        self.later_leads[seat] = cards
        self.notify(f"{SEAT_NAMES[seat]} later leads: "
                    + (" ".join(card_label(c) for c in cards) or "none"))

    # ----- versions ----------------------------------------------------------
    def snapshot_version(self, name):
        v = Version(name=name, hands=self.hands(),
                    created=datetime.now().isoformat(timespec="seconds"))
        self.versions.append(v)
        self.notify(f"Version '{name}' saved")
        return v

    def restore_version(self, index):
        v = self.versions[index]
        self._record()
        self.location = {c: None for c in ALL_CARDS}
        for seat, cards in v.hands.items():
            for c in cards:
                self.location[c] = seat
        self.notify(f"Restored version '{v.name}'")

    def delete_version(self, index):
        name = self.versions.pop(index).name
        self.notify(f"Deleted version '{name}'")

    def rename_version(self, index, name):
        self.versions[index].name = name
        self.notify(f"Renamed version to '{name}'")
