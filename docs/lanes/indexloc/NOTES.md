# lane.indexloc: a line shift is not an index change

## The defect

`nv2a_index.json` records every site as `file:LINE`, and `nv2a_index.py check`
compared `symbols` and `sites` byte for byte. So any edit that moved a line in a
scanned file failed CI until the lane committed a regenerated index, and any two
open PRs touching the same source file conflicted in the index even when their
code never overlapped. GitHub runs no CI on a conflicting PR, and fold.sh waits
on CI, so on 2026-09-26 four PRs (#268, #321, #330, #332) froze and 31
dispatchable issues sat behind them.

## The change

`check` now compares `symbols` and `sites` by anchor instead of by bytes.

- **Site anchor:** (hardware symbol, file, role, the matched line's text with
  whitespace collapsed). Sites are compared as a multiset per symbol, so
  losing one of two identical lines is caught, and reordering within a file
  is drift.
- **Symbol anchor:** the definition with `defined_at`'s line number dropped.

The anchor is the `text` field the index already stores, so
**`nv2a_index.json` does not change**. The brief listed that file, but five
open PRs claim it, and a schema change would have been one more rewrite for
all of them.

`check` outcomes:

| What changed | `check` | `check --exact` |
|---|---|---|
| Nothing | pass | pass |
| Only line numbers, all anchors match | **pass, INFO line** | fail (the old message) |
| Site added, removed, moved to another file, anchor text gone, symbol added/removed/redefined | fail, each named | fail |
| Suites, tracker, empty suite half, provenance-pinned tests tree | unchanged | unchanged |

`build` is untouched and still writes current line numbers. The CI workflow is
untouched: it runs plain `check`, which is now the tolerant one. `preflight.sh`
also runs plain `check`, so lanes are no longer told to regenerate for drift.

## Needs lane.foldflow: `check --exact` in fold.sh

`regen_index` in `docs/testing/jobs/fold.sh:218` rebuilds only when `check`
fails. With this change, drift passes, so **master's line numbers stop being
refreshed** until the next fold that really adds or removes a site. `query`,
`blast` and `scan_gaps`' ±8-line neighbourhood read those numbers. The fix is
one token, `check --exact`, on the first `check` at line 218 only. The
post-build check at :222 is fine either way.

**Order matters.** Master's `nv2a_index.py` must have `--exact` before
fold.sh passes it. Otherwise argparse rejects the flag, `check` fails, `build`
runs, the second `check` fails too, and every fold hands back. So this PR folds
first, then foldflow adds the token. The request went to #356 as a comment.

Until that lands, master's line numbers drift: that is a soft staleness in
query output, and no PR is blocked by it. I chose this default on purpose. The
other way round (strict `check`, tolerant under a flag) would have needed
preflight.sh, which belongs to the instruments lane. Until that change landed,
lanes would keep committing rewrites, and the jam would persist.

**Resolved (2026-09-25):** lane.foldflow's #356 makes `regen_index` pass
`--exact` only when the merged tree's `nv2a_index.py check --help` lists it,
so the order of #360 and #356 no longer matters. This branch's `check --help`
lists `--exact`.

## Proof

- **Fixtures**, `docs/testing/jobs/selftest.d/75-nv2a-index-drift.sh`, 20
  legs. They run the real `cmd_check` over a synthetic emulator tree, tests
  tree and tracker:
  - pass: a pure shift, a shift in nv2a_regs.h, functions reordered in a file
  - fail, with the site named: added, removed, one of two identical lines
    removed, changed text, renamed to another symbol, moved to another file,
    a changed symbol value
  - line drift does not mask a suite change
  - `--exact` fails a pure shift
- **Falsifier:** the same fragment run against master's `nv2a_index.py`
  (keyword dropped so it loads) fails exactly the 8 drift and naming legs and
  passes the 12 strictness legs.
- **Live demonstration**, `demo.sh <tests> <pbkit>`, against origin/master
  d3e3e0bf7c. It builds two plumbing commits off master, with no worktree and
  no branch. A inserts 4 lines after psh.c:40, B inserts 6 lines after
  psh.c:4080.
  - Both pass `check` without touching the index: INFO lines for 132 and 6
    symbols.
  - `git merge-tree A B` is clean.
  - Contrast, under the old regime: A's regenerated index rewrites 228 lines,
    B's 9, and `merge-tree` of the two conflicts in `nv2a_index.json`.
- `check` and `check --exact` both pass on master 8552e1ff89 and on this
  branch after merging d3e3e0bf7c.
- `preflight.sh` passes.

## Attempt 2 (2026-09-25): why attempt 1 did not finish, and the re-run

Attempt 1 committed this NOTES file but never pushed it, and never marked the
PR ready. It ended waiting on the full `jobs/selftest.sh`, which it had
started as a session background task. That task died with the session, and
its log stopped partway through the arms fragments. Nothing outside the
session was ever going to resume it.

Re-run in the foreground after merging origin/master 24208f15cb (58 commits,
none touching `nv2a_index.py`, `fold.sh` or the workflow):

- `check` and `check --exact`, with `--tests`/`--support` at the pinned
  provenance (tests 6743b6ab, pbkit e91d509e): both pass, 951 symbols,
  2869 sites, 104 suites.
- Fragment 75 alone under the selftest preamble: 20/20.
- `demo.sh` against 24208f15cb: A (+4 after psh.c:40) and B (+6 after
  psh.c:4080) both pass with INFO for 132 and 6 symbols. `merge-tree` is
  clean. The old regime rewrites 228 and 9 lines, and conflicts in
  `nv2a_index.json`.
- `preflight.sh --allow-tracker` passes.
- I did not complete the full `jobs/selftest.sh` locally. It takes more than
  10 minutes: the arms fragments alone ran past 590 s. CI's `selftest` job
  runs it; it passed on the previous head and is the gate of record.

Next lane: do not run the full selftest as a session background task. Run
the fragment you touched under the preamble (source it with `ok`, `bad`,
`check`, `T`, `HERE` and `REPO` defined), and leave the whole run to CI.

## Do not repeat

- Do not add an anchor field to the JSON for this. `text` already is one, and
  a schema change rewrites every entry of a file five PRs hold.
- Do not make `check` exit 0 on drift inside fold.sh's regeneration step
  without `--exact`, or master's line numbers stop being refreshed.
- `gaps` and `unread` were never compared by `check`, and still are not.
  Adding them would re-create the churn for gap `symbols` lists, which depend
  on ±8-line proximity.
