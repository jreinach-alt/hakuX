# lane.burnoutbrief1012

## What the frames and log show (run `1-1791793410-lane.local-336876`, ref c03e17b8a0)

`index.tsv` (device clock, one frame about every 31s) and the `ROUTE` lines of `run.log` together:

- `mark gameplay` at device time `01:59:05.634`.
- `frames/f00014.png` (`01:59:13`) and `f00015.png` (`01:59:44`): the race, matching the brief.
- `frames/f00016.png` (`02:00:16`): **RESULTS [TRAFFIC ATTACK]** -- Retry (B) / More details (Y) /
  Continue (A). First frame confirming RESULTS.
- `frames/f00017.png` (`02:00:48`): the **event brief** for the restarted event ("TRAFFIC ATTACK --
  Check traffic to beat the Score Targets!", $500,000/$150,000/$50,000 targets), **Continue (A)**
  the only prompt shown. First frame confirming the brief.
- Every `press B` in `run.log` between those two frame times: `01:59:49.185`, `02:00:11.857`,
  `02:00:34.434`. Exactly one of those, `02:00:34.434`, falls in the window after RESULTS is
  confirmed (`02:00:16`) and before the brief is confirmed (`02:00:48`) -- that is the press this
  log can actually pin to the RESULTS -> brief transition. The two earlier presses (`01:59:49.185`,
  `02:00:11.857`) land in the ~32s gap between `f00015` (still racing) and `f00016` (RESULTS), where
  the exact moment the race ended and RESULTS first appeared is not resolved by these frames --
  Traffic Attack is known short (prior lane's notes: ends well under a minute after the mark), so
  RESULTS plausibly appeared before either of those presses, in which case one of them was the
  actual Retry and `02:00:34.434`'s B landed on an already-reloading/already-brief screen and did
  nothing. Either way, the log bounds the RESULTS -> brief transition at **at most 14.3s**
  (`02:00:34.434` to the `02:00:48` frame that confirms the brief) and at least long enough to not
  be instant (no frame shows the brief before `02:00:48`).
- `frames/f00017` through `f00040` (`02:00:48` to `02:12:58`), every one of them: the same brief,
  unchanged, while `run.log` shows `press B` continuing on its usual ~21-22s cadence throughout
  that whole span. B does nothing on the brief, confirming the brief needs a different input.

**What the frames show about A during a race: nothing.** The route's play loop before this fix
never sent A after `mark gameplay` (only `RT`/`LX` and, since c03e17b8a0, `B`), and no frame in
this run or in `route-frames/` (which stop before the mark) shows an A press landing during live
racing. Whether A is also a race control is not established by anything on disk; I am not guessing
a control map from memory or from the Burnout 3 routes.

## The fix

Only the play loop after `mark gameplay` changed; the new comment explaining it sits after the
mark too (`git diff origin/master` shows the first changed line is right after `mark gameplay`,
confirmed below). Old loop tail (from c03e17b8a0):

```
    axis RT min
    wait 0.3
    press B
    wait 1.0
}
```

New:

```
    axis RT min
    wait 0.3
    press B
    wait 0.3
    press A
    wait 1.0
}
```

- `press A` comes right after `press B`, inside the same outer iteration, so a run that lands on
  the brief continues into the race within -- at most -- the loop cycle after the one whose B
  retried it (see "Does the 0.3s gap hold" below for why it's usually the cycle after, not the same
  one).
- **The trap, and why the gap is 0.3s, not longer.** A on RESULTS is Continue, which leaves the
  event entirely, for screens this route has never recorded. B must dismiss RESULTS (Retry) before
  A can safely fire; if RESULTS appears for the first time in the gap between this iteration's B
  and A -- i.e., the race happens to end in that exact slice of time -- A would hit a RESULTS
  screen B never got a chance to Retry, and Continue off it unrecorded. A short gap bounds how much
  of each outer loop is exposed to that: at 0.3s against this run's observed outer-loop period of
  roughly 21.4-22.7s (the `press B` cadence measured above, before this run's press A existed; the
  new loop adds about 0.3-0.4s of overhead per iteration for the extra press, so call the period
  ~22-23s now), the exposed fraction is about `0.3 / 22.5 ≈ 1.3%` of each iteration. Since a given
  race only ends once, this is a roughly 1-in-75 chance per race-end that it lands in the trap
  window, not a per-loop-tick risk.
- **Is 0.3s still long enough to register as two separate presses?** Yes, by a wide margin.
  `perf/pad.sh`'s `press()` sends button-down, sleeps the hold (default 60ms), then sends
  button-up, and returns only after that -- it is synchronous, so B's button-up is already done
  before A's button-down is even attempted. The dry-run check below shows the actual B-to-A gap
  landing at ~0.38s wall time (0.3s explicit wait plus the adb/bash overhead already visible
  elsewhere in this route's timings), several multiples of the 60ms hold -- nowhere close to being
  read as one merged input.
- **Does the 0.3s gap hold against the measured load time?** Yes. Section above bounds the
  RESULTS -> brief transition at up to 14.3s, far longer than the 0.3s gap. So the ordinary case is:
  this iteration's B lands on RESULTS and starts the reload; this iteration's A, 0.3s later, is
  still mid-load (a load screen takes input the way RESULTS/brief take B -- as a no-op) and does
  nothing; the *next* iteration's A, ~22s later -- well past the load -- lands on the now-settled
  brief and dismisses it via Continue. So in practice this costs one extra loop iteration (~22s),
  not the "within one loop cycle" best case, whenever B's Retry windows up needing the full load
  time. That's still well inside the brief's own description of the problem it fixes (a run that
  previously sat on the brief for 12+ minutes, per the frames above).
- Race inputs (`RT max`, `LX` steering) are unchanged; `RT` is still released with `axis RT min`
  (a trigger's rest, not `mid` -- `mid` is half throttle on the Nova, per burnoutloop1012's fix)
  before the B/A presses.
- **Cost if A turns out to be a live race control.** Bound by the same cadence already accepted
  for B in c03e17b8a0: A fires at most once per ~22-23s outer iteration, immediately after B, never
  once per 6s inner-drive tick. If A is e.g. a handbrake-style discrete action, a once-per-lap tap
  is a comparable disturbance to what B's existing cadence already introduces and was accepted for.
  The more likely reading, unchanged from the prior lane's notes, is that Retry/More
  details/Continue are RESULTS/brief UI-row buttons, not HUD controls, so the extra presses cost
  nothing during racing.

## Checks

```
$ bash docs/testing/titles/route.sh --check docs/testing/titles/routes/burnout-revenge.returning.route
route ok: docs/testing/titles/routes/burnout-revenge.returning.route (171 lines)
$ echo $?
0

$ ROUTE_DRY=1 SERIAL=dryrun timeout 400 bash docs/testing/titles/route.sh docs/testing/titles/routes/burnout-revenge.returning.route > out 2>&1
$ echo $?
124   # timeout, expected: the loop is `forever`

$ grep -n "mark gameplay\|axis RT min\|press B\|press A" out | head -8
116:ROUTE 02:26:35.635 mark gameplay
154:ROUTE 02:26:53.823 axis RT min
157:ROUTE 02:26:54.141 press B
161:ROUTE 02:26:54.516 press A      # B-to-A gap: 0.375s
201:ROUTE 02:27:14.687 axis RT min
204:ROUTE 02:27:15.004 press B
208:ROUTE 02:27:15.377 press A      # B-to-A gap: 0.373s
```

Both commands ran against this worktree's own copy
(`/home/justin/hakux-work/wt/burnoutbrief1012`). The dry run stepped past the mark and through
multiple `press B` / `press A` pairs before the 400s timeout cut it, as expected for a `forever`
loop.

`git diff origin/master -- docs/testing/titles/routes/burnout-revenge.returning.route` shows its
first changed line is the new comment block immediately after the `mark gameplay` context line --
the mark line and everything above it is byte-identical to origin/master.

## What a later lane should not repeat

- RESULTS and the event brief are different screens with different single valid inputs (B /
  Retry vs. A / Continue); a loop step added for one must not assume it also serves the other.
  Confirm each with its own frame evidence before wiring an input to it.
- A short gap between two presses that must land in a specific order (B before A) is not a
  stylistic choice -- it is what bounds how much of the loop is exposed to the one case where the
  order could matter (RESULTS appearing new in that gap). Computing that exposed fraction from the
  measured loop period is cheap and worth doing before picking the gap, not after.
- `press()` in `perf/pad.sh` is synchronous (down, hold, up, return) with a default 60ms hold, so
  any non-zero explicit wait between two `press` steps is already many times the hold -- the
  "separate inputs" concern is not what limits how short the gap can be; the RESULTS/brief
  ordering trap is.
- This run's frames still show nothing about A during live racing -- that remains unresolved. If a
  future confirmation's frames show an A press landing mid-race (a visible control response, or an
  unexplained race restart away from a Retry/Continue cycle), that is the first real evidence
  either way and is worth recording.
