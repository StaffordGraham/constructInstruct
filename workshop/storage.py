"""Saving, loading, tutor import/export and settings. No tkinter in here."""

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .cards import (SEATS, card_code, from_pbn, parse_card, sorted_cards,
                    to_pbn)
from .model import AuthorInfo, Contract, Deal, Version, STRAINS

FORMAT_ID = "bidw"
FORMAT_VERSION = 1

TUTOR_SEAT_KEYS = {"S": "south_cards", "W": "west_cards",
                   "N": "north_cards", "E": "east_cards"}
_STRAIN_WORDS = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club", "N": "NoTrump"}

# Tutor fields the workshop manages itself; everything else is kept as-is.
_MANAGED_TUTOR_KEYS = {
    "name", "description", "book", "page", "all_cards",
    "south_cards", "west_cards", "north_cards", "east_cards",
    "contract", "contract_level", "contract_trump", "declarer",
    "w_leads", "e_leads", "west_leads", "east_leads",
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


# ----- workshop format -------------------------------------------------------

def to_workshop_dict(deal):
    c = deal.contract
    return {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "hands": {s: to_pbn(deal.hand(s)) for s in SEATS},
        "pool": to_pbn(deal.pool()),
        "contract": {"level": c.level, "strain": c.strain, "declarer": c.declarer},
        "opening_lead": card_code(deal.opening_lead) if deal.opening_lead is not None else "",
        "later_leads": {s: [card_code(x) for x in v] for s, v in deal.later_leads.items()},
        "author": asdict(deal.author),
        "versions": [{"name": v.name, "created": v.created,
                      "hands": {s: to_pbn(v.hands.get(s, [])) for s in SEATS}}
                     for v in deal.versions],
        "tutor_extra": deal.tutor_extra,
        "saved": datetime.now().isoformat(timespec="seconds"),
    }


def save_workshop(deal, path):
    atomic_write_json(path, to_workshop_dict(deal), indent=2)


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
    out = []
    for code in codes or []:
        try:
            out.append(parse_card(code))
        except ValueError:
            pass
    return out


def from_workshop_dict(data):
    deal = Deal()
    hands = {}
    for seat in SEATS:
        try:
            hands[seat] = from_pbn(data.get("hands", {}).get(seat, ""))
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
    lead = _parse_codes([data.get("opening_lead")] if data.get("opening_lead") else [])
    deal.opening_lead = lead[0] if lead else None
    later = data.get("later_leads", {}) or {}
    deal.later_leads = {"W": _parse_codes(later.get("W")), "E": _parse_codes(later.get("E"))}

    a = data.get("author", {}) or {}
    deal.author = AuthorInfo(**{k: str(a.get(k, "") or "") for k in AuthorInfo.field_names()})

    for v in data.get("versions", []) or []:
        try:
            vh = {s: from_pbn(v.get("hands", {}).get(s, "")) for s in SEATS}
        except ValueError:
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
                "last_dir": "", "four_colour": False}

    def __init__(self, path=None):
        self.path = Path(path) if path else self.PATH
        self.data = dict(self.DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass

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
        except OSError:
            pass
