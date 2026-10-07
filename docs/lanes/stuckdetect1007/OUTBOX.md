# OUTBOX -- lane.stuckdetect1007 asks lane.local for a grant

Territory right now: `docs/lanes/stuckdetect1007/**` only. `docs/testing/titles/pathfind.py` is
lane.pathfind's file; `docs/testing/jobs/selftest.d/` is grant-gated. This lane built and
validated a standalone detector (`docs/lanes/stuckdetect1007/stuckdetect.py`,
`docs/lanes/stuckdetect1007/NOTES.md`) against stored frames with no device time. The integration
below is what a grant would move; this lane does not touch either file itself.

## 1. Move the selftest leg into selftest.d

`docs/lanes/stuckdetect1007/95-stuckdetect.sh` -> `docs/testing/jobs/selftest.d/95-stuckdetect.sh`
(a plain `git mv`; the number is free -- `95-affinity.sh` is the only other `95-*`). It expects
`docs/lanes/stuckdetect1007/stuckdetect.py` to exist at that same relative path; either move that
file too (and update the leg's `SD=` line) or leave `stuckdetect.py` where it is and have the leg
reference it by its current path -- lane.local's call, both work as written today.

## 2. pathfind.py: wire the hook into hold_play

All line numbers below are against this lane's base (`master @ cd20abf797`); re-check them
against lane.pathfind's current HEAD before applying, since that file is under active work there
(its own `hold.jsonl` already shows a `ladder`/`ladder_round` field this lane's base does not
have -- see NOTES.md's Gui Yi section. Treat these as the shape of the change, not a diff to
apply blind).

- **Import**, near the top (after the existing `sys.path.insert` for `classify`/`hangwatch`,
  pathfind.py:56-60):
  ```python
  sys.path.insert(0, os.path.join(HERE, "..", "lanes", "stuckdetect1007"))  # or wherever it lands
  import stuckdetect
  ```
- **Single source of truth for the unstick ladder**: `stuck_step`'s `unstick_ladder` parameter
  is designed to take `pathfind.HOLD_UNSTICK[genre]` directly (pathfind.py:139-146) rather than a
  second copy living in `stuckdetect.py` -- so nothing to change there, just pass it through.
  Same for `HOLD_SHED_STATES` (pathfind.py:150) and a fallback ladder built from
  `UNLOCK_LADDER` (pathfind.py:100) for genres with no `HOLD_UNSTICK` entry.
- **In `hold_play`** (pathfind.py:1412 on this lane's base), at the point a kept frame is
  recorded (the `keep` block, pathfind.py:1553-1582 on this base) add a signature:
  ```python
  sig = stuckdetect.frame_signature(png)
  sig_history.append(sig)
  state_history.append(a.get("state") if off else None)   # `a` is the last hold_look answer, or None off-cycle
  decision = stuckdetect.stuck_step(sig_history, genre, rung=stuck_rung, states=state_history,
                                     shed_states=HOLD_SHED_STATES, unstick_ladder=HOLD_UNSTICK.get(genre),
                                     fallback_ladder=UNLOCK_LADDER[:3])
  if decision["stuck"]:
      if decision["abort"]:
          reason = f"stuck_abort: {decision['reason']} after {stuck_rung} unstick attempt(s)"
          break   # ends the hold the same way the existing `nav > HOLD_NAV_MAX` branch does
      self.send(decision["action"]); stuck_rung += 1
  else:
      stuck_rung = 0
  ```
  `sig_history`/`state_history`/`stuck_rung` are new per-hold locals (`StuckWatch` in
  `stuckdetect.py` already bundles this bookkeeping if that shape is preferred instead).
- **The abort itself**: `hold.jsonl` and `result.json`'s `hold` dict both already have a
  `reason` field (pathfind.py:1515, :1595); a `stuck_abort` just needs its own `reason` string
  (as above) and the same early-break the existing `nav > HOLD_NAV_MAX` path takes
  (pathfind.py:1514-1517), so `held["ok"]` comes out `False` with a reason, not a Playable, per
  the brief's "a flagged invalid-for-Playable result with telemetry, not a pass."

## 3. Why no device smoke was queued

`validate` in `stuckdetect.py` only needs stored frames, which this lane had (lane.pathfind's own
`runs/`), so there was nothing to prove on a live device that offline replay could not already
show. The Nova is Playable-only and already held by lane.pathfind's own queue; a smoke run after
this grant lands is lane.local's or lane.pathfind's call, not something this lane should queue
pre-emptively.

## 4. A follow-up this lane is NOT proposing to build itself

NOTES.md's "Why HOLD_SHED did not fire again for Gui Yi" section suggests the shop reopened from
the genre loop's own walk (proximity), not from a fixed button -- a button-shed cannot fix that.
A positional retreat (back up N steps before resuming the genre loop, the first entry of the
genre's own `HOLD_UNSTICK` ladder already does something like this for `drive`/`shooter`/
`attack`) is the plausible fix, but Gui Yi's genre has no `HOLD_UNSTICK` entry today
(`team`/`other`), and inventing one unasked is outside this lane's brief. Flagging it here for
whoever picks the integration up.
