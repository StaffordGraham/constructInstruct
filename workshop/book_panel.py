"""The book pane: the book's outline, and details of the part selected in it.

Clicking a hand opens it in the deal editor beside the pane. Changes to the book
itself (titles, introductions, the order of chapters and hands) are saved as they are
made; a hand's cards and text are saved with the deal editor's Save, as before.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from .book import TRAINING_HANDS, deal_problems, roman

UNPLACED = "unplaced"
TRIMS = ["6x9", "7x10", "8.5x11"]
SAVE_DELAY_MS = 800
PROBLEM_FG = "#b26a00"
DONE_FG = "#1b5e20"


def _short(text, n=40):
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n - 1] + "…"


class BookPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=(6, 4, 2, 4))
        self.app = app
        self._save_job = None
        self._shown = None           # the tree item whose details are on show
        self._opened = None          # tree items left open, kept across rebuilds

        top = ttk.Frame(self)
        top.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(top, show="tree", selectmode="browse", height=18)
        scroll = ttk.Scrollbar(top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        self.tree.column("#0", width=290)
        self.tree.tag_configure("todo", foreground=PROBLEM_FG)
        self.tree.tag_configure("done", foreground=DONE_FG)
        self.tree.tag_configure("muted", foreground="#666")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Button-3>", self._on_right_click)

        row = ttk.Frame(self)
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="▲", width=3, command=lambda: self.move(-1)).pack(side="left")
        ttk.Button(row, text="▼", width=3, command=lambda: self.move(+1)).pack(side="left", padx=2)
        ttk.Label(row, text="Right-click for more", foreground="#666").pack(side="left", padx=6)

        self.details = ttk.LabelFrame(self, text="", padding=6)
        self.details.pack(fill="both", pady=(6, 0))

    # ----- the outline -----------------------------------------------------
    @property
    def project(self):
        return self.app.book

    def refresh(self):
        """Rebuild the outline from the project, keeping what was open and selected."""
        p = self.project
        tree = self.tree
        selected = tree.selection()
        if self._opened is None:
            self._opened = {"book", UNPLACED} | {f"s:{s.id}" for s in p.book.sections}
        else:
            self._opened = {i for i in self._items() if tree.item(i, "open")}
        tree.delete(*tree.get_children())
        tree.insert("", "end", "book", text=p.book.title or "Untitled book",
                    open="book" in self._opened)
        for s_num, section in enumerate(p.book.sections, start=1):
            sid = f"s:{section.id}"
            tree.insert("book", "end", sid, text=f"{roman(s_num)}   {section.title}",
                        open=sid in self._opened)
            for c_num, chapter_id in enumerate(section.chapters, start=1):
                chapter = p.chapters.get(chapter_id)
                if chapter is None:
                    continue
                cid = f"c:{chapter_id}"
                done = not p.chapter_problems(chapter_id)
                tree.insert(sid, "end", cid, text=f"{c_num}   {chapter.title}",
                            open=cid in self._opened, tags=("done",) if done else ())
                for slot in chapter.hands:
                    did = f"d:{slot.deal}"
                    if not tree.exists(did):
                        tree.insert(cid, "end", did, text=self._hand_text(slot.deal),
                                    tags=self._hand_tags(slot.deal))
        unplaced = p.unplaced_deals()
        tree.insert("", "end", UNPLACED, text=f"Unplaced hands ({len(unplaced)})",
                    open=UNPLACED in self._opened, tags=("muted",))
        for deal in unplaced:
            tree.insert(UNPLACED, "end", f"d:{deal.id}", text=self._unplaced_text(deal),
                        tags=self._hand_tags(deal.id))
        keep = [i for i in selected if tree.exists(i)]
        if keep:
            self.select(keep[0], show=keep[0] != self._shown)
        elif self._shown and not tree.exists(self._shown):
            self._show_details(None)

    def _items(self, parent=""):
        for item in self.tree.get_children(parent):
            yield item
            yield from self._items(item)

    def _hand_text(self, deal_id):
        p = self.project
        title = p.deals[deal_id].author.title.strip() if deal_id in p.deals else ""
        return f"{p.hand_label(deal_id)}   {title or '(untitled)'}"

    def _unplaced_text(self, deal):
        a = deal.author
        title = a.title.strip() or "(untitled)"
        return f"{title}   — {_short(a.concept, 30)}" if a.concept.strip() else title

    def _hand_tags(self, deal_id):
        return ("todo",) if self.hand_problems(deal_id) else ()

    def hand_problems(self, deal_id):
        p = self.project
        deal = p.deals.get(deal_id)
        if deal is None:
            return ["Missing from the deals folder"]
        problems = []
        where = p.placement(deal_id)
        if where and where[0].hands[where[1]].role == "hand" and not deal.author.concept.strip():
            problems.append("No concept: fill in Concept in the Author panel")
        return problems + deal_problems(deal)

    def select(self, item, show=True):
        """Select an item and show its details, without opening its hand again.

        Tk delivers <<TreeviewSelect>> later; by then the item is the one shown,
        so _on_select leaves it alone.
        """
        if not self.tree.exists(item):
            return
        parent = self.tree.parent(item)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)
        self.tree.selection_set(item)
        self.tree.see(item)
        if show:
            self._show_details(item)

    def _on_select(self, event=None):
        sel = self.tree.selection()
        item = sel[0] if sel else None
        if item == self._shown:
            return
        if item and item.startswith("d:") and item[2:] != self.app.book_deal_id:
            if not self.app.open_book_hand(item[2:]):
                if self._shown:
                    self.select(self._shown, show=False)
                return
        self._show_details(item)

    # ----- details of the selected item --------------------------------------
    def _show_details(self, item):
        self.flush()
        self._shown = item
        for child in self.details.winfo_children():
            child.destroy()
        p = self.project
        if item is None:
            self.details.config(text="")
            return
        kind, _, key = item.partition(":")
        if item == "book":
            self.details.config(text="Book")
            self._entry("Title", p.book, "title", rebuild=True)
            self._entry("Author", p.book, "author")
            self._choice("Trim size (inches)", p.book, "trim", TRIMS)
        elif item == UNPLACED:
            self.details.config(text="Unplaced hands")
            self._note("Hands in the book that are not in a chapter yet. Right-click one "
                       "to put it in a chapter, or right-click a chapter to add one.")
        elif kind == "s":
            section = p.section(key)
            number = p.book.sections.index(section) + 1
            self.details.config(text=f"Section {roman(number)}")
            self._entry("Title", section, "title", rebuild=True)
            self._text("Introduction", section, "intro", 5)
        elif kind == "c":
            chapter = p.chapters[key]
            s_num, c_num = p.chapter_number(key)
            self.details.config(text=f"Section {roman(s_num)}, Chapter {c_num}")
            self._entry("Title", chapter, "title", rebuild=True)
            self._text("Introduction", chapter, "intro", 5)
            self._text("Notes (not printed)", chapter, "notes", 3)
            self._problems(p.chapter_problems(key), "Ready: hands and training hands in place")
        elif kind == "d":
            deal = p.deals.get(key)
            code = p.hand_code(key)
            self.details.config(text=f"{p.hand_label(key)}   ({code})" if code else "Unplaced hand")
            if deal is not None:
                self._note(deal.author.title.strip() or "(untitled)", bold=True)
                if deal.author.concept.strip():
                    self._note("Concept: " + deal.author.concept.strip())
                self._note("Its cards, concept and commentary are edited on the right, "
                           "and saved with Save (Ctrl+S).", muted=True)
            self._problems(self.hand_problems(key), "Ready to play-test")

    def _label(self, text):
        ttk.Label(self.details, text=text).pack(anchor="w", pady=(4, 0))

    def _entry(self, label, obj, attr, rebuild=False):
        self._label(label)
        var = tk.StringVar(value=getattr(obj, attr))

        def changed(*_):
            setattr(obj, attr, var.get())
            self._changed(rebuild)
        var.trace_add("write", changed)
        ttk.Entry(self.details, textvariable=var, width=40).pack(fill="x")

    def _choice(self, label, obj, attr, values):
        self._label(label)
        box = ttk.Combobox(self.details, values=values, state="readonly", width=10)
        box.set(getattr(obj, attr))

        def changed(event):
            setattr(obj, attr, box.get())
            self._changed()
        box.bind("<<ComboboxSelected>>", changed)
        box.pack(anchor="w")

    def _text(self, label, obj, attr, height):
        self._label(label)
        t = tk.Text(self.details, height=height, width=40, wrap="word", undo=True,
                    font=("Segoe UI", 9), relief="solid", borderwidth=1)
        t.insert("1.0", getattr(obj, attr))
        t.edit_reset()
        t.edit_modified(False)

        def changed(event):
            if not t.edit_modified():
                return
            t.edit_modified(False)
            setattr(obj, attr, t.get("1.0", "end-1c"))
            self._changed(rebuild=(attr == "intro"))    # an introduction can finish a chapter
        t.bind("<<Modified>>", changed)
        t.pack(fill="x")

    def _note(self, text, bold=False, muted=False):
        ttk.Label(self.details, text=text, wraplength=300, justify="left",
                  foreground="#666" if muted else "",
                  font=("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

    def _problems(self, problems, ok_text):
        self._label("To do")
        if not problems:
            tk.Label(self.details, text="✔ " + ok_text, fg=DONE_FG, anchor="w",
                     font=("Segoe UI Symbol", 9)).pack(anchor="w")
        for text in problems:
            tk.Label(self.details, text="• " + text, fg=PROBLEM_FG, anchor="w", justify="left",
                     wraplength=300, font=("Segoe UI Symbol", 9)).pack(anchor="w")

    # ----- saving ------------------------------------------------------------
    def _changed(self, rebuild=False):
        """A book detail was typed: save it shortly (and redraw the outline, if asked)."""
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(SAVE_DELAY_MS, lambda: self._save(rebuild))

    def _save(self, rebuild=False):
        self._save_job = None
        try:
            self.project.save()
        except OSError as e:
            self.app.set_status(f"Book not saved: {e}", error=True)
            return
        if rebuild:
            self.refresh()      # new labels; the details being typed in stay as they are

    def flush(self):
        """Save any book detail still waiting to be saved."""
        if self._save_job:
            self.after_cancel(self._save_job)
            self._save()

    def changed(self, select=None):
        """The book's structure changed: save it and redraw the outline."""
        self.flush()
        try:
            self.project.save()
        except OSError as e:
            self.app.set_status(f"Book not saved: {e}", error=True)
        self._shown = None
        self.refresh()
        if select:
            self.select(select)

    # ----- actions -----------------------------------------------------------
    def selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def move(self, step):
        item = self.selected()
        if not item:
            return
        kind, _, key = item.partition(":")
        p = self.project
        moved = {"s": p.move_section, "c": p.move_chapter}.get(kind, lambda *_: False)(key, step)
        if kind == "d" and p.placement(key):
            moved = p.move_hand(key, step)
        if moved:
            self.changed(select=item)
        else:
            self.app.set_status("It can't move further that way")

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        if item != self.selected():
            self.tree.selection_set(item)
            self._on_select()
            if self.selected() != item:        # opening the hand was cancelled
                return
        menu = tk.Menu(self, tearoff=False)
        kind, _, key = item.partition(":")
        p = self.project
        if item == "book":
            menu.add_command(label="Add section", command=self.add_section)
        elif kind == "s":
            menu.add_command(label="Add chapter", command=lambda: self.add_chapter(key))
            menu.add_separator()
            menu.add_command(label="Move section up", command=lambda: self.move(-1))
            menu.add_command(label="Move section down", command=lambda: self.move(+1))
            menu.add_command(label="Remove section", command=lambda: self.remove_section(key),
                             state="normal" if not p.section(key).chapters else "disabled")
        elif kind == "c":
            menu.add_command(label="New hand", command=lambda: self.new_hand(key, "hand"))
            menu.add_command(label="New training hand",
                             command=lambda: self.new_hand(key, "training"))
            for role, words in (("hand", "Add an unplaced hand"),
                                ("training", "Add an unplaced hand as a training hand")):
                sub = tk.Menu(menu, tearoff=False)
                for deal in p.unplaced_deals():
                    sub.add_command(label=self._unplaced_text(deal),
                                    command=lambda d=deal.id, r=role: self.place(d, key, r))
                menu.add_cascade(label=words, menu=sub,
                                 state="normal" if p.unplaced_deals() else "disabled")
            menu.add_separator()
            menu.add_command(label="Move chapter up", command=lambda: self.move(-1))
            menu.add_command(label="Move chapter down", command=lambda: self.move(+1))
            menu.add_command(label="Remove chapter…", command=lambda: self.remove_chapter(key))
        elif kind == "d" and p.placement(key):
            menu.add_command(label="Move up", command=lambda: self.move(-1))
            menu.add_command(label="Move down", command=lambda: self.move(+1))
            menu.add_command(label="Take out of chapter (back to unplaced)",
                             command=lambda: self.unplace(key))
            menu.add_separator()
            menu.add_command(label="Remove from book…", command=lambda: self.remove_deal(key))
        elif kind == "d":
            for role, words in (("hand", "Put in chapter as a hand"),
                                ("training", "Put in chapter as a training hand")):
                menu.add_cascade(label=words, menu=self._chapter_menu(menu, key, role))
            menu.add_separator()
            menu.add_command(label="Remove from book…", command=lambda: self.remove_deal(key))
        else:
            return
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _chapter_menu(self, parent, deal_id, role):
        menu = tk.Menu(parent, tearoff=False)
        p = self.project
        for s_num, section in enumerate(p.book.sections, start=1):
            sub = tk.Menu(menu, tearoff=False)
            for c_num, chapter_id in enumerate(section.chapters, start=1):
                full = role == "training" and len(p.chapters[chapter_id].training()) >= TRAINING_HANDS
                sub.add_command(label=f"{c_num}   {p.chapters[chapter_id].title}",
                                state="disabled" if full else "normal",
                                command=lambda c=chapter_id: self.place(deal_id, c, role))
            menu.add_cascade(label=f"{roman(s_num)}   {section.title}", menu=sub,
                             state="normal" if section.chapters else "disabled")
        return menu

    def place(self, deal_id, chapter_id, role):
        try:
            self.project.place(deal_id, chapter_id, role)
        except ValueError as e:
            self.app.set_status(str(e), error=True)
            return
        self.changed(select=f"c:{chapter_id}")
        self.app.book_deal_moved()
        self.app.set_status(f"{self.project.deal_title(deal_id)} is now "
                            f"{self.project.hand_label(deal_id)} of {self.project.chapters[chapter_id].title}")

    def unplace(self, deal_id):
        chapter = self.project.placement(deal_id)[0]
        self.project.unplace(deal_id)
        self.changed(select=f"c:{chapter.id}")
        self.app.book_deal_moved()

    def add_section(self):
        section = self.project.add_section("New section")
        self.changed(select=f"s:{section.id}")

    def add_chapter(self, section_id):
        chapter = self.project.add_chapter(section_id, "New chapter")
        self.changed(select=f"c:{chapter.id}")

    def new_hand(self, chapter_id, role):
        self.app.new_book_hand(chapter_id, role)

    def remove_section(self, section_id):
        self.project.remove_section(section_id)
        self.changed()

    def remove_chapter(self, chapter_id):
        chapter = self.project.chapters[chapter_id]
        hands = len(chapter.hands)
        extra = f"\n\nIts {hands} hand{'s' if hands != 1 else ''} will stay in the book, " \
                f"under Unplaced hands." if hands else ""
        if not messagebox.askyesno("Remove chapter",
                                   f"Remove the chapter “{chapter.title}”?{extra}\n\n"
                                   "Its file is kept in the book's removed folder.",
                                   parent=self):
            return
        self.project.remove_chapter(chapter_id)
        self.changed()
        self.app.book_deal_moved()

    def remove_deal(self, deal_id):
        title = self.project.deal_title(deal_id)
        if not messagebox.askyesno("Remove hand",
                                   f"Remove “{title}” from the book?\n\n"
                                   "Its file is kept in the book's removed folder.",
                                   parent=self):
            return
        self.app.book_deal_removed(deal_id)
        self.project.remove_deal(deal_id)
        self.changed()
