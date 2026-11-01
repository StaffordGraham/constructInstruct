import json
import tempfile
import unittest
from pathlib import Path

from tests.test_core import sample_deal
from workshop.book import BookProject, TRAINING_HANDS, roman, slug
from workshop.book_import import import_deals, new_project, plan_outline, read_plan
from workshop.cards import parse_card
from workshop.model import Deal
from workshop.storage import (FileFormatError, library_deals, load_any, read_library,
                              save_workshop, to_library_dict, to_workshop_dict)

OUTLINE = """Section I-Two Basic Rules
Chapter 1 Suit Contracts- Draw Trumps
Hand 1
Concept
Hand1  display
Hand 1 Commentary
Training Hand 1
Display

Chapter 2 No Trump Contracts Keep Control
Concept
Hand 1 display

Section II How to Make Tricks
Chapter 1 Intro: Explanation
Chapter 2 Ruffing Losers in Dummy
Section II  Getting From Dummy and Back
Chapter 1The Importance of Entries

Section IV


Section II Planning the Hand
Section IV Putting it All Together
Plan The Hand-Suit Contracts
"""
PLAN = [(None, line) for line in OUTLINE.splitlines()]


def variant(n):
    """sample_deal with two small clubs exchanged n ways, so each is a different hand."""
    d = sample_deal()
    north, east = [parse_card(c) for c in ("C2", "C5", "C7")], [parse_card(c) for c in ("C7", "C8", "C9")]
    if n:
        d.swap(north[n % 2], east[n % 3])
    d.author.title = f"Hand {n}"
    return d


class DealIdTests(unittest.TestCase):
    def test_new_deals_get_different_ids(self):
        self.assertNotEqual(Deal().id, Deal().id)
        self.assertRegex(Deal().id, r"^d-[0-9a-f]{8}$")

    def test_id_status_and_parent_survive_saving(self):
        d = sample_deal()
        d.status, d.derived_from = "written", "d-0000abcd"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            save_workshop(d, p)
            d2, kind = load_any(p)
        self.assertEqual((kind, d2.id, d2.status, d2.derived_from),
                         ("workshop", d.id, "written", "d-0000abcd"))

    def test_version_2_file_gets_an_id(self):
        data = to_workshop_dict(sample_deal())
        for k in ("id", "status", "derived_from"):
            del data[k]
        data["version"] = 2
        d, _ = load_any_dict(data)
        self.assertRegex(d.id, r"^d-[0-9a-f]{8}$")
        self.assertEqual((d.status, d.derived_from), ("draft", None))

    def test_bad_id_and_status_are_replaced(self):
        data = to_workshop_dict(sample_deal())
        data.update(id="../evil", status="finished", derived_from=7)
        d, _ = load_any_dict(data)
        self.assertNotEqual(d.id, "../evil")
        self.assertEqual((d.status, d.derived_from), ("draft", None))

    def test_library_entry_is_unchanged_by_version_3(self):
        # SmallCards never sees the new fields
        self.assertFalse({"id", "status", "derived_from"} & to_library_dict(sample_deal()).keys())


def load_any_dict(data):
    from workshop.storage import deal_from_dict
    return deal_from_dict(json.loads(json.dumps(data)))


class PlanTests(unittest.TestCase):
    EXPECTED = [
        ("Two Basic Rules", ["Suit Contracts- Draw Trumps", "No Trump Contracts Keep Control"]),
        ("How to Make Tricks", ["Intro: Explanation", "Ruffing Losers in Dummy"]),
        ("Getting From Dummy and Back", ["The Importance of Entries"]),
        ("Planning the Hand", []),
        ("Putting it All Together", ["Plan The Hand-Suit Contracts"])]

    def test_text_outline(self):
        # hand lines are not chapters; the empty "Section IV" is dropped
        self.assertEqual(plan_outline(PLAN), self.EXPECTED)

    def test_text_outline_from_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "outline.txt"
            path.write_text(OUTLINE, encoding="utf-8")
            self.assertEqual(read_plan(path), self.EXPECTED)

    def test_word_outline(self):
        # Heading 1 = section, Heading 2 = chapter; other Word text is ignored,
        # except as the title of a section that has none
        self.assertEqual(plan_outline([
            ("Heading 1", "Section I-Two Basic Rules"),
            ("Heading 2", "Suit Contracts- Draw Trumps "),
            ("Normal", "Drawing Trumps"),
            ("Heading 1", "Section II "),
            ("Normal", "Planning the Hand"),
            ("Heading 2", "Chapter 1 Plan The Hand-Suit Contracts")]),
            [("Two Basic Rules", ["Suit Contracts- Draw Trumps"]),
             ("Planning the Hand", ["Plan The Hand-Suit Contracts"])])

    def test_slug_and_roman(self):
        self.assertEqual(slug("Ruffing Losers in Dummy"), "ruffing-losers-in-dummy")
        self.assertEqual(slug("Drawing Trumps", {"drawing-trumps"}), "drawing-trumps-2")
        self.assertEqual(slug("!!!"), "untitled")
        self.assertEqual([roman(n) for n in (1, 4, 9, 30)], ["I", "IV", "IX", "30"])


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "Book"
        self.project = new_project(self.folder, "Learn Declarer Play", "Graham",
                                   plan_outline(PLAN))

    def tearDown(self):
        self.tmp.cleanup()

    def chapter(self, title):
        return next(c for c in self.project.chapters.values() if c.title == title)

    def test_files_on_disk(self):
        names = sorted(p.relative_to(self.folder).as_posix() for p in self.folder.rglob("*.json"))
        self.assertEqual(names, ["book.json",
                                 "chapters/intro-explanation.json",
                                 "chapters/no-trump-contracts-keep-control.json",
                                 "chapters/plan-the-hand-suit-contracts.json",
                                 "chapters/ruffing-losers-in-dummy.json",
                                 "chapters/suit-contracts-draw-trumps.json",
                                 "chapters/the-importance-of-entries.json"])
        book = json.loads((self.folder / "book.json").read_text(encoding="utf-8"))
        self.assertEqual((book["format"], book["title"], book["trim"], book["interior"]),
                         ("bidw-book", "Learn Declarer Play", "6x9", "colour"))
        self.assertEqual(book["sections"][1]["chapters"], ["intro-explanation",
                                                          "ruffing-losers-in-dummy"])

    def test_hands_then_training_hands(self):
        p = self.project
        ruffing = self.chapter("Ruffing Losers in Dummy")
        deals = [p.add_deal(variant(n)) for n in range(4)]
        p.place(deals[0].id, ruffing.id, "training")
        p.place(deals[1].id, ruffing.id, "hand")
        p.place(deals[2].id, ruffing.id, "hand")     # teaching hands go before training
        p.place(deals[3].id, ruffing.id, "training")
        self.assertEqual([s.deal for s in ruffing.hands],
                         [deals[1].id, deals[2].id, deals[0].id, deals[3].id])
        self.assertEqual(p.chapter_number(ruffing.id), (2, 2))
        self.assertEqual([p.hand_label(d.id) for d in deals],
                         ["Training Hand 1", "Hand 1", "Hand 2", "Training Hand 2"])
        self.assertEqual([p.hand_code(d.id) for d in deals],
                         ["II.2.T1", "II.2.1", "II.2.2", "II.2.T2"])
        p.unplace(deals[1].id)
        self.assertEqual((p.hand_code(deals[1].id), p.hand_code(deals[2].id)), ("", "II.2.1"))
        self.assertEqual(p.unplaced_deals(), [deals[1]])

    def test_a_deal_has_one_place_and_a_chapter_five_training_hands(self):
        p = self.project
        drawing = self.chapter("Suit Contracts- Draw Trumps")
        deals = [p.add_deal(variant(n)) for n in range(TRAINING_HANDS + 1)]
        p.place(deals[0].id, drawing.id, "hand")
        with self.assertRaises(ValueError):
            p.place(deals[0].id, self.chapter("Ruffing Losers in Dummy").id, "hand")
        with self.assertRaises(ValueError):
            p.place(deals[1].id, drawing.id, "example")
        for d in deals[1:]:
            p.place(d.id, drawing.id, "training")
        extra = p.add_deal(variant(1))
        with self.assertRaises(ValueError):
            p.place(extra.id, drawing.id, "training")

    def test_save_and_open_round_trip(self):
        p = self.project
        d = p.add_deal(variant(1))
        d.derived_from = "d-12345678"
        entries = self.chapter("The Importance of Entries")
        entries.intro = "Entries let you cross between hands."
        p.place(d.id, entries.id, "hand")
        written = p.save()
        self.assertIn(p.deal_path(d.id), written)
        self.assertEqual(p.save(), [])          # nothing changed, nothing written

        q = BookProject.open(self.folder)
        self.assertEqual(q.book, p.book)
        self.assertEqual(q.chapters, p.chapters)
        self.assertEqual(q.deals[d.id].hands(), d.hands())
        self.assertEqual(q.deals[d.id].derived_from, "d-12345678")
        self.assertEqual(q.hand_code(d.id), "III.1.1")
        self.assertEqual((q.problems(), q.load_warnings), ([], []))

    def test_only_changed_deals_are_written(self):
        p = self.project
        a, b = p.add_deal(variant(1)), p.add_deal(variant(2))
        p.save()
        a.author.notes = "changed"
        p.deal_changed(a.id)
        self.assertEqual(p.save(), [p.deal_path(a.id)])
        self.assertEqual(load_any(p.deal_path(a.id))[0].author.notes, "changed")
        self.assertEqual(b.author.notes, "")

    def test_deal_files_open_in_the_deal_designer(self):
        p = self.project
        d = p.add_deal(variant(1))
        p.save()
        d2, kind = load_any(p.deal_path(d.id))
        self.assertEqual((kind, d2.id, d2.hands()), ("workshop", d.id, d.hands()))

    def test_taken_id_is_replaced(self):
        p = self.project
        a = p.add_deal(variant(1))
        b = variant(2)
        b.id = a.id
        p.add_deal(b)
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(len(p.deals), 2)

    def test_chapter_to_do_list(self):
        p = self.project
        drawing = self.chapter("Suit Contracts- Draw Trumps")
        self.assertEqual(p.chapter_problems(drawing.id), ["No hands yet"])
        intro = self.chapter("Intro: Explanation")
        intro.intro = "Declarer makes tricks in five ways."
        self.assertEqual(p.chapter_problems(intro.id), [])     # a chapter of text only
        with_concept, without = variant(1), variant(2)
        with_concept.author.concept = "Draw trumps first"
        with_concept.commentary = "Draw trumps."
        without.commentary = "Some words."
        unplayable = variant(3)
        unplayable.opening_lead = None
        p.place(p.add_deal(with_concept).id, drawing.id, "hand")
        p.place(p.add_deal(without).id, drawing.id, "hand")
        p.place(p.add_deal(unplayable).id, drawing.id, "training")
        empty = Deal()
        p.place(p.add_deal(empty).id, drawing.id, "training")
        self.assertEqual(p.chapter_problems(drawing.id), [
            f"2 training hands ({TRAINING_HANDS} planned)",
            "Hand 2: no concept",
            "Training Hand 1: Set an opening lead — SmallCards starts play with it",
            "Training Hand 2: Cards not all dealt (0 of 52)",
            "Training Hand 2: No contract set"])

    def test_problems_found_on_opening(self):
        p = self.project
        d = p.add_deal(variant(1))
        p.save()
        book = json.loads((self.folder / "book.json").read_text(encoding="utf-8"))
        book["sections"][0]["chapters"].append("ruffing-losers-in-dummy")     # listed twice
        book["sections"][1]["chapters"].append("no-such-chapter")
        (self.folder / "book.json").write_text(json.dumps(book), encoding="utf-8")
        renamed = self.folder / "deals" / "d-99999999.json"         # file renamed by hand
        p.deal_path(d.id).rename(renamed)
        q = BookProject.open(self.folder)
        self.assertEqual(q.problems(), [
            "'Ruffing Losers in Dummy' is in both 'Two Basic Rules' and 'How to Make Tricks'",
            "Section 'How to Make Tricks' lists no-such-chapter, which has no chapter file"])
        self.assertIn("d-99999999", q.deals)
        self.assertEqual(len(q.load_warnings), 1)
        q.save()                                                     # puts the id right
        self.assertEqual(load_any(renamed)[0].id, "d-99999999")

    def test_bad_files_are_reported_by_name(self):
        (self.folder / "chapters" / "intro-explanation.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(FileFormatError, "intro-explanation.json"):
            BookProject.open(self.folder)
        with self.assertRaises(FileFormatError):
            BookProject.open(self.folder / "chapters")

    def test_moving_hands_chapters_and_sections(self):
        p = self.project
        ruffing = self.chapter("Ruffing Losers in Dummy")
        a, b, t = (p.add_deal(variant(n)) for n in range(3))
        for d, role in ((a, "hand"), (b, "hand"), (t, "training")):
            p.place(d.id, ruffing.id, role)
        self.assertTrue(p.move_hand(b.id, -1))
        self.assertEqual([p.hand_label(d.id) for d in (a, b)], ["Hand 2", "Hand 1"])
        self.assertFalse(p.move_hand(b.id, -1))         # already first
        self.assertFalse(p.move_hand(a.id, +1))         # hands never pass training hands
        self.assertFalse(p.move_hand(t.id, -1))

        sections = p.book.sections
        self.assertTrue(p.move_chapter("intro-explanation", +1))
        self.assertEqual(sections[1].chapters, ["ruffing-losers-in-dummy", "intro-explanation"])
        self.assertTrue(p.move_chapter("intro-explanation", +1))     # into the next section
        self.assertEqual(sections[2].chapters, ["intro-explanation", "the-importance-of-entries"])
        self.assertTrue(p.move_chapter("intro-explanation", -1))     # and back to the end
        self.assertEqual(sections[1].chapters[-1], "intro-explanation")
        self.assertFalse(p.move_chapter("suit-contracts-draw-trumps", -1))
        self.assertTrue(p.move_section(sections[1].id, -1))
        self.assertEqual(sections[0].title, "How to Make Tricks")
        self.assertEqual(p.hand_code(a.id), "I.1.2")
        self.assertFalse(p.move_section(sections[0].id, -1))

    def test_removing_keeps_the_files(self):
        p = self.project
        ruffing = self.chapter("Ruffing Losers in Dummy")
        a, b = p.add_deal(variant(1)), p.add_deal(variant(2))
        p.place(a.id, ruffing.id, "hand")
        p.place(b.id, ruffing.id, "hand")
        p.save()
        p.remove_deal(a.id)
        self.assertTrue((self.folder / "removed" / "deals" / f"{a.id}.json").is_file())
        self.assertNotIn(a.id, p.deals)
        self.assertEqual(p.hand_label(b.id), "Hand 1")
        p.remove_chapter(ruffing.id)
        self.assertTrue((self.folder / "removed" / "chapters" / f"{ruffing.id}.json").is_file())
        self.assertEqual(p.unplaced_deals(), [b])          # its hand stays in the book
        p.save()
        q = BookProject.open(self.folder)
        self.assertEqual((sorted(q.deals), sorted(q.chapters)), ([b.id], sorted(p.chapters)))
        self.assertEqual(q.problems(), [])
        with self.assertRaises(ValueError):
            q.remove_section(q.book.sections[0].id)       # it still has chapters
        empty = q.book.sections[3]
        self.assertEqual(empty.title, "Planning the Hand")
        q.remove_section(empty.id)
        self.assertNotIn(empty, q.book.sections)

    def test_reload_drops_unsaved_changes(self):
        p = self.project
        d = p.add_deal(variant(1))
        self.assertIs(p.reload_deal(d.id), d)              # never saved: kept as it is
        p.save()
        d.author.title = "Changed but not saved"
        fresh = p.reload_deal(d.id)
        self.assertEqual(fresh.author.title, "Hand 1")
        self.assertIs(p.deals[d.id], fresh)

    def test_create_refuses_a_folder_in_use(self):
        with self.assertRaises(FileExistsError):
            BookProject.create(self.folder, "Another")


class ImportTests(unittest.TestCase):
    LIBRARY = Path(__file__).parent / "fixtures" / "libraries" / "SmallCards_dealLibrary.js"

    def test_import_files_and_libraries_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            project = new_project(tmp / "Book", "Test", outline=[])
            d = variant(1)
            d.author.title, d.author.book, d.author.page = "  Hand 1 ", "Breakthrough Bridge", "49"
            save_workshop(d, tmp / "Hand 1.json")
            save_workshop(d, tmp / "Hand 1 copy.json")
            d.author.title = "Same cards, new title"
            save_workshop(d, tmp / "Retitled.json")
            (tmp / "junk.json").write_text("[]", encoding="utf-8")
            added, skipped = import_deals(project, [tmp / "Hand 1.json", tmp / "Hand 1 copy.json",
                                                    tmp / "junk.json", tmp / "Retitled.json",
                                                    self.LIBRARY])
            entries = sum(1 for _, label in added if label.startswith(self.LIBRARY.name))
            self.assertEqual([label for _, label in added[:2]], ["Hand 1.json", "Retitled.json"])
            self.assertEqual(len(added), 2 + entries)
            self.assertGreater(entries, 0)
            first = added[0][0]
            self.assertEqual((first.author.title, first.author.book, first.author.page),
                             ("Hand 1", "Breakthrough Bridge", "49"))   # where it came from is kept
            self.assertEqual([label for label, _ in skipped[:2]], ["Hand 1 copy.json", "junk.json"])

            project.save()
            again, skipped = import_deals(BookProject.open(tmp / "Book"), [self.LIBRARY])
            self.assertEqual(again, [])
            in_library = len(library_deals(read_library(self.LIBRARY)[0]))
            self.assertEqual(len(skipped), in_library)      # including repeats within it


if __name__ == "__main__":
    unittest.main()


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.p = new_project(self.folder / "Book", "Plan", outline=plan_outline(PLAN))

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_sections_and_chapters_go_after_the_selected_one(self):
        p = self.p
        first = p.book.sections[0]
        added = p.add_section("Counting", after=first.id)
        self.assertEqual(p.book.sections[1], added)
        self.assertEqual(p.add_section("At the end").id, p.book.sections[-1].id)
        new = p.add_chapter(first.id, "Counting Winners", after="suit-contracts-draw-trumps")
        self.assertEqual(first.chapters, ["suit-contracts-draw-trumps", new.id,
                                          "no-trump-contracts-keep-control"])
        self.assertEqual(p.chapter_number(new.id), (1, 2))

    def test_a_new_chapter_never_reuses_a_removed_chapters_name(self):
        p = self.p
        chapter = p.add_chapter(p.book.sections[0].id, "New chapter")
        p.save()
        p.remove_chapter(chapter.id)
        again = p.add_chapter(p.book.sections[0].id, "New chapter")
        self.assertNotEqual(again.id, chapter.id)
        p.save()
        p.remove_chapter(again.id)
        self.assertEqual(len(list((self.folder / "Book" / "removed" / "chapters").glob("*.json"))), 2)

    def test_new_book_folder(self):
        from workshop.book_import import new_book_folder
        self.assertEqual(new_book_folder(self.folder, 'Bridge: "Play"?'), self.folder / "Bridge Play")
        with self.assertRaises(FileExistsError):
            new_book_folder(self.folder, "Book")              # already used, not empty
