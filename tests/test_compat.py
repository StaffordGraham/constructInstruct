"""SmallCards compatibility: every real deal library survives a trip through ConstructInstruct.

The fixtures in tests/fixtures/libraries are copies of the deal libraries found on the
author's machine (see their README). Each deal is read, turned into a workshop Deal and
written back as a library entry, and must come out with nothing lost.

SmallCardsTests go one step further: they run SmallCards' own Deal.js under Node and check
that SmallCards builds the same deal from the regenerated library as from the original.
They are skipped when Node or the SmallCards folder is not available.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from workshop.storage import (LibraryText, append_to_library_text, deal_from_dict,
                              library_deals, load_any, read_library, save_workshop,
                              to_library_dict)

HERE = Path(__file__).resolve().parent
FIXTURES = sorted((HERE / "fixtures" / "libraries").glob("*.js"))
SMALLCARDS_DEAL_JS = HERE.parents[1] / "SmallCards" / "Deal.js"
PROBE = HERE / "smallcards_probe.js"

HAND_KEYS = ("south_cards", "west_cards", "north_cards", "east_cards")
# Filled in from "contract" when a library leaves them empty
DERIVED_KEYS = ("contract_trump", "contract_level")

# A deal using every field SmallCards reads that the workshop does not manage itself
UNMANAGED = {
    "southAuto": [12, 11], "westAuto": [], "northAuto": [3], "eastAuto": [],
    "vulnerability": "None", "bidSuit": "S",
    "eastPartnerLeadSuit": "H", "westPartnerLeadSuit": "",
    "west_leadto_return": "D", "east_leadto_return": "", "w_leadto_return": "C", "e_leadto_return": "",
    "checkpoints": [{"trick": 2, "seat": "N", "accept": [43, 44], "play": 43,
                     "hint": "Ruff a heart first", "explanation": "Dummy's trumps are for ruffing"}],
}


def full_entry():
    entry, = library_deals(FIXTURES[0].read_text(encoding="utf-8-sig"))[:1]
    return dict(entry, **UNMANAGED)


def fixture_entries():
    """(file name, index, entry) for every deal in every fixture library."""
    for path in FIXTURES:
        text, _ = read_library(path)
        for i, entry in enumerate(library_deals(text)):
            yield path.name, i, entry


def damaged(entry):
    """True when the entry's own hands are not 52 different cards, 13 each."""
    hands = [entry.get(k) or [] for k in HAND_KEYS]
    cards = [c for h in hands for c in h]
    return len(set(cards)) != 52 or len(cards) != 52 or any(len(h) != 13 for h in hands)


def round_trip(entry):
    deal, _ = deal_from_dict(entry)
    return deal, to_library_dict(deal)


class FixtureTests(unittest.TestCase):
    def test_fixtures_present(self):
        self.assertGreaterEqual(len(FIXTURES), 8)
        self.assertGreater(len(list(fixture_entries())), 30)


class LibraryRoundTripTests(unittest.TestCase):
    def test_no_field_is_lost(self):
        for name, i, entry in fixture_entries():
            with self.subTest(library=name, deal=i):
                _, out = round_trip(entry)
                self.assertEqual([k for k in entry if k not in out], [])

    def test_values_unchanged(self):
        for name, i, entry in fixture_entries():
            with self.subTest(library=name, deal=i):
                _, out = round_trip(entry)
                for k, v in entry.items():
                    if k in HAND_KEYS or (k in DERIVED_KEYS and v == ""):
                        continue
                    self.assertEqual(out[k], v, k)

    def test_hands_unchanged_or_damage_reported(self):
        for name, i, entry in fixture_entries():
            with self.subTest(library=name, deal=i):
                deal, out = round_trip(entry)
                if damaged(entry):
                    v = deal.validation()
                    self.assertTrue(deal.duplicates or not v.complete)
                else:
                    for k in HAND_KEYS:
                        self.assertEqual(sorted(out[k]), sorted(entry[k]), k)

    def test_unmanaged_fields_survive(self):
        _, out = round_trip(full_entry())
        for k, v in UNMANAGED.items():
            self.assertEqual(out[k], v, k)

    def test_unmanaged_fields_survive_a_workshop_file(self):
        deal, direct = round_trip(full_entry())
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "hand.json"
            save_workshop(deal, p)
            reloaded, kind = load_any(p)
        self.assertEqual(kind, "workshop")
        self.assertEqual(to_library_dict(reloaded), direct)

    def test_library_text_rebuilds_exactly(self):
        for path in FIXTURES:
            with self.subTest(library=path.name):
                text, _ = read_library(path)
                self.assertEqual(LibraryText(text).text(), text)

    def test_append_leaves_existing_deals_alone(self):
        deal, _ = round_trip(full_entry())
        for path in FIXTURES:
            with self.subTest(library=path.name):
                text, _ = read_library(path)
                lib = LibraryText(text)
                entries_end = len(text) - len(lib.trail) - len(lib.after)
                new = append_to_library_text(text, deal)
                self.assertTrue(new.startswith(text[:entries_end]))
                self.assertEqual(library_deals(new)[:-1], library_deals(text))


@unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
@unittest.skipUnless(SMALLCARDS_DEAL_JS.exists(), "SmallCards is not next to this project")
class SmallCardsTests(unittest.TestCase):
    """SmallCards builds the same Deal from a regenerated library as from the original."""

    def probe(self, texts):
        result = subprocess.run(["node", str(PROBE), str(SMALLCARDS_DEAL_JS)],
                                input=json.dumps(texts), capture_output=True,
                                text=True, encoding="utf-8", check=True)
        return json.loads(result.stdout)

    def regenerated(self, entries):
        text = "var libDeals = [\n];\n"
        for entry in entries:
            text = append_to_library_text(text, deal_from_dict(entry)[0])
        return text

    def expected(self, entry, seen):
        """What SmallCards should see after the trip: the original, with the
        improvements the workshop makes on purpose."""
        exp = json.loads(json.dumps(seen))
        if damaged(entry):
            for k in HAND_KEYS:
                exp["deal"].pop(k)
        for short, long in (("w_leads", "west_leads"), ("e_leads", "east_leads")):
            if short not in entry:          # old libraries name the leads only one way
                exp["deal"][short] = entry.get(long) or []
        if "west_leads" not in entry:
            exp["entry"]["west_leads"] = exp["deal"]["w_leads"]
        for k in ("description", "reference"):
            if k not in entry:              # the library table showed "undefined"
                exp["entry"][k] = ""
        if exp["deal"]["declarer"] is None:  # stored by SmallCards, never used
            exp["deal"]["declarer"] = "S"
        return exp

    def compare(self, entries, before, after):
        self.assertEqual(len(before), len(after))
        for i, (entry, b, a) in enumerate(zip(entries, before, after)):
            with self.subTest(deal=i, name=entry.get("name")):
                exp = self.expected(entry, b)
                for part in ("entry", "deal"):
                    got = {k: v for k, v in a[part].items() if k in exp[part]}
                    if part == "deal":
                        for k in HAND_KEYS:
                            if k in got:     # SmallCards sorts each hand as it deals it
                                got[k], exp[part][k] = sorted(got[k]), sorted(exp[part][k])
                    self.assertEqual(got, exp[part])

    def test_every_fixture_library(self):
        libraries = [library_deals(read_library(p)[0]) for p in FIXTURES]
        originals = [read_library(p)[0] for p in FIXTURES]
        before = self.probe(originals)
        after = self.probe([self.regenerated(entries) for entries in libraries])
        for path, entries, b, a in zip(FIXTURES, libraries, before, after):
            with self.subTest(library=path.name):
                self.compare(entries, b, a)

    def test_unmanaged_fields(self):
        entry = full_entry()
        original = "var libDeals = [\n" + json.dumps(entry) + "\n];\n"
        before, after = self.probe([original, self.regenerated([entry])])
        self.compare([entry], before, after)


if __name__ == "__main__":
    unittest.main()
