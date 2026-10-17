import json
import tempfile
import unittest
from pathlib import Path

from workshop.cards import (card, card_label, from_pbn, hcp, parse_card,
                            parse_suit_group, shape_text, to_pbn)
from workshop.commands import CommandError, run_command
from workshop.model import Contract, Deal
from workshop.storage import (contract_text, from_tutor_dict, load_any,
                              save_workshop, to_tutor_dict, tutor_json_text)

SAMPLE = {"N": "AQ72.K63.984.A52", "E": "865.42.765.KT987",
          "S": "KT3.AQJT9.A32.Q4", "W": "J94.875.KQJT.J63"}


def sample_deal():
    d = Deal()
    for seat, pbn in SAMPLE.items():
        d.set_hand(seat, from_pbn(pbn))
    d.contract = Contract(level=4, strain="H", declarer="S")
    d.opening_lead = parse_card("DK")
    d.history.clear()
    return d


class CardTests(unittest.TestCase):
    def test_numbering_matches_tutor(self):
        self.assertEqual(parse_card("SA"), 12)
        self.assertEqual(parse_card("H2"), 13)
        self.assertEqual(parse_card("KD"), 37)
        self.assertEqual(parse_card("♣A"), 51)
        self.assertEqual(parse_card("10D"), card(2, 8))

    def test_suit_group(self):
        self.assertEqual(parse_suit_group("SAKQ"), [12, 11, 10])
        self.assertEqual(parse_suit_group("D10"), [card(2, 8)])

    def test_pbn_round_trip(self):
        cards = from_pbn("AKQ7.J94.K5.432")
        self.assertEqual(to_pbn(cards), "AKQ7.J94.K5.432")
        self.assertEqual(hcp(cards), 9 + 1 + 3)
        self.assertEqual(shape_text(cards), "4-3-2-3")
        self.assertEqual(to_pbn(from_pbn("A10 . . . ")), "AT...")
        with self.assertRaises(ValueError):
            from_pbn("AA...")


class DealTests(unittest.TestCase):
    def test_complete_deal_validates(self):
        v = sample_deal().validation()
        self.assertTrue(v.complete)
        self.assertEqual(v.errors, [])
        self.assertEqual(v.warnings, [])

    def test_swap_and_undo(self):
        d = sample_deal()
        q, seven = parse_card("DQ"), parse_card("D7")   # West, East
        self.assertTrue(d.swap(q, seven))
        self.assertEqual(d.location[q], "E")
        self.assertEqual(d.location[seven], "W")
        self.assertFalse(d.swap(q, parse_card("D6")))  # both East
        d.undo()
        self.assertEqual(d.location[q], "W")
        d.redo()
        self.assertEqual(d.location[q], "E")

    def test_move_counts_and_lead_warning(self):
        d = sample_deal()
        d.move([parse_card("DK")], "E")
        v = d.validation()
        self.assertFalse(v.complete)
        self.assertIn("West has 12 cards", v.errors)
        self.assertTrue(any("Opening lead" in w for w in v.warnings))

    def test_set_hand_pulls_cards_and_releases_others(self):
        d = sample_deal()
        d.set_hand("N", from_pbn("AQ72.K63.984.A5Q"))   # take ♣Q from South, drop ♣2
        self.assertEqual(d.location[parse_card("CQ")], "N")
        self.assertIsNone(d.location[parse_card("C2")])
        self.assertEqual(len(d.hand("S")), 12)

    def test_versions(self):
        d = sample_deal()
        d.snapshot_version("base")
        d.clear_all()
        self.assertEqual(len(d.pool()), 52)
        d.restore_version(0)
        self.assertEqual(to_pbn(d.hand("N")), SAMPLE["N"])


class StorageTests(unittest.TestCase):
    def test_workshop_round_trip(self):
        d = sample_deal()
        d.author.title = "Hand 12"
        d.author.notes = "Ducking ♦"
        d.later_leads["W"] = [parse_card("DQ")]
        d.snapshot_version("base")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            save_workshop(d, p)
            d2, kind = load_any(p)
        self.assertEqual(kind, "workshop")
        self.assertEqual(d2.hands(), d.hands())
        self.assertEqual(d2.contract, d.contract)
        self.assertEqual(d2.opening_lead, d.opening_lead)
        self.assertEqual(d2.later_leads, d.later_leads)
        self.assertEqual(d2.author, d.author)
        self.assertEqual(d2.versions[0].hands, d.versions[0].hands)

    def test_tutor_export_fields(self):
        d = sample_deal()
        d.later_leads["W"] = [parse_card("DQ")]
        out = to_tutor_dict(d)
        self.assertEqual(out["contract"], "4 Hearts")
        self.assertEqual(out["contract_trump"], "H")
        self.assertEqual(out["w_leads"], [parse_card("DK"), parse_card("DQ")])
        self.assertEqual(out["west_leads"], out["w_leads"])
        self.assertEqual(out["si_player"], 4)
        self.assertEqual(out["south_cards"][0], parse_card("SK"))   # spades first, high first
        json.loads(tutor_json_text(d))    # valid JSON

    def test_contract_text(self):
        self.assertEqual(contract_text(Contract(1, "S")), "1 Spade")
        self.assertEqual(contract_text(Contract(3, "N")), "3 NoTrumps")

    def test_tutor_import_with_duplicates(self):
        data = {"south_cards": [12, 11], "west_cards": [12, 9], "north_cards": [],
                "east_cards": [], "contract": "5 Clubs", "west_leads": [9],
                "east_leads": [], "si_action": 2, "commentary": "hi"}
        d = from_tutor_dict(data)
        self.assertEqual(d.duplicates, [12])
        self.assertEqual(d.location[12], "S")
        self.assertEqual(d.contract, Contract(5, "C", "S"))
        self.assertEqual(d.opening_lead, 9)
        out = to_tutor_dict(d)
        self.assertEqual(out["si_action"], 2)
        self.assertEqual(out["commentary"], "hi")

    def test_real_tutor_files_round_trip(self):
        """Import every tutor file found next to this project and re-export it."""
        root = Path(__file__).resolve().parents[2]
        files = [root / "BWARepo" / "1a Mendelson7.json",
                 root / "Bridge_Declarer Web App" / "Mendelson33",
                 root / "Book" / "Hands" / "Hand45.json"]
        files = [f for f in files if f.exists()]
        if not files:
            self.skipTest("no sample tutor files on this machine")
        for f in files:
            with self.subTest(file=f.name):
                original = json.loads(f.read_text(encoding="utf-8-sig"))
                d, kind = load_any(f)
                self.assertEqual(kind, "tutor")
                out = to_tutor_dict(d)
                for key in ("south_cards", "west_cards", "north_cards", "east_cards"):
                    self.assertEqual(sorted(out[key]), sorted(original[key]))
                orig_w = original.get("w_leads") or original.get("west_leads") or []
                self.assertEqual(out["w_leads"], orig_w)


class CommandTests(unittest.TestCase):
    def test_commands(self):
        d = sample_deal()
        run_command(d, "DQ x D7")
        self.assertEqual(d.location[parse_card("DQ")], "E")
        run_command(d, "CAK P")
        self.assertIsNone(d.location[parse_card("CK")])
        run_command(d, "CK CA N")
        self.assertEqual(d.location[parse_card("CK")], "N")
        run_command(d, "S: KT3.AQJT9.A32.Q4")
        run_command(d, "lead DJ")
        self.assertEqual(d.opening_lead, parse_card("DJ"))
        with self.assertRaises(CommandError):
            run_command(d, "DQ Z")
        with self.assertRaises(CommandError):
            run_command(d, "D6 x D5")      # same hand


if __name__ == "__main__":
    unittest.main()
