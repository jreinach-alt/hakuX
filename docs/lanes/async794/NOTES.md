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

## Do not repeat

- Do not read fps20786's "sd" column as one mechanism. `[sdcall]` names the
  caller; `txr dl` names the texture bind's own sync download, which
  `[sdcall]`'s `tobuf` column does not time (it times only the completion at
  its entry).
- Removing a completion is not removing a wait when a later record must
  complete the same batch: check `complete_submitted_downloads`-style forced
  completions downstream before claiming a wait is gone.
