# lane.burnoutloop1012

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

Only the play loop after `mark gameplay` changed (`git diff` shows no change above it, verified
below). The old loop:

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
    axis RT mid
    wait 0.3
    press B
    wait 1.0
}
```

- The inner `repeat 3` is the same 6 s drive block as before, unmodified, run three times (18 s),
  so the race inputs are unchanged whenever the race is actually live.
- `axis RT mid` releases the trigger and `axis LX mid` is already the last step of the inner
  block, so every axis is back at mid before `press B` -- I chose to release RT before B because
  I have no frame evidence either way on whether a held trigger changes what B does on this
  screen, and releasing first is the cheaper assumption to be wrong about (worst case: a wasted
  B press that does nothing).
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

## Checks

```
$ bash docs/testing/titles/route.sh --check docs/testing/titles/routes/burnout-revenge.returning.route
route ok: .../burnout-revenge.returning.route (150 lines)
$ echo $?
0

$ ROUTE_DRY=1 SERIAL=dryrun timeout 400 bash docs/testing/titles/route.sh docs/testing/titles/routes/burnout-revenge.returning.route
...
ROUTE 00:42:45.903 mark gameplay
...
ROUTE 00:43:04.539 press B      # mark + 18.6s
...
ROUTE 00:43:25.088 press B      # + 20.5s
$ echo $?
124   # timeout, expected: the loop is `forever`
```

Both ran against the worktree's own copy of the files.

`git diff` confirms nothing above `mark gameplay` changed (verified by inspection of the diff
hunk -- the only changed lines are the new comment block and the loop body after `mark
gameplay`).

## A process note, not a route defect

I first ran the edit against `/home/justin/hakuX/docs/testing/titles/routes/...` (the main
checkout, on `master`) by mistake instead of this worktree's copy. Caught it before committing
anything (`git -C /home/justin/hakuX status` showed the stray modification against a clean
`master`), reverted it with `git checkout --` there, and redid the edit in
`/home/justin/hakux-work/wt/burnoutloop1012`. Noting it here in case the stray diff is still
visible in that checkout's reflog/history to anyone else working in it -- it was reverted, not
committed.

## What a later lane should not repeat

- Don't guess Burnout Revenge's control map from the Burnout 3 routes or from memory -- the
  frames available here never show B pressed during a live race, so "what B does mid-race" is
  still genuinely unknown. If a future confirmation run's frames show a B press landing during
  the race (visible car behavior change, or a race restart mid-timer), that would be the first
  real evidence either way and is worth recording.
- `route.sh` requires `SERIAL` even under `ROUTE_DRY=1` (`: "${SERIAL:?route.sh: SERIAL is
  required}"` runs unconditionally before the dry/live branch) -- set a dummy `SERIAL` for any
  future dry-run check of this or other routes.
