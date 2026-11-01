"""Start a book project from an outline, and bring existing hands into it. No tkinter in here.

    python -m workshop.book_import new <folder> --title "Book title" [--author A] [--plan outline.txt]
    python -m workshop.book_import add <folder> <deal files or .js libraries...>

Imported hands go into the project unplaced; the author decides which chapter each
one belongs to.
The original files are only read, never changed.
"""

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from .book import BookProject, roman
from .storage import (FileFormatError, deal_from_dict, library_deals, load_any,
                      overrides_to_list, read_library)

_SECTION = re.compile(r"^section\s+[ivxlc\d]+\b[\s\-–—:.]*(.*)$", re.IGNORECASE)
_CHAPTER = re.compile(r"^chapter\s*\d+\s*[\-–—:.]?\s*(.*)$", re.IGNORECASE)
# placeholders in an outline that stand for a hand and its parts, not chapters
_HAND_LINE = re.compile(r"^(training\s+)?hand\s*\d+\b|^(concept|display|commentary)\b",
                        re.IGNORECASE)


def plan_outline(paragraphs):
    """Sections and chapters from an outline's (style, text) lines.

    A section starts at a 'Section II ...' line or a Heading 1; a chapter at a
    'Chapter 3 ...' line or a Heading 2. The numbers are dropped, because they come
    from the order. Lines standing for hands ('Hand 1', 'Training Hand 2', 'Concept',
    'Display', 'Commentary') are skipped. In a plain-text outline (style None) any
    other line in a section is a chapter. A section with nothing after its number
    takes its title from the next line, and one with neither title nor chapters is
    dropped. Returns [(section title, [chapter titles])].
    """
    outline, untitled = [], False
    for style, text in paragraphs:
        text = " ".join((text or "").split())
        if not text or _HAND_LINE.match(text):
            continue
        section = _SECTION.match(text)
        chapter = _CHAPTER.match(text)
        if style == "Heading 1" or section:
            title = section.group(1).strip() if section else text
            outline.append([title, []])
            untitled = not title
        elif untitled:
            outline[-1][0] = chapter.group(1).strip() if chapter else text
            untitled = False
        elif outline and (style == "Heading 2" or chapter or style is None):
            outline[-1][1].append(chapter.group(1).strip() if chapter else text)
    return [(title or "Untitled section", chapters) for title, chapters in outline
            if title or chapters]


def read_plan(path):
    """The outline of a plan: a Word document (needs python-docx) or a text file."""
    path = Path(path)
    if path.suffix.lower() != ".docx":
        return plan_outline((None, line) for line in
                            path.read_text(encoding="utf-8-sig").splitlines())
    try:
        import docx
    except ImportError as e:
        raise RuntimeError("Reading a Word plan needs python-docx: pip install python-docx") from e
    document = docx.Document(str(path))
    return plan_outline((p.style.name, p.text) for p in document.paragraphs)


def new_book_folder(parent, title):
    """The folder for a new book: named after its title, inside parent. It must not exist."""
    name = "".join(ch for ch in title if ch not in '\\/:*?"<>|').strip().rstrip(".") or "Book"
    folder = Path(parent) / name
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(f"{folder} already exists and is not empty")
    return folder


def new_project(folder, title, author="", outline=()):
    project = BookProject.create(folder, title, author)
    for section_title, chapters in outline:
        section = project.add_section(section_title)
        for chapter_title in chapters:
            project.add_chapter(section.id, chapter_title)
    project.save()
    return project


def _deal_key(deal):
    """Two deals are copies only if everything matches, the text as well as the cards:
    a hand saved again under a new title is kept, so no author's text is lost."""
    text = {k: v.strip() for k, v in asdict(deal.author).items()}
    return json.dumps([deal.hands(), asdict(deal.contract), deal.opening_lead,
                       deal.later_leads, overrides_to_list(deal), text, deal.tutor_extra],
                      sort_keys=True, default=str)


def _deals_in_file(path):
    """(deal, label) for each deal in a deal file or a .js library."""
    path = Path(path)
    if path.suffix.lower() == ".js":
        text, _ = read_library(path)
        return [(deal_from_dict(entry)[0], f"{path.name} #{k}")
                for k, entry in enumerate(library_deals(text), start=1)]
    return [(load_any(path)[0], path.name)]


def import_deals(project, paths):
    """Add the deals in paths to the project, unplaced, skipping hands it already has.

    Returns (added, skipped): added is [(deal, label)], skipped is [(label, reason)].
    Nothing is saved; call project.save().
    """
    have = {_deal_key(d): d for d in project.deals.values()}
    added, skipped = [], []
    for path in paths:
        try:
            found = _deals_in_file(path)
        except (OSError, FileFormatError) as e:
            skipped.append((Path(path).name, str(e)))
            continue
        for deal, label in found:
            key = _deal_key(deal)
            if key in have:
                skipped.append((label, f"same hand as {have[key].author.title or have[key].id}"))
                continue
            a = deal.author
            a.title = a.title.strip() or label.removesuffix(".json")
            a.concept = a.concept.strip()
            project.add_deal(deal)
            have[key] = deal
            added.append((deal, label))
    return added, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m workshop.book_import",
                                     description="Start a book project or add hands to one.")
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="start a book project")
    new.add_argument("folder")
    new.add_argument("--title", required=True)
    new.add_argument("--author", default="")
    new.add_argument("--plan", help="an outline: a text file of 'Section ...' and 'Chapter ...' "
                                    "lines, or a Word plan (Heading 1 = section, Heading 2 = chapter)")
    add = commands.add_parser("add", help="add hands from deal files or .js libraries")
    add.add_argument("folder")
    add.add_argument("files", nargs="+")
    args = parser.parse_args(argv)

    if args.command == "new":
        outline = read_plan(args.plan) if args.plan else []
        project = new_project(args.folder, args.title, args.author, outline)
        print(f"Created {project.folder}: {len(project.book.sections)} sections, "
              f"{len(project.chapters)} chapters")
        for s_num, section in enumerate(project.book.sections, start=1):
            print(f"  Section {roman(s_num)}  {section.title}")
            for c_num, chapter_id in enumerate(section.chapters, start=1):
                print(f"      Chapter {c_num}  {project.chapters[chapter_id].title}")
        return 0

    project = BookProject.open(args.folder)
    added, skipped = import_deals(project, args.files)
    project.save()
    for deal, label in added:
        print(f"added    {deal.id}  {deal.author.title}  ({label})")
    for label, reason in skipped:
        print(f"skipped  {label}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
