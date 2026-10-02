# lane.collapse433 notes

#433 (0.5: 50 Playable). Brief: find why Battlefield 2: Modern Combat (and
Blood Wake) lose frame rate, with the Nova's data first; decide whether the
Thor's collapse is heat.

All reads are of COPIES of the result dirs (`scratch/`, not committed). Times
are device-log local time (PDT). Offsets are seconds after the run's
`ROUTE ... mark gameplay` line in `run.log`. Tools: `pacetab.py` and
`joinread.py` (this dir) bucket the always-on 2 s instrument lines against
that offset.

## 1. BF2 on the Nova (`1790877270-autoverdict-2187810`, ref ec244430e3)

verdict.json: gameplay 514.7 s, fps_ok_share 0.6655, fps_window_median 29.9,
min 16.47, `pace.late_per_100` 11.15, worst_stall 247.9 ms, no hang, audio
0.0% short, thermal measured (28 samples), no pause, regimen default.

**Shape: recurring dips that fade with time, not a collapse and not a flat
ceiling.** Per 30 s bucket after the mark (`joinread.py ... 30`):

| offset s | fps med | windows >= 29.5 | vbl Hz | main-loop timer late, max ms | deferred VBLANKs | grid clamps | TBs generated | guest idle % |
|---|---|---|---|---|---|---|---|---|
| 0-30 | 23.8 | 3/11 | 49.9 | 27.4 | 37 | 15 | 4307 | 4.8 |
| 30-60 | 27.1 | 4/12 | 54.3 | 23.0 | 20 | 6 | 1298 | 5.7 |
| 60-90 | 26.1 | 5/13 | 57.6 | 17.4 | 30 | 4 | 1004 | 13.3 |
| 90-120 | 29.3 | 6/13 | 59.9 | 6.5 | 12 | 0 | 562 | 15.3 |
| 150-180 | 28.9 | 5/13 | 59.5 | 10.2 | 21 | 1 | 314 | 6.7 |
| 180-210 | 27.6 | 6/14 | 57.8 | 19.4 | 16 | 2 | 257 | 12.9 |
| 210-240 | 26.8 | 4/13 | 55.8 | 23.3 | 21 | 4 | 207 | 10.8 |
| 300-330 | 30.0 | 13/15 | 59.9 | 1.6 | 0 | 0 | 122 | 20.4 |
| 360-390 | 30.0 | 15/15 | 59.9 | 3.8 | 1 | 0 | 101 | 22.8 |
| 420-450 | 30.0 | 15/15 | 59.9 | 5.6 | 0 | 0 | 93 | 23.8 |

Columns come from `hakuX-pace` (fps), `vbl n= ... rate=` (vbl Hz),
`vblphase ... nodef(max=)` / `def(n=)` / `clamp=`, `hakuX-pages inval ... cg=`,
and `[rr425w] idle_us/(idle_us+busy_us)`.

- The bad windows are the first ~300 s of the mission. After 300 s nearly
  every window is at 30. The game's pace is 2 VBLANKs per flip, i.e. 30 fps.
- In a bad window the VBLANK clock itself runs slow (50-58 Hz). The adaptive
  deferral in `nv2a_vblank_timer_cb` (hw/xbox/nv2a/nv2a.c) holds a VBLANK
  while the game is mid-frame. Late main-loop timers (17-32 ms) also trip the
  grid clamp, which discards the lateness. The deferral is the RESPONSE to a
  game frame slightly over 33.4 ms, not the cause. It turns a 35 ms frame
  into 28.5 fps instead of 20.
- **Guest idle is 5-13% in the bad windows and 20-24% in the good ones. BF2
  runs at the edge of the vCPU budget even when it holds 30.** This is the
  `[rr425w]` read that memory says to take first. A bad window is one where
  the guest's per-frame work goes over 33 ms.
- **The first minute is JIT warmup.** Translated blocks per window fall
  4307 -> 1298 -> 1004 -> 562 -> ... -> 65. In 0-60 s the sampled `[rr425]`
  estimators put 28-39% of vCPU wall time outside guest code (their
  `gapus`/`tbus` sum past 100% later, so they are only usable in the first
  minute). The 150-240 s dips have little codegen (200-300 TBs per window)
  and still show late main-loop timers and low guest idle. Warmup alone does
  not explain them.
- Scene weight is steady across the whole window: `[rdc]` vertex and texture
  upload counts, `Tq` and renderer idle `Ri` all hold flat. Renderer idle
  `Ri` is 15-24 ms per frame in every bucket, so **the renderer is not the
  bound.**
- Ruled out on this run: `ubo_ring_grow` reached its 16-pool cap at
  10:57:35, 3 min BEFORE the mark, and never logs again (the next log would
  be n256). `hitch_report.py`: 9 hitches, 2 shader-classified, both before
  9.2 s of offset. No `[pb569]` build or `dpm` in the bad windows.
- **Frames: only the mark frame exists** (`110044-gameplay.png`: first
  person, mission clock 00:20, in the level). The request had
  `frames_every 0`, so nothing shows whether the player kept moving for the
  514 s. The route is a blind walk/turn/fire loop. Scene-weight counters are
  steady, consistent with staying in the same area, but they do not prove
  movement.

## 2. The Thor runs: heat, by signature (no thermal record exists)

Neither Thor run has `thermal.jsonl`. Both ran `regimen=max` (perf_mode 2,
`perf_regimen.json`).

| run | launch (route start) | collapse starts | after launch | before -> after |
|---|---|---|---|---|
| BF2 `1-1790517591-titleroutes-1523259` | 08:07:09.8 | ~08:15:19 (mark+95 s) | 8 m 10 s | 19-24 fps -> 3.8-4.8 fps |
| Blood Wake `1-1790508532-titleroutes-1074940` | 04:31:25.6 | ~04:36:21 (mark+94 s) | 4 m 56 s | 37-39 fps -> 5.8-6.4 fps |

- A single step to a rate 5-7x lower, with no recovery. That is the
  thermal-pause-F8 signature (cpu3-7 paused, everything on cpu0-2). It is
  documented as 5-6 min from a cool start at MAX, and "fps 5-7x" (#507).
- **The VBLANK clock stays clean (59.9 Hz, no clamps) through the Thor
  collapse.** The Nova's dips are the opposite: a slow clock with late
  timers. So these are two different mechanisms.
- vCPU thread CPU (`[tlb68] cpu=` / dt) falls 93-96% -> 73-77% at the step.
  The thread is runnable but not running, which is what a run queue on three
  little cores looks like.
- The Nova runs the same route past the same offsets (90-300 s) at 26-30 fps
  with no step.
- **Verdict: heat artifact, not an emulator defect.** This rests on the
  signature, not on a cooling-device read. The Thor runs predate
  `thermal.jsonl`. Their refs (`3ea9cd9a34`, `7e38a5628d`) are older than the
  Nova's (`ec244430e3`) and carry no `[rr425w]` line.

## 3. Blood Wake on the Nova (`1790876348-autoverdict-2155592`): most of the window is not play

The brief's secondary question was the 21-callback audio burst at 10:44:51.
That burst is mark+131 s, and it sits exactly on a state change that the
rest of the run never leaves:

| offset s | fps | guest idle % | TBs gen | `Tq` | `[rdc]` vtx | renderer idle Ri ms | deferred VBLANKs |
|---|---|---|---|---|---|---|---|
| 0-128 (live) | 54-60 | 5-30 | 15-40 | ~1200 | ~1370 | 0.4-11 | 43-88 |
| 128-136 | 59 | 16-30 | **853, 1273** | -- | -- | -- | 5 |
| 136-667 | 59.9 flat | **0.0** | 1-9 | **32** | **420** | 15.6 | 0 |

- After 136 s the guest spends 100% of its time in one user-mode loop.
  `[rr425pc]` top entry is `g:000d2410` at 51,867 per window, and `[rr425w]`
  books all 2.01 s to one class. The renderer is idle 15.6 of 16.7 ms.
  Texture-dirty queries fall 1200 -> 32 and vertex uploads fall to 30%. For
  531 s nothing moves in the counters.
- This looks like a static screen (mission-failed, pause or results) that
  the blind RT/stick loop does not leave. No frame after the mark exists
  (`frames_every 0`) to say which.
- **Consequence:** Blood Wake's accepted 99.47% (OWNER_ACCEPTED.txt) rests on
  ~131 s of gameplay plus ~536 s of what is very probably a menu or
  static screen. The audio burst is the transition into it: a code burst of
  853 + 1273 TBs at mark+128-136 s, the same shape as the pre-mark
  short-callback bursts at load transitions (10:40:13, 10:40:28, 10:41:51).
  It is not a gameplay stall.
- The Nova Blood Wake run therefore says little about a collapse past
  131 s. Its 0-131 s of live play ran 54-60 fps in unlock mode, past the
  Thor's 94 s collapse point.

## 4. Nova perflog soak (step 3)

(pending; see section 5 for the request id)

## Process notes

- The brief asks for the soak "under `hold.sh wait nova collapse433:$$ 900`".
  A hold makes the Nova's dispatcher claim nothing (`dispatcher.sh`, top of
  the serve loop), so a hold taken by the requester blocks its own request.
  I queued the request without a hold. It is hard-pinned to the Nova, and the
  queue serves one request at a time per device anyway.
- `request.sh` reads the issue's labels with `gh api` for release priority,
  and `gh` is down. `HAKUX_RELEASE_PRIO=1` skips the read: #433 is the 0.5
  issue.
