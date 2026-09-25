# Audit pass 2 — PR #206, `claude/dispatch-script-deps`

*dispatcher: hash every file the snapshot ships, or an edit never reaches a
worker*

- **Auditor:** `job.cloud`, 2026-09-24, pass 2 (scenario verification)
- **Head at audit:** `0c6838537c`, CI `build`/`build`/`selftest` all SUCCESS,
  `MERGEABLE`/`CLEAN`
- **Remediation read:** `0e9409ab41` (fleet.py `queue_stall` rewrite, 98),
  `bf240e7f32` (dispatcher.sh lists, 97 closure check), `0c6838537c` (NOTES,
  mutation harness)
- **Verdict:** clean. Every pass-1 scenario was checked and none can still
  occur. Three new LOWs, none blocking → `fold-ready`

---

## Scenario by scenario

### H1 — a request waiting its turn behind FIFO work was reported as stalled

**Closed.** The rule is no longer "a result landed after I was queued". A
request is reported only when **every** live claimer has walked past it:
either it is running something that sorts after R and was claimed after R
was written, after the last change to R's pin inputs, or it has done nothing
for a settle period since R was written. The pass-1 remedy ("something queued
after me completed") would also have failed: rule 2 lets the other handheld
serve later work while a pair waits for its own device. The rewrite handles
that case and the pass-1 remedy does not.

Checked by running the tests, not by reading the table:

- `runfrag.sh … 98-fleet-queue-stall.sh`: 25/25 queue-stall checks pass. The
  `H1:` fixture is the one pass 1 asked for: queue depth 2, a burst of two
  pairs pinned to nova by rule 2, pair 1's base completed after the burst,
  pair 2 at 150 min (past the old threshold), and thor serving later soaks.
  The result is quiet. The `2026-09-20` fixture checks the other direction:
  nova claimed later work while thor and desktop sat idle, and the result is
  FAIL.
- `mutate98.py`: all 11 mutants of `fleet.py` turn exactly their own checks
  red, as tabled in NOTES. `order` (dropping `x > name`) turns the H1 fixture
  red, so the fixture does real work.
- I also tried scenarios that no fixture covers, looking for a way back to a
  false FAIL. None fired:
  - A running sibling that sorts after R because two requests were queued in
    the same second with pids of different lengths (`…-4999` < `…-500`). The
    sibling's own claim is in `sib[key]`, so `claimed > changed` is false.
  - A rule-3 hash pin moving when the pool changes. `lanes/` and `hold/`
    directory mtimes are in `epoch`.
  - Lane-file rewrites on every tick would pin `epoch` to now and silence
    the check. `lane_claim` writes only when the file is missing or holds
    another pid (`dispatcher.sh:520-523`), so this does not happen.
  - `.lastbrief` stamps churning `lanes/` mtime. That writer is retired
    (`check_coverage.py:755`).

### M1 — `all_held` had no liveness test and the wrong denominator

**Closed.** Liveness now comes from `affinity.serving()` (the scheduler's own
`kill -0`), not from a second copy. The hold branch is keyed on holds:
`pooled_unheld` empty plus any handheld held gives `on_hold`, printed on
stdout and never a FAIL. An explicit pin to a held label is also on-hold.
NOTES adds a second reason the old quiet branch could never be reached: a
held worker `lane_release`s its file (`dispatcher.sh:1266`), so `lanes/` held
only `desktop`.

- 98 `every handheld held, desktop still serving -> waiting on the hold`
  passes. This is pass 1's exact case (`{desktop,nova,thor}` with
  `{nova,thor}` held).
- 98 `a dead lane file does not keep the held branch from being taken`
  passes. The `pooled` mutant (lane files without `kill -0`) turns it red,
  and the `holdall` mutant turns 4 checks red, including the stdout/no-FAIL
  pair.

### M2 — `sweep_queue.sh` ran from `$SNAP` but was in neither list

**Closed.** `sweep_queue.sh` and `make_isolation_discs.py` (which it runs) are
now in both `SCRIPT_DEPS` and `snapshot_scripts` (`dispatcher.sh:90-91`,
`:118`). 97 now checks the invariant the deploy needs: the snapshot must
contain every sibling that a shipped script runs, in four forms. I ran 97
against two mutants of my own, in scratch copies of `docs/testing`:

| mutant | 97 |
|---|---|
| `sweep_queue.sh` removed from **both** lists (pass 1's state: both lists agree) | 1 red: "a shipped script runs a sibling the snapshot does not carry" |
| `soak_title.sh` gains `bash "$HERE/unshipped_probe.sh"`; the file exists in the tree but is shipped by neither list | 1 red: same check |

The unmutated tree passes 97 at 21/21, including the four built-in
per-form probes.

### L1–L5

- **L1**: removed along with the mtime code. No claim about result-directory
  names remains.
- **L2**: the call now sits after the `if unclaimed:` block
  (`fleet.py:983`).
- **L3**: the FAIL text has no `dispatcher.sh:<n>` reference. It names the
  snapshot `diff -q` and the evidence instead.
- **L4**: 98 runs board.sh's own `2>&1 >/dev/null | grep '^FAIL'` pipeline.
  The `nocall` mutant turns it red, along with the rc and stdout checks.
- **L5**: the PR body now has `Lane/Base/Files/Prediction/Needs device`, and
  `Files:` lists all four touched harness files plus the lane directory.

---

## New findings (LOW only)

- **N1: an off-pool lane can delay a stall while it is the only live
  lane.** If both handheld workers die without a hold, `live = {desktop}`
  and desktop becomes the only claimer of a handheld request. Suppose
  desktop is busy with a desktop-pinned run that sorts before R. That is a
  break, not evidence, so the FAIL waits until that run ends. It is a false
  negative with a bounded delay, and the FAIL text then reads "desktop idle",
  which is true but does not point at the dead handhelds. Consider treating
  OFFPOOL lanes as non-claimers for requests with no pin.
- **N2: any mtime bump on `lanes/` or `hold/` voids busy-claimer
  evidence.** Placing or lifting an unrelated hold, or a worker restarting,
  voids busy-claimer evidence until each claimer's next claim. This can only
  delay a FAIL, never cause a false one. That is the right direction, and
  NOTES states it.
- **N3: the dormant sweep-preemption defect is recorded but has no owner.**
  NOTES item 1: `sweep_queue.sh` still dies on `${VAR:?}` before `pause`.
  It is recorded in NOTES "for its own lane", but I found no board row or
  brief that carries it. Shipping the file (M2) is correct regardless.

## What remains

Nothing blocks the fold. N1–N3 are for a later harness lane if anyone wants
them.
