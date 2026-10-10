# lane fleetflush1010 (#433 umbrella -- fleet.py FAIL lines land mid-line)

## The bug, confirmed by hand before touching anything

`docs/testing/fleet.py` never configures its own stdout. Off a tty (a file, a
pipe) CPython block-buffers stdout at 8 KB while `sys.stderr` stays
line-buffered regardless of where it points. Every selftest `fleet_run` and
`session-start.sh`'s `fleet.py 2>&1 | grep '^FAIL'` merge both streams into
one file or pipe, so once enough stdout has been printed-but-not-yet-flushed,
a later stderr `FAIL:` write lands in the file before the buffered stdout
tail does -- splicing the FAIL into the middle of an inventory line, exactly
as the fold log on 2026-10-10 showed:

    "  #9401 -            selftest: an open issue no lane ownsFAIL: 1 open..."

Reproduced this by hand before writing anything: copied fleet.py/board_files.py/
gh_rest.py to a scratch dir, padded territory.toml with 300 dummy `[lane.ghostN]`
rows (~8001 bytes), ran it with stdout+stderr merged. With `sys.stdout`
untouched the merged file showed the identical splice ("...no lane
ownsFAIL: 1 open issue(s)..."); after adding `sys.stdout.reconfigure(line_buffering=True)`
at the top of `main()`, the same run produced one `FAIL:` at column 0 and
none mid-line. That is the whole fix -- fleet.py has no `print(..., end="")`
anywhere (checked with grep), so every print() is already a complete line and
line-buffering is sufficient; no caller needed to change.

## What I changed

- `docs/testing/fleet.py`: one line, `sys.stdout.reconfigure(line_buffering=True)`,
  first thing in `main()`. No FAIL text or condition touched.
- `docs/testing/jobs/selftest.d/96-fleet-flush.sh` (new): runs fleet.py from a
  scratch copy (same "run from a copy of itself" layout 55-localtime.sh's
  fixture uses) with 400 dummy ghost lanes as padding and one real gh issue
  (#9401, unclassified) as the probe. Asserts (a) the padding and the merged
  output both exceed 8 KB, so the test doesn't depend on timing luck, (b)
  every `FAIL:` in the output starts at column 0, (c) the probe's FAIL is
  still found by `^FAIL`. **Mutant**: commented out the `reconfigure` line
  and reran this fragment alone -- both (b) and (c) go red, reproducing the
  exact spliced line from the fold log. Restored the fix and reran; all four
  checks pass. (This mutant run is not in the branch; I ran it by hand and
  reverted, per the brief's instruction to report which checks fail rather
  than carry a broken state.)

## Item 3 (isolate 96-fleet-registry.sh from the live board): declined, live read kept

`96-fleet-registry.sh`'s `fleet_run` does not set `HAKUX_BOARD_REF`, so
`board_files._from_ref` resolves `origin/board` for real in this worktree
(confirmed: `git show origin/board:docs/testing/territory.toml` succeeds) --
territory.toml is ~38 KB and nv2a_issues.toml ~509 KB live, which is exactly
why this fixture started flaking as the board grew.

I'm leaving the live read in place rather than isolating it, for two reasons:

1. **The fix already removes the size dependency that made this dangerous.**
   Line-buffered stdout flushes every line as it's printed regardless of how
   much came before it, so a live board of any size can no longer corrupt the
   ordering. Verified directly: `SELFTEST_ONLY=96-fleet-registry` against the
   current live board (38 KB + 509 KB) now gives 28 passed, 0 failed -- up
   from the brief's reported 27 passed, 1 failed on the same board before the
   fix. The flake this item is about no longer exists.
2. **Isolating it for real is a bigger, separate change.** This fixture has
   two `==` sections and ~30 checks built on fleet.py's full output shape:
   RUNNING, REMOTE LANES, READY-NOT-FOLDED, RELEASED-AT-READY, FOLD-READY,
   BLOCKED, LANE-CLAIMED-WITH-NO-AGENT, RUNNING-WITH-NO-ROW, DISPATCHABLE,
   BLOCKER-NEVER-TESTED and NEITHER-BLOCKED, plus the `lane.sh`
   start/fleet-end/fleet-gc checks later in the same file that read
   `terr.get("lane")` indirectly through territory.toml's shape. Building a
   fixture territory.toml/nv2a_issues.toml that reproduces every one of those
   sections' preconditions (and doesn't collide with the synthetic lane/PR
   names the fixture already uses: `alive`, `ghostlane`, `draftlane`,
   `donelane`, `heldlane`, `stucklane`, `selftestlane`) is a redesign of the
   fixture, not an output-order fix, and this lane's territory is "output
   order only" (brief, "Rules"). `fleet.py` is on loan from
   [lane.toolsmith]; a structural rework of its own selftest fixture belongs
   there, not in a borrow.

Said here and in PR.md per the brief's fallback clause ("If isolation would
cost that, keep the live read and say why in PR.md").

## Verification run

- `env -u DISPATCH_DIR -u HAKUX_WORK -u SELFTEST_DIR -u SELFTEST_SHARD bash
  docs/testing/jobs/selftest.sh` (whole, no shard): **3227 passed, 0 failed,
  all 131 fragments.**
- `SELFTEST_SHARD=3/4` (the shard that failed in the fold): **992 passed, 0
  failed.** Fleet-flush/fleet-registry did not land in this particular shard
  3/4 draw (sharding groups by chain, not `i % n` -- see selftest.sh's own
  comment), but both ran clean in the whole-suite pass above and in isolated
  `SELFTEST_ONLY` runs.
- `SELFTEST_ONLY=96-fleet-flush` alone, with the fix: 4/4 ok. With the fix
  temporarily removed (mutant): 2/4 ok, 2 FAIL -- "every FAIL: ... starts at
  column 0" and "the one real issue's FAIL is still found by a ^FAIL grep".
  Fix restored before committing.

## Do not repeat

- Don't assume `96-fleet-registry.sh`'s `fleet_run` runs against fixture
  data -- it reads the real `origin/board` territory.toml/nv2a_issues.toml
  because `HAKUX_BOARD_REF` is unset there. Any check added to that fixture
  that asserts an exact count (not just "contains #N") is at the mercy of the
  live board's current size and content.
- Don't try to reproduce the splice by padding `nv2a_issues.toml`'s per-issue
  sections if you need a *controlled* size -- padding `territory.toml` with
  bare `[lane.ghostN]\nfiles = []` rows is cheaper and lands in a stdout
  section (`LANE CLAIMED WITH NO RUNNING AGENT`) that raises no FAIL of its
  own, so it pads without touching the thing under test.
