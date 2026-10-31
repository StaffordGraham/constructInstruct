// What SmallCards sees in deal library files. Run by tests/test_compat.py:
//     node smallcards_probe.js <path to SmallCards Deal.js>   (JSON array of library texts on stdin)
// Prints, for each library, one record per deal: the fields SmallCards' library table reads
// straight from the entry, and the fields of the Deal object SmallCards builds from it.

const fs = require("fs")

const DEAL_FIELDS = [
  "name", "south_cards", "north_cards", "east_cards", "west_cards",
  "southAuto", "westAuto", "northAuto", "eastAuto",
  "contract", "bidLevel", "bidSuit", "declarer", "vulnerability", "w_leads", "e_leads",
  "eastPartnerLeadSuit", "westPartnerLeadSuit",
  "west_leadto_return", "east_leadto_return", "w_leadto_return", "e_leadto_return",
  "book", "description", "page", "commentary", "checkpoints", "defensiveOverrides",
]
// Read from the entry itself: the library table (script.js populateLibraryTable) and loadLastHand
const ENTRY_FIELDS = ["name", "description", "reference", "west_leads"]

const Deal = new Function(fs.readFileSync(process.argv[2], "utf8") + "\nreturn Deal")()

// The same evaluation as loadDealLibrary in SmallCards' DealLibraries.js
function libDeals(text) {
  return new Function("module", "exports",
    text + "\nreturn typeof libDeals === 'undefined' ? undefined : libDeals")({ exports: {} }, {})
}

function pick(obj, keys) {
  const out = {}
  for (const k of keys) { out[k] = obj[k] === undefined ? null : obj[k] }
  return out
}

const libraries = JSON.parse(fs.readFileSync(0, "utf8"))
const result = libraries.map(text => libDeals(text).map(entry => ({
  entry: pick(entry, ENTRY_FIELDS),
  deal: pick(new Deal(entry), DEAL_FIELDS),
})))
process.stdout.write(JSON.stringify(result))
