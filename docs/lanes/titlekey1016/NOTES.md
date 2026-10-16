# titlekey1016: one display name per title_id (#433)

Lane brief: one display name per title_id, defined in one place; nothing
keyed by a name. Triggered by the 32 h status-page crash (10-14 23:42 to
10-16) on `KeyError: 'Crimson Skies: High Road to Revenge'` and the
77-vs-87 Playable count mismatch between GitHub's landing page and the
ledger. lane.statusfix1016 patched the one crashing lookup; this lane is
the systemic fix the owner asked for (verbatim, 10-16 ~07:4x: "Inconsistent
naming has been a recurring footgun for this project... Yes, dispatch
this.").

## Status as this session writes NOTES.md

Item 1 (single name source) and the `title_registry.py check` drift
detector (feeds item 4) are DONE and verified. `status_html.py` is still
held by lane.statusfix1016 (its fold has not landed on origin/master as of
this check -- see "Blocked" below), so the `titles05`/`canon`/`resolve`
rewrite in item 2 has not started. Items 3 and 4's host-tools deliverables
are in progress.

## Item 1: the one name source

`docs/testing/title_registry.py`'s `Catalog` is the shared identity
resolver (`build_catalog()`), used by `build()` and (indirectly) by every
other reader. It had two bugs, not one:

1. **`Catalog.add()`'s override rule was "listing wins, else first write
   wins."** Only a `listing-*` source (a device file listing, parsed from
   a filename with underscores for spaces) could override an existing
   name; every other source -- including the Playable ledger and
   targets.toml, the two sources a human actually edits -- only set a name
   if nothing had claimed it yet. Whichever of those ran first in
   `build_catalog()`'s fixed read order won, regardless of which one a
   human curates.
2. **`build()` had a SECOND, independent "ledger wins" rule** on top of
   that (`name = (ledger.get(tid) or {}).get("title") or cat.names.get(tid)
   or ""`), live only inside `build()`. Any other reader that called
   `build_catalog()` directly (`status_html._title_catalog`, this lane's
   own `check` CLI) got the FIRST rule's answer, not the second's -- two
   call paths, two different winners, from the same function.
3. **`build_catalog()` never loaded the ledger at all.** The ledger was
   folded into the catalog only inside `build()`'s own loop, as a
   `cat.add(tid, r.get("title"), "playable-accepted.tsv")` call. A caller
   that built a catalog WITHOUT also running `build()`'s ledger loop (the
   `check` CLI, before this lane; `status_html._title_catalog`'s separate
   ledger overlay) got a catalog that had never seen the ledger's spelling
   at all.

Fix: one explicit priority ranking, `_name_priority(where)` --
`playable-accepted.tsv` (0) > `targets.toml` (1) > a device listing (2) >
everything else (3, e.g. the console inventory's raw XBE title string,
`owner-library-done.tsv`'s shorthand, an xemu-compat alias) -- used
uniformly inside `Catalog.add()`. Lower always overrides higher; equal or
higher never does. `build_catalog()` now loads the ledger itself, last (so
`cat.resolve()` sees every alias before the one ledger row with no
title_id column needs to resolve by name), so its result IS the final
name -- no second "ledger wins" rule anywhere else. `build()`'s own
per-row name assignment collapsed from
`(ledger.get(tid) or {}).get("title") or cat.names.get(tid) or ""` to
just `cat.names.get(tid) or ""`.

### The drift check

`title_registry.py check` (every invocation, not just `--pages`) now runs
`name_drift(p, cat)`: for every title_id either of the two curated sources
(ledger, targets.toml) names, compare that source's spelling against
`cat.names[tid]` (the one name every reader is supposed to display) and
against the OTHER curated source. Any disagreement prints
`NAME DRIFT <tid>: source=name; source=name...` and fails the check (exit
3). This catches both kinds of drift: a curated source whose text the
catalog doesn't resolve to (the priority bug), and two curated sources
that silently disagree with each other even after resolution (nothing
upstream of this lane checked that).

Why compare against the resolved name, not just ledger vs targets.toml:
verified live that for the crash's own example (Crimson Skies,
`4D530021`) the ledger and targets.toml already AGREE with each other
("Crimson Skies: High Road to Revenge" in both) -- a ledger-vs-targets.toml
check alone would stay green on today's buggy master and miss the exact
bug this lane exists to catch. Comparing each curated source against the
catalog's resolved name is what makes the check red pre-fix (the catalog
resolved to an alias, "Crimson Skies", despite both curated sources
agreeing on the full title) and green post-fix.

### Red before, green after -- reproduced

The brief cites "54 of 106 registry titles" mismatched, measured ~07:4x. A
live rerun finds a different count: the registry (`pm/title-registry.tsv`,
967 rows today, not 106 -- the row count has grown since titledb1014
folded) and the ledger/targets.toml sources have moved. Three
methodologies, for the record:

| comparison | count |
|---|---|
| ledger text vs pre-fix `Catalog.names` (brief's own comparison) | 56 |
| targets.toml text vs pre-fix `Catalog.names` | 20 (overlaps with the above) |
| `name_drift()` run against the ORIGINAL (pre-fix) code + original targets.toml | **78** |

The 78-count is the one that matters: it is the actual input to the new
check, run against the actual pre-fix code, so it is what "red on today's
master" means operationally. Examples it finds (title_id, pre-fix
resolved name, curated source(s)):

| title_id | pre-fix catalog (resolved) | ledger | targets.toml |
|---|---|---|---|
| 4D530021 | Crimson Skies | Crimson Skies: High Road to Revenge | Crimson Skies: High Road to Revenge |
| 4D530051 | Conker: Live and Reloaded | -- | Conker: Live & Reloaded |
| 4D530013 | Blinx The Time Sweeper | -- | Blinx: The Time Sweeper |
| 54430003 | NINJA GAIDEN | -- | Ninja Gaiden |
| 4D530004 | Halo | Halo: Combat Evolved | Halo: Combat Evolved |
| 4D530046 | PhantomDust | -- | Phantom Dust |
| 41560001 | Tony Hawk s Pro Skater 2x | Tony Hawk's Pro Skater 2x | Tony Hawk's Pro Skater 2x |

(full 78-row list reproduced by running, from this branch:
`python3 /tmp/titlekey_before_repro.py` -- see "Reproducing the before/after"
below; not committed, since it is a scratch driver over a git-HEAD copy of
the pre-fix file, not part of the fix itself.)

After the `Catalog`/`build_catalog()` fix, rerunning `check` against the
SAME pre-fix targets.toml left exactly 4 real disagreements -- not bugs in
the priority logic, but two curated sources that actually disagree with
each other and need a human pick:

| title_id | ledger (wins) | targets.toml (was) |
|---|---|---|
| 49470018 | Jet Set Radio Future | JSRF: Jet Set Radio Future |
| 53410002 | Guilty Gear XX #Reload | Guilty Gear XX #Reload: The Midnight Carnival |
| 534E0007 | KOF: Maximum Impact – Maniax (en dash) | KOF: Maximum Impact - Maniax (hyphen) |
| 545400B0 | Family Guy Video Game | Family Guy: Video Game! |

Verified these are genuinely what's shown publicly today (not a case where
targets.toml's fuller title is the one the Wall/README/COMPATIBILITY.md
actually display): `docs/COMPATIBILITY.md`'s Playable table today reads
"Guilty Gear XX #Reload", "Jet Set Radio Future", and "KOF: Maximum
Impact – Maniax" (en dash) verbatim -- the ledger's own spelling, exactly
as `build()`'s old (buggy) `(ledger.get(tid) or {}).get("title") or ...`
rule already produced when the ledger had a row for that build run. Per
the owner's decision ("the registry spelling wins -- it is what the Wall,
README and COMPATIBILITY.md show today"), fixed `targets.toml`'s `name =`
field for these 4 to match the ledger:
`docs/testing/titles/targets.toml` (`49470018`, `53410002`, `534E0007`,
`545400B0`).

`python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --no-forge`
after both fixes: zero `NAME DRIFT` lines (only the unrelated "STALE
registry is N min old" freshness line, which just means the on-disk
`pm/title-registry.tsv` hasn't been rebuilt by the periodic job since this
edit -- confirmed the generator itself produces 87 PLAYABLE rows with no
drift via `title_registry.py build --out /tmp/title-registry-test.tsv`,
matching the ledger's actual 87).

### Reproducing the before/after

```
# before (pre-fix code + pre-fix targets.toml, both git HEAD):
git show HEAD:docs/testing/title_registry.py > /tmp/before/title_registry.py
git show HEAD:docs/testing/titles/targets.toml > /tmp/before/targets.toml
# append curated_names()/name_drift()/_name_priority (new in this lane) to
# the pre-fix file, since the check itself didn't exist before -- the
# question is what it WOULD have said -- then run build_catalog()+name_drift()
# against /tmp/before/targets.toml as TITLE_TARGETS. 78 drifting title_ids.

# after (this branch):
python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --no-forge
# zero NAME DRIFT lines.
```

## Item 2: site-by-site audit of name-keyed reads

| site | before | now / verdict |
|---|---|---|
| `title_registry.py` `Catalog.add()`/`build_catalog()`/`build()` | see above | fixed (this lane) |
| `docs/testing/jobs/status_html.py` `titles05`/`canon`/`resolve`/ledger load | builds `names`, `where`, `tid_of` dicts keyed by display name; `canon()` has a name-matching fallback | **BLOCKED** -- file is held by lane.statusfix1016 until its fold lands on `origin/master` (checked, not yet landed -- see "Blocked" below). Per the brief's explicit order-of-work, not touched this session. |
| `docs/testing/title_locations.py` | -- | audited below |
| `pm/prequeue.py` (host-only) | -- | audited below: left name-keyed, scoped and bounded, documented |
| `host-tools/home_page.py` / `status_page.py` (host-only) | README Playable count re-derived from STATUS.md text when not passed explicitly | fixed (item 3, below) |
| `host-tools/hourly_report.sh` (host-only) | no public-status alarm | new alarm added (item 4, below) |
| `host-tools/status_md.py` (host-only) | generic HTML->Markdown, no name-keyed logic found | no change needed |
| Wall sync check (`pm/.wall-synced`) | a count, not a name-keyed structure (`page_playable_counts()` already reads it as a row count) | no change needed |
| README/COMPATIBILITY.md generation | -- | see item 3 below for the Playable count; the per-row title text itself already comes from the registry (title_id keyed) via `compat_page.py` |
| `docs/testing/compat_page.py` `notes_by_title` | keyed by `(section, title)` tuple, not title_id | flagged below; not converted this session -- said why |

### `title_locations.py`

Grepped for `["name"]`, `.names`, `nkey(`, `resolve(`, `where[` -- no
matches. Already title_id-keyed throughout (it's the output of
locations1014, the lane immediately before this one). No change needed.

### `compat_page.py`

`build_playable_rows()` joined the ledger to `compat_notes.tsv`'s
"playable" section by `("playable", title)` text, even though
`compat_notes.tsv` already HAS a `title_id` column (`NOTES_COLS`) -- just
unpopulated for 20 of its 57 playable rows. Converted the join to title_id:
`notes_by_id = {r["title_id"]: r ...}`, `build_playable_rows(ledger_rows,
notes_by_id, registry_by_title)`. Backfilled the 20 blank `title_id` cells
in `docs/testing/compat_notes.tsv` first (`playable` section only), looked
up against the ledger (and, for the one ledger row recorded before
title_id tracking -- NBA 2K3 -- against the already-built registry, which
is title_id-keyed throughout). `build_playable_rows()` itself now also
handles that one row's own empty ledger `title_id` the same way, as a
one-time bridge, not a second name-keyed join: `registry_by_title` is
consulted ONLY when `lr["title_id"]` is empty.

Verified behavior-preserving: ran both the pre-fix and this-lane's
`build_playable_rows()` against the live ledger filtered down to just the
57 titles `compat_notes.tsv` already covers (`/tmp/compat_playable_compare.py`,
not committed -- a scratch comparison script). Row-for-row identical
output, with the sole difference being the now-populated `title_id` field
(previously blank for 20 of the 57 rows) -- a correctness improvement,
not a behavior change in which rows are selected or how they render.

**Not regenerating `docs/COMPATIBILITY.md`/`docs/compatibility.csv` in
this PR.** Confirmed `compat_page.py --check` against the LIVE ledger (87
Playable rows) fails identically before and after this lane's change: 29
playable and 4 below_bar titles have ledger/registry rows with no
`compat_notes.tsv` entry at all (not a missing title_id -- a missing ROW,
pre-existing, unrelated to this lane). Per `pm/lanelocal-log.md` (10-13
~11:29, lane.compatrefresh1013), backfilling those rows (device, fps,
region, a human frame-review note per title) is its own recurring,
hand-reviewed "compatrefresh" lane -- a data-entry task needing device
evidence, not a code fix, and far outside this lane's scope. The page is
currently frozen at the 57 Playable titles from the last compatrefresh;
regenerating it now would still raise `SystemExit` on the same 33 missing
rows this lane did not introduce.

Ran the existing `compat_page_selftest.py` (19 tests) against the
converted join: one failure, `CheckFailsOnStalePage` -- its fixture gave
the ledger row `title_id = "-"` (none) with an empty registry, the one
case genuinely unresolvable by title_id (every other fixture in this file
already carries a real title_id, e.g. `registry_row(title_id="4D57001A",
...)`). That test is about stale-file detection, not name-matching, so
fixed the fixture to carry a title_id like its siblings
(`AAAA0099`) rather than special-casing a textual fallback back into
`compat_page.py`. All 19 pass now.

## Blocked

Checked `git -C /home/justin/hakuX log --oneline origin/master -5`: still
at `15a72e10dc` (titledb1014's fold), the same sha this branch started
from. lane.statusfix1016's fold has NOT landed. Per the brief, not editing
`status_html.py` this session; will recheck before finishing and, if still
unfolded, this is a `NEED:` line in OUTBOX.md rather than a guess at
editing a file another lane holds.
