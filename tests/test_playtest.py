import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from tests.test_core import sample_deal
from workshop.cards import parse_card
from workshop.model import Contract, lho
from workshop.playtest import (PlayTestServer, is_smallcards_folder, playtest_problems,
                               playtest_record, playtest_report)
from workshop.storage import load_any, save_workshop, to_library_dict

# Trick 1 of sample_deal: West leads ♦K, North ♦4, East ♦7, South wins with ♦A.
# SmallCards holder numbers: 0 South, 1 West, 2 North, 3 East.
TRICK_1 = {"cards": [[1, 37], [2, 28], [3, 31], [0, 38]], "winner": 0}


HOLDER = {"S": 0, "W": 1, "N": 2, "E": 3}


def tricks(ns_tricks, played=13):
    """A whole hand of sample_deal: each seat plays its cards in order (legality is not
    checked here); N-S win the first ns_tricks tricks (South), E-W the rest (West)."""
    hands = sample_deal().hands()
    out, leader = [], "W"
    for i in range(played):
        seats = [leader]
        while len(seats) < 4:
            seats.append(lho(seats[-1]))
        winner = "S" if i < ns_tricks else "W"
        out.append({"cards": [[HOLDER[s], hands[s][i]] for s in seats], "winner": HOLDER[winner]})
        leader = winner
    return out


class ProblemTests(unittest.TestCase):
    def test_ready(self):
        self.assertEqual(playtest_problems(sample_deal()), [])

    def test_incomplete_deal(self):
        d = sample_deal()
        d.move([parse_card("SA")], None)
        self.assertIn("North has 12 cards", playtest_problems(d))

    def test_declarer_must_be_south(self):
        d = sample_deal()
        d.contract = Contract(level=4, strain="H", declarer="N")
        self.assertEqual(playtest_problems(d), ["SmallCards needs South to declare"])

    def test_needs_opening_lead_held_by_west(self):
        d = sample_deal()
        d.opening_lead = None
        self.assertIn("opening lead", playtest_problems(d)[0])
        d.opening_lead = parse_card("SA")       # North's card
        self.assertIn("not in West's hand", playtest_problems(d)[0])


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.entry = to_library_dict(sample_deal())

    def test_record(self):
        rec = playtest_record({"tricks": tricks(10)}, self.entry)
        self.assertEqual(rec["tricks"], 10)
        self.assertEqual(rec["needed"], 10)
        self.assertTrue(rec["made"])
        self.assertTrue(rec["complete"])
        self.assertEqual(rec["contract"], "4 Hearts")
        self.assertEqual(rec["play"][0], {"leader": "W", "cards": [9, 12, 6, 11], "winner": "S"})
        self.assertEqual(rec["play"][-1]["winner"], "W")
        self.assertEqual(rec["hands"]["S"], self.entry["south_cards"])

    def test_failed_and_unfinished(self):
        rec = playtest_record({"tricks": tricks(9, played=10)}, self.entry)
        self.assertFalse(rec["made"])
        self.assertFalse(rec["complete"])

    def test_numbers_sent_as_strings(self):
        t = {"cards": [["1", "37"], ["2", "28"], ["3", "31"], ["0", "38"]], "winner": "0"}
        self.assertEqual(playtest_record({"tricks": [t]}, self.entry)["play"][0]["cards"],
                         [37, 28, 31, 38])

    def test_rejects_malformed(self):
        bad_tricks = [
            {"cards": [[1, 37], [2, 28], [3, 31]], "winner": 0},            # 3 cards
            {"cards": [[1, 37], [3, 31], [2, 28], [0, 38]], "winner": 0},   # not clockwise
            {"cards": [[1, 52], [2, 28], [3, 31], [0, 38]], "winner": 0},   # not a card
            {"cards": [[1, 37], [2, 28], [3, 31], [0, 38]], "winner": 7},   # no such seat
            {"cards": [[1, True], [2, 28], [3, 31], [0, 38]], "winner": 0},
        ]
        for t in bad_tricks:
            with self.subTest(trick=t):
                self.assertIsNone(playtest_record({"tricks": [t]}, self.entry))
        self.assertIsNone(playtest_record({"tricks": []}, self.entry))
        self.assertIsNone(playtest_record("nonsense", self.entry))
        self.assertIsNone(playtest_record({"tricks": tricks(1)}, None))   # unknown version

    def test_rejects_impossible_play(self):
        self.assertIsNone(playtest_record({"tricks": [TRICK_1, TRICK_1]}, self.entry))
        wrong_hand = {"cards": [[1, 38], [2, 28], [3, 31], [0, 37]], "winner": 0}   # S's ♦A by W
        self.assertIsNone(playtest_record({"tricks": [wrong_hand]}, self.entry))


class DealPlaytestTests(unittest.TestCase):
    def test_saved_with_the_deal(self):
        d = sample_deal()
        rec = playtest_record({"tricks": tricks(13)}, to_library_dict(d))
        messages = []
        d.add_listener(messages.append)
        d.add_playtest(rec)
        self.assertEqual(messages, ["Play-test: 13 tricks in 4 Hearts — made"])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "deal.json"
            save_workshop(d, p)
            text = p.read_text(encoding="utf-8")
            loaded, _ = load_any(p)
        self.assertEqual(loaded.playtests, [rec])
        self.assertIn('"cards": [9, 12, 6, 11]', text)      # card lists kept on one line

    def test_current_layout(self):
        d = sample_deal()
        d.add_playtest(playtest_record({"tricks": tricks(13)}, to_library_dict(d)))
        self.assertTrue(d.playtest_is_current(d.playtests[0]))
        self.assertIn("[this layout]", playtest_report(d))
        d.swap(parse_card("SA"), parse_card("SK"))
        self.assertFalse(d.playtest_is_current(d.playtests[0]))
        self.assertIn("[an earlier layout]", playtest_report(d))

    def test_report(self):
        d = sample_deal()
        self.assertIn("No play-tests yet", playtest_report(d))
        d.add_playtest(playtest_record({"tricks": tricks(9)}, to_library_dict(d)))
        report = playtest_report(d)
        self.assertIn("4 Hearts: 9 tricks (needed 10) — FAILED", report)
        self.assertIn("1.  W ♠J", report)
        self.assertIn("S ♠K", report)
        self.assertIn("won by W", report)

    def test_bad_saved_records_skipped(self):
        d = sample_deal()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "deal.json"
            save_workshop(d, p)
            data = json.loads(p.read_text(encoding="utf-8"))
            data["playtests"] = [{"tricks": 3}, "junk", None]
            p.write_text(json.dumps(data), encoding="utf-8")
            loaded, _ = load_any(p)
        self.assertEqual(loaded.playtests, [])


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        folder = Path(self.tmp.name)
        (folder / "index.html").write_text("<p>SmallCards</p>", encoding="utf-8")
        (folder / "PlayTest.js").write_text("// play-test", encoding="utf-8")
        self.server = PlayTestServer(folder)
        self.entry = to_library_dict(sample_deal())

    def tearDown(self):
        self.server.close()
        self.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.server.origin + path) as r:
            return r.read().decode("utf-8"), r.headers

    def post(self, data, origin=None, raw=None):
        body = raw if raw is not None else json.dumps(data).encode("utf-8")
        req = urllib.request.Request(self.server.origin + "/playtest/result", data=body,
                                     headers={"Content-Type": "application/json"})
        if origin:
            req.add_header("Origin", origin)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            e.close()
            return e.code

    def test_folder_check(self):
        self.assertTrue(is_smallcards_folder(self.tmp.name))
        self.assertFalse(is_smallcards_folder(Path(self.tmp.name) / "missing"))
        self.assertFalse(is_smallcards_folder(""))

    def test_serves_smallcards(self):
        text, headers = self.get("/index.html")
        self.assertEqual(text, "<p>SmallCards</p>")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertTrue(self.server.url.endswith("/index.html?playtest=1"))

    def test_state(self):
        self.assertFalse(self.server.page_open())
        self.assertEqual(json.loads(self.get("/playtest/state")[0]), {"version": 0, "deal": None})
        self.assertTrue(self.server.page_open())
        v = self.server.publish(self.entry)
        state = json.loads(self.get("/playtest/state?have=")[0])
        self.assertEqual(state, {"version": v, "deal": self.entry})
        # The page already has this version: no need to send the deal again
        self.assertEqual(json.loads(self.get(f"/playtest/state?have={v}")[0]),
                         {"version": v, "deal": None})

    def test_result_is_queued(self):
        v = self.server.publish(self.entry)
        data = {"version": v, "tricks": tricks(13)}
        self.assertEqual(self.post(data, origin=self.server.origin), 200)
        record, raw = self.server.results.get(timeout=2)
        self.assertEqual(raw, data)
        self.assertEqual(record["tricks"], 13)

    def test_result_for_unknown_version(self):
        self.assertEqual(self.post({"version": 99, "tricks": tricks(13)}), 200)
        record, _ = self.server.results.get(timeout=2)
        self.assertIsNone(record)

    def test_rejects_other_pages_and_bad_bodies(self):
        self.assertEqual(self.post({"tricks": []}, origin="http://evil.example"), 403)
        self.assertEqual(self.post(None, raw=b"{not json"), 400)
        self.assertEqual(self.post(None, raw=b"x" * 300_000), 400)
        self.assertTrue(self.server.results.empty())


if __name__ == "__main__":
    unittest.main()
