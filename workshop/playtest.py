"""Play-test bridge: serves SmallCards and the deal being edited. No tkinter in here.

ConstructInstruct runs one PlayTestServer on 127.0.0.1. SmallCards, opened at
    http://127.0.0.1:<port>/index.html?playtest=1
loads the deal from it instead of showing its library screen, and reports each
finished hand back. No files are written.

    GET  /playtest/state?have=<n>   {"version": n, "deal": entry, or null if the page has it}
    POST /playtest/result           a finished hand, queued for the app (see playtest_record)
Everything else is served from the SmallCards folder.
"""

import ctypes
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .cards import SEAT_NAMES, card_label
from .model import lho

PAGE = "index.html?playtest=1"
WINDOW_TITLE = "SmallCards Play-test"     # set by SmallCards' PlayTest.js
HOLDER_SEATS = "SWNE"                     # SmallCards' holder numbers 0-3
MAX_RESULT_BYTES = 200_000


def is_smallcards_folder(path):
    p = Path(path) if path else None
    return bool(p) and (p / "index.html").is_file() and (p / "PlayTest.js").is_file()


def default_smallcards_folder():
    """SmallCards next to this project, if it is there."""
    guess = Path(__file__).resolve().parents[2] / "SmallCards"
    return guess if is_smallcards_folder(guess) else None


def playtest_problems(deal):
    """Reasons SmallCards cannot play this deal ([] if it can)."""
    v = deal.validation()
    problems = list(v.errors)
    if v.errors:
        return problems
    if deal.contract.declarer != "S":
        problems.append("SmallCards needs South to declare")
    elif deal.opening_lead is None:
        problems.append("Set an opening lead — SmallCards starts play with it")
    elif deal.location[deal.opening_lead] != deal.contract.leader:
        problems.append(f"The opening lead {card_label(deal.opening_lead)} is not in "
                        f"{SEAT_NAMES[deal.contract.leader]}'s hand")
    return problems


def _card(value):
    """A card number from SmallCards (it may send numbers as strings); None if not a card."""
    try:
        c = int(value)
    except (TypeError, ValueError):
        return None
    return c if 0 <= c < 52 and str(c) == str(value).strip() else None


def _trick(t):
    """One reported trick as {"leader": seat, "cards": [...]}, or None if malformed."""
    if not isinstance(t, dict) or not isinstance(t.get("cards"), list) or len(t["cards"]) != 4:
        return None
    seats, cards = [], []
    for pair in t["cards"]:
        if not isinstance(pair, list) or len(pair) != 2:
            return None
        holder, c = _card(pair[0]), _card(pair[1])
        if holder is None or holder > 3 or c is None:
            return None
        seats.append(HOLDER_SEATS[holder])
        cards.append(c)
    for a, b in zip(seats, seats[1:]):
        if b != lho(a):           # play goes clockwise from the leader
            return None
    winner = _card(t.get("winner"))
    if winner is None or winner > 3:
        return None
    return {"leader": seats[0], "cards": cards, "winner": HOLDER_SEATS[winner]}


def playtest_record(data, entry):
    """The record kept in the deal for one finished hand, or None if data is not one.

    data is what SmallCards posts: {"tricks": [{"cards": [[holder, card] x4], "winner": holder}]}.
    entry is the library entry that was played, so the record names the hands it was
    tested on even if the deal has been changed since.
    """
    if not isinstance(data, dict) or not isinstance(data.get("tricks"), list) or not entry:
        return None
    tricks = [_trick(t) for t in data["tricks"][:13]]
    if not tricks or None in tricks:
        return None
    hands = {s: list(entry[f"{SEAT_NAMES[s].lower()}_cards"]) for s in "NESW"}
    played = set()
    for t in tricks:              # every card once, by the seat that holds it
        seat = t["leader"]
        for c in t["cards"]:
            if c in played or c not in hands[seat]:
                return None
            played.add(c)
            seat = lho(seat)
    level = int(entry.get("contract_level") or 0)
    won = sum(t["winner"] in "NS" for t in tricks)
    return {
        "played": datetime.now().isoformat(timespec="seconds"),
        "contract": entry.get("contract", ""),
        "tricks": won,
        "needed": level + 6,
        "made": won >= level + 6,
        "complete": len(tricks) == 13,
        "hands": hands,
        "play": tricks,
    }


def playtest_report(deal):
    """The deal's play-tests as text, newest first, trick by trick."""
    if not deal.playtests:
        return ("No play-tests yet.\n\nPress F5 to play this deal in SmallCards. Each hand "
                "you finish there is recorded here, and saved with the deal.")
    out = []
    for n, rec in reversed(list(enumerate(deal.playtests, start=1))):
        layout = "this layout" if deal.playtest_is_current(rec) else "an earlier layout"
        result = "made" if rec["made"] else "FAILED"
        out.append(f"#{n}  {rec.get('played', '')}   {rec['contract']}: {rec['tricks']} tricks "
                   f"(needed {rec.get('needed', '?')}) — {result}   [{layout}]")
        for i, t in enumerate(rec.get("play", []), start=1):
            seat, cards = t["leader"], []
            for c in t["cards"]:
                cards.append(f"{seat} {card_label(c)}")
                seat = lho(seat)
            out.append(f"   {i:>2}.  " + "   ".join(f"{x:<6}" for x in cards) + f"  won by {t['winner']}")
        out.append("")
    return "\n".join(out)


class PlayTestServer:
    """The local web server SmallCards talks to while play-testing."""

    def __init__(self, folder, port=0):
        self.folder = Path(folder)
        self.results = queue.Queue()      # (record or None, raw data); read by the app
        self._lock = threading.Lock()
        self._version = 0
        self._entries = {}                # version -> published library entry
        self._last_poll = None
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.port = self.httpd.server_port
        self.origin = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"{self.origin}/{PAGE}"

    def publish(self, entry):
        """Make entry (a library entry dict) the deal SmallCards plays next."""
        with self._lock:
            self._version += 1
            self._entries[self._version] = entry
            return self._version

    def page_open(self, within=3.0):
        """True if a play-test page has asked for the deal in the last few seconds."""
        with self._lock:
            return self._last_poll is not None and time.monotonic() - self._last_poll < within

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    # ----- requests --------------------------------------------------------------
    def _state(self, have):
        with self._lock:
            self._last_poll = time.monotonic()
            v = self._version
            return {"version": v, "deal": self._entries.get(v) if have != v else None}

    def _result(self, data):
        version = data.get("version") if isinstance(data, dict) else None
        with self._lock:
            entry = self._entries.get(version)
        self.results.put((playtest_record(data, entry), data))

    def _handler(self):
        server = self

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(server.folder), **kwargs)

            def do_GET(self):
                url = urlparse(self.path)
                if url.path == "/playtest/state":
                    have = parse_qs(url.query).get("have", [""])[0]
                    self.send_json(server._state(int(have) if have.isdigit() else None))
                else:
                    super().do_GET()

            def do_POST(self):
                if urlparse(self.path).path != "/playtest/result":
                    return self.send_error(404)
                # Only the play-test page itself may report, not another web page
                if self.headers.get("Origin", server.origin) != server.origin:
                    return self.send_error(403)
                length = int(self.headers.get("Content-Length") or 0)
                if not 0 < length <= MAX_RESULT_BYTES:
                    return self.send_error(400)
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return self.send_error(400)
                server._result(data)
                self.send_json({"ok": True})

            def send_json(self, data):
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def end_headers(self):
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-SmallCards", "1")     # what serve.py sends too
                super().end_headers()

            def log_message(self, format, *args):
                pass

        return Handler


# ----- the play-test window ----------------------------------------------------

_BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]


def open_window(url):
    """Open url in a window of its own (Chrome or Edge 'app' window), else the default browser."""
    exe = next((b for b in _BROWSERS if Path(b).is_file()), None) or shutil.which("chrome")
    if exe:
        try:
            subprocess.Popen([exe, f"--app={url}", "--window-size=1280,880"])
            return
        except OSError:
            pass
    webbrowser.open(url)


def raise_window(title=WINDOW_TITLE):
    """Bring the play-test window to the front (Windows only). True if it was found."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def visit(hwnd, _):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.startswith(title) and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
                return False
            return True

        user32.EnumWindows(visit, 0)
        if not found:
            return False
        if user32.IsIconic(found[0]):
            user32.ShowWindow(found[0], 9)       # SW_RESTORE
        user32.SetForegroundWindow(found[0])
        return True
    except (AttributeError, OSError):
        return False
