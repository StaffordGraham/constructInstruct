"""A hand's commentary and its SmallCards coaching checkpoints. No tkinter in here.

Commentary is plain text with a little markup:

    a blank line            starts a new paragraph
    - at the start of a line  a bullet point
    **words**               bold
    *words*                 italic
    ♠5  ♥A  ♦10  ♣K        a card (a suit symbol, then the rank)

Typing !s !h !d !c gives ♠ ♥ ♦ ♣.

Each card the commentary mentions is remembered with the hand it was in when it was
first mentioned (deal.commentary_cards). If the card is moved later, card_changes()
reports it, because a sentence such as "ruff with dummy's ♠5" may now be wrong.
"""

import re

from .cards import SEAT_NAMES, SUITS, card, card_label, rank_of, suit_of

SUIT_SYMBOLS = "♠♥♦♣"
SHORTCUTS = {"!s": "♠", "!h": "♥", "!d": "♦", "!c": "♣"}
_RANKS = "23456789TJQKA"
CARD_TOKEN = re.compile(r"([♠♥♦♣])(10|[AKQJT2-9])(?![0-9A-Za-z])")
_INLINE = re.compile(r"\*\*(.+?)\*\*|\*(?!\s)(.+?)(?<!\s)\*")


# ----- cards mentioned in the text --------------------------------------------

def card_mentions(text):
    """(start, end, card number) for each card written in the text, in order."""
    out = []
    for m in CARD_TOKEN.finditer(text):
        rank = "T" if m.group(2) == "10" else m.group(2)
        out.append((m.start(), m.end(), card(SUIT_SYMBOLS.index(m.group(1)), _RANKS.index(rank))))
    return out


def update_card_record(deal):
    """Remember where each newly mentioned card is now; forget cards no longer mentioned.

    A card already remembered keeps the hand it was in when first mentioned, so moving
    it in the diagram is reported until the author says the commentary is right.
    """
    old = deal.commentary_cards
    deal.commentary_cards = {c: old.get(c, deal.location[c])
                             for _, _, c in card_mentions(deal.commentary)}


def accept_card_record(deal):
    """The author has checked the commentary against the cards as they are now."""
    deal.commentary_cards = {c: deal.location[c] for _, _, c in card_mentions(deal.commentary)}


def card_changes(deal):
    """[(card, was, now)] for mentioned cards that are no longer where they were."""
    return [(c, was, deal.location[c]) for c, was in sorted(deal.commentary_cards.items())
            if deal.location[c] != was]


def _holder(seat):
    return f"{SEAT_NAMES[seat]}'s" if seat else "in the pool"


def card_change_text(change):
    c, was, now = change
    return (f"{card_label(c)} was {_holder(was)} when the commentary mentioned it; "
            f"it is now {_holder(now)}")


# ----- markup -------------------------------------------------------------------

def inline_runs(text):
    """A line's text as [(style, text or card)] with style 'text', 'bold', 'italic' or
    'card'. Cards inside bold or italic are cards too."""
    runs = []

    def plain(t, style):
        pos = 0
        for start, end, c in card_mentions(t):
            if start > pos:
                runs.append((style, t[pos:start]))
            runs.append(("card", c))
            pos = end
        if pos < len(t):
            runs.append((style, t[pos:]))

    pos = 0
    for m in _INLINE.finditer(text):
        plain(text[pos:m.start()], "text")
        if m.group(1) is not None:
            plain(m.group(1), "bold")
        else:
            plain(m.group(2), "italic")
        pos = m.end()
    plain(text[pos:], "text")
    return runs


def parse(text):
    """The commentary as blocks: ('para', runs) or ('bullets', [runs, ...]).

    Lines next to each other join into one paragraph; a blank line ends it. Lines
    starting '- ' are bullet points.
    """
    blocks, para = [], []

    def end_para():
        if para:
            blocks.append(("para", inline_runs(" ".join(para))))
            para.clear()

    for line in text.splitlines():
        line = line.strip()
        if not line:
            end_para()
        elif line.startswith(("- ", "• ")):
            end_para()
            item = inline_runs(line[2:].strip())
            if blocks and blocks[-1][0] == "bullets":
                blocks[-1][1].append(item)
            else:
                blocks.append(("bullets", [item]))
        else:
            para.append(line)
    end_para()
    return blocks


def markup_spans(text):
    """(start, end, kind) for the editor to colour: kinds 'bold', 'italic', 'marker'
    (the * signs) and 'card-S' 'card-H' 'card-D' 'card-C'."""
    spans = []
    for m in _INLINE.finditer(text):
        n = 2 if m.group(1) is not None else 1
        spans.append((m.start(), m.end(), "bold" if n == 2 else "italic"))
        spans.append((m.start(), m.start() + n, "marker"))
        spans.append((m.end() - n, m.end(), "marker"))
    for start, end, c in card_mentions(text):
        spans.append((start, end, "card-" + SUITS[suit_of(c)]))
    return spans


# ----- coaching checkpoints (SmallCards Coach.js) ------------------------------
#
#   {"trick": 2 | "suitLed": 0-3, "seat": "S" | "N", "accept": [cards],
#    "play": card (optional), "hint": "...", "explanation": "..."}

COACH_SEATS = ("S", "N")


def checkpoint_when(cp):
    if isinstance(cp.get("trick"), int):
        return f"Trick {cp['trick']}"
    if isinstance(cp.get("suitLed"), int) and 0 <= cp["suitLed"] < 4:
        return f"First {('spade', 'heart', 'diamond', 'club')[cp['suitLed']]} lead"
    return "?"


def checkpoint_problems(deal, cp):
    """What SmallCards' Coach.js would warn about, in words."""
    problems = []
    seat = cp.get("seat")
    if seat not in COACH_SEATS:
        problems.append("the player must be South or dummy (North)")
    if not isinstance(cp.get("trick"), int) and not isinstance(cp.get("suitLed"), int):
        problems.append("say which trick, or which suit's first lead")
    accept = cp.get("accept") or []
    if not accept:
        problems.append("no correct card chosen")
    if seat in COACH_SEATS:
        cards = list(accept) + ([cp["play"]] if isinstance(cp.get("play"), int) else [])
        for c in cards:
            if not isinstance(c, int) or not 0 <= c < 52:
                problems.append(f"{c!r} is not a card")
            elif deal.location[c] != seat:
                problems.append(f"{card_label(c)} is not in {SEAT_NAMES[seat]}'s hand")
    return problems


def all_checkpoint_problems(deal):
    """['Checkpoint 2 (Trick 3): ...'] for every checkpoint SmallCards would object to."""
    return [f"Checkpoint {i} ({checkpoint_when(cp)}): {p}"
            for i, cp in enumerate(deal.checkpoints, start=1)
            for p in checkpoint_problems(deal, cp)]


def cards_text(cards):
    return " ".join(card_label(c) for c in cards if isinstance(c, int) and 0 <= c < 52)


def rank_order(cards):
    """Cards high to low within suits, spades first (as a hand is shown)."""
    return sorted(cards, key=lambda c: (suit_of(c), -rank_of(c)))
