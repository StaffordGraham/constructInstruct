"""Library Manager: list a libDeals library's deals, delete and reorder them, save.

Changes are held in memory until Save, which writes through the same safe
replace_library() as Check Out (verified, .bak backup, one-step replace).
Double-clicking a deal opens it in the editor through the app's own loader.
Save Current Deal adds the editor's deal (or replaces one of the same name) and
writes the file at once, through the same replace_library().
"""

import copy
import dataclasses
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .panels import library_deal_name
from .storage import (FileFormatError, LibraryText, append_to_library_text,
                      library_deals, library_entry_text, read_library,
                      replace_library, to_library_dict)

TITLE = "Library Manager"
# Where Browse… starts when no library folder has been remembered yet (skipped if missing).
DEFAULT_LIBRARY_DIR = Path(r"C:\Users\sgcam\Projects\DealLibraries")


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
        ttk.Label(top, text="Library file").pack(side="left")
        self.path_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.path_var, width=60)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 4))
        entry.bind("<Return>", lambda e: self.open_library())
        ttk.Button(top, text="Browse…", command=self.browse).pack(side="left")
        ttk.Button(top, text="Open Library", command=self.open_library).pack(side="left", padx=(4, 0))
        self.file_label = ttk.Label(f, text="No library open", foreground="#666")
        self.file_label.pack(anchor="w", pady=(4, 0))

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
                          ("Save Current Deal", self.save_current_deal),
                          ("Move Up", lambda: self.move(-1)),
                          ("Move Down", lambda: self.move(1)),
                          ("Delete", self.delete),
                          ("Save", self.save),
                          ("Close", self.close)]:
            b = ttk.Button(btns, text=text, command=cmd, width=18)
            b.pack(fill="x", pady=2)
            self.buttons[text] = b

        self.status = ttk.Label(f, foreground="#666",
                                text="Choose a deal library with Browse… (or type its path and "
                                     "press Open Library).")
        self.status.pack(anchor="w")
        self._refresh()
        entry.focus_set()

    # ----- loading and saving ---------------------------------------------------
    def browse(self):
        """Pick a library file. Choosing one opens it straight away."""
        from .app import LIBRARY_TYPES      # app imports this module, so import late
        path = filedialog.askopenfilename(parent=self, title="Choose a deal library",
                                          initialdir=self._start_folder(), filetypes=LIBRARY_TYPES)
        if not path:
            self._say("No library chosen." if self.path is None
                      else f"No new library chosen — {self.path.name} is still open.")
            return
        self.path_var.set(str(Path(path)))
        self.open_library()

    def _start_folder(self):
        """Where Browse… opens: the first of these folders that exists.

        The folder of the library in the path box, then the last library folder used
        (remembered in settings across sessions), then DEFAULT_LIBRARY_DIR, then the
        last folder used for any file. None lets the system choose.
        """
        settings = self.app.settings
        typed = self.path_var.get().strip().strip('"')
        candidates = [Path(typed).parent if typed and Path(typed).is_absolute() else None,
                      settings["library_dir"], DEFAULT_LIBRARY_DIR, settings["last_dir"]]
        for folder in candidates:
            if folder and Path(folder).is_dir():
                return str(folder)
        return None

    def open_library(self):
        """Open the library named in the path box."""
        typed = self.path_var.get().strip().strip('"')
        if not typed:
            self.bell()
            self._say("Choose a library with Browse…, or type its path, first.")
            return
        path = Path(typed)
        if not path.is_file():
            problem = "is a folder, not a library file" if path.is_dir() else "does not exist"
            self._error(f"{path} {problem}",
                        FileFormatError("Choose another library with Browse…, or correct the path."))
            return
        if not self._confirm_discard():
            return
        self.load(str(path))

    def load(self, path):
        name = Path(path).name
        try:
            text, had_bom = read_library(path)
            layout = LibraryText(text)
            deals = library_deals(text)
        except (OSError, FileFormatError) as e:
            self._error(f"{name} could not be opened as a deal library", e)
            self._say(f"{name} could not be opened. Choose another library with Browse…"
                      + (f" ({self.path.name} is still open)." if self.path else "."))
            return
        self.path, self.text, self.had_bom = Path(path), text, had_bom
        self.path_var.set(str(self.path))
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

    def save_current_deal(self):
        """Write the editor's deal into this library: appended, or replacing a deal of the
        same name if the user chooses. The file is updated at once."""
        if self.path is None:
            messagebox.showinfo(TITLE, "No library is open.", parent=self)
            return
        deal = self.app.deal
        errors = deal.validation().errors
        if errors:
            self._error("The current deal can't be saved to the library yet",
                        FileFormatError("\n".join(errors)))
            return
        if self.modified:
            if not messagebox.askyesno(TITLE, f"You have other unsaved changes to {self.path.name}. "
                                       "They must be saved first. Save them now?", parent=self):
                self._say("Nothing was saved.")
                return
            if not self.save():
                return

        name, description = deal.author.title.strip(), deal.author.concept
        while True:
            answer = DealNameDialog(self, name, description).result
            if answer is None:
                self._say("Nothing was saved.")
                return
            name, description = answer
            same = [i for i, d in enumerate(self.deals) if str(d.get("name", "")).strip() == name]
            if not same:
                index = None
                break
            choice = ChoiceDialog(
                self, f"{self.path.name} already has a deal called '{name}' (deal {same[0] + 1}).",
                ["Replace Existing Deal", "Save as New Name", "Cancel"]).result
            if choice == "Replace Existing Deal":
                index = same[0]
                break
            if choice != "Save as New Name":
                self._say("Nothing was saved.")
                return

        # Serialise a copy carrying the chosen name, so the editor changes only on success.
        named = copy.copy(deal)
        named.author = dataclasses.replace(deal.author, title=name, concept=description)
        entry = to_library_dict(named)
        expected = list(self.deals)
        try:
            if index is None:
                new_text = append_to_library_text(self.text, named)
                expected.append(entry)
                select = len(self.deals)
            else:
                layout = LibraryText(self.text)
                newline = "\r\n" if "\r\n" in self.text else "\n"
                layout.entries[index] = library_entry_text(entry, newline=newline).lstrip()
                new_text = layout.text()
                expected[index] = entry
                select = index
            replace_library(self.path, self.text, self.had_bom, new_text, expected)
        except (OSError, FileFormatError) as e:
            self._error(f"The deal was not saved, and {self.path.name} is unchanged", e)
            return

        self.text, self.layout, self.deals = new_text, LibraryText(new_text), library_deals(new_text)
        self.modified = False
        self._refresh(select=select)
        verb = "Added" if index is None else "Replaced"
        self._say(f"{verb} '{name}' as deal {select + 1} in {self.path.name} "
                  f"(previous version kept as {self.path.name}.bak).")
        deal.author.title, deal.author.concept = name, description
        self.app.author_panel.refresh(deal)
        self.app.author_changed(redraw=True)
        self.app.set_status(f"{verb} '{name}' in {self.path.name}")

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
            self.bell()
            if self.path is None:
                self._say("No library is open. Use Browse… to choose one.")
            elif not self.deals:
                self._say(f"{self.path.name} has no deals to open.")
            else:
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
        self.file_label.config(text=(f"Open: {self.path.name} — {len(self.deals)} deal"
                                     f"{'s' if len(self.deals) != 1 else ''}"
                                     + ("   (unsaved changes)" if self.modified else ""))
                               if self.path else "No library open")
        has = ["!disabled"] if self.deals else ["disabled"]
        for name in ("Open in Editor", "Move Up", "Move Down", "Delete"):
            self.buttons[name].state(has)
        self.buttons["Save"].state(["!disabled"] if self.modified else ["disabled"])

    def _say(self, text):
        self.status.config(text=text)

    def _error(self, what, e):
        self._say(f"{what}.")
        messagebox.showerror(TITLE, f"{what}.\n\n{friendly_error(e)}", parent=self)


class _Modal(tk.Toplevel):
    """Small modal dialog: subclasses build the body, then call _run(); result stays None
    if it is cancelled or closed."""

    def __init__(self, master, title):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        self.body = ttk.Frame(self, padding=12)
        self.body.pack(fill="both", expand=True)
        self.bind("<Escape>", lambda e: self.destroy())

    def _run(self, focus):
        self.grab_set()
        focus.focus_set()
        self.wait_window()


class DealNameDialog(_Modal):
    """Ask for the deal's library name (required) and description (optional).
    result is (name, description)."""

    def __init__(self, master, name, description):
        super().__init__(master, "Save Current Deal")
        self.name = tk.StringVar(value=name)
        self.description = tk.StringVar(value=description)
        ttk.Label(self.body, text="Deal name").grid(row=0, column=0, sticky="w", pady=2)
        entry = ttk.Entry(self.body, textvariable=self.name, width=40)
        entry.grid(row=0, column=1, sticky="we", padx=(8, 0), pady=2)
        ttk.Label(self.body, text="Description (optional)").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(self.body, textvariable=self.description, width=40).grid(
            row=1, column=1, sticky="we", padx=(8, 0), pady=2)
        self.hint = ttk.Label(self.body, text="", foreground="#a00")
        self.hint.grid(row=2, column=0, columnspan=2, sticky="w")
        btns = ttk.Frame(self.body)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Save", command=self._ok).pack(side="left")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left", padx=(4, 0))
        self.bind("<Return>", lambda e: self._ok())
        entry.select_range(0, "end")
        self._run(entry)

    def _ok(self):
        name = self.name.get().strip()
        if not name:
            self.hint.config(text="Type a name for the deal.")
            return
        self.result = (name, self.description.get().strip())
        self.destroy()


class ChoiceDialog(_Modal):
    """A message with one button per option; result is the chosen label, None if closed."""

    def __init__(self, master, message, options):
        super().__init__(master, TITLE)
        ttk.Label(self.body, text=message, wraplength=380).pack(anchor="w")
        btns = ttk.Frame(self.body)
        btns.pack(anchor="e", pady=(12, 0))
        buttons = [ttk.Button(btns, text=o, command=lambda o=o: self._pick(o)) for o in options]
        for b in buttons:
            b.pack(side="left", padx=(4, 0))
        self._run(buttons[-1])          # focus on the last (safe) option

    def _pick(self, option):
        self.result = None if option == "Cancel" else option
        self.destroy()
