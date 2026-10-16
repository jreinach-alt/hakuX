# One display name per title_id, and nothing keyed by a name (#433)

State: draft

Lane: titlekey1016            Issue: #433
Base: master @ 15a72e10dc
Files: docs/testing/title_registry.py, docs/testing/titles/targets.toml, docs/lanes/titlekey1016/NOTES.md, docs/lanes/titlekey1016/PR.md
Prediction: none: analysis/data-consistency fix, no device or pixel claim
Needs device: no    Needs NDK: no

Release note (performance|stability|rendering|other|none): none

## What this is

The systemic fix behind the 32 h status-page crash (10-14 23:42 to 10-16,
`KeyError` on a name lookup) and the 77-vs-87 Playable count mismatch
between GitHub's landing page and the ledger. lane.statusfix1016 patched
the one crashing lookup; this lane makes title_id the only key a display
name is ever looked up by, with one source of truth for what that name is.

`docs/testing/title_registry.py`'s `Catalog` had two independent,
disagreeing "which name wins" rules (one inside `Catalog.add()`, a second
inside `build()`), and `build_catalog()` never loaded the Playable ledger
at all -- a caller that built a catalog directly (this lane's own `check`
CLI, `status_html._title_catalog`'s separate overlay) got a different
answer than `build()` did. Replaced both with one explicit priority order
(`_name_priority`): the Playable ledger, then `targets.toml`, then a
device listing, then everything else (console-inventory XBE strings,
`owner-library-done.tsv`). `build_catalog()` now loads the ledger itself,
so its result IS the final display name everywhere, with no second rule
to drift out of sync.

`title_registry.py check` now runs a `name_drift()` check on every
invocation: any title_id where the ledger or targets.toml disagrees with
the catalog's resolved name, or with each other, prints `NAME DRIFT <tid>:
source=name; ...` and fails. Reproduced red on the pre-fix code (78
drifting title_ids; see NOTES.md for the full list and the brief's cited
Crimson Skies/Conker/Blinx/Ninja Gaiden examples), green after the fix
(zero drift once the 4 real targets.toml-vs-ledger disagreements left over
were fixed by hand: JSRF, Guilty Gear XX #Reload, KOF Maximum Impact's
dash, Family Guy -- all 4 now match the ledger spelling, which is what the
Wall/README/COMPATIBILITY.md already publicly show for 3 of the 4).

## In progress / not yet in this push

- `status_html.py`'s `titles05`/`canon`/`resolve` name-keyed structures
  (item 2's largest piece): **blocked** on lane.statusfix1016's fold,
  which held this file and had not landed on `origin/master` as of this
  push (still at `15a72e10dc`, the sha this branch also started from).
  Per the brief's explicit order-of-work, not edited yet.
- `docs/testing/title_locations.py` audit: not started.
- Item 3 (README Playable count tracks the ledger even when the status
  render is degraded) and item 4 (hourly alarm for a stale/wrong public
  count): not yet written.
- The selftest fixture (Crimson Skies/Conker mismatched spellings) with
  its mutant proof: not yet written.
- `docs/testing/compat_page.py`'s `notes_by_title`, keyed by
  `(section, title)`: flagged, not converted or ruled out yet.

See NOTES.md for the full audit table, the 78-row before/after drift
list, and the exact reproduction commands. This PR stays in draft until
status_html.py is unblocked (or a NEED: is filed) and items 3/4 and the
selftest are in.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
