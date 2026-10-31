# Deal library fixtures

Unchanged copies of every distinct deal library found on the author's machine on
2026-10-31, used by `tests/test_compat.py`. The file name is `<project folder>_<file name>`.
`BWA/dealLibrary.js` was identical to `DealLibraries/dealLibrary.js`, so it is not repeated.

Do not edit these files: they stand for libraries already in use. To cover a new library,
add a copy of it here.

Two deals contain errors in the original data, and the tests expect ConstructInstruct to report them:
- `BWARepo_dealLibrary.js`, Hand 5: West holds ♥J (22) twice.
- `DealCreator_dealLibrary.js`, Hand 5: West holds 14 cards.
