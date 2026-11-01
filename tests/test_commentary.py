import tempfile
import unittest
from pathlib import Path

from tests.test_core import sample_deal
from workshop.cards import parse_card
from workshop.commentary import (accept_card_record, all_checkpoint_problems, card_changes,
                                 card_change_text, card_mentions, markup_spans, parse,
                                 update_card_record)
from workshop.storage import (deal_from_dict, load_any, save_workshop, to_library_dict,
                              to_tutor_dict, to_workshop_dict)

C = parse_card


class CardMentionTests(unittest.TestCase):
    def test_cards_in_text(self):
        text = "Win the ♦A, ruff with dummy's ♠5, cash ♥10 and ♣K. Not ♠Ace or ♥1."
        self.assertEqual([c for _, _, c in card_mentions(text)],
                         [C("DA"), C("S5"), C("HT"), C("CK")])
        start, end, _ = card_mentions(text)[2]
        self.assertEqual(text[start:end], "♥10")

    def test_moved_cards_are_reported_until_accepted(self):
        d = sample_deal()                     # North holds ♠2, East ♠5
        d.commentary = "Ruff with dummy's ♠2."
        update_card_record(d)
        self.assertEqual(card_changes(d), [])
        d.swap(C("S2"), C("S5"))              # ♠2 goes to East
        self.assertEqual(card_changes(d), [(C("S2"), "N", "E")])
        self.assertEqual(card_change_text(card_changes(d)[0]),
                         "♠2 was North's when the commentary mentioned it; it is now East's")
        d.commentary += " Then lead ♠5."      # a new mention is recorded where it is now
        update_card_record(d)
        self.assertEqual(d.commentary_cards[C("S5")], "N")
        self.assertEqual(card_changes(d), [(C("S2"), "N", "E")])   # still reported
        accept_card_record(d)
        self.assertEqual(card_changes(d), [])
        d.commentary = "Nothing about cards."
        update_card_record(d)
        self.assertEqual(d.commentary_cards, {})


class MarkupTests(unittest.TestCase):
    def test_blocks(self):
        text = ("Count your **losers**: there are\nfour.\n\n"
                "- Draw *two* rounds\n- Ruff the ♥3\n\nThen claim.")
        self.assertEqual(parse(text), [
            ("para", [("text", "Count your "), ("bold", "losers"),
                      ("text", ": there are four.")]),
            ("bullets", [[("text", "Draw "), ("italic", "two"), ("text", " rounds")],
                         [("text", "Ruff the "), ("card", C("H3"))]]),
            ("para", [("text", "Then claim.")])])

    def test_cards_inside_bold(self):
        self.assertEqual(parse("**Duck the ♦K!**")[0][1],
                         [("bold", "Duck the "), ("card", C("DK")), ("bold", "!")])

    def test_a_lone_star_is_text(self):
        self.assertEqual(parse("5 * 3 = 15")[0][1], [("text", "5 * 3 = 15")])

    def test_editor_spans(self):
        kinds = sorted(k for _, _, k in markup_spans("**A** ♠5"))
        self.assertEqual(kinds, ["bold", "card-S", "marker", "marker"])


class CheckpointTests(unittest.TestCase):
    def test_problems_match_coach_js(self):
        d = sample_deal()
        d.checkpoints = [
            {"trick": 2, "seat": "N", "accept": [C("CA")], "hint": "h", "explanation": "e"},
            {"suitLed": 1, "seat": "S", "accept": [C("CA")], "play": C("HA")},
            {"seat": "W", "accept": []}]
        self.assertEqual(all_checkpoint_problems(d), [
            "Checkpoint 2 (First heart lead): ♣A is not in South's hand",
            "Checkpoint 3 (?): the player must be South or dummy (North)",
            "Checkpoint 3 (?): say which trick, or which suit's first lead",
            "Checkpoint 3 (?): no correct card chosen"])


class StorageTests(unittest.TestCase):
    def deal(self):
        d = sample_deal()
        d.commentary = "Ruff with dummy's ♠2."
        update_card_record(d)
        d.checkpoints = [{"trick": 2, "seat": "N", "accept": [C("S2")], "hint": "Ruff",
                          "explanation": "Dummy's trumps ruff", "extra": "kept"}]
        return d

    def test_workshop_file_round_trip(self):
        d = self.deal()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            save_workshop(d, p)
            d2, _ = load_any(p)
        self.assertEqual((d2.commentary, d2.commentary_cards, d2.checkpoints),
                         (d.commentary, {C("S2"): "N"}, d.checkpoints))
        self.assertNotIn("commentary", d2.tutor_extra)

    def test_smallcards_gets_both(self):
        out = to_library_dict(self.deal())
        self.assertEqual(out["commentary"], "Ruff with dummy's ♠2.")
        self.assertEqual(out["checkpoints"][0]["extra"], "kept")
        self.assertEqual(to_tutor_dict(self.deal())["checkpoints"], out["checkpoints"])
        self.assertNotIn("checkpoints", to_library_dict(sample_deal()))   # none: not written

    def test_library_entry_brings_them_in(self):
        entry = to_library_dict(self.deal())
        d, kind = deal_from_dict(entry)
        self.assertEqual((kind, d.commentary, d.checkpoints),
                         ("tutor", entry["commentary"], entry["checkpoints"]))
        self.assertFalse({"commentary", "checkpoints"} & d.tutor_extra.keys())

    def test_older_workshop_file_moves_them_out_of_tutor_extra(self):
        data = to_workshop_dict(sample_deal())
        del data["commentary"], data["checkpoints"]
        data["tutor_extra"] = {"commentary": "Old words", "checkpoints": [{"trick": 1}]}
        d, _ = deal_from_dict(data)
        self.assertEqual((d.commentary, d.checkpoints, d.tutor_extra),
                         ("Old words", [{"trick": 1}], {}))


if __name__ == "__main__":
    unittest.main()
