# lane.armpin -- the A/B pair that split across two handhelds

Brief: on 2026-09-19 `affinity.py`'s pinning was inert because `serving()`
returned `[]`, because `$D/lanes/` held no worker pid files. #89's pair ran
base on the `thor` and fix on the `nova`. Three tasks, in order: (1) find what
emptied `$D/lanes/`, (2) make an empty `serving()` visible, (3) give
`$D/splits/` a consumer.

## 1. What emptied `$D/lanes/` -- the brief's hypothesis is REFUTED

The brief names the hold path as the suspect:

> it `rm -f`s unconditionally while held and restores only under
> `[ "$held_logged" = 1 ]`, which is per-process. A worker that starts while a
> hold is in force never sets `held_logged`, so it never restores.

**The second sentence is false, and reading the code is enough to show it.**
`dispatcher.sh` before this branch, lines 1154-1165:

```sh
if [ -e "$D/hold/$DEVICE_LABEL" ]; then
    [ "$held_logged" = 1 ] || log "HELD by ..."
    held_logged=1                      # <-- set in the SAME iteration
    rm -f "$D/lanes/$DEVICE_LABEL"
    sleep 30; continue
fi
if [ "$held_logged" = 1 ]; then
    log "hold released; serving again"
    held_logged=0
    printf '%s' "$$" > "$D/lanes/$DEVICE_LABEL"
fi
```

`held_logged=1` is assigned unconditionally on the same line-run as the `rm`,
every iteration the hold is seen. A worker that starts under a hold therefore
DOES set it on its first tick and DOES restore the file when the hold lifts.
The hold path self-heals within one process. It is not the remover, and the
brief's own timeline already disagreed with it: holds lifted 11:08, workers
started 16:34, `$D/lanes/` changed 16:44.

Two further hypotheses tested and killed:

- **EXIT-trap leakage into subshells.** `trap 'rm -f ...' EXIT` would be
  catastrophic if bash ran it on every `$(...)`, because the worker loop does
  `now_hash="$(src_hash)"` every tick. Tested on this host's bash: a command
  substitution and a `( ... )` subshell both leave the file alone. Not it.
- **A third remover somewhere else in the tree.** `grep -rn 'lanes'` over every
  `*.sh`/`*.py`/`*.md` in the repo, filtered for
  `rm|rmdir|-delete|unlink|prune|clean|shutil`, yields exactly three sites, all
  in `dispatcher.sh`: the `mkdir -p`, the EXIT trap, and the hold path.
  `check_coverage.py:572` WRITES `lanes/<lane>.lastbrief` -- that is where the
  two stray 09-14 files came from -- but removes nothing. No timer, unit or job
  sweeps `$D`.

**What I could not do, stated plainly:** this lane's sandbox refuses to read
outside its worktree, so `/home/justin/hakux-work/dispatch/lanes/`, `hold/` and
the dispatcher log were unreachable. **I could not name the process that fired
at 16:44, and this branch does not claim to have.** The question is still open.
Whoever picks it up: read the three refutations above first rather than
re-deriving them, then from a session that can reach the host run

```
ls -la --time-style=full-iso $D/lanes $D/hold
grep -n 'HELD\|hold released\|re-exec\|requeueing orphan' $D/logs/dispatcher.log
```

and look for a `16:34`-`16:44` worker start/exit pair.

## What I fixed instead, and why it does not need the answer

The removal is a whodunnit; the *defect* is that it was **permanent**. The lane
pid file was written exactly twice in a worker's life -- at startup and on a
hold release -- so any removal, by any actor, took that device out of
`serving()` until the dispatcher was restarted. That is what turned a transient
`rm` at 16:44 into five hours of unpinned pairs. Fixing permanence closes the
outage whatever fired.

The most plausible remaining mechanism, and one this covers without having to
prove it, is a **stale predecessor's EXIT trap**. Workers are `&` children, so
a supervisor killed with SIGKILL leaves them running; the next supervisor
starts a NEW worker for the same label, which registers itself; when the OLD
worker finally exits, its trap `rm -f`s the file the live worker owns, and
nothing ever recreates it. The trap removed a file by NAME and never checked
that the name still held its own pid. This fits every observation -- present at
start, gone ten minutes later, never restored, correct again after a restart --
but I could not confirm it, so it stays labelled a hypothesis.

In `dispatcher.sh`:

- `lane_claim` re-asserts `lanes/$DEVICE_LABEL` at the top of every loop tick,
  after the hold check, not just at startup. One `cat` and usually no write.
  Any removal is self-healing within one tick instead of one restart.
- the EXIT trap and the hold path both go through `lane_release`, which removes
  the file only if it still holds **my** pid. A predecessor cannot evict its
  successor.
- `held_logged` is now purely a log-once flag; the restore no longer depends on
  which process observed the hold. The brief's suspected defect is closed even
  though the mechanism it described was not the one present.

**Residual, deliberately not fixed:** the re-assertion happens per loop tick,
and the loop is blocked inside `serve_one` for the length of a device run. A
lane file removed 30 seconds into a 26-minute A/B arm stays missing until that
arm finishes. Closing that needs a background refresher, which is a bigger
change than this brief asks for -- and the window is now loud rather than
silent, because the next claim logs `AFFINITY BLIND` and the status page says
so. If it recurs, that is the thing to build.

## 2. An empty `serving()` is now audible

- `affinity.py` gains `_note_blind()`, the same shape as `_note_split()`: a
  request that WOULD have been pinned (it names a prediction, or is a soak keyed
  on its requester) and reaches rule 3 with no live lanes writes
  `$D/splits/<req>.blind.txt` naming the prediction. Only when `serving()` is
  **empty** -- one serving device needs no pin, since everything lands there
  anyway, and noting that would be noise.
- `affinity.py <dir> --serving` exposes the liveness check, so the dispatcher
  and the status page ask the one implementation rather than each rewriting a
  pid test that took three attempts to get right.
- `dispatcher.sh` gains `lane_blind_check`, called from `serve_one` after the
  claim. It logs `AFFINITY BLIND: ...` once per outage and
  `lanes registered again` once on recovery -- on the transition, not per
  claim, because the corpus sweep enqueues one request per suite.

Failing open is unchanged and still correct: no pin blocks a claim, and the two
controls below prove the fallthrough still fires.

## 3. `$D/splits/` has a consumer

`status.sh`'s "Handhelds and arms" section grows two lines: which lanes are
serving (or a warning in bold that none are and pinning is inert), and the five
most recent notes from `$D/splits/` in the last 24h, split notes and blind notes
alike. It asks `affinity.py --serving` rather than counting files, because
`$D/lanes/` is shared with `check_coverage.py`'s `<lane>.lastbrief` stamps and a
file count there would report devices that do not exist.

## Falsification -- measured, not asserted

`selftest.sh`, new block appended immediately before the summary line.
Old code restored with `git show origin/master:<file> > <file>` for
`affinity.py`, `dispatcher.sh` and `status.sh` together, re-run, restored.

Measured before merging `origin/master`, which brought `lane/notespath`'s 19
further checks in:

```
before the merge   new code:  selftest: 66 passed,  0 failed
                   old code:  selftest: 49 passed, 17 failed
after the merge    new code:  selftest: 85 passed,  0 failed
```

All 17 failures are mine; no pre-existing check broke. The three that pass both
ways are the ones labelled CONTROL:

| control | old | new | discriminates? |
|---|---|---|---|
| a pin to a device that is NOT serving falls through rather than stalling | ok | ok | yes -- both versions really compute this |
| a pin to a device that IS serving is still honoured | ok | ok | yes -- ditto |
| a request pinned normally leaves no blind note | ok | ok | only against the new code (old writes no notes at all) |

Four checks passed both ways on the first falsification run and were rewritten
because they were **vacuous**, not because they were controls:

- `! ... | grep -q lastbrief` is satisfied by no output at all, which is what a
  missing `--serving` produces. Now counts words instead.
- three `disp 'lane_claim; ...; [ ! -e file ]'` checks passed against a file
  with no `lane_claim` in it: the missing function failed, nothing was ever
  created, and "the file is absent" came out true. Now chained with `&&`
  throughout so a missing function fails the whole check.

That rewrite is the only reason the falsification count is 17 and not 12.

## For the next lane

- Do not re-derive the hold-path hypothesis. It is refuted above by reading;
  re-reading it will cost you an hour and end where this did.
- `$D/lanes/` is shared with `check_coverage.py`'s `<lane>.lastbrief` files -- a
  different feature and a different meaning of "lane". `serving()` survives them
  only because a date stamp does not parse as an int. If anything ever writes a
  NUMERIC `.lastbrief` there, `serving()` will invent a device.
- `ab_compare.py`'s cross-device refusal was not touched. It is the backstop and
  it worked.
- The selftest now takes much longer than "seconds" when several lanes run it at
  once: six other worktrees were running `arms.sh` concurrently and a 900s
  timeout was not enough. Budget 2400s, or expect a false red.
