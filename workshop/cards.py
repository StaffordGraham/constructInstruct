"""Card numbering, names and hand statistics.

Card numbers match the Declarer Play Tutor and DealCreator:
    number = suit * 13 + rank
    suit 0..3 = Spades, Hearts, Diamonds, Clubs
    rank 0..12 = 2 .. Ace
"""

SUITS = "SHDC"
SUIT_SYMBOLS = "♠♥♦♣"
SUIT_NAMES = ["Spades", "Hearts", "Diamonds", "Clubs"]
RANKS = "23456789TJQKA"
SEATS = "NESW"
SEAT_NAMES = {"N": "North", "E": "East", "S": "South", "W": "West"}
ALL_CARDS = range(52)

_HCP = {"A": 4, "K": 3, "Q": 2, "J": 1}


def card(suit, rank):
    return suit * 13 + rank


def suit_of(c):
    return c // 13


def rank_of(c):
    return c % 13


def rank_char(c):
    return RANKS[rank_of(c)]


def rank_label(c):
    """Rank as shown on screen: '10' rather than 'T'."""
    r = rank_char(c)
    return "10" if r == "T" else r


def card_code(c):
    """Plain-text code used in files, e.g. 'DQ'."""
    return SUITS[suit_of(c)] + rank_char(c)


def card_label(c):
    """Display label, e.g. '♦Q'."""
    return SUIT_SYMBOLS[suit_of(c)] + rank_label(c)


def sort_key(c):
    """Spades first, high cards first within a suit."""
    return (suit_of(c), -rank_of(c))


def sorted_cards(cards):
    return sorted(cards, key=sort_key)


def _suit_index(ch):
    ch = ch.upper()
    if ch in SUITS:
        return SUITS.index(ch)
    if ch in SUIT_SYMBOLS:
        return SUIT_SYMBOLS.index(ch)
    # Symbol variants (outline suits)
    alt = "♤♡♢♧"
    if ch in alt:
        return alt.index(ch)
    return None


def _rank_index(text):
    text = text.upper()
    if text == "10":
        text = "T"
    if len(text) == 1 and text in RANKS:
        return RANKS.index(text)
    return None


def parse_card(text):
    """Parse 'DQ', 'QD', '♦Q', 'Q♦', '10D', 'D10' into a card number.

    Raises ValueError if the text is not a card.
    """
    t = text.strip()
    if len(t) >= 2:
        s = _suit_index(t[0])
        r = _rank_index(t[1:])
        if s is not None and r is not None:
            return card(s, r)
        s = _suit_index(t[-1])
        r = _rank_index(t[:-1])
        if s is not None and r is not None:
            return card(s, r)
    raise ValueError(f"'{text}' is not a card")


def parse_suit_group(text):
    """Parse a token of one or more cards.

    Accepts a single card ('QD', 'DQ', '♦Q') or a suit followed by several
    ranks ('DQJ7', 'SAK10').
    """
    t = text.strip()
    try:
        return [parse_card(t)]
    except ValueError:
        pass
    s = _suit_index(t[:1]) if t else None
    if s is None or len(t) < 2:
        raise ValueError(f"'{text}' is not a card")
    ranks = t[1:].upper().replace("10", "T")
    result = []
    for ch in ranks:
        r = _rank_index(ch)
        if r is None:
            raise ValueError(f"'{text}' is not a card")
        result.append(card(s, r))
    return result


def hcp(cards):
    return sum(_HCP.get(rank_char(c), 0) for c in cards)


def shape(cards):
    counts = [0, 0, 0, 0]
    for c in cards:
        counts[suit_of(c)] += 1
    return tuple(counts)


def shape_text(cards):
    return "-".join(str(n) for n in shape(cards))


def to_pbn(cards):
    """'AKQ7.J94.K5.432' (spades.hearts.diamonds.clubs)."""
    parts = []
    for s in range(4):
        ranks = sorted((rank_of(c) for c in cards if suit_of(c) == s), reverse=True)
        parts.append("".join(RANKS[r] for r in ranks))
    return ".".join(parts)


def from_pbn(text):
    """Inverse of to_pbn. Also accepts '10' for ten and spaces as separators.

    Raises ValueError on bad input.
    """
    t = text.strip().upper().replace("10", "T")
    if not t:
        return []
    if "." in t:
        parts = [p.replace(" ", "") for p in t.split(".")]
    else:
        parts = t.split()
    if len(parts) > 4:
        raise ValueError("A hand has at most four suits (♠.♥.♦.♣)")
    cards = []
    for s, part in enumerate(parts):
        for ch in part:
            if ch in "-":
                continue
            r = _rank_index(ch)
            if r is None:
                raise ValueError(f"'{ch}' is not a rank")
            c = card(s, r)
            if c in cards:
                raise ValueError(f"{card_label(c)} is listed twice")
            cards.append(c)
    return cards
