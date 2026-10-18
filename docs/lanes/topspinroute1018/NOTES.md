# topspinroute1018: a state:any route for Top Spin past Controller Select

Issue #433. Brief: `docs/lanes/topspinroute1018.md` (not in this tree; see the
session's brief block). No device time in this lane; the fix is read from an
existing result directory, not a new run.

## Already-tried

| Attempt | Result | Why it didn't work |
|---|---|---|
| (none before this lane) | -- | lane.local's defect report (dispatch/results/z-1792314505-lanelocal-3439642) is the first look at this specific failure; no prior lane touched gen-top-spin.route. |

Stop rule: the same failure for one cause, twice, means stop and report. Not
reached -- this is a first pass.

## What the defect actually shows

`dispatch/results/z-1792314505-lanelocal-3439642/route-state.tsv` (kept in
the tree, no device needed to read it) is the ground truth for timing, not
just the route-sh prose in the brief:

```
t       state        action
0.4     boot         wait
4.8     intro_video  press A (skip intro_video)
31.4    intro_video  press A (skip intro_video)   # second skip cycle
33.6    logo         press A (skip logo)
38.6    title        press START (title 1)        # time_to_title_s=39.2 (video length, not a tunable)
41.5    ingame_menu  press A (ingame_menu 1)       # Main Menu -> Exhibition (correct)
44.3    ingame_menu  press A (ingame_menu 2)       # Settings -> Continue   (correct)
47.0    ingame_menu  press A (ingame_menu 3)       # Venue -> Select        (correct)
49.6    ingame_menu  press A (ingame_menu 4)       # Court -> Select Court  (correct)
52.5    ingame_menu  press A (ingame_menu 5)       # Controller Select: A does nothing from here on
...
123.4   ingame_menu  ROUTE FAIL (press 25)
```

`pathclass` (the generic drive profile's classifier) names Main Menu,
Settings, Venue, Court AND Controller Select all `ingame_menu`/`submenu` --
one label for five different screens -- and its policy is "press A". That is
*correct* for the first four (proven right here, in the run that failed) and
a no-op on the fifth, because Controller Select needs the 1P pad moved off
the middle with the hat before A does anything (`fps786-topspin.route` step
16: `axis HATX min` / `axis HATX mid` / `press A`). `menu_max_presses=25` at
`menu_gap_s=2.0` (`drive-profiles/generic.toml` has no override) is what
turns that no-op into `ROUTE FAIL` 25 presses later.

## The fix

`gen-top-spin.route` (same file, still the one `targets.toml` points `4D530035`
at) now splits in two:

1. `drive generic 75` -- the classifier handles boot/intro/logo/title AND
   the four correct submenu advances above, which is exactly the part whose
   length is NOT a fixed number: the intro_video skip took two cycles and
   ~29 s in the one run on record, and `time_to_title_s` is however long the
   FMV actually is, not a tunable. A blind `wait N` sized for this run is the
   exact bug `drive.py`'s own doc opens with (Simpsons Hit & Run, Sonic
   Heroes, Forza) -- replacing it with the classifier is the point of this
   fix, not just a workaround for Controller Select.
2. Steps 14-25 of `fps786-topspin.route`, copied verbatim (same waits, same
   presses, including its own two wasted presses -- A, then START -- on
   Controller Select before the hat move that actually clears it). That
   sequence is proven: it is a real recorded playthrough. It should not
   depend on first-run vs kept-profile, since by the time it starts the
   profile question is already behind us (Main Menu is up either way); only
   the boot-to-title stretch above does.

### Why 75 s for the `drive` step, and the residual risk

From the tsv: Controller Select is first reached (capture, not press) at
t=52.5 (relative to the drive step's own start), and the run's 25th press
(FAIL) lands at t=123.4 -- a 70.9 s gap between "stuck" and "FAIL" that comes
from the profile's fixed `menu_gap_s`, not from anything that varies run to
run. 75 s clears the observed Controller-Select arrival (52.5 s) with 22.5 s
of margin, and sits comfortably under a FAIL floor estimated at ~85-87 s (a
worst-case guess of 14-16 s to reach Controller Select if the whole
boot/intro/logo/title/menu chain ran far faster than this sample, +70.9 s).

That worst-case floor is a guess, not a measurement -- this lane has no
device time to check it. If `drive generic 75` still lands on, or before,
Court/Venue/Settings (undershoot), the two filler presses copied from
fps786 steps 14-15 (`press A`, `press START`) still advance those screens
correctly before the hat-move step; the only way this route fails on a real
run is the classifier chain itself running fast enough to rack up the 25
stuck presses on Controller Select inside 75 s (i.e. reaching it before
~t=4-5 s), which would need the whole intro/logo/title sequence to resolve
almost instantly. The device run after this lane is where that gets checked
for real.

## Checked

`route.sh --check docs/testing/titles/routes/gen-top-spin.route` passes.
`titlestate.py`'s `route_state()` reads the first `# state: any` comment
line unchanged from before this edit -- still `any`, still what
`request.sh` needs to admit a kept-profile disk.

No change to `targets.toml`'s `route = "gen-top-spin"` (the file is still
that name); its `notes` line was updated to say the Controller Select fix
is in and still not device-proven.

`drive.py`, `classify.py`, `pathclass.py` and every `drive-profiles/*.toml`
were read for this but not edited (out of this lane's files).

Selftest: none beyond `route.sh --check` -- one route file, no code.
