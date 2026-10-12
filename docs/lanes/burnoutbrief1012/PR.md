# burnoutbrief1012: press Continue (A) after Retry so a run on the event brief keeps racing (#433, 0.5)

State: ready

## What changed

`docs/testing/titles/routes/burnout-revenge.returning.route`: the play loop after `mark gameplay`
now presses `A` 0.3s after each `press B`, so a run that lands on Burnout Revenge's event brief
("TRAFFIC ATTACK -- Check traffic to beat the Score Targets!", Continue (A) the only prompt)
continues into the race, instead of sitting there. Only the loop after the mark changed; everything
above it is byte-identical to `origin/master`. `docs/lanes/burnoutbrief1012/NOTES.md` has the full
frame reading, the fix, and the checks.

## Why

lane.burnoutloop1012 (folded `c03e17b8a0`) added a periodic `press B` (Retry) because a run sat on
the RESULTS screen once the timed Traffic Attack event ended. The next confirmation
(`1-1791793410-lane.local-336876`) shows the Retry works, but then fails on position (81% of
samples with no picture change): the frames show B landed on RESULTS and restarted the event, which
loads into an event brief with no B prompt at all -- only Continue (A). The loop never pressed A,
so once Retry lands on the brief, the run waits there (12+ minutes of unchanged frames in this
run).

## The fix, in short

```
    axis RT min
    wait 0.3
    press B
    wait 0.3
    press A
    wait 1.0
}
```

A 0.3s gap between B and A: short enough that RESULTS appearing new in that exact slice (the one
case where A landing on RESULTS instead of the brief would wrongly Continue off the event) is
~1.3% of one outer loop (~22-23s observed), but non-zero so the two presses are distinct inputs
(`perf/pad.sh`'s `press()` holds for 60ms by default and is synchronous, so 0.3s is several
multiples of that). The measured RESULTS -> brief load time (up to 14.3s, from this run's frames)
outlasts the 0.3s gap, so the ordinary case costs one extra loop iteration (A's first attempt lands
mid-load and does nothing; the next iteration's A, ~22s later, lands on the settled brief). Full
reasoning, including the cost if A turns out to be a live race control, is in NOTES.md.

## Checks

```
$ bash docs/testing/titles/route.sh --check docs/testing/titles/routes/burnout-revenge.returning.route
route ok: docs/testing/titles/routes/burnout-revenge.returning.route (171 lines)
exit 0

$ ROUTE_DRY=1 SERIAL=dryrun timeout 400 bash docs/testing/titles/route.sh docs/testing/titles/routes/burnout-revenge.returning.route
exit 124   # timeout, expected: the loop is `forever`; stepped past the mark through multiple press B / press A pairs
```

`git diff origin/master -- docs/testing/titles/routes/burnout-revenge.returning.route`: first
changed line is right after `mark gameplay`; nothing above the mark touched.

## Device

No device runs in this lane. lane.local queues the next confirmation after the fold; that run's
frames are the proof this works (or don't, in which case they're the next evidence of what A
actually does).

## Prediction

None: this lane edits a route file and does not itself claim a performance/frame-rate number.

Files: `docs/lanes/burnoutbrief1012/NOTES.md`, `docs/lanes/burnoutbrief1012/PR.md`,
`docs/testing/titles/routes/burnout-revenge.returning.route`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
