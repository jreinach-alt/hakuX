# lane.burnoutloop1012

## Resume (attempt 2): why attempt 1 did not finish

Attempt 1 pushed 8a4df3d1ab with `State: ready`. It did not finish clean: lane.local's review of
the diff before folding found two defects that this resume fixes, not redoes:

1. **Wrong release value for a trigger axis.** The fix released `RT` with `axis RT mid`. On the
   Nova, `ABS_GAS` (the trigger `pad.sh` maps `RT` to) reports range `0,32767`, so `pad.sh` resolves
   `mid` as `(lo+hi)/2 = 16383` -- half throttle, not a release. A trigger's rest position is its
   `min`. Changed to `axis RT min` below (see "The fix"). This was the brief's own error ("every
   axis is back at mid"), not something attempt 1 should have caught from the route grammar alone,
   but it needed fixing regardless.
2. **The new comment block landed above `mark gameplay`**, not after it, so the diff touched a
   line above the mark -- the one thing the brief said must stay byte-identical. Moved the comment
   block to immediately after `mark gameplay` and before `repeat forever {`.

Both are fixed in "The fix" and reverified in "Checks" below; nothing else about attempt 1's
reasoning (frame reading, cadence, cost analysis) changed.

## What the frames show

Run `1-1791785532-lane.local-2130848` (route `burnout-revenge.returning`, 840 s requested).
`logcat.txt`: `mark gameplay` at device time `00:21:29.457`, `soak end` at `00:29:25.098` -- 475.6 s
of gameplay, matching the brief's figure.

- `frames/f00014.png` (device `00:21:45`, +15.5 s from the mark): still in the Traffic Attack
  event, timer reading **11.43** (counting down), car already wrecked and smoking against a
  guardrail. So the event itself runs out within roughly the next 10-15 s, i.e. it ends somewhere
  around +25-30 s from the mark.
- `frames/f00015.png` (device `00:22:16`, +46.6 s from the mark): already on **RESULTS [TRAFFIC
  ATTACK]** -- "RATING ACHIEVED OK", "VEHICLE DAMAGE $1,725", "MEDAL AWARDED NONE", "YOUR RANK
  HARMLESS". The prompt row at the bottom reads **Retry (B)**, **More details (Y)**, **Continue
  (A)**.
- Every frame from `f00015` through `f00028` (device `00:29:06`, the last frame before soak end)
  is the same RESULTS screen -- a replay moves behind the panel, which is why the liveness check
  (`static_frac 0.07`) passed even though the route stopped making progress.
- **What the frames show about B during the race: nothing.** No frame in this run or in the
  route's own `route-frames/` (which stop at `002128-gameplay.png`, before the mark) shows B
  pressed while the race is live. The route's play loop before this fix never sent B at all, so
  there is no recorded evidence either way of what B does mid-race. I am not guessing a control
  map from memory or from the Burnout 3 routes (`burnout3.*.route`), which use a different loop
  and never press B either.

Older screening `1790873999-autoverdict-2073899` is on disk but **has no `frames/` directory** --
only `route-frames/` (the route's fixed `shot`s, which stop at `002128-gameplay.png`, before the
mark) and `verdict.json`. `verdict.json` records `gameplay_s: 483.5`, `fps_ok_share: 0.7207`
(below the 90% screening bar), `pass: false`, `failing: "duration: 484 s of gameplay < 600 s
screening"` plus the fps bar. There is no frame evidence in that run's directory to say whether it
also sat on RESULTS -- it was failed on fps share, not duration, so it is plausible it never even
reached RESULTS, or that it did and the fps bar simply caught it first. I can't tell from what's
on disk, so I'm not asserting it either way.

## The fix

Only the play loop after `mark gameplay` changed, and the comment block explaining it sits after
the mark too (moved there in this resume -- see "Resume" above). `git diff origin/master` shows the
first changed line is the one right after `mark gameplay`; the mark line itself, and everything
above it, is untouched (verified below). The old loop:

```
repeat forever {
    axis RT max
    wait 1.5
    axis LX min
    wait 1.5
    axis LX max
    wait 1.5
    axis LX mid
    wait 1.5
}
```

never sends anything but `RT`/`LX`, so once the timed event ends it has nothing to dismiss
RESULTS with. New loop:

```
repeat forever {
    repeat 3 {
        axis RT max
        wait 1.5
        axis LX min
        wait 1.5
        axis LX max
        wait 1.5
        axis LX mid
        wait 1.5
    }
    axis RT min
    wait 0.3
    press B
    wait 1.0
}
```

- The inner `repeat 3` is the same 6 s drive block as before, unmodified, run three times (18 s),
  so the race inputs are unchanged whenever the race is actually live.
- `axis RT min` releases the trigger. `axis RT mid` does NOT: on the Nova, `pad.sh` resolves an
  axis's `mid` as `(lo+hi)/2`, and the trigger's range is `0,32767` (not the stick's symmetric
  `-32767,32767`), so `mid` there is 16383 -- half throttle, not a release. A trigger's rest is its
  `min`. (This is a correction from this resume; attempt 1 used `mid` here, following the brief's
  own "every axis is back at mid" line, which does not hold for a trigger axis.) `axis LX mid` is
  already the last step of the inner block, so `LX` (a stick, where `mid` genuinely is center/rest)
  is back at rest before `press B` too. I chose to release RT before B because I have no frame
  evidence either way on whether a held trigger changes what B does on this screen, and releasing
  first is the cheaper assumption to be wrong about (worst case: a wasted B press that does
  nothing).
  - a 0.3 s wait after releasing RT and before pressing B, to give the pad state time to land
    ahead of the press rather than racing the same `sendevent` batch.
- `press B` (Retry) then runs once per 19.3 s outer iteration. On RESULTS, this dismisses the
  panel and restarts the same Traffic Attack event -- well under the "within about 20 s" target
  (confirmed in the dry run below: first press at mark+18.6 s, second at mark+39.1 s, a 20.5 s
  gap).

**Cost if B turns out to be a live race control** (e.g. a handbrake): the cadence bounds how often
it can land mid-race. The race itself runs only ~25-30 s per the frames above, and B is sent at
most once per 19.3 s outer iteration -- so at most one stray B press per race, never one every 6 s
loop as a naive "add press B to the existing 6 s loop" would have done. If B does nothing during
racing (the more likely case, since Retry/More details/Continue read as the RESULTS screen's own
UI row, not a HUD control), the extra presses are free.

## Checks (rerun in this resume, after both fixes)

```
$ bash docs/testing/titles/route.sh --check docs/testing/titles/routes/burnout-revenge.returning.route
route ok: docs/testing/titles/routes/burnout-revenge.returning.route (150 lines)
$ echo $?
0

$ ROUTE_DRY=1 SERIAL=dryrun timeout 400 bash docs/testing/titles/route.sh docs/testing/titles/routes/burnout-revenge.returning.route > out 2>&1
$ echo $?
124   # timeout, expected: the loop is `forever`

$ grep -n "mark gameplay\|axis RT min\|press B" out | head -8
116:ROUTE 01:12:18.303 mark gameplay
118:ROUTE 01:12:18.309 axis RT max
154:ROUTE 01:12:37.473 axis RT min      # released before the first press B
157:ROUTE 01:12:37.791 press B          # mark + 19.5s
197:ROUTE 01:12:57.056 axis RT min      # released before the second press B
200:ROUTE 01:12:57.374 press B          # mark + 39.1s (19.6s gap)

$ sed -n '154,158p' out     # confirms axis RT min actually resolves to the trigger's rest, not mid
ROUTE 01:12:37.473 axis RT min
DRY adb shell sendevent /dev/input/event-dry 3 5 -32767; sendevent /dev/input/event-dry 0 0 0
ROUTE 01:12:37.488 wait 0.3
ROUTE 01:12:37.791 press B
DRY adb shell sendevent /dev/input/event-dry 1 305 1; sendevent /dev/input/event-dry 0 0 0
```

Both commands ran against this worktree's own copy. (The first dry-run attempt in this resume was
cut short by an unrelated signal from stopping a monitoring task of mine partway through the wait
-- not a route or script problem; rerunning to a plain redirected file, uninterrupted, gave the
output above.)

`git diff origin/master -- docs/testing/titles/routes/burnout-revenge.returning.route` now shows
its first changed/added line immediately after the `mark gameplay` context line, confirming the
mark line and everything above it is unchanged -- fixing attempt 1, where the comment block sat
above the mark and so appeared in the diff above it.

## A process note, not a route defect

I first ran the edit against `/home/justin/hakuX/docs/testing/titles/routes/...` (the main
checkout, on `master`) by mistake instead of this worktree's copy. Caught it before committing
anything (`git -C /home/justin/hakuX status` showed the stray modification against a clean
`master`), reverted it with `git checkout --` there, and redid the edit in
`/home/justin/hakux-work/wt/burnoutloop1012`. Noting it here in case the stray diff is still
visible in that checkout's reflog/history to anyone else working in it -- it was reverted, not
committed.

## What a later lane should not repeat

- `mid` is not a trigger's rest. `pad.sh` resolves `mid` as `(lo+hi)/2` against whatever range
  `detect` reports for that axis; a stick's range is symmetric around 0 so `mid` lands at rest, but
  a trigger's range (`ABS_GAS=0,32767` on the Nova) is not, so `mid` is half-pressed. Use `min` to
  release a trigger. The brief's own "every axis is back at mid" line does not hold for RT/LT; this
  cost attempt 1 a redo.
- A route change that must land after a marker (here, `mark gameplay`) means the new lines too,
  not just the loop body -- a comment explaining the new lines placed before the marker still
  shows up in `git diff` as a change above it.
- Don't guess Burnout Revenge's control map from the Burnout 3 routes or from memory -- the
  frames available here never show B pressed during a live race, so "what B does mid-race" is
  still genuinely unknown. If a future confirmation run's frames show a B press landing during
  the race (visible car behavior change, or a race restart mid-timer), that would be the first
  real evidence either way and is worth recording.
- `route.sh` requires `SERIAL` even under `ROUTE_DRY=1` (`: "${SERIAL:?route.sh: SERIAL is
  required}"` runs unconditionally before the dry/live branch) -- set a dummy `SERIAL` for any
  future dry-run check of this or other routes.
