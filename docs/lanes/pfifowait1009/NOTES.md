# lane.pfifowait1009

Issue: #433 umbrella (no GitHub issue; dispatched directly by lane.local).
Territory: `docs/lanes/pfifowait1009/**`, `hw/xbox/nv2a/pfifo.c`,
`hw/xbox/nv2a/pgraph/vk/reports.c`, `docs/testing/titles/routes/amped2.route`,
`docs/testing/predictions/pfifowait1009-*.json`.

## 1. The route (brief step 4, done first as instructed)

`amped2.route` did not exist on disk (pmucounters generated it from a dispatch
request's `route` field and deleted its working copy). Per Addendum 1 to the
brief, the source is `dispatch/results/1-1791538465-fpstelemetry1008-1131600/
request.json`'s `route` field, confirmed byte-identical to that result dir's
plaintext `route.txt`.

Two commits:
1. `730824d21e` -- the verbatim text, byte-identical to the source
   (`diff` + `sha256sum` both confirmed before committing).
2. This one -- pacing-robustness for the deterministic menu phase (steps
   1-12), using the route DSL's own `waitfor` primitive instead of fixed
   timers.

### What broke before, and why `waitfor` fixes the menu phase

pmucounters' NOTES.md (~968, ~1100-1135): both of its shipped-wait arms went
void. One run ended up physically stuck against a tree mid-gameplay (the
game showed "Press BACK to reset position"); the other got stuck cycling
pause/career/gear menus, most likely during the genre loop. Both are
attributed to pacing drift: the fixed `wait N` before each `shot`/press in
the original route assumes a constant amount of real time maps to "the next
screen has loaded," which stops holding once frame pacing changes (exactly
what flipping `HAKUX_PFIFOWAIT` is expected to do).

Steps 1-12 are a deterministic, single-path menu walk (publisher logo ->
intro videos -> title -> name entry -> main menu -> career submenus), one
press per screen. For this phase, `waitfor <name> <timeout> <region>
<threshold>` is a direct, mechanical fix: poll the live screen against a
reference crop of the expected next screen, once a second, until it matches
or the (now generous) timeout elapses; a timeout aborts the route
(`ROUTE FAIL waitfor ...`) instead of pressing blind into whatever is
actually up. This is the same primitive `castlevania-cod.first-run.route`
already uses for an identical class of problem (a 10+ s transition-time
variance that fixed waits could not cover; see `route.sh`'s grammar comment
and that route's own header).

**Calibration.** `waitfor_match.py` scores mean abs diff over a grayscale
64x48 downscale; the reference PNG does not have to be pre-cropped to the
box's position, only comparable after the resize. For steps 1-12 I used the
region `0,0,1280,960` (the whole frame) and the already-captured screenshots
from the fpstelemetry1008 run (`route-frames/031804-s01-...png` etc.) as
reference crops verbatim -- no new device time needed. Measured scores
between each step's own reference and the immediately-preceding (wrong)
screen, via the real `waitfor_match.py`, not a hand-rolled approximation:

| adjacent pair (wrong screen vs next ref) | score |
|---|---|
| s01 vs s02 | 66.0 |
| s05 vs s07 | 39.5 |
| s07 vs s08 | 109.1 |
| s08 vs s09 | 76.9 |
| s09 vs s10 | 50.7 |
| s10 vs s11 | 54.6 |
| s11 vs s12 | 51.9 |

All comfortably above the threshold I used (25), with margin; a same-screen
self-compare scores 0 (exact match). Timeouts are 4x the original fixed
wait before each shot, floored at 20s (e.g. s01: 12.1s -> 48s timeout; s12:
11.4s -> 46s). On a normal run this costs nothing extra: `waitfor` returns
as soon as it matches, polling once a second, so the typical case is
indistinguishable in wall time from the original fixed wait that happened
to be long enough.

### What I did NOT robustify, and why

Steps 13-25 (gameplay/probe) and the genre loop are where pmucounters'
actual two void causes happened (tree-stuck mid-gameplay; menu-cycling,
most likely in the genre loop) -- not in steps 1-12. I tried to build an
analogous `waitfor` gameplay-HUD checkpoint for this phase and could not
make it discriminate reliably:

- Full-frame compare between different gameplay/probe frames of the *same*
  route segment scores 45-108 (camera motion and the open 3D scene alone
  move the pixels that much), so a full-frame region is useless here --
  unlike the menu phase, "same screen, different moment" is not low-score
  for free-roam 3D gameplay.
- A tight region on the top-left trophy/score HUD badge (where the badge
  itself is present only during gameplay, not menus) still overlaps badly:
  across the 12 gameplay/probe sample frames vs a single late reference
  (s25), scores ranged 0-108 (dark transition frame aside, 21-82 is the
  realistic steady-state range); across the 12 menu frames against the same
  reference, scores ranged 28-134 -- but several menu frames (s09: 41,
  s12: 37) land *inside* the gameplay range. The badge is alpha-blended
  with the moving 3D scene behind it and its digits change as score
  accrues, so there is no threshold that separates "gameplay HUD is up"
  from "this is some menu" without false positives in both directions. A
  second candidate region (the bottom-right board-switch icon) had the same
  problem (gameplay min 23-32 overlaps menu min 28.7).
- Per `docs/testing/titles/hub-checks-that-check-nothing.md`-style concerns
  (a check that cannot actually discriminate the failure it is meant to
  catch is worse than no check -- it gives false confidence), I did not
  ship a `waitfor` gate for this phase.

I left steps 13-25 and the genre loop's timing completely unchanged: the
plain travel waits there are not provably the cause of either void (the
tree-stuck case looks like a physics/collision outcome of exactly-timed
inputs meeting different terrain under different pacing, not a
screen-recognition failure; the menu-cycling case most likely came from a
`press B` in the genre loop landing on an unexpected pause-style prompt),
and I have no device-side evidence yet that widening them helps. The DSL's
`drive <profile> <seconds>` primitive (screen-aware autonomous play, with
real pause-recovery and a clean `ROUTE FAIL` on a stall or an unrecognized
screen) is the actual answer to this phase, but it needs a
`drive-profiles/<profile>.toml` file under
`docs/testing/titles/drive-profiles/`, which is outside my territory. If
the two pacing-robustness validation runs below still void in this phase
the same way pmucounters' did, that is the concrete next step and belongs
in an OUTBOX request, not a guess spent on more device time first.

### Territory note on the reference crops

The brief names exactly `docs/testing/titles/routes/amped2.route` as
in-territory, not the `routes/refs/amped2/` directory the DSL requires for
`waitfor` to validate at all (`route.sh`'s own `validate()` hard-fails if a
named reference crop is missing). The brief's own step 4 asks for "retries
keyed on what is on screen," which only exists via `waitfor`/`press-until`,
so I read the ref crops as inseparable, same-tree companions to the named
file (same `routes/` directory, title- and lane-specific, no plausible
collision with another lane) rather than a separate grant to queue for.
Flagging this judgment call here rather than silently assuming it, and
again in the PR body.

### Validation still owed before any scored arm

Per brief step 4: two actual device runs of this route, at different frame
pacing, before any A/B arm is queued. Not yet run (no device time spent
yet this lane). Planned next after the lock-mechanism investigation below
reaches a checkpoint worth protecting with a commit.

## 2. Lock analysis (brief step 1) -- in progress

Confirmed via direct reading (not the brief's own phrasing) that at the
`pgraph_process_pending_reports(d)` call site in `pfifo_thread`
(`hw/xbox/nv2a/pfifo.c`, loop body), only `pfifo.lock` is actually held.
`pgraph.lock` is not taken until *after* that call returns (the
`diag_capture` block a few lines later explicitly drops `pfifo.lock`,
takes `pgraph.lock` for `surface_update`/`flip_stall`, then reverses). So
the brief's "(and pgraph.lock)" framing is almost certainly about a
correlated-but-separate contributor to the same low-fps windows (the brief
itself keeps `lw` and the `pgraph.lock` +2.8ms figure as separate clauses),
not literal co-holding at this call site. Still need to trace the full
`pgraph_process_pending_reports` (pfifo.c) ->
`pgraph_vk_process_pending_reports` (reports.c:361) ->
`_internal` (reports.c:213) call chain precisely before finalizing the fix
shape and scope. Continuing next.
