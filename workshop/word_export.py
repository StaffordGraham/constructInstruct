"""Export the deal to a Word document as a bridge diagram. No tkinter in here.

export_to_word() builds the document from small steps, so later additions
(title, reference number, diagram numbering, instructional text, bidding and
play notes) are new add_*() steps called from export_to_word(), not a rewrite.
Needs python-docx (pip install python-docx); it is imported only when used.
"""

from docx import Document
from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from .cards import SEATS, SEAT_NAMES, SUIT_SYMBOLS, SUITS, card_label, rank_label, sorted_cards, suit_of

FONT = "Calibri"
FONT_SIZE = Pt(12)
COLUMN_WIDTHS = (Inches(2.0), Inches(1.3), Inches(2.0))
ROW_HEIGHT = Inches(1.5)

# (row, column) of each hand in the 3 x 3 table; the compass is at (1, 1).
HAND_CELLS = {"N": (0, 1), "W": (1, 0), "E": (1, 2), "S": (2, 1)}
COMPASS_CELL = (1, 1)


def export_to_word(deal, path):
    """Write the deal's diagram to a .docx file."""
    doc = create_document()
    add_contract(doc, deal)
    table = create_bridge_table(doc)
    populate_hands(table, deal)
    save_document(doc, path)


def create_document():
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = FONT_SIZE
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.line_spacing = 1.0
    return doc


def contract_symbol_text(contract):
    """'4♥ by South', '3NT by North'; empty when no contract is set."""
    if not contract.is_set:
        return ""
    strain = "NT" if contract.strain == "N" else SUIT_SYMBOLS[SUITS.index(contract.strain)]
    return f"{contract.level}{strain} by {SEAT_NAMES[contract.declarer]}"


def add_contract(doc, deal):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(contract_symbol_text(deal.contract) or "Contract not set")
    run.bold = True
    run.font.size = Pt(14)


def create_bridge_table(doc):
    """3 x 3 table, centred, borderless except for the compass cell."""
    table = doc.add_table(rows=3, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    _set_borders(table._tbl.tblPr, "tblBorders", ("top", "left", "bottom", "right",
                                                  "insideH", "insideV"), "nil")
    for row in table.rows:
        row.height = ROW_HEIGHT
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        for cell, width in zip(row.cells, COLUMN_WIDTHS):
            cell.width = width
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    compass = table.cell(*COMPASS_CELL)
    _set_borders(compass._tc.get_or_add_tcPr(), "tcBorders",
                 ("top", "left", "bottom", "right"), "single")
    lines = ["N", "", "W   E", "", "S"]
    _write_lines(compass, lines, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)
    return table


def hand_lines(cards):
    """['♠ AKJ7', '♥ Q42', '♦ KJ5', '♣ A987'], with '—' for a void."""
    by_suit = [[] for _ in SUITS]
    for c in sorted_cards(cards):
        by_suit[suit_of(c)].append(rank_label(c))
    return [f"{SUIT_SYMBOLS[s]} {''.join(ranks) or '—'}" for s, ranks in enumerate(by_suit)]


def populate_hands(table, deal):
    """Each hand in its compass cell; the opening lead heads the leader's cell."""
    leader = deal.contract.leader
    for seat in SEATS:
        lines = hand_lines(deal.hand(seat))
        if seat == leader and deal.opening_lead is not None:
            lines = [f"Opening Lead: {card_label(deal.opening_lead)}", ""] + lines
        _write_lines(table.cell(*HAND_CELLS[seat]), lines)


def save_document(doc, path):
    doc.save(str(path))


# ----- helpers ----------------------------------------------------------------

def _write_lines(cell, lines, align=WD_ALIGN_PARAGRAPH.LEFT, bold=False):
    """Replace the cell's text with one paragraph per line."""
    cell.paragraphs[0].text = ""
    for i, line in enumerate(lines):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.alignment = align
        run = p.add_run(line)
        run.bold = bold


# Elements that must come after the borders element in tblPr / tcPr (OOXML schema order).
_AFTER_BORDERS = {
    "tblBorders": ("shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription"),
    "tcBorders": ("shd", "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark"),
}


def _set_borders(parent, tag, edges, value):
    """Set the named edges of a table (tblBorders) or cell (tcBorders) border element."""
    borders = parent.find(qn(f"w:{tag}"))
    if borders is None:
        borders = OxmlElement(f"w:{tag}")
        later = [parent.find(qn(f"w:{t}")) for t in _AFTER_BORDERS[tag]]
        later = [el for el in later if el is not None]
        if later:
            min(later, key=parent.index).addprevious(borders)
        else:
            parent.append(borders)
    for edge in edges:
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), value)
        if value != "nil":
            el.set(qn("w:sz"), "8")
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), "000000")
