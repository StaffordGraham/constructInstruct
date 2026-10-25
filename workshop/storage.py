"""Saving, loading, tutor import/export and settings. No tkinter in here."""

import json
import os
import re
import shutil
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .cards import (SEATS, SEAT_NAMES, SUITS, from_pbn, parse_card,
                    sorted_cards)
from .model import AuthorInfo, Contract, Deal, DefensiveOverride, Version, STRAINS

FORMAT_ID = "bidw"
FORMAT_VERSION = 2     # 2: every card is a card number (version 1 hands were PBN strings)

TUTOR_SEAT_KEYS = {"S": "south_cards", "W": "west_cards",
                   "N": "north_cards", "E": "east_cards"}
_STRAIN_WORDS = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club", "N": "NoTrump"}

# Tutor fields the workshop manages itself; everything else is kept as-is.
_MANAGED_TUTOR_KEYS = {
    "name", "description", "book", "page", "all_cards",
    "south_cards", "west_cards", "north_cards", "east_cards",
    "contract", "contract_level", "contract_trump", "declarer",
    "w_leads", "e_leads", "west_leads", "east_leads", "defensiveOverrides",
}
_TUTOR_DEFAULTS = {"reference": "", "si_player": 4, "si_pos": 0, "si_suit": 0,
                   "si_action": 0, "commentary": ""}


class FileFormatError(Exception):
    pass


def atomic_write_json(path, data, **dump_args):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, **dump_args)
    os.replace(tmp, path)


# ----- defensive play overrides (same records in every format) ---------------

_SEAT_BY_NAME = {name: seat for seat, name in SEAT_NAMES.items()}


def overrides_to_list(deal):
    """Overrides as saved: card numbers and full player names, never card codes."""
    return [{"player": SEAT_NAMES[o.player], "suitLed": o.suit_led,
             "occurrence": o.occurrence, "cardToPlay": o.card}
            for o in deal.defensive_overrides]


def overrides_from_list(items):
    """Parse saved overrides, skipping malformed records. Missing section -> []."""
    out = []
    for r in items if isinstance(items, list) else []:
        if not isinstance(r, dict):
            continue
        suit, n, card = r.get("suitLed"), r.get("occurrence"), r.get("cardToPlay")
        seat = _SEAT_BY_NAME.get(r.get("player"))
        seat = seat if seat in ("E", "W") else None     # defenders only
        if (suit in SUITS and isinstance(n, int) and n >= 1 and seat
                and isinstance(card, int) and 0 <= card < 52):
            out.append(DefensiveOverride(suit_led=suit, occurrence=n, player=seat, card=card))
    return out


# ----- workshop format -------------------------------------------------------

def to_workshop_dict(deal):
    c = deal.contract
    return {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "hands": {s: deal.hand(s) for s in SEATS},
        "pool": deal.pool(),
        "contract": {"level": c.level, "strain": c.strain, "declarer": c.declarer},
        "opening_lead": deal.opening_lead,
        "later_leads": {s: list(v) for s, v in deal.later_leads.items()},
        "defensiveOverrides": overrides_to_list(deal),
        "author": asdict(deal.author),
        "versions": [{"name": v.name, "created": v.created,
                      "hands": {s: sorted_cards(v.hands.get(s, [])) for s in SEATS}}
                     for v in deal.versions],
        "tutor_extra": deal.tutor_extra,
        "saved": datetime.now().isoformat(timespec="seconds"),
    }


# A list of numbers as json.dump(indent=2) lays it out, one per line. JSON strings
# cannot hold a raw newline, so this never matches inside text the author typed.
_NUMBER_LIST = re.compile(r"\[\n\s*(-?\d+(?:,\n\s*-?\d+)*)\n\s*\]")


def workshop_json_text(deal):
    """Indented JSON with each list of card numbers kept on one line."""
    text = json.dumps(to_workshop_dict(deal), ensure_ascii=False, indent=2)
    return _NUMBER_LIST.sub(lambda m: "[" + ", ".join(m.group(1).replace(",", " ").split()) + "]",
                            text) + "\n"


def save_workshop(deal, path):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(workshop_json_text(deal), encoding="utf-8")
    os.replace(tmp, path)


def _place_hands(deal, hands_by_seat, order):
    """Put cards into seats, recording duplicates (first holder keeps the card)."""
    dups = []
    for seat in order:
        for c in hands_by_seat.get(seat, []):
            if deal.location[c] is not None:
                if c not in dups:
                    dups.append(c)
                continue
            deal.location[c] = seat
    deal.duplicates = dups


def _parse_codes(codes):
    """Card numbers, or card codes such as 'DQ' from files saved before leads were numbers."""
    out = []
    for code in codes or []:
        if isinstance(code, int) and not isinstance(code, bool):
            if 0 <= code < 52:
                out.append(code)
            continue
        try:
            out.append(parse_card(code))
        except (ValueError, AttributeError) as e:
            _warn(f"lead {code!r} skipped: {e or 'not a card'}")
    return out


def _warn(message):
    """Note a problem the loader worked around, so it is not lost silently."""
    print(f"ConstructInstruct warning: {message}", file=sys.stderr)


def _hand_cards(value):
    """A saved hand: a list of card numbers, or a PBN string from files saved before version 2."""
    if isinstance(value, list):
        if not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < 52 for c in value):
            raise ValueError("cards must be card numbers from 0 to 51")
        return list(value)
    return from_pbn(value or "")


def from_workshop_dict(data):
    deal = Deal()
    hands = {}
    for seat in SEATS:
        try:
            hands[seat] = _hand_cards(data.get("hands", {}).get(seat))
        except ValueError as e:
            raise FileFormatError(f"{seat} hand: {e}") from e
    _place_hands(deal, hands, SEATS)

    c = data.get("contract", {}) or {}
    level = c.get("level")
    strain = c.get("strain", "") or ""
    declarer = c.get("declarer", "S") or "S"
    deal.contract = Contract(level=level if isinstance(level, int) and 1 <= level <= 7 else None,
                             strain=strain if strain in STRAINS else "",
                             declarer=declarer if declarer in SEATS else "S")
    lead = data.get("opening_lead")
    lead = _parse_codes([lead] if lead not in (None, "") else [])
    deal.opening_lead = lead[0] if lead else None
    later = data.get("later_leads", {}) or {}
    deal.later_leads = {"W": _parse_codes(later.get("W")), "E": _parse_codes(later.get("E"))}

    deal.defensive_overrides = overrides_from_list(data.get("defensiveOverrides"))

    a = data.get("author", {}) or {}
    deal.author = AuthorInfo(**{k: str(a.get(k, "") or "") for k in AuthorInfo.field_names()})

    for v in data.get("versions", []) or []:
        try:
            vh = {s: _hand_cards(v.get("hands", {}).get(s)) for s in SEATS}
        except ValueError as e:
            _warn(f"version {v.get('name', '?')!r} skipped: {e}")
            continue
        deal.versions.append(Version(name=v.get("name", "version"), hands=vh,
                                     created=v.get("created", "")))
    deal.tutor_extra = dict(data.get("tutor_extra", {}) or {})
    return deal


# ----- tutor format ----------------------------------------------------------

def contract_text(contract):
    """DealCreator style: '1 Spade', '4 Hearts', '3 NoTrumps'."""
    if not contract.is_set:
        return ""
    word = _STRAIN_WORDS[contract.strain]
    return f"{contract.level} {word}{'s' if contract.level > 1 else ''}"


def parse_contract_text(text):
    """Return (level, strain) from '4 Hearts', '3 NoTrumps', '4H', '3NT'."""
    t = (text or "").strip()
    if not t or t[0] not in "1234567":
        return None, ""
    level = int(t[0])
    rest = t[1:].strip().upper()
    if not rest:
        return level, ""
    ch = rest[0]
    if ch in "♠♥♦♣":
        ch = "SHDC"["♠♥♦♣".index(ch)]
    return level, ch if ch in STRAINS else ""


def leads_for_export(deal):
    """(w_leads, e_leads): leader gets opening lead first, then later leads."""
    leads = {"W": list(deal.later_leads.get("W", [])), "E": list(deal.later_leads.get("E", []))}
    leader = deal.contract.leader
    if deal.opening_lead is not None and leader in leads:
        leads[leader] = [deal.opening_lead] + [c for c in leads[leader] if c != deal.opening_lead]
    return leads["W"], leads["E"]


def to_tutor_dict(deal):
    a = deal.author
    w_leads, e_leads = leads_for_export(deal)
    extra = dict(_TUTOR_DEFAULTS)
    extra.update(deal.tutor_extra)
    out = {
        "name": a.title,
        "description": a.concept,
        "book": a.book,
        "page": a.page,
        "reference": extra.pop("reference"),
        "all_cards": [[], [], [], []],
    }
    for seat in "SWNE":   # the tutor's own order
        out[TUTOR_SEAT_KEYS[seat]] = sorted_cards(deal.hand(seat))
    out.update({
        "contract": contract_text(deal.contract),
        "contract_level": str(deal.contract.level or ""),
        "contract_trump": deal.contract.strain if deal.contract.is_set else "",
        "declarer": deal.contract.declarer,
        "w_leads": w_leads,
        "e_leads": e_leads,
        "west_leads": list(w_leads),
        "east_leads": list(e_leads),
    })
    # Older loader reads si_position; DealCreator writes si_pos.
    extra.setdefault("si_position", extra.get("si_pos", 0))
    out.update(extra)
    out["defensiveOverrides"] = overrides_to_list(deal)
    return out


def tutor_json_text(deal):
    """One line per field, card arrays on one line, like DealCreator's library."""
    data = to_tutor_dict(deal)
    lines = [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in data.items()]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def export_tutor(deal, path):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(tutor_json_text(deal), encoding="utf-8")
    os.replace(tmp, path)


# ----- JavaScript deal library (dealLibrary.js and friends) ------------------

# SmallCards libraries use 'var' (so one library can replace another); older ones 'const'.
_LIBRARY_START = re.compile(r"(?:const|let|var)\s+libDeals\s*=\s*\[")
_NO_LIB_DEALS = "File does not contain a libDeals array ('var libDeals = [' or 'const libDeals = [')"


def to_library_dict(deal):
    """The deal as one entry of a tutor libDeals array, in the library's field order."""
    a = deal.author
    w_leads, e_leads = leads_for_export(deal)
    extra = dict(_TUTOR_DEFAULTS)
    extra.update(deal.tutor_extra)
    out = {
        "name": a.title,
        "description": a.concept,
        "book": a.book,
        "reference": extra.get("reference", ""),
        "all_cards": [[], [], [], []],
    }
    for seat in "SWNE":
        out[TUTOR_SEAT_KEYS[seat]] = sorted_cards(deal.hand(seat))
    out.update({
        "contract": contract_text(deal.contract),
        "contract_trump": deal.contract.strain if deal.contract.is_set else "",
        "contract_level": str(deal.contract.level or ""),
        "w_leads": w_leads,
        "e_leads": e_leads,
        "si_player": extra.get("si_player", 4),
        "si_pos": extra.get("si_pos", 0),
        "si_suit": extra.get("si_suit", 0),
        "si_action": extra.get("si_action", 0),
        "commentary": extra.get("commentary", ""),
        "page": a.page,
        "comment": extra.get("comment", ""),
        "defensiveOverrides": overrides_to_list(deal),
    })
    return out


def library_entry_text(data, indent="    ", newline="\n"):
    """One array entry laid out like the existing library files."""
    inner = indent * 2
    lines = []
    for k, v in data.items():
        if k == "all_cards":
            rows = f",{newline}".join(inner + indent + json.dumps(r) for r in v)
            lines.append(f"{inner}{json.dumps(k)}: [{newline}{rows}{newline}{inner}]")
        else:
            lines.append(f"{inner}{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}")
    body = f",{newline}".join(lines)
    return f"{indent}{{{newline}{body}{newline}{indent}}}"


def _js_tokens(text, start):
    """Yield (first, last, ch) for each token of JavaScript text from start.

    A string is one token (ch is its quote, last its closing quote); any other
    non-space character is a token by itself. Comments are skipped. Stops early
    at an unterminated string or comment.
    """
    i, n = start, len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'`":
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if text[j] == "\\" else 1
            if j >= n:
                return
            yield i, j, ch
            i = j + 1
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                return
            i = end + 2
            continue
        if not ch.isspace():
            yield i, i, ch
        i += 1


def _scan_library_array(text, start):
    """From just inside 'libDeals = [', find the matching ']'.

    Skips strings and comments. Returns (close, last) where close is the index
    of the ']' and last is the index of the last character of real content
    (the '[' itself when the array is empty).
    """
    depth, last = 1, start - 1
    for i, j, ch in _js_tokens(text, start):
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0:
                return i, last
        last = j
    raise FileFormatError("The libDeals array is not closed with ']'")


def _library_spans(text):
    """Each libDeals entry as [first, last, comma]: the indexes of its '{' and '}',
    and of the ',' after it (None when nothing follows)."""
    m = _LIBRARY_START.search(text)
    if not m:
        raise FileFormatError(_NO_LIB_DEALS)
    spans, depth = [], 1
    for i, _, ch in _js_tokens(text, m.end()):
        if depth == 1:
            if ch == "]":
                return spans
            if ch == "," and spans and spans[-1][2] is None:
                spans[-1][2] = i
                continue
            if ch != "{":
                raise FileFormatError("libDeals holds something that is not a deal object")
            spans.append([i, None, None])
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 1:
                spans[-1][1] = i
    raise FileFormatError("The libDeals array is not closed with ']'")


def library_deals(text):
    """The libDeals entries as dicts, in file order."""
    deals = []
    for k, (first, last, _) in enumerate(_library_spans(text), start=1):
        try:
            deals.append(json.loads(text[first:last + 1]))
        except json.JSONDecodeError as e:
            raise FileFormatError(f"Deal {k} in libDeals is not plain JSON: {e}") from e
    return deals


def remove_from_library_text(text, index):
    """Return text without libDeals entry index; everything else is left as it was."""
    spans = _library_spans(text)
    first, last, comma = spans[index]
    start = text.rfind("\n", 0, first) + 1
    whole_line = not text[start:first].strip()
    if not whole_line:
        start = first
    end = (comma if comma is not None else last) + 1
    eol = text.find("\n", end)
    eol = len(text) if eol < 0 else eol + 1
    if whole_line and not text[end:eol].strip():
        end = eol
    new = text[:start] + text[end:]
    prev_comma = spans[index - 1][2] if index > 0 else None
    if comma is None and prev_comma is not None:    # it was last: drop the comma before it
        new = new[:prev_comma] + new[prev_comma + 1:]
    return new


def read_library(path):
    """Return (text, had_bom) for a library file, checking it holds libDeals."""
    raw = Path(path).read_bytes()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise FileFormatError(f"Not a UTF-8 text file: {e}") from e
    if not _LIBRARY_START.search(text):
        raise FileFormatError(_NO_LIB_DEALS)
    return text, had_bom


def library_names(text):
    """Deal names already in a library's text (best effort, for duplicate warnings)."""
    return re.findall(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"', text)


def append_to_library_text(text, deal):
    """Return text with the deal appended as the last element of libDeals."""
    m = _LIBRARY_START.search(text)
    if not m:
        raise FileFormatError(_NO_LIB_DEALS)
    close, last = _scan_library_array(text, m.end())
    newline = "\r\n" if "\r\n" in text else "\n"
    entry = library_entry_text(to_library_dict(deal), newline=newline)
    head, tail = text[:last + 1], text[last + 1:]
    sep = "" if text[last] in "[," else ","
    if not tail.startswith(("\n", "\r\n")):
        tail = newline + tail
    return f"{head}{sep}{newline}{entry}{tail}"


def _write_library(path, text, had_bom):
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8-sig" if had_bom else "utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def append_to_library(deal, path, text=None, had_bom=False):
    """Append the deal to a JavaScript library file and save it atomically."""
    path = Path(path)
    if text is None:
        text, had_bom = read_library(path)
    _write_library(path, append_to_library_text(text, deal), had_bom)


def check_out_of_library(path, text, had_bom, index):
    """Remove entry index from a library file read earlier as text.

    Written through replace_library, so the same checks and backup apply.
    """
    new_text = remove_from_library_text(text, index)
    before = library_deals(text)
    replace_library(path, text, had_bom, new_text, before[:index] + before[index + 1:])


def replace_library(path, text, had_bom, new_text, expected):
    """Replace a library file read earlier as text with new_text.

    Nothing is written unless new_text reads back as exactly the deals in
    expected and the file on disk still matches text. The original is copied
    to <name>.bak first, then replaced in one step.
    """
    path = Path(path)
    if library_deals(new_text) != expected:
        raise FileFormatError("The edited library did not read back correctly")
    if read_library(path) != (text, had_bom):
        raise FileFormatError("The library changed on disk after it was read")
    shutil.copy2(path, path.with_name(path.name + ".bak"))
    _write_library(path, new_text, had_bom)


class LibraryText:
    """A library file's text split around its libDeals entries.

    Entries can be deleted or reordered and the text rebuilt: each entry keeps
    its own source text, and the text between and around entries stays where
    it was, so an unchanged layout gives back the original text exactly.
    """

    def __init__(self, text):
        m = _LIBRARY_START.search(text)
        if not m:
            raise FileFormatError(_NO_LIB_DEALS)
        close, _ = _scan_library_array(text, m.end())
        spans = _library_spans(text)
        self.before, self.after = text[:m.end()], text[close:]
        self.entries = [text[first:last + 1] for first, last, _ in spans]
        self.seps = [text[spans[k][1] + 1:spans[k + 1][0]] for k in range(len(spans) - 1)]
        self.lead = text[m.end():spans[0][0]] if spans else ""
        self.trail = text[spans[-1][1] + 1:close] if spans else text[m.end():close]

    def text(self):
        if not self.entries:
            return self.before + self.trail.lstrip(", \t") + self.after
        parts = [self.before, self.lead, self.entries[0]]
        for sep, entry in zip(self.seps, self.entries[1:]):
            parts += [sep, entry]
        return "".join(parts + [self.trail, self.after])

    def delete(self, index):
        self.entries.pop(index)
        if self.seps:
            self.seps.pop(min(index, len(self.seps) - 1))

    def swap(self, i, j):
        self.entries[i], self.entries[j] = self.entries[j], self.entries[i]


def from_tutor_dict(data):
    deal = Deal()
    hands = {}
    for seat, key in TUTOR_SEAT_KEYS.items():
        nums = data.get(key) or []
        hands[seat] = [n for n in nums if isinstance(n, int) and 0 <= n < 52]
    _place_hands(deal, hands, "SWNE")

    level, strain = parse_contract_text(data.get("contract", ""))
    if level is None and str(data.get("contract_level", "")).isdigit():
        level = int(data["contract_level"])
        strain = str(data.get("contract_trump", "") or "")[:1].upper()
    declarer = data.get("declarer")
    declarer = declarer if isinstance(declarer, str) and declarer in SEATS else "S"
    deal.contract = Contract(level=level, strain=strain if strain in STRAINS else "",
                             declarer=declarer)

    w = data.get("w_leads") or data.get("west_leads") or []
    e = data.get("e_leads") or data.get("east_leads") or []
    leads = {"W": [c for c in w if isinstance(c, int)], "E": [c for c in e if isinstance(c, int)]}
    leader = deal.contract.leader
    if leader in leads and leads[leader]:
        deal.opening_lead = leads[leader][0]
        leads[leader] = leads[leader][1:]
    deal.later_leads = leads
    deal.defensive_overrides = overrides_from_list(data.get("defensiveOverrides"))

    deal.author = AuthorInfo(title=str(data.get("name", "") or ""),
                             concept=str(data.get("description", "") or ""),
                             book=str(data.get("book", "") or ""),
                             page=str(data.get("page", "") or ""))
    deal.tutor_extra = {k: v for k, v in data.items() if k not in _MANAGED_TUTOR_KEYS}
    deal.tutor_extra.pop("si_position", None)   # regenerated from si_pos on export
    return deal


# ----- entry points ----------------------------------------------------------

def load_any(path):
    """Load a workshop or tutor file. Returns (deal, kind) with kind 'workshop' or 'tutor'."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise FileFormatError(f"Not valid JSON: {e}") from e
    return deal_from_dict(data)


def deal_from_dict(data):
    """A parsed workshop or tutor deal (from a file or a library entry). Returns (deal, kind)."""
    if not isinstance(data, dict):
        raise FileFormatError("File does not contain a deal")
    if data.get("format") == FORMAT_ID:
        return from_workshop_dict(data), "workshop"
    if any(k in data for k in TUTOR_SEAT_KEYS.values()):
        return from_tutor_dict(data), "tutor"
    raise FileFormatError("Not a workshop or tutor deal file")


# ----- settings --------------------------------------------------------------

class Settings:
    PATH = Path.home() / ".bridge_deal_workshop.json"
    DEFAULTS = {"test_target": "", "test_command": "", "recent_files": [],
                "last_dir": "", "library_dir": "", "four_colour": False}

    def __init__(self, path=None):
        self.path = Path(path) if path else self.PATH
        self.data = dict(self.DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except FileNotFoundError:
            pass                    # first run: defaults
        except (OSError, json.JSONDecodeError) as e:
            _warn(f"settings file {self.path} could not be read, using defaults: {e}")

    def __getitem__(self, key):
        return self.data.get(key, self.DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def add_recent(self, path):
        path = str(path)
        recent = [p for p in self.data.get("recent_files", []) if p != path]
        self.data["recent_files"] = [path] + recent[:9]
        self.data["last_dir"] = str(Path(path).parent)
        self.save()

    def save(self):
        try:
            atomic_write_json(self.path, self.data, indent=2)
        except OSError as e:
            _warn(f"settings could not be saved to {self.path}: {e}")
