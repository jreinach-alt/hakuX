# lane.armpin -- the A/B pair that split across two handhelds

Brief: `affinity.py`'s pinning was inert on 2026-09-19 because `serving()`
returned `[]`, because `$D/lanes/` held no worker pid files. Three tasks, in
order: (1) find what emptied `$D/lanes/`, (2) make an empty `serving()`
visible, (3) give `$D/splits/` a consumer.

## 1. What emptied `$D/lanes/` -- the brief's hypothesis is REFUTED

The brief names the hold path as the suspect:

> it `rm -f`s unconditionally while held and restores only under
> `[ "$held_logged" = 1 ]`, which is per-process. A worker that starts while a
> hold is in force never sets `held_logged`, so it never restores.

**The second sentence is false, and reading the code is enough to show it.**
`dispatcher.sh` (pre-change, lines 1154-1165):

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

`held_logged=1` is assigned on the same line-run as the `rm`, unconditionally,
every iteration the hold is seen. A worker that starts under a hold therefore
DOES set it on its first tick, and DOES restore the file when the hold lifts.
The hold path self-heals within one process. It is not the remover, and the
brief's own timeline agrees: holds were lifted at 11:08, the workers started at
16:34, `$D/lanes/` changed at 16:44.

Two further hypotheses tested and killed:

- **EXIT-trap leakage into subshells.** `trap 'rm -f ...' EXIT` at line 1103
  would be catastrophic if bash ran it on every `$(...)`; the worker loop does
  `now_hash="$(src_hash)"` every tick. Tested on this host's bash: a command
  substitution and a `( ... )` subshell both leave the file alone. Not it.
- **A third remover somewhere else in the tree.** `grep -rn 'lanes'` over every
  `*.sh`/`*.py`/`*.md` in the repo, filtered for `rm|rmdir|-delete|unlink|
  prune|clean|shutil`, yields exactly three sites, all in `dispatcher.sh`:
  the `mkdir -p`, the EXIT trap, and the hold path. `check_coverage.py:572`
  WRITES `lanes/<lane>.lastbrief` (that is where the two stray 09-14 files
  came from) but removes nothing. No timer, unit or job sweeps `$D`.

**What I could not do:** the lane sandbox refuses to read outside the worktree,
so `/home/justin/hakux-work/dispatch/lanes/`, `hold/` and the dispatcher log
were unreachable from here. I could not name the process that fired at 16:44.
That question stays open, and the next lane should not spend another session on
it -- read the forensics above first, then `ls -la --time-style=full-iso
$D/lanes $D/hold` and `grep -n 'HELD\|hold released\|re-exec' $D/logs/dispatcher.log`
from a session that can reach the host.

## What I fixed instead, and why it does not need the answer

The removal is a *whodunnit*; the defect is that it was *permanent*. The lane
pid file was written exactly twice in a worker's life -- once at startup, once
on a hold release -- so ANY removal, by any actor, took that device out of
`serving()` until the dispatcher was restarted. That is what turned a transient
`rm` at 16:44 into five hours of unpinned pairs.

The most plausible remaining mechanism, and one this fix covers without having
to prove it, is a **stale predecessor's EXIT trap**: workers are `&` children,
so a supervisor killed with SIGKILL leaves them running; the next supervisor
starts a NEW worker for the same label, which writes `lanes/<label>`; when the
OLD worker finally exits its trap `rm -f`s the file the live worker owns, and
nothing ever recreates it. The trap removed a file by NAME, never checking that
the name still held its own pid.

So, in `dispatcher.sh`:

- `lane_claim` re-asserts `lanes/$DEVICE_LABEL` at the top of every loop tick,
  not just at startup. Idempotent, one `stat`-and-maybe-`printf` per 30s tick.
  Any removal is now self-healing within one tick instead of one restart.
- the EXIT trap and the hold path go through `lane_release`, which removes the
  file only if it still holds **my** pid. A predecessor's trap can no longer
  evict its successor.

That pair makes the "unresolved" question no longer load-bearing: whatever
fired at 16:44, the lane comes back within 30 seconds.

## 2. An empty `serving()` is now audible

`affinity.py` gains `_note_blind()`, the same shape as `_note_split()`: when a
request that WOULD have been pinned (it names a prediction, or is a soak keyed
on its requester) reaches rule 3 and finds no live lanes, it writes
`$D/splits/<req>.blind.txt`. Failing open is still correct -- the docstring's
"a silent stall costs the measurement" stands and no pin blocks a claim -- but
the degradation from "pairs are pinned" to "pairs are random" now leaves a
record in the one directory that, as of this branch, has a reader.

`dispatcher.sh` also logs `affinity: no live lanes registered ...` once per
worker (not per claim -- a per-claim line would bury the log) when it claims a
request and `$D/lanes/` has nothing live in it.

## 3. `$D/splits/` has a consumer

`status.sh` grows an "Affinity" line in the Handhelds and arms section: the
live lanes by label, and the most recent notes from `$D/splits/` in the last
24h, split note and blind note alike. That is the page the owner reads.

## Falsification -- the new checks FAIL against the code they replace

Six checks appended to `selftest.sh`, immediately before the summary line.
Verified by `git show origin/master:<file> > <file>`, re-running, restoring:

| check | old code |
|---|---|
| a lane file holding another pid is not removed by my trap | FAIL |
| the lane file is re-asserted after an outside `rm` | FAIL |
| affinity notes a claim made with no live lanes | FAIL |
| the blind note names the prediction | FAIL |
| status.sh prints the affinity section | FAIL |
| status.sh lists a recent split note | FAIL |

and two that must pass BOTH ways, as controls that I have not broken the thing
the brief said to leave alone:

| control | old | new |
|---|---|---|
| a pin to a dead device still falls through (no stall) | pass | pass |
| a pin to a live device is still honoured | pass | pass |

## For the next lane

- Do not re-derive the hold-path hypothesis. It is refuted above by reading;
  re-reading it will cost you an hour and end where this did.
- `$D/lanes/` is shared with `check_coverage.py`'s `<lane>.lastbrief` files --
  a different feature and a different meaning of "lane". `serving()` survives
  them only because a `.lastbrief` does not parse as an int. If anything ever
  writes a numeric `.lastbrief` there, `serving()` will invent a device.
- `ab_compare.py`'s cross-device refusal was not touched. It is the backstop
  and it worked.
