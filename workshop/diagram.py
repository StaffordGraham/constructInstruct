"""The bridge diagram and card pool, drawn on one canvas.

The canvas owns the layout and the current selection. It never changes the
deal itself: drops, swaps and typed hands are passed to the app, which calls
the Deal methods (so undo and redraw happen in one place).
"""

import tkinter as tk

from .cards import (SEATS, SEAT_NAMES, SUIT_SYMBOLS, card_label, hcp,
                    rank_label, rank_of, shape_text, suit_of, to_pbn)
from .model import STRAIN_LABELS

FELT = "#256d3a"
BOX = "#2f7d46"
BOX_OUTLINE = "#1b4d2a"
TEXT = "#ffffff"
SUBTEXT = "#cfe8d5"
CARD_FILL = "#ffffff"
CARD_OUTLINE = "#8a8a8a"
SEL_FILL = "#ffd54f"
SEL_OUTLINE = "#a67c00"
LEAD_OUTLINE = "#1565c0"
LATER_LEAD_OUTLINE = "#64b5f6"
DIM_FILL = "#c4d3c8"
DIM_TEXT = "#6f8075"
TARGET = "#ffeb3b"
BAD = "#c62828"
GOOD = "#1b5e20"

# Rank colours on a white card, and suit symbol colours on the felt
TWO_COLOUR_CARD = ["#111111", "#c62828", "#c62828", "#111111"]
FOUR_COLOUR_CARD = ["#111111", "#c62828", "#d35400", "#1b7a2f"]
TWO_COLOUR_FELT = ["#ffffff", "#ff9e9e", "#ff9e9e", "#ffffff"]
FOUR_COLOUR_FELT = ["#ffffff", "#ff9e9e", "#ffcc80", "#b9f6ca"]

DRAG_THRESHOLD = 5


class DiagramCanvas(tk.Canvas):
    def __init__(self, master, app, scale=1.0):
        super().__init__(master, bg=FELT, highlightthickness=0)
        self.app = app
        self.deal = None
        self.scale = scale
        self.four_colour = False
        self.selection = set()
        self._press = None        # (x, y, card or None)
        self._drag_cards = None
        self._ignore_release = False
        self._entry = None        # (seat, Entry widget)
        self._layout()

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Double-Button-1>", self._on_double)
        self.bind("<Button-3>", self._on_right)

    # ----- geometry --------------------------------------------------------
    def S(self, v):
        return int(round(v * self.scale))

    def _layout(self):
        S = self.S
        self.cw, self.ch, self.gap = S(22), S(28), S(2)
        self.title_h = S(30)
        self.row_h = self.ch + S(4)
        self.box_w = S(38) + 13 * (self.cw + self.gap) + S(8)
        self.box_h = self.title_h + 4 * self.row_h + S(8)
        m, sp, cen_w = S(12), S(12), S(150)
        bw, bh = self.box_w, self.box_h
        total_w = 2 * m + 2 * bw + cen_w + 2 * sp
        cx0 = m + bw + sp
        nx0 = (total_w - bw) // 2
        y_mid = m + bh + sp
        y_s = y_mid + bh + sp
        self.boxes = {
            "N": (nx0, m, nx0 + bw, m + bh),
            "W": (m, y_mid, m + bw, y_mid + bh),
            "E": (cx0 + cen_w + sp, y_mid, cx0 + cen_w + sp + bw, y_mid + bh),
            "S": (nx0, y_s, nx0 + bw, y_s + bh),
        }
        self.center = (cx0, y_mid, cx0 + cen_w, y_mid + bh)
        self.margin = m

        self.pw, self.pgap = S(40), S(4)
        pool_w = S(46) + 13 * (self.pw + self.pgap)
        py0 = y_s + bh + S(16)
        px0 = (total_w - pool_w) // 2
        self.pool_box = (px0, py0, px0 + pool_w, py0 + S(28) + 4 * self.row_h + S(6))
        self.total_w = total_w
        self.total_h = self.pool_box[3] + m
        self.config(width=self.total_w, height=self.total_h)

        self.f_rank = ("Segoe UI", -S(16), "bold")
        self.f_suit = ("Segoe UI Symbol", -S(18))
        self.f_title = ("Segoe UI", -S(14), "bold")
        self.f_info = ("Segoe UI", -S(13))
        self.f_small = ("Segoe UI", -S(10), "bold")
        self.f_big = ("Segoe UI", -S(24), "bold")

    def _hand_slot(self, seat, suit, index):
        x0, y0, _, _ = self.boxes[seat]
        x = x0 + self.S(38) + index * (self.cw + self.gap)
        y = y0 + self.title_h + suit * self.row_h + self.S(2)
        return x, y

    def _pool_slot(self, c):
        x0, y0, _, _ = self.pool_box
        col = 12 - rank_of(c)
        x = x0 + self.S(40) + col * (self.pw + self.pgap)
        y = y0 + self.S(28) + suit_of(c) * self.row_h
        return x, y

    def seat_at(self, x, y):
        for seat, (x0, y0, x1, y1) in self.boxes.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return seat
        x0, y0, x1, y1 = self.pool_box
        if x0 <= x <= x1 and y0 <= y <= y1:
            return "pool"
        return None

    def _title_seat_at(self, x, y):
        for seat, (x0, y0, x1, _) in self.boxes.items():
            if x0 <= x <= x1 and y0 <= y <= y0 + self.title_h:
                return seat
        return None

    def card_at(self, x, y):
        """(card, canvas item) under the point, ignoring the drag ghost."""
        for item in reversed(self.find_overlapping(x, y, x, y)):
            tags = self.gettags(item)
            if "drag" in tags:
                continue
            for t in tags:
                if t.startswith("c") and t[1:].isdigit():
                    return int(t[1:]), item
        return None, None

    # ----- drawing ---------------------------------------------------------
    def set_deal(self, deal):
        self.deal = deal
        self.selection.clear()
        self.close_entry()
        self.redraw()

    def redraw(self):
        self.delete("all")
        if self.deal is None:
            return
        for seat in SEATS:
            self._draw_hand(seat)
        self._draw_center()
        self._draw_corners()
        self._draw_pool()
        if self._entry:
            self._place_entry()

    def _colours(self):
        if self.four_colour:
            return FOUR_COLOUR_CARD, FOUR_COLOUR_FELT
        return TWO_COLOUR_CARD, TWO_COLOUR_FELT

    def _draw_card(self, x, y, w, c, dim=False, seat_letter=""):
        S = self.S
        card_cols, _ = self._colours()
        selected = c in self.selection
        fill = SEL_FILL if selected else (DIM_FILL if dim else CARD_FILL)
        outline, width = (SEL_OUTLINE, 2) if selected else (CARD_OUTLINE, 1)
        if c == self.deal.opening_lead:
            outline, width = LEAD_OUTLINE, 3
        elif any(c in v for v in self.deal.later_leads.values()):
            outline, width = LATER_LEAD_OUTLINE, 3
        tags = ("card", f"c{c}")
        self.create_rectangle(x, y, x + w, y + self.ch, fill=fill, outline=outline,
                              width=width, tags=tags)
        colour = DIM_TEXT if (dim and not selected) else card_cols[suit_of(c)]
        tx = x + (w // 2 if not seat_letter else S(13))
        self.create_text(tx, y + self.ch // 2, text=rank_label(c), fill=colour,
                         font=self.f_rank, tags=tags)
        if seat_letter:
            self.create_text(x + w - S(4), y + self.ch - S(3), text=seat_letter,
                             anchor="se", fill="#24473a", font=self.f_small, tags=tags)

    def _draw_hand(self, seat):
        S = self.S
        x0, y0, x1, y1 = self.boxes[seat]
        _, felt_cols = self._colours()
        self.create_rectangle(x0, y0, x1, y1, fill=BOX, outline=BOX_OUTLINE, width=2)
        cards = self.deal.hand(seat)
        n = len(cards)
        ty = y0 + self.title_h // 2
        self.create_text(x0 + S(10), ty, text=SEAT_NAMES[seat].upper(), anchor="w",
                         fill=TEXT, font=self.f_title)
        # Card-count badge: green when 13, red otherwise
        bx1 = x1 - S(8)
        bx0 = bx1 - S(30)
        self.create_rectangle(bx0, ty - S(10), bx1, ty + S(10),
                              fill=GOOD if n == 13 else BAD, outline="")
        self.create_text((bx0 + bx1) // 2, ty, text=str(n), fill=TEXT, font=self.f_title)
        self.create_text(bx0 - S(10), ty, anchor="e", fill=SUBTEXT, font=self.f_info,
                         text=f"{hcp(cards)} HCP    {shape_text(cards)}")
        by_suit = [[c for c in cards if suit_of(c) == s] for s in range(4)]
        for s in range(4):
            ry = y0 + self.title_h + s * self.row_h + self.S(2) + self.ch // 2
            self.create_text(x0 + S(20), ry, text=SUIT_SYMBOLS[s], fill=felt_cols[s],
                             font=self.f_suit)
            if not by_suit[s]:
                self.create_text(x0 + S(40), ry, text="—", anchor="w", fill=SUBTEXT,
                                 font=self.f_info)
            for i, c in enumerate(by_suit[s]):
                x, y = self._hand_slot(seat, s, i)
                self._draw_card(x, y, self.cw, c)

    def _draw_center(self):
        S = self.S
        x0, y0, x1, y1 = self.center
        self.create_rectangle(x0, y0, x1, y1, fill="#1f5c31", outline=BOX_OUTLINE, width=2)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        pad = S(14)
        hcps = {s: hcp(self.deal.hand(s)) for s in SEATS}
        pos = {"N": (cx, y0 + pad), "S": (cx, y1 - pad),
               "W": (x0 + pad + S(6), cy), "E": (x1 - pad - S(6), cy)}
        decl = self.deal.contract.declarer
        for s, (x, y) in pos.items():
            colour = TARGET if s == decl else TEXT
            self.create_text(x, y, text=f"{s}\n{hcps[s]}" if s in "WE" else f"{s} {hcps[s]}",
                             fill=colour, font=self.f_title, justify="center")
        c = self.deal.contract
        self.create_text(cx, cy - S(10), text=c.short_text() or "—", fill=TEXT, font=self.f_big)
        lead = self.deal.opening_lead
        self.create_text(cx, cy + S(18), fill=SUBTEXT, font=self.f_info,
                         text=f"lead {card_label(lead)}" if lead is not None else "no lead")

    def _draw_corners(self):
        S = self.S
        m = self.margin
        nx0 = self.boxes["N"][0]
        d = self.deal
        c = d.contract
        title = d.author.title or "Untitled hand"
        lines = [title]
        if c.is_set:
            lines.append(f"{c.level}{STRAIN_LABELS[c.strain]} by {SEAT_NAMES[c.declarer]}")
        if d.opening_lead is not None:
            lines.append(f"Lead: {card_label(d.opening_lead)}")
        self.create_text(m + S(4), m + S(4), anchor="nw", text="\n".join(lines),
                         fill=TEXT, font=self.f_title, width=nx0 - m - S(12))
        ns = hcp(d.hand("N")) + hcp(d.hand("S"))
        ew = hcp(d.hand("E")) + hcp(d.hand("W"))
        nx1 = self.boxes["N"][2]
        self.create_text(self.total_w - m - S(4), m + S(4), anchor="ne", justify="right",
                         text=f"N-S {ns} HCP\nE-W {ew} HCP", fill=TEXT, font=self.f_title,
                         width=self.total_w - nx1 - m - S(12))

        sx0, sy0, sx1, _ = self.boxes["S"]
        sel = sorted(self.selection, key=lambda x: (suit_of(x), -rank_of(x)))
        sel_text = ("Selected: " + " ".join(card_label(x) for x in sel)) if sel else "Nothing selected"
        self.create_text(m + S(4), sy0 + S(4), anchor="nw", text=sel_text, fill=SUBTEXT,
                         font=self.f_info, width=sx0 - m - S(12))
        hint = ("click = select\nN E S W = move\nX = swap two\nP = to pool\n"
                "Shift-drag onto a card = swap\ndouble-click title = type hand")
        self.create_text(self.total_w - m - S(4), sy0 + S(4), anchor="ne", justify="right",
                         text=hint, fill=SUBTEXT, font=self.f_info)

    def _draw_pool(self):
        S = self.S
        x0, y0, x1, y1 = self.pool_box
        _, felt_cols = self._colours()
        self.create_rectangle(x0, y0, x1, y1, fill=BOX, outline=BOX_OUTLINE, width=2)
        unused = len(self.deal.pool())
        self.create_text(x0 + S(10), y0 + S(14), anchor="w", fill=TEXT, font=self.f_title,
                         text=f"CARD POOL   {unused} unused")
        self.create_text(x1 - S(10), y0 + S(14), anchor="e", fill=SUBTEXT, font=self.f_info,
                         text="white = unused    grey = in a hand (seat shown)")
        for s in range(4):
            ry = y0 + S(28) + s * self.row_h + self.ch // 2
            self.create_text(x0 + S(22), ry, text=SUIT_SYMBOLS[s], fill=felt_cols[s],
                             font=self.f_suit)
        for c, loc in self.deal.location.items():
            x, y = self._pool_slot(c)
            self._draw_card(x, y, self.pw, c, dim=loc is not None, seat_letter=loc or "")

    # ----- selection -------------------------------------------------------
    def set_selection(self, cards):
        self.selection = set(cards)
        self.redraw()
        self.app.selection_changed()

    def clear_selection(self):
        if self.selection:
            self.set_selection([])

    # ----- mouse -----------------------------------------------------------
    def _on_press(self, event):
        self.focus_set()
        card, _ = self.card_at(event.x, event.y)
        self._press = (event.x, event.y, card)
        self._drag_cards = None
        self._ignore_release = False

    def _on_motion(self, event):
        if not self._press or self._press[2] is None:
            return
        px, py, card = self._press
        if self._drag_cards is None:
            if abs(event.x - px) < DRAG_THRESHOLD and abs(event.y - py) < DRAG_THRESHOLD:
                return
            self._drag_cards = sorted(self.selection) if card in self.selection else [card]
            self._make_ghost(event.x, event.y)
            self.config(cursor="fleur")
        self._move_ghost(event.x, event.y)
        self._highlight_target(self._drop_target(event))

    def _on_release(self, event):
        if self._ignore_release or not self._press:
            self._ignore_release = False
            self._press = None
            return
        _, _, card = self._press
        self._press = None
        if self._drag_cards is None:
            # A plain click: toggle the card, or clear the selection on empty felt
            if card is None:
                self.clear_selection()
            else:
                self.selection ^= {card}
                self.redraw()
                self.app.selection_changed()
            return
        target = self._drop_target(event)
        cards = self._drag_cards
        self._drag_cards = None
        self.delete("drag", "hl")
        self.config(cursor="")
        if target is None:
            self.app.set_status("Drop cancelled")
            return
        kind, value = target
        if kind == "swap":
            self.app.do_swap(cards[0], value)
        else:
            self.app.do_move(cards, None if value == "pool" else value)

    def _on_double(self, event):
        self._ignore_release = True
        seat = self._title_seat_at(event.x, event.y)
        if seat:
            self.open_entry(seat)

    def _on_right(self, event):
        card, _ = self.card_at(event.x, event.y)
        if card is not None:
            self.app.card_menu(card, event)
            return
        seat = self.seat_at(event.x, event.y)
        if seat in SEATS:
            self.app.hand_menu(seat, event)
        elif seat == "pool":
            self.app.pool_menu(event)

    # ----- drag helpers ----------------------------------------------------
    def _drop_target(self, event):
        shift = bool(event.state & 0x0001)
        if shift and len(self._drag_cards) == 1:
            other, item = self.card_at(event.x, event.y)
            src = self._drag_cards[0]
            if other is not None and other != src and \
                    self.deal.location[other] != self.deal.location[src]:
                return ("swap", other)
            return None
        seat = self.seat_at(event.x, event.y)
        return ("move", seat) if seat else None

    def _make_ghost(self, x, y):
        S = self.S
        cards = self._drag_cards
        label = card_label(cards[0]) + (f" +{len(cards) - 1}" if len(cards) > 1 else "")
        w = S(40) if len(cards) == 1 else S(64)
        self.create_rectangle(0, 0, w, self.ch, fill=SEL_FILL, outline=SEL_OUTLINE,
                              width=2, tags=("drag",))
        card_cols, _ = self._colours()
        self.create_text(w // 2, self.ch // 2, text=label, font=self.f_rank,
                         fill=card_cols[suit_of(cards[0])], tags=("drag",))
        self._ghost_at = (0, 0)
        self._ghost_w = w

    def _move_ghost(self, x, y):
        gx = x - self._ghost_w // 2
        gy = y - self.ch - self.S(6)   # just above the pointer, so the target stays visible
        ox, oy = self._ghost_at
        self.move("drag", gx - ox, gy - oy)
        self._ghost_at = (gx, gy)
        self.tag_raise("drag")

    def _highlight_target(self, target):
        self.delete("hl")
        if target is None:
            return
        kind, value = target
        if kind == "swap":
            # Outline every place the target card is drawn
            for item in self.find_withtag(f"c{value}"):
                if self.type(item) == "rectangle":
                    x0, y0, x1, y1 = self.coords(item)
                    self.create_rectangle(x0 - 3, y0 - 3, x1 + 3, y1 + 3, outline=TARGET,
                                          width=3, tags=("hl",))
        else:
            box = self.pool_box if value == "pool" else self.boxes[value]
            self.create_rectangle(*box, outline=TARGET, width=4, tags=("hl",))
        self.tag_raise("drag")

    # ----- typed hand entry ------------------------------------------------
    def open_entry(self, seat):
        self.close_entry()
        e = tk.Entry(self, font=("Consolas", -self.S(15)), relief="flat", bg="#fffde7")
        e.insert(0, to_pbn(self.deal.hand(seat)))
        e.select_range(0, "end")
        e.bind("<Return>", lambda ev: self._apply_entry())
        e.bind("<KP_Enter>", lambda ev: self._apply_entry())
        e.bind("<Escape>", lambda ev: self.close_entry())
        self._entry = (seat, e)
        self._place_entry()
        e.focus_set()
        self.app.set_status(f"Type {SEAT_NAMES[seat]}'s hand as ♠.♥.♦.♣, e.g. AKJ74.K3.A62.Q85 "
                            "— Enter to apply, Esc to cancel")

    def _place_entry(self):
        seat, e = self._entry
        x0, y0, x1, _ = self.boxes[seat]
        S = self.S
        self.create_window(x0 + S(4), y0 + S(4), anchor="nw", window=e,
                           width=x1 - x0 - S(8), height=self.title_h - S(8), tags=("entry",))

    def _apply_entry(self):
        seat, e = self._entry
        if self.app.apply_hand_text(seat, e.get()):
            self.close_entry()

    def close_entry(self):
        if self._entry:
            self._entry[1].destroy()
            self._entry = None
            self.delete("entry")
