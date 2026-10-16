# One display name per title_id, and nothing keyed by a name (#433)

State: ready

Lane: titlekey1016            Issue: #433
Base: master @ 15a72e10dc
Files: docs/testing/title_registry.py, docs/testing/titles/targets.toml, docs/testing/title_registry_selftest.py, docs/testing/compat_page.py, docs/testing/compat_page_selftest.py, docs/testing/compat_notes.tsv, docs/lanes/titlekey1016/NOTES.md, docs/lanes/titlekey1016/PR.md, docs/lanes/titlekey1016/OUTBOX.md, docs/lanes/titlekey1016/host-tools/INSTALL.md, docs/lanes/titlekey1016/host-tools/status_page.py, docs/lanes/titlekey1016/host-tools/status_alarm.py, docs/lanes/titlekey1016/host-tools/status_alarm_selftest.py
Prediction: none: analysis/data-consistency fix, no device or pixel claim
Needs device: no    Needs NDK: no

Release note (performance|stability|rendering|other|none): none

## What this is

The systemic fix behind the 32 h status-page crash (10-14 23:42 to 10-16,
`KeyError` on a name lookup) and the 77-vs-87 Playable count mismatch
between GitHub's landing page and the ledger. lane.statusfix1016 patched
the one crashing lookup; this lane makes title_id the only key a display
name is ever looked up by, with one source of truth for what that name is.

**Item 1 -- the one name source.** `docs/testing/title_registry.py`'s
`Catalog` had two independent, disagreeing "which name wins" rules (one
inside `Catalog.add()`, a second inside `build()`), and `build_catalog()`
never loaded the Playable ledger at all -- a caller that built a catalog
directly (this lane's own `check` CLI, `status_html._title_catalog`'s
separate overlay) got a different answer than `build()` did. Replaced both
with one explicit priority order (`_name_priority`): the Playable ledger,
then `targets.toml`, then a device listing, then everything else
(console-inventory XBE strings, `owner-library-done.tsv`). `build_catalog()`
now loads the ledger itself, so its result IS the final display name
everywhere, with no second rule to drift out of sync.

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

`docs/testing/title_registry_selftest.py` (new) proves the mechanism with
the brief's own Crimson Skies/Conker examples in a throwaway fixture, each
real-code assertion paired with a mutant that must flip the outcome
(first-source-wins `Catalog.add()`, a disabled `name_drift()`) -- 5/5 pass,
both mutants caught.

**Item 2 -- site audit.** `docs/testing/title_locations.py` and the Wall
sync check are already title_id-keyed (no change needed).
`docs/testing/compat_page.py`'s `build_playable_rows()` joined the ledger
to `compat_notes.tsv` by `("playable", title)` text; converted to
title_id, backfilling 20 blank `title_id` cells in `compat_notes.tsv`
first. Verified behavior-preserving against the live ledger (row-for-row
identical output; only the previously-blank `title_id` field changed).
`pm/prequeue.py` (host-only) is left name-keyed, deliberately: its `NAMES`
list is pre-filtered to rows matching the one human-typed query before any
match runs, is read-only diagnostic output, and exists specifically to find
pre-title_id runs that carry no title_id at all -- see NOTES.md for the
full reasoning. `status_html.py`'s `titles05`/`canon`/`resolve`/ledger-load
(the largest remaining name-keyed site) is **blocked**: the file is held by
lane.statusfix1016's fold, which has not landed on `origin/master` as of
this push (checked at session start and end, both times still at
`15a72e10dc`). `docs/lanes/titlekey1016/OUTBOX.md` carries the `NEED:` line
for it.

**Item 3 -- README Playable count follows the ledger, not STATUS.md.**
`host-tools/status_page.py`'s `main()` called `home_page.update(home_blobs
or None)` with no `playable=`; `home_page.update()` only re-derives
`playable` from the ledger when the caller omits it, and otherwise regexes
`Playable **N**` out of whatever `STATUS.md` blob it's handed -- which, on
a stale/crashed render (`home_blobs == {}`), is the EXISTING stale
home-branch blob. That is the exact 77-vs-87 mechanism. Fixed:
`home_page.update(home_blobs or None, playable=len(led))`, `led` being the
ledger `main()` already loads. Delivered as a full copy (host-only, outside
this worktree) under `docs/lanes/titlekey1016/host-tools/status_page.py`,
with install instructions in that directory's `INSTALL.md`.

**Item 4 -- hourly alarm.** New `docs/lanes/titlekey1016/host-tools/status_alarm.py`
(host-only, not yet wired into `hourly_report.sh` -- see `INSTALL.md` for
the one-section splice) compares the `home` branch's published
`STATUS.md` against the live ledger and prints an `ALARM:` line for a
stale `_updated` stamp (>2 h) or a Playable-count mismatch. Verified RED on
today's live data:

```
  ALARM: home:STATUS.md is 33.5 h stale (cap 2h, updated 2026-10-14 22:39 PDT)
  ALARM: home:STATUS.md says Playable 77, ledger has 87
```

`status_alarm_selftest.py` (4/4 pass) proves the quiet, stale-only,
mismatch-only and both-wrong cases against a throwaway bare git repo.

See `docs/lanes/titlekey1016/NOTES.md` for the full audit table, the 78-row
before/after drift list, the exact reproduction commands, and the mutant
proof writeup.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
