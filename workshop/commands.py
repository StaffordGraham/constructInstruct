"""The toolbar command line.

    DQ E            move ♦Q to East
    DQ D7 SAK N     move several cards (a suit letter followed by ranks = several cards)
    DQ x D7         swap two cards (also '<>' or '↔')
    HJ P            return to the pool
    N: AKQ7.J94.K5.432   set a whole hand (PBN, spades first)
    lead DK         set the opening lead
"""

from .cards import SEATS, from_pbn, parse_card, parse_suit_group

SWAP_WORDS = {"x", "X", "<>", "↔", "swap"}
POOL_WORDS = {"P", "POOL"}


class CommandError(ValueError):
    pass


def _cards(tokens):
    out = []
    for t in tokens:
        try:
            out.extend(parse_suit_group(t))
        except ValueError as e:
            raise CommandError(str(e)) from e
    return out


def run_command(deal, text):
    """Apply a command to the deal. Raises CommandError if it cannot be understood."""
    text = text.strip()
    if not text:
        raise CommandError("Empty command")

    # Whole hand: 'N: AKQ7.J94.K5.432' or 'N=...'
    head = text[:2].upper()
    if len(text) > 1 and head[0] in SEATS and head[1] in ":=":
        try:
            cards = from_pbn(text[2:])
        except ValueError as e:
            raise CommandError(str(e)) from e
        deal.set_hand(head[0], cards)
        return

    tokens = text.split()
    if tokens[0].lower() == "lead":
        if len(tokens) != 2:
            raise CommandError("Use: lead DK")
        try:
            deal.set_opening_lead(parse_card(tokens[1]))
        except ValueError as e:
            raise CommandError(str(e)) from e
        return

    swap_at = [i for i, t in enumerate(tokens) if t in SWAP_WORDS]
    if swap_at:
        i = swap_at[0]
        left, right = _cards(tokens[:i]), _cards(tokens[i + 1:])
        if len(left) != 1 or len(right) != 1:
            raise CommandError("Swap needs one card on each side: DQ x D7")
        if not deal.swap(left[0], right[0]):
            raise CommandError("Those cards are already in the same place")
        return

    if len(tokens) < 2:
        raise CommandError("Say where to: e.g. 'DQ E' or 'DQ P'")
    dest_word = tokens[-1].upper()
    if dest_word in POOL_WORDS:
        dest = None
    elif dest_word in SEATS and len(dest_word) == 1:
        dest = dest_word
    else:
        raise CommandError(f"'{tokens[-1]}' is not N, E, S, W or P")
    cards = _cards(tokens[:-1])
    if deal.move(cards, dest) == 0:
        raise CommandError("Nothing to move: the cards are already there")
