# Audit pass 1: PR #503, lane/affinitybacklog

#502: the arms job pins a new A/B pair to the handheld with less work queued
ahead of it. Diff read at head `ac1c8a3f07` against `origin/master`. Code
under review: `docs/testing/affinity.py`, `docs/testing/jobs/arms.sh`,
`docs/testing/jobs/selftest.d/99-affinity-backlog.sh`.

**Verdict: one HIGH, three LOW. Remediation needed.**

## Checked and sound

- The `before` bound. request.sh writes ids as `[1-]<epoch>-<who>-<pid>`,
  and arms.sh passes `[1-]<epoch>`. Release-priority ids (`1-...`) sort
  before plain epoch ids, and `z-*` sweep legs sort after both, so the queue
  is priced in the order the workers walk it. A request queued in the same
  second as the pair sorts after the bare prefix and is not counted. That
  errs light and does no harm.
- `_est` is byte-identical to request.sh's pilot-gate `est()`.
- The CHOOSE tie-break `(i - h) % n` sends a tie to the device rule 3 would
  have hashed to, so an empty queue gives the old answer.
- arms.sh: the pin is computed once and passed to both `request.sh` calls,
  so there is a single writer and no read-read race. A crash in
  `--choose` is swallowed (`2>/dev/null`) and leaves `pin` empty, which gives
  the old unpinned behaviour. `${pinarg[@]+...}` is safe under `set -u`. The
  request id is still read from the last word of stdout, because request.sh
  prints the pin on stderr.
- `_is_load_pin` keys on `requester` starting `arms-`, which is what
  `--who arms-<name>-base|fix` writes. Soaks (`title`) and off-pool labels
  are excluded, so a hand pin or a desktop pin stays absolute.
- Rule 2b ignores soaks: their key is `who:<requester>`, which never equals
  the basename of an `expect`.
- `decide(notes=False)` writes no split or blind notes while CHOOSE prices
  the queue.

## HIGH

### H1. A load pin outranks rule 2, so a hold on the pinned device splits the pair

`decide()` returns an explicit `device` as soon as that device is live, and
only then looks at running/results siblings. Under this PR every arms-job
pair carries an explicit `device`, so a sibling that actually ran elsewhere
no longer pins its partner once the pinned device comes back.

Scenario (holds are routine, and one is in force on the thor today):

1. arms.sh queues pair P and `--choose` returns `thor`. Both arms carry
   `device: thor`.
2. Before the thor claims either arm, the thor is held.
   `dispatcher.sh:1568` calls `lane_release`, `lanes/thor` goes away, and
   `_live(thor)` is false.
3. The nova walks the queue. For the base arm, the explicit thor is a load
   pin and not live, so it falls through. The 2b sibling is a load pin to a
   dead device and is skipped. There is no running or results sibling, and
   rule 3 has one pooled device, so the answer is `""`. **The nova claims
   the base arm.**
4. The hold lifts and the thor re-registers.
5. The thor walks the queue. For the fix arm, the explicit thor is live, so
   `decide` returns `thor` at the first line and never reaches the
   running-sibling check that would have said "nova". **The thor claims the
   fix arm.** The pair has split across two handhelds, the confound this
   module exists to prevent. The only trace is a split note from step 3;
   step 5 writes none.

Reproduced against the two affinity.py files. The script is not committed.
It builds a scratch dispatch dir with both lanes live, removes `lanes/thor`,
moves the base arm into running/ with owner `nova`, and restores
`lanes/thor`:

```
PR head, both arms device=thor:
  hold: base -> ''
  after hold, base running on nova: fix -> 'thor'     <- split
origin/master, both arms unpinned (what arms.sh queued before):
  hold: base -> ''
  after hold, base running on nova: fix -> 'nova'     <- kept together
```

The same thing happens after any temporary loss of `lanes/thor`: a worker
restart, the 2026-09-19 lanes/ wipe, or an adb reconnect. It happens
whenever the pinned device returns between the two claims, and an arm runs
for tens of minutes. The selftest's "load pin to a dead device" case keeps
the thor dead throughout, so it cannot see this.

**Remedy direction.** A load pin must rank below rule 2. When the explicit
device is a load pin, first follow a sibling that is running or has run on a
live device, and use the load pin only when no sibling has landed. A hand
pin (`_is_load_pin` false) stays at rule 1. Add a selftest step that
reproduces the sequence above, fix arm must answer `nova`, and add a mutant
that answers `thor`.

## LOW

### L1. fleet.py still treats every `device` as absolute

`fleet.py` `queue_stall()` sets `claimers = {pin} & live` for any pinned
request (the "affinity.py rule 1" comment). With this PR, an `arms-*` request
pinned to a pooled device that has died, without a hold, can be claimed by
the other handheld. fleet.py reports it as stalled ("pinned to thor, which no
live worker serves") once the live handheld has been busy longer than
`QUEUE_SETTLE_S`, even though the busy handheld will take it next. The
blast radius is small: it fires only alongside a real outage, and the
wording is what misleads. This is a second copy of the rule that the diff
did not update. Mirror `_is_load_pin` there, or import it.

### L2. Deploy skew between arms.sh and the dispatcher snapshot

arms.sh runs `$T/affinity.py` from the repo checkout, while the workers run
the snapshot in `$DISPATCH_DIR/bin`. Between the fold and the dispatcher's
next re-snapshot, the new arms.sh writes load pins that the old affinity.py
treats as absolute. During that window, a hold or outage on the pinned
device stalls the pair instead of letting it fall through. A hold is bounded
at about 30 min, and an outage lasts until the update window. Say in the PR
that the dispatcher update must land with the fold, or have arms.sh write no
pin while `$DISPATCH_DIR/bin/affinity.py` lacks `--choose`.

### L3. `backlog()` is quadratic in the queue

Each queued request ahead of the pair calls `decide()`, and each call lists
and loads every `queue/*.req` for rule 2b and every `running/*.req`. That is
O(n²) JSON loads per pair per arms tick. Today it is harmless, because `z-*`
legs sort after the bound and are skipped, but a large epoch-tier batch
(titleplay-scale, hundreds) would make each tick slow. Build the queued
`key -> device` map once, as `_results_index` already does for results.
