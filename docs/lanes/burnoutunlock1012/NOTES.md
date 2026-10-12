# lane.burnoutunlock1012

Burnout Revenge's play loop must get back into a race after RESULTS sends it to World Tour
(#433, 0.5). Device: none for this lane -- everything below reads frames/logs already on disk
(`1-1791800854-lane.local-2819291`, Nova, 1600s requested, and `1-1791793410-lane.local-336876`
for the no-medal RESULTS variant) plus the route and engine files.

## Step 1: state table

Every screen the post-mark loop can land on, from `press B / wait 0.3 / press A / wait 1.0`
repeated forever. "Recorded" means a frame or log line on disk shows it; nothing here is filled
from game-world memory.

| Screen | Recorded? | Evidence | What B does | What A does |
|---|---|---|---|---|
| Racing (live gameplay) | yes | `frames/f00020.png` (03:43:22, FPS 54), `f00030.png` (03:49:11, FPS 46), confirmation-1 `f00014`/`f00015`; route-frames `start1`/`steer-right` | **unrecorded** -- no frame in either confirmation or in `route-frames/` (which stops before the mark) shows a B press landing mid-race (burnoutloop1012 NOTES says the same) | **unrecorded** -- same gap, noted in burnoutbrief1012 NOTES |
| RESULTS, no medal | yes | confirmation-1 `frames/f00016.png` (02:00:16): "Vehicle Damage 4" (counting), no medal panel, prompts **Retry (B) / More details (Y) only, no Continue** | confirmed: restarts the event -- `run.log`'s B at `02:00:34.434` bounds the RESULTS->brief transition at **at most 14.3s** (next frame `f00017` at `02:00:48` is already the brief) | **unrecorded** -- no Continue prompt shown on this variant, so A's effect here has no on-screen label and is not exercised by any frame |
| Event brief (post-Retry, no medal) | yes | confirmation-1 `f00017` onward: "TRAFFIC ATTACK -- Check traffic to beat the Score Targets!", **Continue (A) the only prompt** | confirmed no-op: `f00017`-`f00040` (12+ minutes) all show the same unchanged brief while B kept firing on its ~22s cadence (burnoutbrief1012 NOTES) | confirmed: dismisses the brief into the race (the fix burnoutbrief1012 made) |
| RESULTS, medal awarded | yes | confirmation-2 `frames/f00044.png` (03:56:35): "GOOD/2 stars", "$87,350 damage", "MEDAL AWARDED BRONZE", "NEW EVENT UNLOCKED! / NEW TRAFFIC ATTACK HIGH SCORE!", prompts **More details (Y) / Continue (A) only, no Retry** | inferred no-op (no Retry label to press); not independently isolated since the B at `03:56:33.526` and the A at `03:56:34.175` are 0.65s apart with no frame between them | confirmed: Continue -- the next frame (`f00045`, 03:57:06) is WORLD TOUR's location-select, so this A is what left the event |
| World Tour, location select (post-medal, real choice) | yes | confirmation-2 `f00045`-`f00053` (03:57:06-04:01:19), every frame: MOTOR CITY "0/2 EVENTS COMPLETED" NEW highlighted, Lone Peak locked, Angel Valley locked, prompts **Driver Details (Y) / Select (A)** (B unlabeled on this frame) | B's per-press effect here is **not separable from A's** in this data -- frames are ~31s apart (close to the loop's ~22s period), and across the whole stuck tail the *net* effect of one full B-then-A cycle is: still on this same screen type. Whether B alone backs out a level and A alone re-enters it, or the carousel cursor drift from the loop's `axis LX` steering presses onto a locked destination also plays a part, cannot be told apart from what's on disk | same caveat: net effect per cycle is "no escape"; A alone has a recorded on-screen meaning here ("Select"), but a single isolated A press was never tested apart from the B that always precedes it by 0.3s |
| Event-type select, rank select, car select, loading, event brief -- all *after* re-entering Motor City from a state where it now has more than one event unlocked | **unrecorded** | The only recording of this chain is from the original fresh-profile boot (route lines 26-33 / 84-121), where everything auto-skipped to a single choice because nothing else was unlocked yet. Confirmation-2's medal just unlocked a second event in Motor City ("NEW EVENT UNLOCKED!"), so this chain may now present a real choice screen the fresh-boot recording never exercised. No frame on disk shows this chain in the post-medal state. | n/a | n/a |

No frame anywhere shows Retry, More details, and Continue together on one RESULTS screen -- the
route comment that claimed otherwise was wrong; fixed in this lane (see "The fix" below).

## Step 2: where confirmation 2 actually went

Scenario (a) from the brief -- **medal removes Retry, and the existing B/A pair's A becomes
Continue off RESULTS into World Tour** -- is confirmed, not scenario (b) (race ending in the
0.3s B-A gap):

- `f00044` (03:56:35) already shows the medalled RESULTS with no Retry prompt, so by the time
  this frame was taken the event had already ended and been scored; it isn't a frame mid-race.
- `run.log`'s `press B` at `03:56:33.526` and `press A` at `03:56:34.175` are both *before*
  `f00044`'s timestamp by less than 2s -- i.e. they landed on (or immediately before) the already-
  medalled RESULTS, not on a still-running race. There is no press in the log between the last
  confirmed-racing frame and `f00044` that could instead be "a race ending mid-gap" -- the gap
  mechanism scenario (b) describes requires a press to land *while still racing*, and nothing
  in the log does.
- `f00045` (03:57:06), 31s after `f00044`, is already World Tour's location select -- consistent
  with A=Continue firing at `03:56:34.175` and taking effect well within that 31s window.

The one thing this data does **not** fully separate (flagged in the state table): once on World
Tour's location select, whether the stall is purely B-undoes-a-level/A-reenters-it ping-ponging,
or whether the loop's `axis LX min`/`axis LX max` steering presses (sent every 1.5s during the
"racing" portion of each outer cycle, before the B/A pair) also drift the location carousel's
highlighted city, is not resolved by 31s-apart frames against a ~22s press cadence. Either way,
the measured outcome is the same: stuck on this screen for the rest of the run.

## Step 4: cost findings

**World-Tour-entry-to-gameplay cost, fresh/auto-skip path (the only one recorded):** summing the
route's own `wait` values from the `press A` into WORLD TOUR (line 84, `wait 7.7`) through the
`wait 5.6` just before `mark gameplay` (line 122): **188.5s**, confirmed by direct summation of
lines 84-122. Every route-frame FPS overlay sampled across that stretch reads 26-29 (e.g.
`033749-loading.png` FPS 27, `033810-after-car.png` FPS 26, `033832-grid1.png` FPS 26) -- i.e.
this entire recovery, even in the best case, runs below the 30fps bar throughout.

**fps budget math:**
- A 600s confirmation (the screening/default length) allows at most 10% of gameplay below bar to
  still clear the 0.90 share: **60s**. A single World-Tour recovery at the recorded 188.5s
  minimum -- *even if it worked* -- is more than three times that allowance on its own, before
  counting any racing/retry time at all.
- The actual 1600s-requested run scored `gameplay_s: 1256.7` (`verdict.json`), so its budget was
  10% of that: **125.7s** below bar. Measured below-bar time was `(1 - 0.8172) * 1256.7 =
  229.7s`, closely matching the ~287s the frames show stuck on World Tour (`03:56:35`-`04:01:19`
  plus run tail) -- i.e. even this long a confirmation was already over budget from *one* stall,
  and the recorded best-case recovery cost (188.5s) alone would have consumed essentially the
  entire 125.7s allowance by itself even if the loop could escape every time.

**Conclusion, stated as a finding per the brief's own framing:** a working fix that reliably
returns the loop to a race after every medal would still very likely fail the fps bar on any
confirmation length used so far (600s or the 1600s tried here), because the recovery path itself
runs 188.5s+ below the 30fps bar, and that alone is larger than the below-bar budget a 600s run
allows and close to consuming the budget a 1600s run allows. Getting back into a race is
necessary but, on this evidence, not sufficient to pass the fps bar -- the harness would need
either a much longer confirmation window, a route that avoids ever earning a medal (so Retry
never disappears), or some other strategy change. That decision belongs to lane.local / the
owner, not this lane.

**Cost of extra in-race button presses:** this lane adds none. The existing B/A cadence (once
per ~22s outer loop) and its accepted risk framing (0.3s gap bounds "A as a live race control"
exposure to ~1.4% of one loop cycle, several multiples of `pad.sh`'s 60ms press hold) are
unchanged, documented already in the route's own comments, and not re-derived here since no new
press was added.

## The fix

Only the comment block immediately after `mark gameplay` changed (`git diff` confirms the first
changed line is right after the mark; everything above, including the mark line itself, is
byte-identical to `origin/master`):

- Removed the stale claim that RESULTS shows Retry (B) / More details (Y) / Continue (A)
  together on one screen -- no frame anywhere supports that; replaced with the two-variant
  breakdown from the state table above, cited to `f00016` (no medal) and `f00044` (medal).
- Documented the new failure mode (medal removes Retry, Continue leaves the event for World
  Tour) and pointed at this file for the full analysis.

**The play loop itself (lines 156-173) is unchanged.** `route.sh`'s grammar has exactly one way
to make a route react differently to different screens without guessing: `waitfor`/`press-until`,
both of which **hard-abort the whole route** (`exit 1`, confirmed by reading `route.sh` lines
301-360 and 420-423) if their one expected outcome doesn't show up in time. Put either inside
`repeat forever` to detect "are we stuck on World Tour", and the instant a normal racing cycle
runs long enough to hit the timeout, the entire confirmation aborts -- worse than the current fps
FAIL, which still books partial credit and never crashes/hangs. The grammar's one *non*-aborting
screen-aware construct, `drive <profile> <seconds>`, could in principle carry different actions
for different named screen states, but every drive-profile on disk
(`docs/testing/titles/drive-profiles/*.toml`: forza, castlevania-cod, sonic-heroes,
super-monkey-ball-deluxe, buffy) was built from a device path-finding session (see `gta-3.route`'s
own provenance comment, "PATHFOUND by pathfind.py on the Nova"), and the screens this would need
to classify past location-select -- event-type select and car select in a state where Motor City
now has a second event unlocked -- are exactly the ones the state table above marks
**unrecorded**. Building that profile correctly needs the Nova; this lane has no device. Adding
blind, unconditional presses for those screens into a loop that runs forever (so every single
normal racing cycle would also execute them) is the guess the brief says not to make, and would
in any case run during live racing, which "add a step to skip a menu" in a *route* can afford but
a step inside an *infinite loop around live gameplay* cannot.

## WAITING

What's needed to actually fix this, for whoever next has Nova access (an owner-approved
path-finding session, same shape as `gta-3.route`'s or `castlevania-cod.first-run.route`'s):

1. Reach Burnout Revenge's medalled-RESULTS -> World-Tour-location-select state again (repeat
   confirmation 2's run, or Retry-and-medal deliberately), then record what happens pressing A
   ("Select") on Motor City once it has more than one event unlocked -- does it show a real
   event-choice screen, or still auto-skip? Record reference crops for whatever comes up
   (`routes/refs/burnout-revenge.returning/`) if a `drive`-profile approach is pursued.
2. Independently of (1): the cost finding above (188.5s+ minimum recovery, below the fps bar
   throughout) means it's worth deciding, before investing in that path-finding session, whether
   a correct recovery can even pass the fps bar at a confirmation length anyone is willing to
   run, or whether the real fix is elsewhere (e.g. a route that never lets the event earn a
   medal, or accepting this title needs a much longer confirmation).

## Checks

- `bash docs/testing/titles/route.sh --check docs/testing/titles/routes/burnout-revenge.returning.route`
  -> `route ok: ... (192 lines)`, exit 0.
- `git diff origin/master -- docs/testing/titles/routes/burnout-revenge.returning.route`: first
  changed line is immediately after `mark gameplay` (line 124); nothing above the mark differs.
- `ROUTE_DRY=1 SERIAL=dryrun timeout 395 bash docs/testing/titles/route.sh
  docs/testing/titles/routes/burnout-revenge.returning.route`: reaches `mark gameplay` at
  `04:32:23.923`, then runs two full `press B` / `press A` loop cycles (`04:32:42`, `04:33:03`)
  before the 395s timeout killed it (exit 124, expected -- the loop is `repeat forever`). No
  `ROUTE FAIL` anywhere in the output.
