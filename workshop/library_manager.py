"""Library Manager: list a libDeals library's deals, delete and reorder them, save.

Changes are held in memory until Save, which writes through the same safe
replace_library() as Check Out (verified, .bak backup, one-step replace).
Double-clicking a deal opens it in the editor through the app's own loader.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .panels import library_deal_name
from .storage import (FileFormatError, LibraryText, library_deals, read_library,
                      replace_library)

TITLE = "Library Manager"


def friendly_error(e):
    """Plain-English text for the errors a library read or write can raise."""
    if isinstance(e, FileNotFoundError):
        return "The file could not be found. It may have been moved or deleted."
    if isinstance(e, PermissionError):
        return ("Permission was denied. The file may be read-only or open in another "
                "program.")
    if isinstance(e, OSError):
        return f"The file could not be read or written ({e.strerror or e})."
    return str(e)


def _field(entry, key):
    value = entry.get(key)
    return str(value).strip() if value is not None else ""


def manager_row_text(number, entry):
    """'3. Mendelson | Chapter 2 | Hand 6': where a deal sits, no bridge details.

    The position number keeps deals with the same book and hand apart. Missing
    fields show a placeholder instead.
    """
    book = _field(entry, "book") or "No book"
    chapter = _field(entry, "chapter")
    if not chapter:
        chapter = "Chapter ?"
    elif not chapter.lower().startswith("chapter"):
        chapter = f"Chapter {chapter}"
    hand = _field(entry, "name") or _field(entry, "title") or _field(entry, "handId")
    if not hand:
        hand = "Hand ?"
    elif hand.isdigit():
        hand = f"Hand {hand}"
    return f"{number}. {book} | {chapter} | {hand}"


class LibraryManager(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.path = None
        self.text = ""          # file text as last read or saved, to detect outside changes
        self.had_bom = False
        self.layout = None      # LibraryText being edited
        self.deals = []         # parsed entries, in the same order as self.layout.entries
        self.modified = False
        self.title(TITLE)
        self.protocol("WM_DELETE_WINDOW", self.close)

        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Button(top, text="Open Library…", command=self.choose).pack(side="left")
        self.file_label = ttk.Label(top, text="No library open", foreground="#666", wraplength=480)
        self.file_label.pack(side="left", padx=8)

        body = ttk.Frame(f)
        body.pack(fill="both", expand=True, pady=6)
        self.listbox = tk.Listbox(body, width=72, height=20, activestyle="none",
                                  exportselection=False)
        bar = ttk.Scrollbar(body, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=bar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        bar.pack(side="left", fill="y")
        self.listbox.bind("<Double-Button-1>", lambda e: self.open_in_editor())
        self.listbox.bind("<Return>", lambda e: self.open_in_editor())
        self.listbox.bind("<Delete>", lambda e: self.delete())

        btns = ttk.Frame(body)
        btns.pack(side="left", fill="y", padx=(8, 0))
        self.buttons = {}
        for text, cmd in [("Open in Editor", self.open_in_editor),
                          ("Move Up", lambda: self.move(-1)),
                          ("Move Down", lambda: self.move(1)),
                          ("Delete", self.delete),
                          ("Save", self.save),
                          ("Close", self.close)]:
            b = ttk.Button(btns, text=text, command=cmd, width=15)
            b.pack(fill="x", pady=2)
            self.buttons[text] = b

        self.status = ttk.Label(f, foreground="#666",
                                text="Double-click a deal to open it in the editor. "
                                     "The file changes only when you press Save.")
        self.status.pack(anchor="w")
        self._refresh()
        self.after_idle(self.choose)

    # ----- loading and saving ---------------------------------------------------
    def choose(self):
        if not self._confirm_discard():
            return
        from .app import LIBRARY_TYPES      # app imports this module, so import late
        settings = self.app.settings
        path = filedialog.askopenfilename(
            parent=self, title="Open deal library",
            initialdir=settings["library_dir"] or settings["last_dir"] or None,
            filetypes=LIBRARY_TYPES)
        if path:
            self.load(path)

    def load(self, path):
        name = Path(path).name
        try:
            text, had_bom = read_library(path)
            layout = LibraryText(text)
            deals = library_deals(text)
        except (OSError, FileFormatError) as e:
            self._error(f"{name} could not be opened as a deal library", e)
            return
        self.path, self.text, self.had_bom = Path(path), text, had_bom
        self.layout, self.deals, self.modified = layout, deals, False
        self.app.settings["library_dir"] = str(self.path.parent)
        self._refresh(select=0)
        self._say(f"{len(deals)} deal{'s' if len(deals) != 1 else ''} in {name}.")
        if not deals:
            messagebox.showinfo(TITLE, f"{name} is a valid library, but its libDeals "
                                "array has no deals.", parent=self)

    def save(self):
        """Write the edited library. Returns False if it could not be saved."""
        if self.path is None or not self.modified:
            return True
        new_text = self.layout.text()
        try:
            replace_library(self.path, self.text, self.had_bom, new_text, self.deals)
        except (OSError, FileFormatError) as e:
            self._error(f"{self.path.name} was not saved, and the file on disk is unchanged", e)
            return False
        self.text, self.layout, self.modified = new_text, LibraryText(new_text), False
        self._refresh(select=self._index())
        self._say(f"Saved {self.path.name} (previous version kept as {self.path.name}.bak).")
        return True

    # ----- editing -------------------------------------------------------------
    def delete(self):
        i = self._selected()
        if i is None:
            return
        if not messagebox.askyesno(
                TITLE, f"Delete deal {i + 1}, '{library_deal_name(self.deals[i])}', "
                f"from {self.path.name}?\n\nThe file is not changed until you press Save.",
                parent=self):
            return
        self.deals.pop(i)
        self.layout.delete(i)
        self.modified = True
        self._refresh(select=min(i, len(self.deals) - 1))

    def move(self, step):
        i = self._selected()
        if i is None:
            return
        j = i + step
        if not 0 <= j < len(self.deals):
            return
        self.deals[i], self.deals[j] = self.deals[j], self.deals[i]
        self.layout.swap(i, j)
        self.modified = True
        self._refresh(select=j)

    def open_in_editor(self):
        i = self._selected()
        if i is None or not self.app.confirm_discard():
            return
        title = self.app.load_library_entry(self.deals[i], self.path.name)
        if title is not None:
            self.app.set_status(f"Opened '{title}' from {self.path.name} — the library is unchanged")
            self._say(f"Opened '{title}' in the editor.")

    def close(self):
        if self._confirm_discard():
            self.destroy()

    # ----- helpers -------------------------------------------------------------
    def _confirm_discard(self):
        if not self.modified:
            return True
        answer = messagebox.askyesnocancel(TITLE, f"Save changes to {self.path.name} first?",
                                           parent=self)
        if answer is None:
            return False
        return self.save() if answer else True

    def _index(self):
        sel = self.listbox.curselection()
        return sel[0] if sel and sel[0] < len(self.deals) else None

    def _selected(self):
        i = self._index()
        if i is None:
            self._say("Select a deal first.")
        return i

    def _refresh(self, select=None):
        self.listbox.delete(0, "end")
        for n, d in enumerate(self.deals, start=1):
            self.listbox.insert("end", manager_row_text(n, d))
        if self.path is not None and not self.deals:
            self.listbox.insert("end", "(this library has no deals)")
        if select is not None and 0 <= select < len(self.deals):
            self.listbox.selection_set(select)
            self.listbox.activate(select)
            self.listbox.see(select)
        star = " *" if self.modified else ""
        self.title(f"{TITLE} — {self.path.name}{star}" if self.path else TITLE)
        self.file_label.config(text=(f"{self.path.name}" + ("   (unsaved changes)" if self.modified else "")
                                     + f"\nin {self.path.parent}") if self.path else "No library open")
        has = ["!disabled"] if self.deals else ["disabled"]
        for name in ("Open in Editor", "Move Up", "Move Down", "Delete"):
            self.buttons[name].state(has)
        self.buttons["Save"].state(["!disabled"] if self.modified else ["disabled"])

    def _say(self, text):
        self.status.config(text=text)

    def _error(self, what, e):
        self._say(f"{what}.")
        messagebox.showerror(TITLE, f"{what}.\n\n{friendly_error(e)}", parent=self)
