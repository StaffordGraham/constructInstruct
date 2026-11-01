"""The book, or one chapter, as a Word document for print (Amazon KDP). No tkinter in here.

Fonts, sizes and colours live in the book's template.docx, not in this code. The first
export writes a template with the house styles; after that the author can change any
style in Word (Home > Styles > Modify) and every later export follows it. The page
size and margins come from the book's trim size.

Styles used:  Title, Heading 1 (section), Heading 2 (chapter), Heading 3 (hand),
Heading 4 (training hand), Normal (text), List Bullet, Concept, Contract, Diagram,
and the character styles Spades, Hearts, Diamonds, Clubs for suit symbols.

Needs python-docx (pip install python-docx); it is imported only when used.
"""

from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from .book import roman
from .cards import SUIT_SYMBOLS, SUITS, rank_label, sorted_cards, suit_of
from .commentary import parse
from .word_export import _set_borders, contract_symbol_text

TEMPLATE = "template.docx"
EXPORTS = "exports"
SUIT_STYLES = {"S": "Spades", "H": "Hearts", "D": "Diamonds", "C": "Clubs"}
SUIT_COLOURS = {"S": "274C77", "H": "D00000", "D": "008000", "C": "000000"}  # as SmallCards
BODY_FONT = "Georgia"
DIAGRAM_FONT = "Arial"           # has the four suit symbols in every version
# (inside, outside, top, bottom) margins in inches; inside allows for the binding
MARGINS = (0.75, 0.5, 0.6, 0.6)
HAND_COLUMNS = (1.55, 1.2, 1.55)    # West, compass, East (inches)
HAND_CELLS = {"N": (0, 1), "W": (1, 0), "E": (1, 2), "S": (2, 1)}


# ----- the template ---------------------------------------------------------------

def _style(doc, name, kind=WD_STYLE_TYPE.PARAGRAPH, base=None):
    try:
        return doc.styles[name]
    except KeyError:
        style = doc.styles.add_style(name, kind)
        if base:
            style.base_style = doc.styles[base]
        return style


def _set_font(style, name):
    """Use this font, not the Word theme's (which would override it)."""
    style.font.name = name
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        fonts.attrib.pop(qn(attr), None)
    fonts.set(qn("w:cs"), name)


def write_template(path):
    """A template holding the house styles (and no text)."""
    doc = Document()
    normal = doc.styles["Normal"]
    _set_font(normal, BODY_FONT)
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    def heading(name, size, before, page_break=False, colour="1F3864"):
        s = doc.styles[name]
        _set_font(s, BODY_FONT)
        s.font.size = Pt(size)
        s.font.bold = True
        s.font.italic = False
        s.font.color.rgb = RGBColor.from_string(colour)
        pf = s.paragraph_format
        pf.space_before = Pt(before)
        pf.space_after = Pt(6)
        pf.keep_with_next = True
        pf.page_break_before = page_break

    title = doc.styles["Title"]
    _set_font(title, BODY_FONT)
    title.font.size = Pt(28)
    heading("Heading 1", 22, 0, page_break=True)       # section
    heading("Heading 2", 17, 0, page_break=True)       # chapter
    heading("Heading 3", 13, 14)                       # hand
    heading("Heading 4", 11, 10, colour="404040")      # training hand

    concept = _style(doc, "Concept", base="Normal")
    concept.font.italic = True
    concept.paragraph_format.keep_with_next = True
    contract = _style(doc, "Contract", base="Normal")
    contract.font.bold = True
    contract.paragraph_format.keep_with_next = True
    contract.paragraph_format.space_after = Pt(2)
    diagram = _style(doc, "Diagram", base="Normal")
    _set_font(diagram, DIAGRAM_FONT)
    diagram.font.size = Pt(10)
    diagram.paragraph_format.space_after = Pt(0)
    diagram.paragraph_format.line_spacing = 1.0
    diagram.paragraph_format.keep_with_next = True
    for suit, name in SUIT_STYLES.items():
        s = _style(doc, name, WD_STYLE_TYPE.CHARACTER)
        _set_font(s, DIAGRAM_FONT)
        s.font.color.rgb = RGBColor.from_string(SUIT_COLOURS[suit])
    doc.save(str(path))


def template_path(project):
    """The book's template, written first if the book has none."""
    path = project.folder / TEMPLATE
    if not path.exists():
        write_template(path)
    return path


def _new_document(project):
    doc = Document(str(template_path(project)))
    body = doc.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)
    width, height = (float(x) for x in project.book.trim.lower().split("x"))
    inside, outside, top, bottom = MARGINS
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(width), Inches(height)
    section.left_margin, section.right_margin = Inches(inside), Inches(outside)
    section.top_margin, section.bottom_margin = Inches(top), Inches(bottom)
    section.header_distance = section.footer_distance = Inches(0.3)
    settings = doc.settings.element
    for tag in ("w:mirrorMargins", "w:updateFields"):
        if settings.find(qn(tag)) is None:
            el = OxmlElement(tag)
            if tag == "w:updateFields":
                el.set(qn("w:val"), "true")
            settings.append(el)      # Word accepts these in any position on opening
    _page_numbers(section)
    return doc


# ----- small pieces -------------------------------------------------------------------

def _field(paragraph, instruction, placeholder=""):
    """A Word field such as PAGE or TOC (Word fills it in)."""
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    run._r.append(begin)
    run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    run._r.append(instr)
    run = paragraph.add_run()
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    run._r.append(sep)
    paragraph.add_run(placeholder)
    run = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(end)


def _page_numbers(section):
    footer = section.footer
    p = footer.paragraphs[0]
    p.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _field(p, "PAGE")


def _card_run(paragraph, c):
    suit = SUITS[suit_of(c)]
    paragraph.add_run(SUIT_SYMBOLS[suit_of(c)], style=SUIT_STYLES[suit])
    paragraph.add_run(rank_label(c))


def _symbols(paragraph, text):
    """Text in which suit symbols get their suit's style (e.g. a contract '4♠ by South')."""
    buf = ""
    for ch in text:
        if ch in SUIT_SYMBOLS:
            if buf:
                paragraph.add_run(buf)
                buf = ""
            paragraph.add_run(ch, style=SUIT_STYLES[SUITS[SUIT_SYMBOLS.index(ch)]])
        else:
            buf += ch
    if buf:
        paragraph.add_run(buf)


def _runs(paragraph, runs):
    for kind, value in runs:
        if kind == "card":
            _card_run(paragraph, value)
        else:
            run = paragraph.add_run(value)
            run.bold = kind == "bold" or None
            run.italic = kind == "italic" or None


def add_markup(doc, text):
    """Commentary or an introduction (commentary.py markup) as paragraphs and bullets."""
    for kind, value in parse(text):
        if kind == "para":
            _runs(doc.add_paragraph(), value)
        else:
            for item in value:
                _runs(doc.add_paragraph(style="List Bullet"), item)


def _hand_paragraphs(cell, cards, lead=None):
    cell.paragraphs[0].text = ""
    lines = []
    if lead is not None:
        lines.append(("lead", lead))
        lines.append(("blank", None))
    by_suit = [[] for _ in SUITS]
    for c in sorted_cards(cards):
        by_suit[suit_of(c)].append(c)
    lines += [("suit", (s, cs)) for s, cs in enumerate(by_suit)]
    for i, (kind, value) in enumerate(lines):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.style = "Diagram"
        if kind == "lead":
            p.add_run("Lead: ")
            _card_run(p, value)
        elif kind == "suit":
            s, cs = value
            p.add_run(SUIT_SYMBOLS[s], style=SUIT_STYLES[SUITS[s]])
            p.add_run(" " + ("".join(rank_label(c) for c in cs) or "—"))


def add_diagram(doc, deal):
    """The four hands round a compass, as in the author's chapters."""
    table = doc.add_table(rows=3, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _set_borders(table._tbl.tblPr, "tblBorders", ("top", "left", "bottom", "right",
                                                  "insideH", "insideV"), "nil")
    for row in table.rows:
        tr_pr = row._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        tr_pr.append(cant)
        for cell, width in zip(row.cells, HAND_COLUMNS):
            cell.width = Inches(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.paragraphs[0].style = "Diagram"
    leader = deal.contract.leader if deal.contract.is_set else None
    for seat, (r, c) in HAND_CELLS.items():
        lead = deal.opening_lead if seat == leader else None
        _hand_paragraphs(table.cell(r, c), deal.hand(seat), lead)
    compass = table.cell(1, 1)
    _set_borders(compass._tc.get_or_add_tcPr(), "tcBorders",
                 ("top", "left", "bottom", "right"), "single")
    compass.paragraphs[0].text = ""
    for i, line in enumerate(["N", "W        E", "S"]):
        p = compass.paragraphs[0] if i == 0 else compass.add_paragraph()
        p.style = "Diagram"
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4) if i else Pt(2)
        p.add_run(line).bold = True
    # a little space after the diagram
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


# ----- the book's parts ------------------------------------------------------------------

def add_hand(doc, project, slot):
    deal = project.deals.get(slot.deal)
    label = project.hand_label(slot.deal)
    title = deal.author.title.strip() if deal else ""
    if slot.role == "hand":
        doc.add_paragraph(f"{label}: {title}" if title else label, style="Heading 3")
    else:
        doc.add_paragraph(label, style="Heading 4")
    if deal is None:
        doc.add_paragraph("(This hand's file is missing.)")
        return
    if slot.role == "hand" and deal.author.concept.strip():
        doc.add_paragraph(deal.author.concept.strip(), style="Concept")
    contract = contract_symbol_text(deal.contract) or "Contract not set"
    _symbols(doc.add_paragraph(style="Contract"), contract)
    add_diagram(doc, deal)
    if slot.role == "hand":
        add_markup(doc, deal.commentary)


def add_chapter(doc, project, chapter_id):
    chapter = project.chapters[chapter_id]
    _, c_num = project.chapter_number(chapter_id)
    doc.add_paragraph(f"Chapter {c_num}: {chapter.title}", style="Heading 2")
    add_markup(doc, chapter.intro)
    for slot in chapter.teaching():
        add_hand(doc, project, slot)
    if chapter.training():
        doc.add_paragraph("Training Hands", style="Heading 3")
        for slot in chapter.training():
            add_hand(doc, project, slot)


def add_section(doc, project, section):
    number = project.book.sections.index(section) + 1
    doc.add_paragraph(f"Section {roman(number)}: {section.title}", style="Heading 1")
    add_markup(doc, section.intro)
    for chapter_id in section.chapters:
        if chapter_id in project.chapters:
            add_chapter(doc, project, chapter_id)


def _title_page(doc, project):
    book = project.book
    for _ in range(6):
        doc.add_paragraph()
    p = doc.add_paragraph(book.title, style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if book.author:
        p = doc.add_paragraph(book.author)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    doc.add_paragraph("Contents", style="Title")
    _field(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u',
           "Word fills in the contents when the document is opened "
           "(or right-click here and choose Update Field).")


# ----- whole documents ---------------------------------------------------------------------

def exports_folder(project):
    folder = project.folder / EXPORTS
    folder.mkdir(exist_ok=True)
    return folder


def _file_name(text):
    return "".join(ch for ch in text if ch not in '\\/:*?"<>|').strip() or "export"


def export_chapter(project, chapter_id, path=None):
    """One chapter, for checking and review. Returns the file written."""
    s_num, c_num = project.chapter_number(chapter_id)
    chapter = project.chapters[chapter_id]
    if path is None:
        path = exports_folder(project) / _file_name(
            f"{roman(s_num)}.{c_num} {chapter.title}.docx")
    doc = _new_document(project)
    add_chapter(doc, project, chapter_id)
    _drop_first_page_break(doc)
    doc.save(str(path))
    return Path(path)


def export_book(project, path=None):
    """The whole book in one document, ready for Word's Save as PDF. Returns the file."""
    if path is None:
        path = exports_folder(project) / _file_name(f"{project.book.title or 'Book'}.docx")
    doc = _new_document(project)
    doc.sections[0].different_first_page_header_footer = True    # no number on the title page
    _title_page(doc, project)
    for section in project.book.sections:
        add_section(doc, project, section)
    doc.save(str(path))
    return Path(path)


def _drop_first_page_break(doc):
    """A chapter on its own should not start with a blank page."""
    first = doc.paragraphs[0] if doc.paragraphs else None
    if first is not None:
        first.paragraph_format.page_break_before = False


def export_problems(project, chapter_ids):
    """The to-do items that will show in the printed chapters (for a warning after export)."""
    out = []
    for chapter_id in chapter_ids:
        s_num, c_num = project.chapter_number(chapter_id)
        out += [f"{roman(s_num)}.{c_num} {project.chapters[chapter_id].title}: {p}"
                for p in project.chapter_problems(chapter_id)]
    return out
