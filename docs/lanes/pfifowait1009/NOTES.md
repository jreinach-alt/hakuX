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

### CORRECTION: `waitfor` does not reach a dispatched run at all -- reverted

Before queueing anything, I tried to reproduce exactly what a worker sees,
rather than trust that my local `route.sh --check` passing meant a
dispatched run would also pass it. It does not, and this is a general gap,
not something specific to this lane's route:

`request.sh --route` resolves the named route locally, then re-checks it
with a **copy of the route file renamed to `route.txt`** (its own comment:
"AND AS THE RUN WILL SEE IT. ... the dispatcher writes the text to
`<result dir>/route.txt` and the worker plays it with the SNAPSHOT's
route.sh"). `route.sh`'s `ref_path()` (`route.sh:124`) is
`$(dirname "$ROUTE")/refs/$(basename "$ROUTE" .route)/$1.png` -- a path
relative to the route file's own name. On a worker the route file is
always literally named `route.txt`, never `<name>.route`, so
`basename "route.txt" .route` does not strip anything and `ref_path()`
always resolves to `refs/route.txt/<name>.png`, regardless of what the
route was originally called. Nothing in `dispatcher.sh` (confirmed by
grep: the only `route.txt` write is the plain text, `dispatcher.sh:1503`)
or `request.sh` ever stages a `refs/` directory next to that file. I
reproduced this directly rather than reasoning it through on paper:

```
$ cp docs/testing/titles/routes/amped2.route /tmp/routecheck/route.txt
$ bash docs/testing/titles/route.sh --check /tmp/routecheck/route.txt
route.sh: /tmp/routecheck/route.txt:5: waitfor 's01-publisher_logo': no
reference crop /tmp/routecheck/refs/route.txt/s01-publisher_logo.png
```

This is exactly the failure `request.sh`'s own comment warns about ("A
route that fails there exits at its first line and the soak runs on with
no input") and exactly the check it runs before queueing ANY `--route`
request -- so `request.sh` would have refused to queue `amped2.route` as
committed, with this same message. It is not specific to my route: ANY
route using `waitfor`/`press-until` hits this today, including
`castlevania-cod.first-run.route`, the precedent I cited for the primitive
-- that route's `waitfor` steps, if it has any reachable from a real
dispatch, have the same problem; I did not go verify that route separately
since it is out of my territory and not needed to establish that mine
cannot run.

**I reverted the `waitfor` conversion.** Steps 1-12 are back to a plain
`wait N` (then `shot` for diagnostic-only frame logging, which needs no
reference and is unaffected) before each press -- structurally identical
to the verbatim original, just with the SAME generous durations I had
already calibrated for the `waitfor` timeouts (4x the original wait,
floored at 20s: s01 12.1s->48s, s02 6.6s->26s, ... s12 11.4s->46s -- see
the table above, now read as `wait` durations instead of `waitfor`
timeouts). This is the brief's OTHER named option ("longer settle waits,"
not "retries keyed on what is on screen") and it is the only one of the
two that is actually deployable through `request.sh` as the pipeline
exists today. Deleted `docs/testing/titles/routes/refs/amped2/` (the 12
reference crops), since nothing can use them; the calibration table above
stays as the record of how the durations were chosen; it just no longer
describes a live mechanism.

The genre-loop/gameplay phase (13-25 + the repeat block) is unchanged from
the verbatim original, same reasoning as before (no device evidence that
widening those specific waits addresses either of pmucounters' actual void
causes, and -- now doubly true -- no mechanism to make a screen-aware
check of it reach the device even if I could calibrate one).

A fix for the staging gap itself (copying a route's `refs/` into
`<result dir>/refs/route.txt/`, keyed by the route name request.sh already
resolves) belongs in `request.sh`/`dispatcher.sh`, both out of my
territory. Not filing an OUTBOX request for it: this lane does not need
`waitfor` to work now that the route is back to plain waits, and the find
is recorded here for whichever lane next tries to use the primitive on a
real dispatch.

### Validation still owed before any scored arm

Per brief step 4: two actual device runs of this route, at different frame
pacing, before any A/B arm is queued. Not yet run. Planned next, and now
able to double as the brief step 5 A/B's first pair: running the same
route once with no env (baseline pacing) and once with
`HAKUX_PFIFOWAIT=1` (the fix's pacing) is two different-pacing runs of the
same route AND the first A/B pair, as long as neither run reports a
`ROUTE FAIL`.

## 2. Lock analysis (brief step 1) -- done

### The call chain, confirmed by reading, not by the brief's own phrasing

`pfifo_thread`'s loop body (`hw/xbox/nv2a/pfifo.c:2119-2163`) takes
`pfifo.lock` once at the top and holds it continuously across
`pgraph_process_pending_reports(d)` at line 2163. `pgraph.lock` is not held
there: it is taken *after* that call returns, for the unrelated
`diag_capture` block a few lines later (2171-2184), which explicitly drops
`pfifo.lock`, takes `pgraph.lock`, then reverses -- itself a working,
in-territory-adjacent example of the plain unlock/relock style this fix
uses, not the flag+cond style (see below). So the brief's "(and
pgraph.lock)" framing is a correlated-but-separate contributor to the same
low-fps windows (the brief itself keeps `lw` and the `pgraph.lock` +2.8ms
figure as separate clauses); `pgraph.lock` is never co-held at this call
site. Grep-confirmed: `reports.c` and `pgraph_vk_finish` (draw.c) never
touch `pg->lock` at all.

`pgraph_process_pending_reports` (`pgraph.c:5698-5707`) is a thin wrapper
whose own comment is the authoritative statement of the problem: "#433
frametrace: called from the PFIFO loop with pfifo.lock held, so a wait in
its STALLED finish is a wait the guest's DMA_PUT store (user.c) queues
behind." It calls `pg->renderer->ops.process_pending_reports(d)`, which for
the Vulkan renderer is `pgraph_vk_process_pending_reports`
(`reports.c:361`, `renderer.c:2880`) -- confirmed by grep to be this
function's *only* caller anywhere in the tree, so it is always reached on
the PFIFO thread with `pfifo.lock` held and never from the render thread or
anywhere else.

Inside `pgraph_vk_process_pending_reports`: it reads `dma_get`/`dma_put`
(plain loads, correctly protected by the already-held `pfifo.lock` -- not
atomics, so they must not become concurrent with `user_write`'s stores),
and if the FIFO is drained and a new draw has happened since the last
stall, it calls `pgraph_vk_finish(pg, VK_FINISH_REASON_STALLED)`
(`reports.c:374`, the brief's second named site). That one call is where
both of the brief's wait sites actually live, nested rather than parallel:

- Inside `pgraph_vk_finish`, the STALLED reason is one of the "deferred"
  reasons (`draw.c:5019-5022`), so after recording and submitting the
  command buffer it waits only for the render thread's `vkQueueSubmit`
  hand-off (`wait_frame_submitted`, `draw.c:5131-5134`) -- not the fence
  itself at that point. But the existing `HAKUX_STALLFIN` comment just
  above my edit (`reports.c:325-344`, present before this lane) already
  names a second, earlier wait inside the same function that I did not
  need to chase into `pgraph_vk_finish`'s body to rely on: "every STALLED
  finish rotates the frame slot, and the rotation waits for the slot two
  finishes back." That rotation wait is a real `vkWaitForFences`, and it
  is why the comment also records the vcpusleep prior art directly,
  unprompted: "Taking the vCPU off the lock alone (c2dfca18a1, reverted in
  f6ac723228) moved the wait to that fence: 8 to 21 ms a frame, fps down."
  This is the same finding `docs/lanes/vcpusleep/OUTBOX.md`'s "attempt 3"
  entry describes at length (PFIFO thread's own sleep going from median
  8.0ms to 21.3ms once the vCPU stopped being paced by the lock), already
  in the code as the warning this lane's own territory grant refers to.
- `pgraph_vk_finish` unconditionally tail-calls
  `pgraph_vk_process_pending_reports_internal` at its very end
  (`draw.c:5364` -- grep-confirmed the *only* call site for `_internal` in
  the tree). That is where the brief's first named site actually is: the
  `#804` occlusion-query wait, `vkWaitForFences(..., UINT64_MAX)` over
  every submitted frame slot (`reports.c:257-262`, unchanged by this lane)
  followed by a blocking `vkGetQueryPoolResults(..., WAIT_BIT)` loop
  (`reports.c:265-273`, also unchanged).

So `pgraph_vk_finish(pg, VK_FINISH_REASON_STALLED)` at `reports.c:374` is a
single call that can block on at least two separate GPU fences (the frame
rotation's and the occlusion queries') before it returns, and the entire
thing runs with `pfifo.lock` held. Nothing inside either wait touches any
`d->pfifo` state: the only `pfifo.lock`-protected reads in this path are
the `dma_get`/`dma_put` loads already taken before the lock is ever
dropped (see fix, below).

### #474's and #796's pattern, and why this fix does not reuse it verbatim

`#474`/`#796`'s `pgraph_lock_release_for_fence()` / `_retake_after_fence()`
(`pgraph.h`, `~160-434`) is a flag (`lock_released_for_fence`) plus a cond
var (`lock_settled_cond`) that lets *other* takers of `pgraph.lock` -- the
guest's MMIO handlers, the VRAM access callback -- notice the release and
park in `pgraph_lock_settled()` until the method ends, rather than
proceeding against a half-finished state. `#796`'s own application of it
(`draw.c:5136-5166`) is gated specifically on
`finish_reason == VK_FINISH_REASON_SURFACE_DOWN && qemu_thread_is_self(&fd->pfifo.thread)`
-- it does not reach the `STALLED` path I am fixing at all, confirming
that path currently has zero lock-release coverage of any kind.

I did not build an analogous flag+cond pair for `pfifo.lock`, because
nothing needs to notice the release the way `#796`'s consumers need to
notice `pgraph.lock`'s: the only other taker of `pfifo.lock` is
`user_write` (`user.c:93-132`), and what it does while holding it --
store `DMA_PUT`/`DMA_GET`/`REF` with `qatomic_store_release` and call
`pfifo_kick(d)` -- is exactly what it is *supposed* to be free to do while
the PFIFO thread is parked waiting on a fence it already queued; there is
no "half-finished state" for `user_write` to race against, because the
PFIFO thread touches no `pfifo.lock`-protected state during either wait
(previous paragraph). The existing `diag_capture` unlock/relock a few
lines below the call site in `pfifo.c` (`pfifo.c:2177-2184`) is already
the established, simpler style for a plain pfifo.lock drop-and-retake by
the PFIFO thread itself, not the flag+cond style -- this fix matches that
existing style rather than importing `#796`'s heavier one needed for a
*different* lock with *different*, notification-dependent consumers.

`pfifo_kick` (`pfifo.c:1532+`) independently supports the safety argument:
its own doc comment establishes it is already designed to be called with
or without `pfifo.lock` held (it distinguishes vCPU-thread callers via
`current_cpu != NULL` from the VBLANK callback's unlocked diag-capture
kick), i.e. the codebase already tolerates `pfifo.lock` not being held
around at least one of `user_write`'s two actions. And since
`pgraph_vk_process_pending_reports` is only ever reached from the single
PFIFO thread (confirmed above), there is no reentrancy hazard to guard
against either -- unlike `#796`, which needed the `qemu_thread_is_self`
check because `pgraph_vk_finish` has non-PFIFO-thread callers for other
finish reasons. This call site has exactly one caller, so the fix needs no
such guard.

### Fix shape chosen: (a), scoped to the one call that blocks

Shape (a) from the brief ("drop both locks across the fence waits, as
`#474` did for the flip") -- but scoped to the single `pfifo.lock`
(`pgraph.lock` is never held here, so there is nothing of (b)'s kind to
retrofit: shape (b), "write each occlusion report when its fence signals,
without blocking the pusher," would mean restructuring `_internal`'s
report-writeback to be fence-callback-driven instead of a synchronous
wait, which is a materially larger, renderer-level change for the same
correctness outcome).

Implemented in `hw/xbox/nv2a/pgraph/vk/reports.c`
(`pgraph_vk_process_pending_reports`): when `HAKUX_PFIFOWAIT=1` (read once,
default off, same `getenv`-cached-static-int style as the file's existing
`stall_reports_only()`), `pfifo.lock` is released immediately before the
`pgraph_vk_finish(pg, VK_FINISH_REASON_STALLED)` call and retaken
immediately after it returns -- bracketing the *entire* call, which
covers both of the brief's named wait sites in one shot regardless of
exactly where inside `pgraph_vk_finish`/`_internal` each fence wait
happens, since nothing in between needs the lock. Unset (the shipped
default), the code takes the unchanged, un-bracketed `else` branch with no
new behavior.

### Guarding explicitly against vcpusleep's exact failure mode

`docs/lanes/vcpusleep/OUTBOX.md` ("attempt 3") is the one prior attempt at
relieving this contention, and it regressed Simpsons' fps (40.05 -> 36.22,
both outcome legs failed) despite doing exactly what it set out to do:
vCPU off-CPU time fell 19.99s -> 2.54s/minute, USER MMIO wait share fell
79.3% -> 3.3%. Its own diagnosis, and the one the `reports.c` comment
baked in, applies to this fix too if I am not careful: "the frame is paced
by the GPU side, and the lock was only making the vCPU wait it out" --
freeing the vCPU just let it spin through GPU-bound idle time (on-CPU
96%), stealing cycles from the PFIFO thread's own progress and making its
fence wait *longer* (median 21.3ms vs 8.0ms).

The mechanism difference matters here: vcpusleep's fix (`c2dfca18a1`)
changed `user_write` to *post* the DMA_PUT store asynchronously, so the
vCPU's write returned immediately regardless of lock state and the guest
could race arbitrarily far ahead of where the PFIFO thread actually was.
This fix leaves `user_write` unchanged -- it still blocks in
`qemu_mutex_lock(&d->pfifo.lock)` exactly as today, just against a lock
that is no longer held for however long the two fence waits take. The
guest cannot race ahead of DMA_PUT/DMA_GET/REF any faster than it could
today when the lock happens to be free; the only change is that those
registers are no longer artificially unreachable for the duration of a
GPU-bound wait that does not need them locked. So the regression
mechanism vcpusleep hit (free the vCPU to spin unboundedly far ahead) does
not apply the same way here -- but the open question it raises (is the
PFIFO thread's own GPU-bound wait, not the vCPU's, the actual fps-limiting
resource on Amped 2?) is exactly what the prediction below (step 3) has to
be able to catch as a miss, not just check that `lw` dropped. See the
prediction's legs for the explicit vcpusleep-style falsifier.

## 3. Prediction registration (brief step 3, done before any arm)

Two files, both on this branch's then-tip `221a22f5a8`, registered and
committed before any device run that could score them:

- `docs/testing/predictions/pfifowait1009-pgraph-inert.json` -- the
  correctness leg, registered via `ab_compare.py --register` (so its
  `disc`/`must_not_move` are machine-checked, not hand-typed prose). One
  binary, `a_ref` = `b_ref` = `221a22f5a8`; the pgraph suite is not run
  with any env override on either side of THIS file -- it exists to pin
  down that the shipped build renders the 26-suite set (the same broad
  "fence-wait/lock-scope-only" disc flip474 and async794 used, plus
  `ZPass_pixel_count` for the occlusion-query path this fix's bracket
  surrounds) identically to itself, i.e. the byte-identical/noise-floor
  claim that brief step 5 asks for gets its own falsifiable record.
  Brief step 5's actual A/B pixel check (flag on vs off, same suite set)
  reads against this file's `disc` composition.
- `docs/testing/predictions/pfifowait1009-amped2-soak.json` -- hand-written,
  copying pmucounters' NOTES.md section 3f format (pre-registration,
  hit/moved/miss framing, explicit outcomes) rather than `ab_compare.py
  --register`'s schema, since a soak writes no captures for that tool to
  diff. `a_ref` = `b_ref` = `221a22f5a8`, env is the independent variable:
  A = `HAKUX_FRAMETRACE=1`, B = `HAKUX_FRAMETRACE=1 HAKUX_PFIFOWAIT=1`.
  The judge is pmucounters' own `waits.py`/`workbin.py` (already built to
  read `[hakuX-ft1]`'s `vw` breakdown, where `vw[1]` is `lw`, the exact
  metric the brief cites). Legs: M0 instrument validity, F0 the env
  actually reached the process, W1 re-measures the premise on THIS route
  revision (thresholds are relative to each run's own A, not pmucounters'
  absolute numbers, since the route's menu-phase waits changed), H1 the
  wait itself must fall, H2 pgraph.lock must stay flat (the lock analysis
  said it is never co-held here -- a mover here is a correctness red
  flag, not just a miss), **P1 is the explicit vcpusleep guard**: fps must
  rise, not just `lw` fall, or the outcome is scored Moved (vcpusleep's
  exact shape: wait relieved, fps flat/down) and not reported as a hit.
  F2 is the pixel/corruption leg in motion (shots + logcat), H0 is the
  no-hang leg (a missed unlock/lock pairing would hang or crash the PFIFO
  thread, not just read slow).

## 4. First device runs (brief step 4's two-pacing-check, 2026-10-10)

Queued on the Nova once the hold from host maintenance lifted
(`jobs/hold.sh who nova` -> `free: nova`, after returning `held: ...
bounded 30 min` on the first check):

- `1-1791616849-pfifowait1009-2796495` -- baseline, no env, `--perflog`,
  900s, `--no-expect "pre-arm route pacing-robustness validation, not a
  scored arm"`. This is step 4's run #1: does the corrected route (plain
  `wait`, no `waitfor`) survive the SHIPPED pacing end to end with no
  `ROUTE FAIL`. Queued behind `lane.surfgpudefault1009`'s active run on
  the Nova (intended -- its runs carry the release tier and go first per
  the brief's Rules section); still queued, not yet started, as of this
  writing.

Plan for run #2 (not yet queued, queue after #1's result is read): the
same route with `HAKUX_PFIFOWAIT=1` and no frametrace, matching run #1's
instrumentation, purely to confirm the route also survives the DIFFERENT
pacing the fix itself produces (the two-pacing-check brief step 4 actually
asks for -- flag on vs off is a real pacing difference on this title,
since it changes when the PFIFO thread blocks). If both come back with no
`ROUTE FAIL`, step 4 is satisfied and the scored A/B pairs (register:
section 3 above) get queued separately, with `HAKUX_FRAMETRACE=1` on
BOTH arms so `waits.py`/`workbin.py` have the `[hakuX-ft1]` lines the
prediction's legs read -- run #1/#2 above deliberately do not carry
frametrace, so they are pacing checks only, not arm data.

### Run #1 result -- PASS (2026-10-10 00:38-00:53 PDT)

`1-1791616849-pfifowait1009-2796495`: `run.log` line 1230, `ROUTE finished
(rc 0) after 896s; holding without input` -- no `ROUTE FAIL` anywhere in
the log. `logcat.txt` has zero `FATAL EXCEPTION`/`ANR in`/`Native crash`
matches. All 25 scripted steps plus the genre loop completed and produced
a shot/probe each (`route-frames/*.png`, 25 named steps + `gameplay`/
`hold` frames after). Eyeballed `s13-gameplay` (26 fps, snowboarding down
an open slope, player clearly in motion) and `s22-probe`/`s23-gameplay`
(29 fps, 23s apart, player weaving through a line of trees lining the
track, board angle and snow trail both changed between the two frames --
moving through the trees as an intentional obstacle section, not the
"parked against a tree" void pmucounters hit). Baseline pacing: route
holds up.

### Resume (attempt 2, 2026-10-10): why attempt 1 did not finish

Attempt 1 ended at 01:14 PDT having just queued run #2
(`1-1791618877-pfifowait1009-3451596`, `HAKUX_PFIFOWAIT=1` pacing, no
frametrace) and did not commit a `WAITING` file naming it, so nothing woke
the lane when the run finished (DONE at 01:25) -- per Addendum 2, this was
the exact "ended a turn waiting on a run with no WAITING marker" failure
mode the lane contract and this file's own earlier text warn about. No
code or route change was lost; only the result-reading and NOTES update
were outstanding. This attempt reads run #2's result below, merges
`origin/master` (15 commits behind at resume, all `surfgpu1009`'s own
files -- `git diff --stat HEAD...origin/master` touched none of this
lane's territory, confirmed before merging), and continues with the
scored A/B arms (brief step 5).

### Run #2 result -- PASS (2026-10-10 01:14-01:25 PDT)

`1-1791618877-pfifowait1009-3451596` (`HAKUX_PFIFOWAIT=1`, no
frametrace, otherwise identical request to run #1): `run.log` line 1229,
`ROUTE finished (rc 0) after 896s; holding without input` -- no `ROUTE
FAIL`. `logcat.txt` has zero `FATAL EXCEPTION`/`ANR in`/`Native crash`
matches. All 25 scripted steps plus the genre loop produced a frame (38
files in `route-frames/`, matching run #1's count). Eyeballed
`s13-gameplay` and `s23-gameplay` (both 29 fps): player under control,
different terrain and camera angle between the two, weaving past distinct
trees -- in motion, not parked or menu-stuck. The route also holds up
under the fix's OWN pacing (PFIFO thread blocks at different points than
shipped), which is what step 4's two-pacing-check actually asks for, not
just two runs of the same pacing. Both pacing checks pass; step 4 is
satisfied. Proceeding to the scored arms (step 5, prediction already
registered in section 3).

## 5. Scored A/B arms queued (brief step 5, 2026-10-10 ~09:17 PDT)

Pilot verdict written first: `$DISPATCH_DIR/pilots/pfifowait1009.ok`,
dated 2026-10-10 01:56 PDT, recording run #1/#2 above (route-holds-up,
not scored) as the pilot per the role contract's "queue at most two
first, write the verdict, then queue the rest." The gate's own stderr on
the third queued request confirms it was read: `pilot gate: pfifowait1009
would hold ~38 min of device time; reviewed pilot ... (0.0 h old) admits
it` (and again at ~54, ~71 min for the following two).

Before queuing: merged `origin/master` (15 commits, all `surfgpu1009`'s
own files, none touching this lane's territory -- `git diff --stat`
checked first) so the device-budget estimate and any shared-tree state
are current, per the lane contract's "merge before concluding anything
from this tree."

`--suites` built from `pfifowait1009-pgraph-inert.json`'s registered
`disc.suites` (27, not 26 -- miscounted when the brief's prose said
"26 suites" in section 3; the registered list itself, which is what
`must_not_move` actually checks, has always had 27) via `s.replace('_',
' ')` -- confirmed that is the right direction by reading
`ab_compare.py:1093` (`want = {s.replace("_", " ") for s in suites}`),
since request.sh's own examples (`uberspike569/host/requeue3.sh`) use
space-separated suite names and the registered JSON's names are the
underscored ab_compare.py-internal form.

| arm | id | what |
|---|---|---|
| pgraph A | `1-1791622671-pfifowait1009-332891` | 27-suite disc, no env, ref 221a22f5a8 |
| pgraph B | `1-1791622678-pfifowait1009-333205` | same suites, `HAKUX_PFIFOWAIT=1`, ref 221a22f5a8 |
| amped2 A run1 | `1-1791622681-pfifowait1009-333368` | `HAKUX_FRAMETRACE=1`, 900s, ref 221a22f5a8 |
| amped2 B run1 | `1-1791622686-pfifowait1009-333514` | `HAKUX_FRAMETRACE=1 HAKUX_PFIFOWAIT=1`, 900s, ref 221a22f5a8 |
| amped2 A run2 | `1-1791622691-pfifowait1009-333706` | `HAKUX_FRAMETRACE=1`, 900s, ref 221a22f5a8 |
| amped2 B run2 | `1-1791622692-pfifowait1009-333840` | `HAKUX_FRAMETRACE=1 HAKUX_PFIFOWAIT=1`, 900s, ref 221a22f5a8 |

All `--who pfifowait1009 --issue 433`, pinned `--device nova`, all scored
against their stated `--expect` prediction file (`ab_compare.py` for the
pgraph pair, `waits.py`/`workbin.py` by hand for the soak pair per the
prediction's own `judge` field). Queued at `release: '0.5'` priority
(auto-picked up from `#433`'s label) -- ahead of plain `study` requests
but, per the brief's Rules, still behind `surfgpu1009`'s and
`perdraw1009`'s own release-tier runs already queued or running on the
shared Nova.

Each `--env HAKUX_FRAMETRACE=1`/`HAKUX_PFIFOWAIT=1` soak request printed
a `WARNING: must_not_move has 1 entry on a SOAK` -- expected and harmless:
that field (the pgraph-inert cross-reference) is read by eye from
`NOTES.md` section 3's text, not by any tool on a soak result; the
warning is request.sh correctly saying so, not a problem with the queued
request.

NFS Most Wanted (the brief's second title, route read from
`lane/perdraw1009`, not edited) is NOT yet queued: its own A/B needs a
registered prediction first (none exists for it in this lane yet), and
that registration is the next step after reading these six results,
not before. Device time already queued here is ~71 min total
((900+90)*4 soak + the two pgraph discs, each materially shorter); adding
a third title's pair before reading what this batch shows would be
spending device time ahead of a decision it could change, which the pilot
rule and `balanced-not-cheap-first` both argue against.

### Ending this turn WAITING, not polling

Six requests queued, ~71+ min of Nova time, shared with two other lanes'
release-tier runs ahead of mine in queue order -- polling synchronously in
this turn risks either the turn ending mid-wait (attempt 1's exact
failure) or spending the whole turn blocked on `sleep` loops for no
benefit over a resume. Per Addendum 2: commit + push
`docs/lanes/pfifowait1009/WAITING` naming all six ids, then stop. The
next resume reads all six results, updates this file, and (if the soak
pair is a Hit/Moved/Miss per section 3's legs and the pgraph pair shows
`worse=0`) moves to registering and queuing the NFS MW pair, then
writes `PR.md` with `State: ready`.

## 6. Resume (attempt 3, 2026-10-10): why attempt 2 did not finish

Attempt 2 did not fail -- it ended its turn correctly, per the lane
contract's own rule ("if you are waiting, that is a finished session too"):
it queued all six scored requests, wrote and pushed `WAITING` naming them,
and stopped rather than polling or risking a repeat of attempt 1's silent
loss. All six were `DONE` by the time this session started (confirmed via
`dispatch/results/<id>/DONE` on all six paths before touching anything
else). This attempt reads them.

## 7. Scored arms read -- VERDICT: the fix is unsafe as implemented, FAIL on both legs

**Headline: do not ship `HAKUX_PFIFOWAIT=1`.** It is default-off and stays
that way. The pgraph disc leg found a real, device-reproducible rendering
regression; the amped2 soak leg found the fix makes the thing it targets
(off-CPU time, fps) *worse*, not better, in the vcpusleep shape the
prediction's P1 leg was written to catch. Below is each leg's reading
against the registered prediction (section 3), then a root-cause
hypothesis for the next lane -- not confirmed, since confirming it costs
more device time that a known-unsafe fix does not earn.

### 7a. pgraph-inert (correctness leg) -- VERDICT: FAIL, real regression

`python3 docs/testing/ab_compare.py --a <pgraph-A> --b <pgraph-B> --expect
docs/testing/predictions/pfifowait1009-pgraph-inert.json`:

```
VERDICT: FAIL -- 16 of 1060 checks violated
```

Two classes of mover, not one. The `Vertex_shader_rounding_tests`
`GeometrySubscreen`/`GeometrySuperscreen` deltas (1 to 800 px) are small
subpixel-rounding movers of the kind the suite is already known to be
sensitive to from a single run (one of the eight even *repaired* to exact,
`GeometrySuperscreen_0.5626`: 570 -> 0) -- plausibly single-run noise.
`Stencil` is not: **all 7 `Stencil` captures that were bit-exact on A moved
to exactly 30,000 differing pixels on B**, every one the same magnitude,
with the flag the only variable (one binary, `ref` identical on both arms,
confirmed by the tool's own PRE-REGISTERED/composition checks).

That uniform 30,000-px jump across 7 unrelated Stencil test variants, with
nothing else in the build differing, is not consistent with "camera jitter"
or "rounding" -- it reads as one systematic state corruption hitting every
stencil-op variant the same way. Per the tool's own caution ("one run per
arm cannot tell a change from device nondeterminism"), I did not stop at a
single run: a second, scoped A/B queued and read in this session (below)
confirms it is not noise.

**Determinism check** (not a scored arm -- `--no-expect`, queued after
reading the first FAIL, before writing any of this up): both arms re-run
at `--runs 3` on just `Stencil,Vertex shader rounding tests` (67 captures,
~7 min total device time -- small because the brief step 5 arm already
proved the 27-suite disc itself is cheap, 174s for one full run):

- `1-1791627956-pfifowait1009-1189883` (A, no env, runs=3)
- `1-1791627963-pfifowait1009-1190823` (B, `HAKUX_PFIFOWAIT=1`, runs=3)

`ab_compare.py --a ... --b ... --allow-same-binary`:

```
ATTRIBUTABLE to the change: both arms ran twice or more and each was
byte-identical with itself, so the device did not do this:
Stencil/Stencil_ZERO_ST_DT, Stencil/Stencil_ZERO_ST_DT_ZB
```

A ran 0 differing pixels on both captures, identically, in all 3 runs. B
ran exactly 30,000 differing pixels on both, identically, in all 3 runs.
Self-consistent on both sides -- the tool's own bar for "attributable to
the change, not the device" is cleared. Four other Stencil variants *did*
show a wide run-to-run band even within one arm (`Stencil_ZERO`: 0 ->
40,000 purely from re-running A three times) -- so this suite is partly
flaky on this device regardless of the flag, which is exactly why the
determinism check, not the single-run disc, is the one that counts: two
of the seven movers are real and reproducible, not noise.

**Conclusion:** the lock analysis in section 2 ("nothing inside either
wait touches any `d->pfifo` state ... there is no half-finished state for
`user_write` to race against") is contradicted by this measurement. Some
piece of GPU-visible state that the Stencil test path depends on IS being
left in a different condition when `pfifo.lock` is released around this
call, on this device, reproducibly. The analysis was wrong somewhere, and
I did not find where by further reading alone (candidates below) -- the
device told me it was wrong before the code review would have.

### 7b. amped2-soak (the brief's actual target metric) -- VERDICT: MISS, and worse

Basic sanity first, all four runs (`A run1/run2` = no env but
`HAKUX_FRAMETRACE=1`; `B run1/run2` = same plus `HAKUX_PFIFOWAIT=1`):
no `ROUTE FAIL`, no crash/ANR/FATAL in any of the four logcats, `ROUTE
finished (rc 0)` at 884-891s on all four, and the `[pfifowait]` startup
line (F0) present on exactly the two B runs and absent on both A runs --
the env reached the process on the arm it should and only that arm.

`python3 docs/lanes/pmucounters/waits.py <logcat>` on each of the four,
from `mark gameplay`:

| run | frames | wall ms/f | on-CPU ms/f | vw.pgraph.lock ms/f | vw.pfifo.lock ms/f |
|---|---|---|---|---|---|
| A run1 | 15240 | 27.01 | 22.48 | 2.37 | (not printed: ~0) |
| A run2 | 11160 | 36.90 | 29.44 | 3.39 | (not printed: ~0) |
| B run1 | 10680 | 38.58 | 30.57 | 6.50 | (not printed: ~0) |
| B run2 | 11220 | 36.87 | 30.20 | 5.46 | (not printed: ~0) |

`waits.py` only prints a `vw.*` component when it is nonzero over the
whole run; `pfifo.lock` (`vw[1]`, the exact counter the brief's `lw` names)
never printed on any of the four runs -- it is ~0 overall on this route
revision, on BOTH arms. That is **W1's premise failing outright**: there
is no large `lw` for the fix to shrink here to begin with, contradicting
the brief's own cited absolute (4.6 ms/frame overall on an older route
revision) and pmucounters' own stand-in measurement. Whatever the STALLED
path's fence wait costs on Amped 2, it is not showing up as vCPU-visible
`pfifo.lock` wait on this route revision -- possibly because the longer
settle waits added to the menu phase in section 1 change how much the
vCPU is itself bottlenecked elsewhere before it ever reaches a DMA_PUT
store, or possibly because this title's gameplay segment does not drive
the STALLED branch (`pg->draw_time != r->last_stall_draw_time`) as often
as pmucounters' route did. Unmeasured which; see candidates below.

**`pgraph.lock` (`vw[2]`) is NOT flat (H2 fails).** B's whole-run average
is 5.46-6.50 ms/frame against A's 2.37-3.39 -- roughly **double**, on a
lock the fix's own code never touches and section 2's analysis said is
"never co-held here." `workbin.py` (binned by matched vCPU work per frame,
so a scene/route difference between runs is not misread as the arm's)
confirms it is not a whole-run artefact of A and B riding different parts
of the route -- it holds *at every matched work bin*:

```
work bin ms/f | A1 lock474 | A2 lock474 | B1 lock474 | B2 lock474
21-23         |   4.34     |   5.92     |  10.94     |  12.10
23-25         |   5.00     |   6.10     |  13.18     |  10.89
25-27         |   3.06     |   3.92     |  17.47     |  10.98
27-99         |   7.39     |   2.69     |  21.53     |  14.39
```

(`lock474` here is the vCPU's PGRAPH MMIO wait for `pgraph.lock` --
`waits.py`'s `vw.pgraph.lock` and `workbin.py`'s `lock474` column read the
same `[lock474]` logcat lines, just aggregated differently.) At every work
bin from 21 ms/frame up, B's `pgraph.lock` wait is roughly double to
triple A's, growing WORSE as the bin gets slower -- the opposite of what a
fix for a slow-window bottleneck should do.

**fps does not rise (P1 fails) -- it falls.** Same `workbin.py` table,
`fps` column, at matched work:

```
work bin ms/f |  A1   A2  |  B1   B2
21-23         | 29.3 26.1 | 22.5 23.9
23-25         | 26.8 24.2 | 24.1 23.9
25-27         | 25.0 24.5 | 20.8 23.7
27-99         | 22.0 23.8 | 18.3 20.7
```

B is lower than both A runs in every one of these four slower bins (the
ones that matter per the brief's own framing: "9.7 ms/frame in windows
under 24 fps"). This is **P1's exact named failure mode** -- "a run where
H1 passes but P1 does not is NOT a hit, it is exactly vcpusleep's
prior-art failure mode" -- except here H1 cannot even be evaluated (lw is
~0 to begin with), so this is worse than Moved: the thing the fix bracket
removed from `pfifo.lock`'s critical path reappeared as *more* contention
on `pgraph.lock`, net fps down, on the title the brief named as the
motivating case.

Per the prediction's own `outcomes` field this is scored **Miss** (H1
fails -- lw does not fall by half in slow windows, because there was no
lw to fall) with the H2 failure flagged separately as a correctness
concern per the prediction's own leg text ("ABOVE means something
co-holds or re-takes pgraph.lock inside the bracketed span that the lock
analysis in NOTES.md section 2 missed -- a correctness concern, not just
a miss, and the fix needs re-reading before it ships"). Combined with 7a,
this is not a borderline miss worth widening the bracket over -- it is
two independent instruments (a disc test and a gameplay soak, neither
touching the other's code path) both saying the same thing: this
particular lock-release bracket is not safe.

### 7c. Root-cause hypothesis (unconfirmed -- for the next lane, not spent on more device time)

Reading `reports.c:400-425` again against both findings: the only state
this function writes after the (now unlocked) call is `r->last_stall_
draw_time = pg->draw_time` -- a plain write, immediately after re-taking
`pfifo.lock`, to state the lock analysis never claimed was protected by
`pfifo.lock` in the first place (it is presumably `pgraph.lock`'s, or
unprotected by design elsewhere). Two candidates, neither verified by
device time in this session since the device already gave a clear enough
verdict without pinning down the mechanism:

1. **Downstream pgraph.lock contention, not a new one.** Releasing
   `pfifo.lock` lets `user_write` (and whatever PGRAPH MMIO the vCPU
   touches next) proceed sooner during the STALLED wait than it could
   before. If the vCPU's next step after `user_write` is itself gated on
   `pgraph.lock` (held by the render/flip path per `#474`'s own pattern),
   the vCPU is not "freed," it is handed off faster to a *different*
   queue -- net neutral-to-worse exactly as vcpusleep found for a
   different pair of resources, and NOTES section 2's "nothing needs to
   notice the release" argument was about reentrancy into THIS function,
   not about what the vCPU does one step later with the time this bracket
   hands back to it.
2. **An actual data race in the STALLED path**, consistent with the
   Stencil disc regression specifically: something `pgraph_vk_finish`
   reads or writes during the frame-slot rotation or the `#804` occlusion
   wait is not in fact `pfifo.lock`-independent the way section 2 argued.
   `r->last_stall_draw_time`'s write, or something inside
   `pgraph_vk_finish`/`_internal` touching `r->report_queue` or a frame
   slot the render thread can also reach without `pfifo.lock` serializing
   against it, is the concrete place to look next -- not re-derived here
   because the two measurements above already answer the question this
   lane was asked (is shape (a), scoped to this one call, safe to ship)
   with a clear "no," and chasing the exact race would be more code
   reading, not more device time, so it belongs to whichever lane picks
   this up next rather than being guessed at here.

### 7d. NFS Most Wanted (brief's second title) -- NOT queued, and why that is the right call

The brief's step 5 asks for both titles' A/B pairs. I am not queuing NFS
MW's. The fix already failed decisively on title 1, on both the
correctness leg (a real, reproducible pixel regression) and the exact
performance metric the brief exists to move (fps at matched work, down
rather than up, in the slow windows that motivated this lane). A second
title's pair cannot change whether this specific implementation ships --
it is already unsafe -- so queuing it would be spending Nova time ahead
of a decision the data cannot still swing, which the role contract's own
ranking rule ("a cheap step goes first only when it decides something")
and `balanced-not-cheap-first` both argue against from the other
direction (don't spend low-probability-of-changing-the-decision device
time just because it is already budgeted). If a future lane revisits
shape (a) with the race in 7c fixed, NFS MW is the second title to run it
against, same as the brief says.

## 8. Outcome

`HAKUX_PFIFOWAIT=1` stays default-off, as implemented. This lane's job
was to implement candidate 1 behind a flag, register a prediction before
any arm, and read the device against it -- all done, and the prediction
did its job: it was written specific enough (H2's co-holds clause, P1's
vcpusleep guard, the pgraph disc's `must_not_move` list) to catch a real
regression instead of letting a partial win ("lw fell!" -- it did not
even measurably exist here) get reported as a hit. The umbrella issue
(#433) candidate-1 approach (shape (a), lock-release-only, scoped to the
single STALLED call) is falsified for Amped 2 on this build; pmucounters'
own candidate list (`docs/lanes/pmucounters/NOTES.md`, the ranked table)
is the place to pick up candidate 2, or a redone shape (a)/(b) that fixes
7c's race first, rather than re-running this exact bracket again without
addressing either finding above.
