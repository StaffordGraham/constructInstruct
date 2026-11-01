import tempfile
import unittest
from pathlib import Path

from tests.test_book import PLAN, variant
from workshop.book_import import new_project, plan_outline

try:
    import docx
    from docx.shared import Pt
    from workshop.book_export import TEMPLATE, export_book, export_chapter, export_problems
except ImportError:          # python-docx is optional
    docx = None


@unittest.skipIf(docx is None, "python-docx is not installed")
class BookExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = new_project(Path(self.tmp.name) / "Book", "Learn Declarer Play", "Graham",
                             plan_outline(PLAN))
        p = self.p
        self.chapter = "ruffing-losers-in-dummy"
        hand = p.add_deal(variant(1))
        hand.author.concept = "Ruff losers in dummy"
        hand.commentary = "Count **losers**.\n\n- Ruff the ♥3 with dummy's ♠2\n- Draw trumps"
        p.place(hand.id, self.chapter, "hand")
        for n in (2, 3):
            p.place(p.add_deal(variant(n)).id, self.chapter, "training")
        p.chapters[self.chapter].intro = "Dummy's trumps make *extra* tricks."
        p.save()

    def tearDown(self):
        self.tmp.cleanup()

    def styled(self, doc):
        return [(para.style.name, para.text) for para in doc.paragraphs if para.text.strip()]

    def test_chapter(self):
        path = export_chapter(self.p, self.chapter)
        self.assertEqual(path.parent.name, "exports")
        self.assertEqual(path.name, "II.2 Ruffing Losers in Dummy.docx")
        doc = docx.Document(str(path))
        section = doc.sections[0]
        self.assertEqual((section.page_width.inches, section.page_height.inches), (6, 9))
        self.assertEqual(self.styled(doc), [
            ("Heading 2", "Chapter 2: Ruffing Losers in Dummy"),
            ("Normal", "Dummy's trumps make extra tricks."),
            ("Heading 3", "Hand 1: Hand 1"),
            ("Concept", "Ruff losers in dummy"),
            ("Contract", "4♥ by South"),
            ("Normal", "Count losers."),
            ("List Bullet", "Ruff the ♥3 with dummy's ♠2"),
            ("List Bullet", "Draw trumps"),
            ("Heading 3", "Training Hands"),
            ("Heading 4", "Training Hand 1"),
            ("Contract", "4♥ by South"),
            ("Heading 4", "Training Hand 2"),
            ("Contract", "4♥ by South")])
        self.assertFalse(doc.paragraphs[0].paragraph_format.page_break_before)
        self.assertEqual(len(doc.tables), 3)                      # one diagram per hand
        bullet = next(p for p in doc.paragraphs if p.style.name == "List Bullet")
        self.assertEqual([r.style.name for r in bullet.runs if r.text in "♠♥♦♣"],
                         ["Hearts", "Spades"])                    # suit colours
        north = doc.tables[0].cell(0, 1).text
        self.assertEqual(north.split("\n"), ["♠ AQ72", "♥ K63", "♦ 984", "♣ A82"])   # variant(1) swapped a club
        west = doc.tables[0].cell(1, 0).text.split("\n")
        self.assertEqual(west[0], "Lead: ♦K")

    def test_whole_book(self):
        doc = docx.Document(str(export_book(self.p)))
        text = self.styled(doc)
        self.assertEqual(text[0], ("Title", "Learn Declarer Play"))
        headings = [t for s, t in text if s in ("Heading 1", "Heading 2")]
        self.assertEqual(headings[:4], ["Section I: Two Basic Rules",
                                        "Chapter 1: Suit Contracts- Draw Trumps",
                                        "Chapter 2: No Trump Contracts Keep Control",
                                        "Section II: How to Make Tricks"])
        self.assertIn("TOC", doc.element.body.xml)
        self.assertIn("mirrorMargins", doc.settings.element.xml)

    def test_template_styles_are_used(self):
        export_chapter(self.p, self.chapter)                       # writes the template
        template = self.p.folder / TEMPLATE
        t = docx.Document(str(template))
        t.styles["Normal"].font.size = Pt(13)                       # the author changes it
        t.save(str(template))
        doc = docx.Document(str(export_chapter(self.p, self.chapter)))
        self.assertEqual(doc.styles["Normal"].font.size, Pt(13))
        self.assertEqual(len(doc.paragraphs) > 0 and "Chapter 2" in doc.paragraphs[0].text, True)

    def test_to_do_items_are_reported(self):
        self.assertEqual(export_problems(self.p, [self.chapter]),
                         ["II.2 Ruffing Losers in Dummy: 2 training hands (5 planned)"])


if __name__ == "__main__":
    unittest.main()
