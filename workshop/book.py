"""A book project: Book -> Section -> Chapter -> hands. No tkinter in here.

A chapter teaches with a few hands, each with its own concept and commentary, and
ends with five training hands that are shown without commentary.

On disk a project is a folder:

    book.json            title, print settings and the sections in order
    chapters/<id>.json   one file per chapter (its introduction and its hands)
    deals/<id>.json      one file per deal: an ordinary workshop file (format bidw,
                         version 3) that ConstructInstruct can open by itself

Each deal is stored once and a chapter refers to it by id. A hand's concept is the
deal's own Concept field. Section, chapter and hand numbers come from where things
sit in the book, so they are worked out when needed and never stored.
"""

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .commentary import all_checkpoint_problems, card_change_text, card_changes
from .model import new_deal_id
from .playtest import playtest_problems
from .storage import FileFormatError, deal_from_dict, save_workshop

BOOK_FORMAT = "bidw-book"
CHAPTER_FORMAT = "bidw-chapter"
PROJECT_VERSION = 1

ROLES = ("hand", "training")    # a teaching hand, or one of the training hands at the end
TRAINING_HANDS = 5
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"]


@dataclass
class HandSlot:
    role: str             # "hand" or "training"
    deal: str             # deal id


@dataclass
class Chapter:
    id: str
    title: str
    intro: str = ""       # text before the first hand
    notes: str = ""       # for the author only; never printed
    hands: list = field(default_factory=list)     # HandSlots: teaching hands, then training

    def teaching(self):
        return [h for h in self.hands if h.role == "hand"]

    def training(self):
        return [h for h in self.hands if h.role == "training"]


@dataclass
class Section:
    id: str
    title: str
    intro: str = ""
    chapters: list = field(default_factory=list)  # chapter ids, in order


@dataclass
class Book:
    title: str = ""
    author: str = ""
    trim: str = "6x9"         # inches, for Amazon KDP
    interior: str = "colour"
    sections: list = field(default_factory=list)


def slug(title, taken=()):
    """A file-name id from a title: 'Ruffing Losers in Dummy' -> 'ruffing-losers-in-dummy'."""
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].strip("-") or "untitled"
    name, n = base, 2
    while name in taken:
        name, n = f"{base}-{n}", n + 1
    return name


def deal_problems(deal):
    """Why a hand is not ready to play-test, in as few words as the to-do list needs."""
    v = deal.validation()
    if not v.complete:
        return [f"Cards not all dealt ({v.assigned} of 52)"] +                [e for e in v.errors if not e.endswith(" cards")]
    return playtest_problems(deal)


def roman(n):
    return ROMAN[n - 1] if 1 <= n <= len(ROMAN) else str(n)


def _write_if_changed(path, text):
    """Write text atomically, unless the file already holds exactly that."""
    path = Path(path)
    try:
        if path.read_text(encoding="utf-8") == text:
            return False
    except FileNotFoundError:
        pass
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return True


def _json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise FileFormatError(f"{Path(path).name}: {e}") from e


def _text(value):
    return value if isinstance(value, str) else ""


# ----- file formats ----------------------------------------------------------

def book_to_dict(book):
    return {"format": BOOK_FORMAT, "version": PROJECT_VERSION,
            "title": book.title, "author": book.author,
            "trim": book.trim, "interior": book.interior,
            "sections": [asdict(s) for s in book.sections]}


def book_from_dict(data):
    if not isinstance(data, dict) or data.get("format") != BOOK_FORMAT:
        raise FileFormatError("book.json is not a ConstructInstruct book file")
    book = Book(title=_text(data.get("title")), author=_text(data.get("author")),
                trim=_text(data.get("trim")) or "6x9",
                interior=_text(data.get("interior")) or "colour")
    for s in data.get("sections") or []:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str):
            raise FileFormatError("book.json: a section has no id")
        book.sections.append(Section(
            id=s["id"], title=_text(s.get("title")), intro=_text(s.get("intro")),
            chapters=[c for c in s.get("chapters") or [] if isinstance(c, str)]))
    return book


def chapter_to_dict(chapter):
    data = {"format": CHAPTER_FORMAT, "version": PROJECT_VERSION}
    data.update(asdict(chapter))
    return data


def chapter_from_dict(data, name):
    if not isinstance(data, dict) or data.get("format") != CHAPTER_FORMAT:
        raise FileFormatError(f"{name}: not a ConstructInstruct chapter file")
    hands = []
    for h in data.get("hands") or []:
        if not (isinstance(h, dict) and h.get("role") in ROLES and isinstance(h.get("deal"), str)):
            raise FileFormatError(f"{name}: a hand needs a role (hand or training) and a deal id")
        hands.append(HandSlot(role=h["role"], deal=h["deal"]))
    return Chapter(id=_text(data.get("id")), title=_text(data.get("title")),
                   intro=_text(data.get("intro")), notes=_text(data.get("notes")),
                   hands=hands)


# ----- the project -----------------------------------------------------------

class BookProject:
    """A book project folder, loaded whole (a book is a few hundred small files)."""

    def __init__(self, folder, book):
        self.folder = Path(folder)
        self.book = book
        self.chapters = {}        # id -> Chapter
        self.deals = {}           # id -> Deal
        self.load_warnings = []   # problems worked around while opening
        self._dirty_deals = set()

    # ----- opening and saving ------------------------------------------
    @classmethod
    def create(cls, folder, title, author=""):
        """A new, empty project. The folder must be new or empty."""
        folder = Path(folder)
        if folder.exists() and any(folder.iterdir()):
            raise FileExistsError(f"{folder} is not empty")
        project = cls(folder, Book(title=title, author=author))
        project.save()
        return project

    @classmethod
    def open(cls, folder):
        folder = Path(folder)
        if not (folder / "book.json").is_file():
            raise FileFormatError(f"{folder} has no book.json, so it is not a book project")
        project = cls(folder, book_from_dict(_read_json(folder / "book.json")))
        for path in sorted((folder / "chapters").glob("*.json")):
            chapter = chapter_from_dict(_read_json(path), path.name)
            if chapter.id != path.stem:
                project.load_warnings.append(
                    f"{path.name} says its id is {chapter.id!r}; using the file name")
                chapter.id = path.stem
            project.chapters[chapter.id] = chapter
        for path in sorted((folder / "deals").glob("*.json")):
            deal, kind = deal_from_dict(_read_json(path))
            if kind != "workshop":
                raise FileFormatError(f"{path.name} is not a workshop deal file")
            if deal.id != path.stem:
                # chapters refer to the file name, so that wins; saving puts the id right
                project.load_warnings.append(
                    f"{path.name} says its id is {deal.id!r}; using the file name")
                deal.id = path.stem
                project._dirty_deals.add(deal.id)
            project.deals[deal.id] = deal
        return project

    def save(self):
        """Write book.json, every chapter, and the deals that have changed.

        Files that would not change are left alone, so a book kept in git shows
        only real changes. Returns the paths written.
        """
        (self.folder / "chapters").mkdir(parents=True, exist_ok=True)
        (self.folder / "deals").mkdir(exist_ok=True)
        written = []
        if _write_if_changed(self.folder / "book.json", _json_text(book_to_dict(self.book))):
            written.append(self.folder / "book.json")
        for chapter in self.chapters.values():
            path = self.folder / "chapters" / f"{chapter.id}.json"
            if _write_if_changed(path, _json_text(chapter_to_dict(chapter))):
                written.append(path)
        for deal_id in sorted(self._dirty_deals):
            path = self.deal_path(deal_id)
            save_workshop(self.deals[deal_id], path)
            written.append(path)
        self._dirty_deals.clear()
        return written

    def deal_path(self, deal_id):
        return self.folder / "deals" / f"{deal_id}.json"

    @property
    def unsaved_deals(self):
        return set(self._dirty_deals)

    def deal_changed(self, deal_id):
        """The deal was edited: write it on the next save."""
        if deal_id not in self.deals:
            raise KeyError(deal_id)
        self._dirty_deals.add(deal_id)

    # ----- changes -------------------------------------------------------
    def add_section(self, title, intro=""):
        section = Section(id=slug(title, {s.id for s in self.book.sections}),
                          title=title, intro=intro)
        self.book.sections.append(section)
        return section

    def add_chapter(self, section_id, title, intro=""):
        chapter = Chapter(id=slug(title, self.chapters.keys()), title=title, intro=intro)
        self.section(section_id).chapters.append(chapter.id)
        self.chapters[chapter.id] = chapter
        return chapter

    def add_deal(self, deal):
        """Add a deal to the project, unplaced. A deal whose id is taken gets a new one."""
        while deal.id in self.deals:
            deal.id = new_deal_id()
        self.deals[deal.id] = deal
        self._dirty_deals.add(deal.id)
        return deal

    def place(self, deal_id, chapter_id, role):
        """Add a deal to the end of a chapter's teaching hands or training hands.

        A deal can be in one place only.
        """
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        if deal_id not in self.deals:
            raise KeyError(deal_id)
        chapter = self.chapters[chapter_id]
        where = self.placement(deal_id)
        if where:
            raise ValueError(f"{self.deal_title(deal_id)} is already in {where[0].title}")
        if role == "training" and len(chapter.training()) >= TRAINING_HANDS:
            raise ValueError(f"{chapter.title} already has {TRAINING_HANDS} training hands")
        slot = HandSlot(role, deal_id)
        if role == "hand":
            chapter.hands.insert(len(chapter.teaching()), slot)
        else:
            chapter.hands.append(slot)

    def unplace(self, deal_id):
        """Take a deal out of its chapter. The deal stays in the project, unplaced."""
        where = self.placement(deal_id)
        if where:
            where[0].hands.pop(where[1])

    def move_hand(self, deal_id, step):
        """Move a hand up (-1) or down (+1) among the chapter's hands of the same kind.
        Returns False if it is already at that end."""
        where = self.placement(deal_id)
        if not where:
            return False
        chapter, i = where
        same = [k for k, h in enumerate(chapter.hands) if h.role == chapter.hands[i].role]
        k = same.index(i) + step
        if not 0 <= k < len(same):
            return False
        j = same[k]
        chapter.hands[i], chapter.hands[j] = chapter.hands[j], chapter.hands[i]
        return True

    def move_chapter(self, chapter_id, step):
        """Move a chapter up or down within its section, or into the next section
        when it is already at the end. Returns False at the start or end of the book."""
        sections = self.book.sections
        for s_num, section in enumerate(sections):
            if chapter_id in section.chapters:
                i = section.chapters.index(chapter_id) + step
                if 0 <= i < len(section.chapters):
                    section.chapters.remove(chapter_id)
                    section.chapters.insert(i, chapter_id)
                    return True
                if not 0 <= s_num + step < len(sections):
                    return False
                section.chapters.remove(chapter_id)
                target = sections[s_num + step].chapters
                target.insert(len(target) if step < 0 else 0, chapter_id)
                return True
        return False

    def move_section(self, section_id, step):
        sections = self.book.sections
        i = sections.index(self.section(section_id))
        if not 0 <= i + step < len(sections):
            return False
        sections[i], sections[i + step] = sections[i + step], sections[i]
        return True

    def _set_aside(self, path):
        """Move a file into removed/ rather than delete it, so nothing is lost."""
        if path.exists():
            dest = self.folder / "removed" / path.parent.name / path.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, dest)

    def remove_deal(self, deal_id):
        """Take a deal out of the book. Its file goes to removed/deals/."""
        self.unplace(deal_id)
        self.deals.pop(deal_id)
        self._dirty_deals.discard(deal_id)
        self._set_aside(self.deal_path(deal_id))

    def remove_chapter(self, chapter_id):
        """Remove a chapter; its hands stay in the book, unplaced. Its file goes to
        removed/chapters/."""
        for section in self.book.sections:
            if chapter_id in section.chapters:
                section.chapters.remove(chapter_id)
        self.chapters.pop(chapter_id)
        self._set_aside(self.folder / "chapters" / f"{chapter_id}.json")

    def remove_section(self, section_id):
        """Remove a section that has no chapters left."""
        section = self.section(section_id)
        if section.chapters:
            raise ValueError(f"{section.title} still has chapters; move or remove them first")
        self.book.sections.remove(section)

    def reload_deal(self, deal_id):
        """The deal as last saved, replacing any unsaved changes held in memory."""
        if deal_id in self._dirty_deals:
            return self.deals[deal_id]      # never saved yet: memory is all there is
        deal, _ = deal_from_dict(_read_json(self.deal_path(deal_id)))
        deal.id = deal_id
        self.deals[deal_id] = deal
        return deal

    # ----- queries -------------------------------------------------------
    def section(self, section_id):
        for s in self.book.sections:
            if s.id == section_id:
                return s
        raise KeyError(section_id)

    def chapter_number(self, chapter_id):
        """(section number, chapter number); chapters are numbered within their section."""
        for s_num, s in enumerate(self.book.sections, start=1):
            if chapter_id in s.chapters:
                return s_num, s.chapters.index(chapter_id) + 1
        return None

    def placement(self, deal_id):
        """(chapter, index in its hands) for a placed deal, else None."""
        for chapter in self.chapters.values():
            for i, slot in enumerate(chapter.hands):
                if slot.deal == deal_id:
                    return chapter, i
        return None

    def hand_label(self, deal_id):
        """Where a deal sits, as the book prints it: 'Hand 2' or 'Training Hand 3'."""
        where = self.placement(deal_id)
        if not where:
            return ""
        chapter, i = where
        slot = chapter.hands[i]
        same = chapter.teaching() if slot.role == "hand" else chapter.training()
        n = same.index(slot) + 1
        return f"Hand {n}" if slot.role == "hand" else f"Training Hand {n}"

    def hand_code(self, deal_id):
        """A short code naming a hand anywhere in the book: 'II.3.2' for Hand 2 of
        chapter 3 of section II, 'II.3.T4' for its Training Hand 4; '' if unplaced."""
        where = self.placement(deal_id)
        numbers = where and self.chapter_number(where[0].id)
        if not numbers:
            return ""
        label = self.hand_label(deal_id)
        n = label.split()[-1]
        return f"{roman(numbers[0])}.{numbers[1]}.{'T' if label.startswith('Training') else ''}{n}"

    def deal_title(self, deal_id):
        deal = self.deals.get(deal_id)
        return (deal.author.title.strip() if deal else "") or deal_id

    def unplaced_deals(self):
        placed = {slot.deal for c in self.chapters.values() for slot in c.hands}
        return sorted((d for i, d in self.deals.items() if i not in placed),
                      key=lambda d: d.author.title.strip().lower())

    def chapter_problems(self, chapter_id):
        """What a chapter still lacks, for the author's to-do list."""
        chapter = self.chapters[chapter_id]
        problems = []
        if not chapter.teaching() and not chapter.intro.strip():
            problems.append("No hands yet")
        training = len(chapter.training())
        if chapter.teaching() and training != TRAINING_HANDS:
            problems.append(f"{training} training hand{'s' if training != 1 else ''} "
                            f"({TRAINING_HANDS} planned)")
        for slot in chapter.hands:
            label = self.hand_label(slot.deal)
            problems += [f"{label}: {p}" for p in self.hand_problems(slot.deal)]
        return problems

    def hand_problems(self, deal_id):
        """What one hand still needs. A teaching hand needs a concept and commentary;
        a training hand is shown without them."""
        deal = self.deals.get(deal_id)
        if deal is None:
            return [f"{deal_id} is missing from the deals folder"]
        problems = []
        where = self.placement(deal_id)
        if where and where[0].hands[where[1]].role == "hand":
            if not deal.author.concept.strip():
                problems.append("no concept")
            if not deal.commentary.strip():
                problems.append("no commentary")
        problems += [f"commentary: {card_change_text(c)}" for c in card_changes(deal)]
        problems += deal_problems(deal)
        problems += all_checkpoint_problems(deal)
        return problems

    def problems(self):
        """Faults in how the project fits together (not unfinished work)."""
        problems = []
        seen = {}
        for s in self.book.sections:
            for c in s.chapters:
                if c not in self.chapters:
                    problems.append(f"Section {s.title!r} lists {c}, which has no chapter file")
                elif c in seen:
                    problems.append(f"{self.chapters[c].title!r} is in both {seen[c]!r} "
                                    f"and {s.title!r}")
                else:
                    seen[c] = s.title
        for c in self.chapters.values():
            if c.id not in seen:
                problems.append(f"{c.title!r} is not in any section")
            if len(c.training()) > TRAINING_HANDS:
                problems.append(f"{c.title!r} has more than {TRAINING_HANDS} training hands")
        holders = {}
        for c in self.chapters.values():
            for slot in c.hands:
                holders.setdefault(slot.deal, []).append(c.title)
        for deal_id, titles in holders.items():
            if len(titles) > 1:
                problems.append(f"{self.deal_title(deal_id)} is a hand in more than one "
                                f"place: {', '.join(titles)}")
        return problems
