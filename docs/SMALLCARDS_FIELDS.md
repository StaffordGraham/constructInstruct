# SmallCards deal library — field contract

What SmallCards reads from a deal library, so ConstructInstruct can keep every library
it writes 100% compatible. Taken from the SmallCards source (`Deal.js`, `script.js`,
`DealLibraries.js`, `Coach.js`) on 2026-10-31. `tests/test_compat.py` checks it
automatically by running SmallCards' own `Deal.js` under Node.

## The file

```js
const libDeals = [ {deal}, {deal}, ... ]     // var and let also work
```

SmallCards runs the file as JavaScript inside its own function and takes `libDeals`. A trailing
`module.exports` line is ignored. Each entry must be an object.

## Fields

| Field | Read by | Notes |
|---|---|---|
| `name` | Deal, library table | Shown in the table's "Hand" column |
| `description` | Deal, library table | Shown in the "Description" column. A missing field shows as "undefined" |
| `reference` | library table | Shown in the column headed "Page" |
| `south_cards` `west_cards` `north_cards` `east_cards` | Deal | Card numbers 0–51 (♠ 0–12, ♥ 13–25, ♦ 26–38, ♣ 39–51; 2 up to A). **Order does not matter**: SmallCards sorts each suit as it deals |
| `contract` | Deal | **Required**, as `"<level> <Word>"`, e.g. `"4 Spades"`, `"3 NoTrumps"`. SmallCards takes the level from the first word and the strain from the first letter of the second word. Any other form stops the deal loading |
| `w_leads` `e_leads` | Deal | Defenders' leads in order; the opening leader's first card is the opening lead. Missing = no leads |
| `west_leads` | `loadLastHand` (loading a single file) | Older name for `w_leads`. ConstructInstruct writes both |
| `declarer` | Deal | Stored but not used. SmallCards assumes South declares |
| `book` `page` `commentary` | Deal | Text |
| `checkpoints` | Coach | Mid-hand coaching; format in `Coach.js` |
| `defensiveOverrides` | Defence | `{player, suitLed, occurrence, cardToPlay}`; see SPEC.md §4.2a |
| `southAuto` `westAuto` `northAuto` `eastAuto` | Deal → auto-play | Card lists for auto-play |
| `eastPartnerLeadSuit` `westPartnerLeadSuit` | Deal | Defence hints |
| `west_leadto_return` `east_leadto_return` `w_leadto_return` `e_leadto_return` | Deal | Defence hints |
| `vulnerability` `bidSuit` | Deal | `bidSuit` is recalculated from `contract` |

Fields SmallCards does not read (`all_cards`, `contract_trump`, `contract_level`, `si_*`,
`comment`) are kept for DealCreator and the older tutor.

## Rules for ConstructInstruct

1. **Never lose a field.** Every field of an imported entry is written back, including
   fields the workshop does not manage (they travel in `tutor_extra`).
2. **Never change what a field means.** Card sets, leads, text and contract stay the same.
   Allowed differences: hands are re-sorted, empty `contract_trump`/`contract_level` are
   filled in from `contract`, and missing `w_leads`/`west_leads`, `declarer`,
   `description` and `reference` are added.
3. **Never write a deal without a contract.** Save To Library refuses incomplete deals.
4. **Additions must be additive.** A new field is fine. A renamed or retyped field is not.

## Known SmallCards issue

`script.js`, around line 205 (take back a trick): `theDeal.west_leads.includes(x)`. A `Deal`
object has no `west_leads` property (it stores `w_leads`), so **Back** throws an error part way
through. To be fixed in Phase 1, with the play-test work.
