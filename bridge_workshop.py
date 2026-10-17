"""Bridge Instructional Deal Workshop — start here.

    python bridge_workshop.py [deal.json]
"""

import sys
import tkinter as tk

from workshop.app import WorkshopApp


def main():
    if sys.platform == "win32":
        # Crisp text on high-DPI screens; the diagram scales itself to match.
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    app = WorkshopApp(root)
    if len(sys.argv) > 1:
        app.open(sys.argv[1])
    root.mainloop()


if __name__ == "__main__":
    main()
