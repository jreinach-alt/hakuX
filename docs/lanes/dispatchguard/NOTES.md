# lane.dispatchguard

## The defect

`selftest.d/50-arms-requeue.sh` and `51-dispatch-hardening.sh` empty
`$DISPATCH_DIR/queue`, `$DISPATCH_DIR/results` and `$HAKUX_WORK/arms/*`
(50: `rm -f queue/*.req` and `clear_markers`; 51: `mv results/*` away and
`rm -rf results/* queue/*.req` twice in part E2), and they run `arms.sh`,
which queues requests into `$DISPATCH_DIR`. They were safe only because
`selftest.sh` exports `DISPATCH_DIR=$T/work/dispatch` and `HAKUX_WORK=$T/work`
under a fresh `mktemp -d` before sourcing any fragment. A one-off script that
sources a fragment directly inherits the caller's exports; in a lane session
those are the live `/home/justin/hakux-work` and its `dispatch/`.

On 2026-09-29 16:23-16:29 PDT the live queue and results were emptied twice,
leaving exactly what line 298 of 51 leaves (dotfiles in results/ and the
`withdrawn/` subdir survive). The lead is a scratch harness in another lane's
worktree that sourced `selftest.d/$FRAGS` with `T` set and `DISPATCH_DIR`
not. This lane did not try to confirm that, nor recover anything; it closes
the gap for any such script.

## The fix

One guard block, identical in both fragments, before any code. It refuses --
message on stderr, `fail` incremented, `return 1` (or `exit 1` when the file
is executed rather than sourced), nothing removed -- unless all of:

1. `DISPATCH_DIR` and `HAKUX_WORK` are exactly `$T/work/dispatch` and
   `$T/work` (realpaths): the layout `selftest.sh` builds, and nothing else;
2. `$T` is strictly below a tmp root (`${TMPDIR:-/tmp}` or `/tmp`) -- the
   positive check, so a production dispatch dir under any other name fails;
3. none of `T`, `HAKUX_WORK`, `DISPATCH_DIR` is inside, equal to, or an
   ancestor of `$HOME/hakux-work`.

51 asks again before part E (the destructive block, 180 lines later), in
case a later edit moves `DISPATCH_DIR` in the main shell. Nothing in the
fragments does today: the two `export DISPATCH_DIR=` lines in 51 are in
`drive.sh` and a `$( ( ... ) )` subshell.

A shared `selftest.d/_dispatch_guard.sh` was not possible: `selftest.sh`
refuses any name under `selftest.d/` that is not `NN-*.sh`, and a helper
elsewhere is outside this lane's files. Instead part J diffs the two copies.

## Proof (51, part J)

Each case sources a fragment in a subshell with a fake `HOME` whose
`hakux-work/` holds a canary request, result and judged marker:

| case | expected | result |
|---|---|---|
| selftest.sh's own tree | guard passes | ok |
| 50, T=mktemp, DISPATCH_DIR=live (the incident) | refused, rc=1, canaries intact | ok |
| 51, same | refused, rc=1, canaries intact | ok |
| scratch-shaped tree at `/dg-not-a-tmp/x` | refused: not below a tmp root | ok |
| scratch-shaped tree below /tmp but = `$HOME/hakux-work` | refused: inside live | ok |
| 50 executed with `bash`, not sourced | exit 1, canaries intact | ok |
| the two guard blocks | byte-identical | ok |
| MUTANT: 50 with the guard deleted, incident shape | canary request removed | ok (J can go red) |

`SELFTEST_ONLY="10-arms-list 20-arms-queue 30-arms-error 40-arms-refusal
50-arms-requeue 51-dispatch-hardening" bash docs/testing/jobs/selftest.sh`:
97 passed, 0 failed. Every pre-existing 50 and 51 leg passes under the guard.

## For the next lane

- `dhmut` must not be used to mutate a file under `jobs/selftest.d/`: its
  tree symlinks `jobs/*` entries, including the `selftest.d` directory, so its
  `rm -f "$dir/$rel"` would delete the real fragment. J builds its mutant with
  a plain `sed` into `$DG`.
- Other fragments (10..40, 55+, ...) also write `$DISPATCH_DIR`. They were out
  of this brief's files; 50 and 51 are the ones with `rm -rf results/*`. A
  fragment that empties the dispatch dir should copy this guard block.
- 51 prints a negative "took" time: it sets `SECONDS=0` itself (lines ~207,
  ~403). Pre-existing, cosmetic, not touched.
