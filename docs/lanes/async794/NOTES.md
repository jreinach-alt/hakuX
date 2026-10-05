# lane.async794: the synchronous surface download, off the render path (#794, #796)

Brief (2026-10-04): take the SURFACE_DOWN wait that lane.fps20786 measured
(13.8 ms/frame on NBA Live 2005 and Counter-Strike, 8-14 ms on the near-30 set)
off the render thread. Fix 1: record the download now, wait where the bytes
are consumed. Fix 2: release pgraph.lock across the wait (Top Spin, #796).

## Step 1 (offline): who pays the wait, per title -- it is not one caller

`sdcallers.py` splits each title's wait by the caller that submitted it, from
the `[sdcall]` lines fps20786's runs already carry, plus hakuX-stall's
download-if-dirty sources and the texture bind's direct downloads (`txr dl`).
fps20786 filed all of them under one name; the logs say there are three
callers, and they need different fixes:

| title (run) | caller | per frame | wait | who consumes the bytes |
|---|---|---|---|---|
| NBA Live 2005 (2876934) | `reuse`: unshelving a struct a pending download names | 1 finish | 11.4 ms | nobody, yet: bookkeeping only |
| Azurik (verdict433-2378176) | `reuse` | 1 finish | 3.3 ms | same |
| Counter-Strike (2876984, 3338415) | texture bind, surface at the address refused by `check_surface_to_texture_compatiblity` (`txr dl`) | 2 | txw sdl 13.7 ms | the texture upload, on the CPU, at once |
| Top Spin (2538884) | texture bind (`txr dl`) | 26.4 | txw sdl 16.4 ms | same; and the vCPU waits for pgraph.lock behind it |
| ToeJam & Earl III, BloodRayne, Burnout, Nightfire | texture bind (`txr dl`) | 1-1.2 | -- | same |
| Midtown Madness 3 (slowtier2-mm3184014) | `surfupd` (6/frame, 5.0 ms) + texture bind (2) | | | the binding's upload / the texture upload |
| Midnight Club 3 (2878057), Nightfire (memfast-1478575) | `range`: a texture/vertex/blit range over a dirty surface | 1 | 6.9 / 6.3 ms | the reader, on the CPU, at once |
| Halo 2 (lanelocal-4097992) | `surfupd` 1 + `tobuf` 0.5 | | 4.2 + 2.3 ms | |

So "wait at the guest's next sync point" (fix 1 as briefed) applies only where
nobody consumes the bytes before the guest could: NBA's (and Azurik's)
`reuse`. In the texture-bind class -- seven titles, the largest -- and in the
range class the consumer is the emulator itself, on the CPU, immediately; no
amount of deferral removes that wait. What removes it is a GPU-side path from
the surface image to the texture (convert on the GPU, no round trip through
VRAM), which is the approach that fits a renderer whose surfaces already live
in VkImages. Which conversion is needed depends on *why* the bind refused the
surface, and nothing logged says that yet. Hence the instrument below.

## What B (c825e4b24f) does

1. **Fix 2 (#796).** `pgraph_vk_finish(SURFACE_DOWN)` on the PFIFO thread waits
   for the GPU with pgraph.lock released (`pgraph_lock_release_for_fence`), as
   `wait_frame_fence` already did for the same downloads' fence waits; and
   `download_surface_complete_deferred` now releases it for every PFIFO-thread
   caller (it did for `surfupd` only). Same safety argument as #474: on the
   PFIFO thread a finish runs inside a method or the flip-stall path under the
   lock; the render thread takes no pgraph.lock; only the guest's INTR/regs
   MMIO runs in the window (STATUS and RDI_DATA reads are still held to the
   method end), and every other taker settles. 0xb10 is PATT_COLOR0, an
   unsettled read.
2. **Fix 1 at NBA's site (#794).** Two parts, because the first alone would
   only have moved the wait:
   - the `reuse` site detaches the struct from its pending download
     (`deferred_downloads_clear_surface`) instead of completing the batch with
     a finish. The detached entry still writes VRAM, marks the range for the
     texture cache, and still answers `deferred_downloads_overlap_range` for
     every reader and the CPU-access watch.
   - each staged download carries its own submission's frame slot. Before,
     the batch had one fence, so the first download recorded after a finish
     had submitted the batch had to complete it (`complete_submitted_downloads`)
     -- with the flip's pre-download in it, that is a wait for the whole
     previous frame at the next frame's first eviction. NBA's ping-pong evicts
     every frame, so without this the 11.4 ms would have reappeared there.
     Now entries complete as a prefix in record order (= submission order):
     at their slot's finish, at the rotation into their slot, at
     `flush_all_frames`, at the next flip's pre-record (submitted ones only,
     never a finish), or when a reader needs the bytes.
   - staging becomes a ring reclaimed from the front, because the pending list
     no longer empties once a frame (it used to rewind the offset only then).
3. **Instrument.** `txdl[...]` on the hakuX-stall `txr` line splits the texture
   bind's direct downloads by the first compatibility test that refused the
   surface (levels, dim, cube, pitch, swz, cvt, bpp, upl, oth); the first four
   of each reason are logged as `[txdl794]` with both shapes. `reuse_detach=`
   on `[sdcall]` counts the detaches.

Checked offline: compiles with the desktop build's flags, plain and
perflog+`__ANDROID__` (`cc_check.py`, with a stub `<android/log.h>`), no new
warnings. Not built for Android here; the dispatcher builds the refs.

## Registered before any device run (this commit)

- `async794-download-paths-must-not-move.json`: golden arm, ten suites that
  read surfaces back, `worse=0`. The arms job runs it.
- Soaks, hand-read, A = master 5e4196fefd, B = c825e4b24f, Nova, perflog both
  arms: `async794-nba2005-soak` (the claim: ph_Fin <= 2.5, F - Ri <= 26;
  falsifier: ph_Fin > 8, or the wait reappears in another caller or in rblk),
  `async794-topspin-soak` (#796: lock wait <= 3 ms, rd_unl > 0, share >= 0.90),
  `async794-cs-soak` (predicted INERT; run for the txdl reasons),
  `async794-mc3-soak` (predicted inert; regression check),
  `async794-burnoutrev-soak` (regression check only: it already clears 30 at
  0.972, targets.toml, so it cannot be a new Playable from this lane).

P x titles, restated on the evidence above (the brief's 2.2 assumed one
mechanism for all five): fix 1 as built moves NBA 2005 (P 0.35 to 30) and
maybe Azurik; fix 2 moves Top Spin (P 0.6); Counter-Strike, MC3 and the
texture-bind set need the GPU-side path, P not yet estimable until txdl says
which conversion. About 1.0 now, with the larger share behind the txdl reading.

## Routes

`make-routes.py` writes `routes/async794-cs.route` (fps786-cs with B after the
loop's A, to close the weapon wheel) and `routes/async794-topspin.route`
(fps786-topspin without the step-24 START that paused the match).

## State at the end of session 1 (2026-10-04 ~15:40Z): waiting

- Pilot queued on the Nova, behind lane.pathfind's hold:
  A `1791128020-lane.async794-3209876` (master 5e4196fefd), B
  `1791128026-lane.async794-3210567` (c825e4b24f), NBA Live 2005, 800 s each
  (trimmed from 880 so the pair fits the 30-minute pilot gate). lane.local
  asked for a window on #794 (comment 14793).
- The golden arm (`async794-download-paths-must-not-move.json`) is the arms
  job's to queue.
- Next session: read the pilot with decompose.py and sdcallers.py against the
  NBA legs; if X1 fires (the wait moved), stop and report. Otherwise write
  `pilots/lane.async794.ok` (python3) and queue the other eight: Top Spin,
  Counter-Strike, MC3, Burnout Revenge, A and B each. Routes are resolved only
  from `docs/testing/titles/routes/`: copy `routes/async794-*.route` (and
  fps20786's `fps786-nba2005.route`) there untracked, queue, delete them.
  Then post per-title numbers in OUTBOX.md and read CS's txdl[] reasons for
  the GPU-side texture path.
- preflight: every gate passes but `coverage` (six board issues with neither
  lane nor blocker), which is the board's.

## Session 2 (2026-10-04, attempt 2): why session 1 did not finish

Session 1 ended correctly in a wait: the two pilot runs were queued behind
lane.pathfind's Nova hold and had not run. It left no `[lane.async794]
waiting:` comment, so lane.local wrote `WAITING` (fdc305f805). Both runs
finished afterwards (DONE 0), and attempt 2 is the resume that reads them.

## The pilot: fix 1 is refuted (the wait moved), fix 2 acts

NBA Live 2005, 800 s, Nova, perflog, the same route on both legs. Both reached
gameplay (frames by eye: a live game, no stale or torn surfaces in B). Neither
logcat has a validation, device-lost, assert or crash line.
A `1791128020-lane.async794-3209876` (master 5e4196fefd, apk 63f4c763dc9a),
B `1791128026-lane.async794-3210567` (c825e4b24f, apk dd99b818c691).

decompose.py, all 2-s rows after the mark (286 / 283):

| | fps | F ms | ph_Fin | ph_Tot | Ri | rblk | lockw | v_blk | share >= 28.5 |
|---|---|---|---|---|---|---|---|---|---|
| A master | 25.89 | 38.63 | 13.40 | 27.40 | 4.15 | 10.48 | 3.38 | 3.86 | 0.20 |
| B fix | 25.34 | 39.46 | 13.80 | 28.10 | 4.50 | 10.85 | 0.27 | 0.88 | 0.19 |

sdcallers.py:

| | caller | fin/frame | wait ms/frame |
|---|---|---|---|
| A | `reuse` | 1.00 | 11.18 |
| B | `surfupd` | 1.00 | 11.48 |

**X1 fires on both counts.** ph_Fin stays at 13.8 ms (> 8). The one finish a
frame did not go away. It moved from `reuse` to `surfupd`, the same size.
By the brief this is not a win, and no second theory is stacked on it here.

Why it moved (read from the code, not measured separately): the unshelved
struct is rebound with `upload_pending`, because its image is not trusted
while a download from its previous life is pending.
`surface_update_may_defer_downloads` refuses to defer when a binding is about
to upload from VRAM, so `pgraph_vk_surface_update` completes the detached
download with a finish, then uploads those same bytes back into an image. So
NBA's download *does* have a consumer before the guest's next sync point: the
emulator's own round trip, image -> VRAM -> image. Deferral cannot remove
that. What could is not doing the round trip: keep the shelved image as the
rebinding's contents when the CPU-access watch saw no guest write in between.
That is a new theory, so it needs its own brief and prediction; it is not
attempted here.

Fix 2's mechanism acts on NBA: the vCPU's lock wait falls 3.38 -> 0.27
ms/frame and v_blk 3.86 -> 0.88. NBA's fps is unchanged, which is expected:
NBA's frame is the renderer's, not the lock's. Top Spin's premise is 13.6 ms of
lock wait, so its pair is the test of fix 2.

## Queued after the pilot review (pilots/lane.async794.ok written)

Only the fix-2 test, `async794-topspin-soak.json`, 990 s each, Nova, behind the
pathfind hold:
A `1791135713-lane.async794-3678571` (master 5e4196fefd),
B `1791135717-lane.async794-3678947` (c825e4b24f).
The CS / MC3 / Burnout Revenge pairs are not queued. Their predictions were
for fix 1 (CS's was INERT, kept only for txdl reasons, and MC3's and
Burnout's were regression checks), and fix 1 is refuted. The golden arm
(`arms-async794-base/fix`) is still in the queue; it is the arms job's.

Next session: read the Top Spin pair against the prediction's legs (P0 in A,
F1/P1/P2/X1 in B), post the numbers in OUTBOX.md and on #796, then decide
the PR. If fix 2 passes, the fix-1 half is dead code that costs nothing on
NBA, but it is unproven elsewhere: strip it to fix 2 alone or keep it.
Decide that on the golden arm's verdict.

## Do not repeat

- Do not detach or defer a pending download whose surface is about to be
  rebound with `upload_pending`: `surfupd` completes it on the spot (pilot
  above). Deferral removes a wait only when no emulator-side reader exists
  before the guest's sync point; check `surface_update_may_defer_downloads`
  and the upload path, not just the call site you moved.

- Do not read fps20786's "sd" column as one mechanism. `[sdcall]` names the
  caller; `txr dl` names the texture bind's own sync download, which
  `[sdcall]`'s `tobuf` column does not time (it times only the completion at
  its entry).
- Removing a completion is not removing a wait when a later record must
  complete the same batch: check `complete_submitted_downloads`-style forced
  completions downstream before claiming a wait is gone.

## Session 3 (2026-10-04, attempt 3): why attempt 2 did not finish

Attempt 2 ended correctly in a wait: the Top Spin pair was queued behind
lane.pathfind's Nova hold, and `WAITING` named both run ids. Both finished
(DONE 0); attempt 3 is the resume that reads them. Nothing was lost.

## Top Spin: fix 2 removes the lock wait, and the fps does not move

990 s, Nova, perflog, route `async794-topspin` (no step-24 START) on both legs.
A `1791135713-lane.async794-3678571` (master 5e4196fefd, apk 63f4c763dc9a),
B `1791135717-lane.async794-3678947` (c825e4b24f, apk dd99b818c691).
Both play a live exhibition match (shots by eye, early and late; B shows no
stale, torn or black surfaces). Neither logcat has a validation, device-lost,
assert or crash line.

decompose.py, all 320 2-s rows; `[lock474]` over the last 300 windows (600 s):

| | fps mean | fps median | share >= 28.5 | F ms | lockw | v_blk | gidle | timer_ms | read wait/frame | 0xb10 wait/frame | rd_unl |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A master | 36.58 | 36.50 | 0.963 | 27.34 | 10.50 | 10.67 | 0.56 | 0.49 | 10.14 | 10.12 | 0 |
| B fix | 35.85 | 35.82 | 0.963 | 27.89 | 0.40 | 0.75 | 15.67 | 12.55 | 0.41 | 0.40 | 308342 |

Legs of `async794-topspin-soak.json`:
- M0 holds (495/496 `[lock474]`, 660/667 `[sdcall]` lines, play in the shots).
- F2 holds (shots, logcat).
- P0 holds: A's read wait 10.14 ms/frame, 0xb10 leading, rd_unl 0.
- F1 holds: B's rd_unl 308k.
- P1 holds: B's read wait 0.41 ms/frame (<= 3); v_blk falls 9.9 ms (>= 8).
- P2 holds, but only because A already passes: share 0.963 in both.
- X1 does not fire: the read wait is 0.41, and the median fell 0.68 (< 1.0).

What it means. The mechanism acts exactly as predicted, and buys no frame
rate: the ~10 ms the vCPU used to wait for the lock it now spends idle in
the guest's timer wait (gidle 0.56 -> 15.67, timer_ms 0.49 -> 12.55). The
guest was never late because of the lock; its frame is paced elsewhere. So
fix 2's P x titles on Top Spin is 0, not 0.6.

The real Top Spin finding is the route. On master, with the step-24 START
removed, Top Spin plays at 36.5 fps median with 0.963 of its rows above the
bar. fps20786's 0.89 (2538884) was a match that the route had paused. Top
Spin is a Playable candidate on master today, pending the 600-s held run,
the frame review and the owner's flicker check. That is the PM's to queue.

The `txdl[]` instrument answers the texture-bind question for Top Spin: all
27 downloads a frame are refused for `cvt` (surface 64x128 swizzled colour,
2 bytes per pixel; texture format 0x5, a converted format, same size). A
GPU-side path for Top Spin's class is a format conversion on the GPU, not a
pitch or swizzle copy. Top Spin no longer needs that path for the bar.

## The fold form: fix 1 stripped (2344ae1ee2)

The golden arm on c825e4b24f passed byte-identical (all 266 captures,
`1791129309-arms-async794-fix-3307191`), so fix 1 is safe as far as the
suites can tell. It still goes out: on NBA it only moved the wait, it buys
nothing measured anywhere, and its per-submission slots and staging ring are
350 lines of completion-order logic nobody needs. The branch merges master
(425ffe1ad1) and keeps only:
- fix 2: the SURFACE_DOWN finish and the deferred-download fence waits release
  pgraph.lock on the PFIFO thread. These are the same lines that ran in B.
- the `txdl[]` / `[txdl794]` instrument.

118 lines against master. They compile, plain and perflog+`__ANDROID__`
(`cc_check.py`), with no new warnings. The folded form is a subset of what
ran, but it was not run as itself. `async794-fix2-must-not-move.json`
(a = 425ffe1ad1, b = 2344ae1ee2) is registered for the arms job. Top Spin is
not re-run on it: the lock-release lines are the ones measured, and the
result the run would confirm is a lock wait that buys no fps.

Release note: none. No player-visible change was measured.

## P x titles, restated after the evidence

- Fix 1: refuted on NBA (the wait moved). 0.
- Fix 2: acts, and moves no fps on Top Spin or NBA. 0 in fps; it frees vCPU
  time in any title whose vCPU polls PGRAPH during a download.
- Top Spin: about 0.8 to Playable on master with the fixed route, from the
  0.963 share and the clean shots. The rest of the gate is still to run.
- NBA Live 2005, Counter-Strike, MC3, the texture-bind set: the wait is the
  emulator's own consumer (NBA: image -> VRAM -> image on rebinding; the
  texture-bind class: a CPU format conversion). Both need GPU-side work, and
  each needs its own brief. Not started here, per the brief's stop rule.

## Do not repeat (session 3)

- Do not read a lock-wait fall as a frame-time fall. Top Spin's vCPU wait
  went to the guest's timer idle. Check gidle/timer_ms with lockw.
- Re-run a title's control on a fixed route before you build a fix for its
  premise. Top Spin's "near-30" was a paused match.

## Session 4 (2026-10-04, attempt 4): why attempt 3 did not finish

Attempt 3 pushed the fold form and registered its golden arm, then ended
without a `State:` line in PR.md, so the fold queue never saw the PR as ready
once the arm passed. The arm was judged at 14:45 PDT: PASS, 266 of 266
captures same, no movers (`1791146467-arms-async794-base-1273188` against
`1791146467-arms-async794-fix-1273227`). This session adds `State: ready` and
does no device work. It does not queue Counter-Strike, MC3 or Burnout Revenge:
their pairs tested fix 1, which is refuted, and fix 2 claims no fps change.
The branch merges `origin/master` (10f14d301d) without conflicts, so the fold
can do that merge itself.

## Session 5 (2026-10-05, attempt 1 of the fold-gate brief): why session 4 did not finish

Session 4 did its brief (`State: ready`), but the fold queue still refused the
head aae14b6f54: the fold rule wants one finished, non-void device run built
from the head, because the PR changes emulator code. No such run could exist.
aae14b6f54 predates master's libfolders change (10f14d301d), and a build without
libfolders boots to the setup wizard on a device whose folder pref has been
migrated, so the soak voids. Session 4 noted the clean merge but left it for
the fold to do; the fold gate needs that merge on the branch.

This session merges origin/master (no conflicts; master's 80 surface.c lines
sit apart from the lane's 8), re-checks draw.c, surface.c and texture.c
(no errors, plain, perflog, and perflog+`__ANDROID__`; the three
unused-variable warnings in texture.c are master's, not this diff's), runs the
jobs selftest, and queues the one fold-gate run: a 120 s Nova hold at the
merge head. No fps claim, no pair.

Do not repeat: the selftest took longer than the Bash tool's 10 minutes here
(three selftests were sharing the host: master_selftest, a fold worktree,
this one), and `timeout 590` runs in the foreground kept cutting it off in
`51-dispatch-hardening` E2, which looked like a hang. It was not. Run it once
as an in-session background task with no timeout, and wait on that.
