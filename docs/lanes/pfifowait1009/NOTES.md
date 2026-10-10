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
