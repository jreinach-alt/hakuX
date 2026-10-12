# lane.burnoutbrief1012

## Why attempt 1 did not finish (attempt 2, resuming)

Attempt 1 wrote this NOTES.md and PR.md with the corrected framing (upper bound only, "at most
14.3s", no claimed lower bound) and a consistent `1.3%` figure in both, and committed/pushed that
as `1b02ba781f` -- but the route comment it was supposed to fix to match
(`docs/testing/titles/routes/burnout-revenge.returning.route`) still has the pre-addendum text:
"A Retry that lands can take over 14s" and "Since the Retry-to-brief transition (>14s) outlasts
the 0.3s gap" (both assert a lower bound nothing on disk supports -- one frame every ~31s cannot
pin a lower bound), plus a `~1.4%` exposed-fraction figure that disagrees with NOTES.md/PR.md's
`1.3%`. Addendum 1 named the route comment first and explicitly as the thing to fix; attempt 1
fixed everything else and left that file untouched. Fixing it now, and standardizing on the
addendum's own worked figure (`0.3 / ~22s is ~1.4%`) everywhere instead of `1.3%`, since that's
the number Addendum 1 computed when it posed the problem.

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
  ~22s now), the exposed fraction is about `0.3 / ~22 ≈ 1.4%` of each iteration (the figure used
  consistently in the route comment, this file, and PR.md). Since a given race only ends once,
  this is a roughly 1-in-70 chance per race-end that it lands in the trap window, not a
  per-loop-tick risk.
- **Is 0.3s still long enough to register as two separate presses?** Yes, by a wide margin.
  `perf/pad.sh`'s `press()` sends button-down, sleeps the hold (default 60ms), then sends
  button-up, and returns only after that -- it is synchronous, so B's button-up is already done
  before A's button-down is even attempted. The dry-run check below shows the actual B-to-A gap
  landing at ~0.38s wall time (0.3s explicit wait plus the adb/bash overhead already visible
  elsewhere in this route's timings), several multiples of the 60ms hold -- nowhere close to being
  read as one merged input.
- **Does the 0.3s gap hold against the measured load time?** The fix does not need a lower bound
  on the transition, and nothing on disk gives one (one frame every ~31s cannot pin a lower bound,
  only the at-most-14.3s upper bound from the section above). Either way is fine: if the brief is
  still loading 0.3s after B's Retry, this iteration's A lands on the load screen (a no-op there,
  same as B would be) and the *next* iteration's A, ~22s later, lands on the now-settled brief and
  dismisses it via Continue; if the brief is already up by 0.3s, this iteration's A dismisses it
  directly. So the brief clears within at most one extra loop iteration beyond the one that
  Retried it (~22s), never the 12+ minutes it sat for before this fix. The order that matters is
  B before A on RESULTS, which the 0.3s gap (not a load-time estimate) is what bounds.
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
route ok: docs/testing/titles/routes/burnout-revenge.returning.route (173 lines)
$ echo $?
0

$ ROUTE_DRY=1 SERIAL=dryrun timeout 400 bash docs/testing/titles/route.sh docs/testing/titles/routes/burnout-revenge.returning.route > out 2>&1
$ echo $?
124   # timeout, expected: the loop is `forever`

$ grep -n "mark gameplay" out
116:ROUTE 02:39:20.536 mark gameplay
$ awk '/mark gameplay/{f=1} f' out | grep -n "press B\|press A\|axis RT min" | head -6
39:ROUTE 02:39:39.708 axis RT min
42:ROUTE 02:39:40.028 press B
46:ROUTE 02:39:40.403 press A      # B-to-A gap: 0.375s
86:ROUTE 02:39:59.689 axis RT min
89:ROUTE 02:40:00.008 press B
93:ROUTE 02:40:00.382 press A      # B-to-A gap: 0.374s
```

Both commands ran against this worktree's own copy
(`/home/justin/hakux-work/wt/burnoutbrief1012`), re-run after the Addendum 1 correction above (the
route gained 2 lines of comment, 171 -> 173). The dry run stepped past the mark and through
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
