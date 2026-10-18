# ralli2audio1018 notes

RalliSport Challenge 2 (4D530039) on the Nova, owner hand-play 2026-10-18
10:19-10:29 PDT. Scorer: fps_ok 0.9873, window median 59.76, gameplay 514 s,
audio_starve_share 0.0134 (bar 0.001), 3 hitches after warm-up, worst 1403 ms.

## Step 0: already tried (read before doing anything)

| Source | What was tried | Measured | Concluded / do not repeat |
|---|---|---|---|
| docs/investigations/audio-baseline.md s4 (383-505) | starve counter design; Galleon on the Thor, 120 s | 21/2936 short, all empty, all at startup; steady state 0/704 x4 | a merely-late producer gives PARTIAL fills; sink asks 8192 B; callback waits <= ~5 ms. Not a stress title, not the Nova |
| docs/investigations/audio-voice-headroom.md F1 | level meter on the audio thread | steady state 0.0000% on Galleon/DOA3/Crimson; startup windows 15-55% (empty calls) | startup starve is expected and excluded; steady starve is title/load specific |
| docs/investigations/audio-harness.md | PCM capture to FUSE from the APU thread | | capture itself can starve; the `starve:` line says `capture ARMED/off` (off in this run) |
| docs/lanes/nfsaudio1011 | buffer 256/512 samples; lock waits; `HAKUX_APU_PACE` | AAudio drains 1920 (2x960) regardless; BQL/voice-lock waits p50 19 us, max 97 us; pace cut NFS replays 15.7% -> 0.0% | pacing is now default on (apu.c:128-140). Shrinking the device buffer does nothing. Do not re-derive the burst mechanism |
| docs/lanes/audio1016 | MON_VP downmix; DSP path on MKSM | DSP path util 0.68 vs 0.26, starve 0.0% | the Nova keeps up with the DSP path on MKSM; do not expect DSP cost alone to starve |
| docs/lanes/forza414 | regime step (2-3 fps) | zero-fill 0.06% -> 40-47% in the same 2 s as the stall; perflog rerun did not reproduce (0%) | lock-step suspected (BQL or guest GPU wait), never named |
| docs/lanes/kabukistall | 20-130 s PFIFO compile stalls | `starve: 0/703` through the stall | a PFIFO/render stall ALONE does not starve audio |
| docs/lanes/idlehalt*, idlehaltdefault | `HAKUX_IDLE_HALT` (opt-in, off by default) | starve 0 on AUF/Blinx; DOA1U flipless 0.0048 on / 0.0077 off | idle halt is not an audio lever; off in this run (`[idlehalt] on=0`) |
| docs/lanes/fabledip1018 FINDINGS | Fable cold start | 2570 ms frame + 75.7% starve in one 5 s window, render idle, no compile | one-time cold-start cost, unnamed (asset I/O suspected) |
| docs/lanes/pipeline413, shaderfb569, shaderplan569 | `[shd413]` creation timing | 96% of a miss is Turnip inside vkCreateGraphicsPipelines on PFIFO; ~350-400 ms/create | async_compile as built still waits; module warm-up < 1%. Ranked plan in shaderplan569 s7 |
| docs/lanes/shaderprebuild569 | compile pool (3 workers), per-title key records, pre-build at renderer init (default on), cache save off PFIFO; GPL ladder `HAKUX_GPL=3` | warm cache: 43 creates 4661 ms -> 1-2 ms (Arctic Thunder); DOA pre-build 640 jobs/57 s | pre-build works on the SECOND run of a title once keys are recorded; new content still compiles cold. Shipped key sets designed, not built |
| pathfind rallisport2-1006 (compatrefresh1013/registry.tsv:578) | 10-06 route run | audio 0.230% short, fps_ok 0.9646, 602.6 s | failed on audio before this capture too |

Device env in this run (from the capture): `apu_pace: on (default)`,
`apu_meter: off`, `capture off`, device buf 8192 B, FIFO 49152 B,
`[idlehalt] on=0`, driver `PurpleVK-public Adreno (TM) 740` (not stock).

Correction to the brief: the `starve:` line is emitted at most every 5 s and
only when its interval had a short callback (or as a 30 s heartbeat); each
line is the DELTA since the previous line, not cumulative (apu.c:366-381).

## Work 1: what fed the FIFO late (offline, owner capture)

Tool: `tools/timeline.py LOGCAT --from 38045 --t0 10:20:26` (t = seconds
after 10:20:26, the first race's start). Each row is one starve window
(starve lines are deltas):

| window (s) | short/calls | zero-fill | frame max ms | draw-thread create ms | JIT TBs | vCPU busy |
|---|---|---|---|---|---|---|
| 14.2-39.0 | 2/582 | 64 ms | 580 | 311 | 3554 | 37% |
| 39.0-58.4 | 1/456 | 5 ms | **1403** | 402 | 23347 | 73% |
| 58.4-63.4 | **48/117** | **597 ms** | 774 | 466 | 10078 | 76% |
| 68.4-78.4 (2 rows) | 27/234 | 480 ms | 144 | 150 | 3705 | 96% |
| 104.3-109.3 | **49/117** | **912 ms** | 410 | 261 | 618 | 92% |
| 109-420 (tail, 25 rows) | 1-4 per row | 5-43 ms per row | <= 121 | 0 to 65 | | 97-99% |
| 420-510 | 0 | 0 | | | | |

**The producer stops; the sink does not burst.** The level meter
(`hakuX-audio: level L: <s>`, apu.c `apu_level_observe`) counts the
samples the APU frame thread pushes into the FIFO, cumulatively. Its
advance per 5 s line against wall time:

| level window (s) | wall s | audio produced s | deficit ms | zero-fill nearby |
|---|---|---|---|---|
| 34.2-39.2 | 5.000 | 4.918 | 82 | 64 ms (14-39) |
| 54.2-59.2 | 5.000 | 4.736 | 264 | |
| 59.2-64.2 | 5.001 | 4.661 | 340 | 597 ms (58-63) |
| 69.2-74.2 | 4.999 | 4.768 | 231 | 240 ms |
| 74.2-79.2 | 5.001 | 4.736 | 265 | 240 ms |
| 104.2-109.2 | 5.001 | **4.085** | **916** | **912 ms** |
| before the race, and 420-510 | 5.00 | 5.00 +- 0.007 | <= 7 | 0 |
| tail rows (109-420) | 5.00 | 4.955-5.045 | -44 to +45 | 5-43 ms |

The deficit equals the zero-fill to within one callback. The APU frame
thread produced 4.085 s of audio in 5.001 s of wall time at 104-109 s. A
sink that drained in bursts would show zero-fill with no producer deficit.
In the tail, production wobbles +-45 ms around real time. Paced at the
mid watermark (16 KB), the FIFO holds one 8 KB callback plus 42.7 ms of
cushion, so a wobble over ~43 ms at the wrong moment gives a partial short
of 1-4 KB.

**The 1403 ms freeze does not starve the audio** (1 short in 456, 5 ms of
zero-fill, in its window). **The big losses sit in shader-compile bursts:**

- 58-63 s: the uber ladder's background workers did 6.1 s of compile in
  about 3 s (`[uber569] next_ms` 10077 -> 16192 between 10:21:23.5 and
  10:21:26.8), and one uber library took 4.2 s on a worker (`lib_ms`
  0.2 -> 4220.8).
- 104-109 s: the draw thread compiled 28 fragment libraries
  (`[gpl569] lib_ms` 701.7 -> 944.7) and 47 pipelines (260 ms).

The frame thread itself has no reason to wait on a compile. Its only
lock outside its own is the BQL, for an interrupt update after a voice
notification (apu.c frame thread loop; vp.c sets `set_irq` on every
notify). Its throughput is a fork-join over 4 voice workers per 5.33 ms
EP frame. Both are exposed to CPU contention: compile workers, PFIFO, the
vCPU (97-99% busy) and the voice workers all run at nice 0 on 8 cores.
Which of these stopped it, the capture cannot say. It has no
producer-side timing.

## Work 1: the instrument added

A `prod:` line (tag hakuX-audiocap) after every starve line, from the same
counters window (apu.c `apu_prod_report`):

- producer blocks, free-run blocks and pacing resets;
- the lowest FIFO level;
- the longest gap between pushes;
- wall and thread-CPU ms per block (wall well over CPU = off CPU);
- the voice fork-join us per VP frame;
- the longest BQL wait;
- run-queue wait from `/proc/self/task/<tid>/schedstat`, for the frame
  thread and the voice workers;
- the CPU histogram of the pushes;
- on the sink side: the callback count, the longest callback gap, and the
  lowest entry level. For the worst short, it gives the bytes missing,
  the level found, the time since the last push and the time since the
  previous callback.

It is not perflog-gated. That is deliberate:

- It prints only when the starve line prints: at most every 5 s, and only
  with a short or as the 30 s heartbeat.
- It costs two clock reads, one thread-CPU read and one getcpu syscall
  per 5.3 ms block, and two preads per report.
- The failure it explains shows up in owner play on release builds,
  where perflog is off. forza414's perflog rerun did not reproduce its
  stall.

## Work 1: the change

1. `HAKUX_APU_PRIO` (default on; `=0` leaves the threads as created) sets
   the APU frame thread and every voice worker to nice -16 at thread start.
   That is Android's THREAD_PRIORITY_AUDIO, the value SDLAudioManager
   already gives its own audio threads. It logs `apu_prio: on|off ...
   N of M set`.
   - It fits the measured shape: the producer falls behind real time
     while other work saturates the cores, and a 1500 Hz fork-join is the
     most wake-latency-sensitive work in the process.
   - It cannot take more than the audio needs, because the FIFO paces it:
     at the high watermark the thread sleeps.
   - It does not help if the stop is a BQL wait. The `bql=` field says
     whether it is.
2. `HAKUX_APU_CUSHION=N` (opt-in, 1-4, default 1) paces the FIFO N device
   periods deep. Each period adds 42.7 ms of latency. It is for the tail
   if the priority alone does not close it. It is off by default because
   latency is a cost the player hears.

## Work 2: the 1403 ms freeze (10:21:20.8, 55 s into the race)

Not a shader or texture compile (draw-thread create 0.1 ms in its frame).
In the same seconds:

- the DVD went idle for 1.41 s (`[ide425d] gap_us_max=1409801`), then
  read a 25.7 MB burst;
- the vCPU discarded 2035 translated blocks (guest stores over code) and
  translated 18607 (`hakuX-pages`);
- vCPU busy 99%, and 10529 guest page faults in the 2 s (`[tlb68] pf`).

At 50-75 us per block that is 0.9-1.4 s of translation. The guest
replaced code in memory (a level-section load) and the JIT re-translated
it before the next read. Removing it is vCPU JIT work: translation cost,
or keeping translations across a reload of identical code. That is
outside this lane's files. It does not starve the audio (above).

## Work 3: the shader hitches (580, 774, 410 ms)

What the cache did in the owner's run:

- `[pb569] start title=4D530039 records=0 jobs=0`: the launch pre-build
  had nothing to build.
- In GPL mode (`HAKUX_GPL=3`, the shipped default), `draw.c` returns from
  its GPL branch (3469-3569) before `pgraph_vk_prebuild_note`, which only
  the monolithic paths call (3650, 3711). So no title records pipeline
  keys under the default, and shaderprebuild569's pre-build replays
  nothing for any title first played since the uber default.
- The uber ladder covered most misses (161 links, 160 specialised builds
  behind it). Six misses were cold, with no uber library yet. Those are
  built on the draw thread: 580 ms at 10:21:05, cold 3 -> 4. The 774 ms
  hitch at 10:21:25 is a 466 ms draw-thread create after the fifth cold
  miss (10:21:22); that class's uber library then took 4.2 s on a worker.
  The 410 ms hitch is 28 fragment-library compiles plus 47 pipeline
  creates on the draw thread.
- The pipeline cache file is saved (`[plc569] save` x13), so a later
  launch of the same build should find these in the driver cache.
  Driver-identity wipes on an update drop it again.

**What removes them:** persisting the uber ladder's combinations per
title and pre-building them at launch. That is
`docs/lanes/stallmeasure569/OUTBOX.md`'s successor brief `uberpersist569`,
which was never dispatched. The missing GPL-path record above is its
first step. It is a lane-sized change in contended pgraph/vk files
(compile_worker.c, draw.c, renderer.c) and needs its own cold/records
falsifier. It is not the smallest certain step for this lane, so it is
handed back, not built here.

## Board

`docs/lanes/ralli2audio1018/**` is granted. The request at
`dispatch/board-requests/ralli2audio1018.md` asks for
`hw/xbox/mcpx/apu/apu.c` (held by x1port1012, a stale hold whose branches
are in master), predictions and a selftest fragment. It was pending at
11:40 PDT.

## Device plan

- Route `routes/ralli2audio1018-drive.route` uses rallisport-2.returning's
  menus with a new drive loop. The old loop's opening reverse parks the
  car in the paddock: the 10-12 run measured a stationary car.
- Cache: every arm sets `HAKUX_PLC_WIPE=1`, so each run compiles cold, as
  the owner's did. Without it, the first arm warms the driver cache for
  the second, and the second looks fixed for the wrong reason.
- Pilot: `HAKUX_APU_PRIO=0 HAKUX_PLC_WIPE=1` (870 s). It gives the `prod:`
  lines that name the mechanism, at the prior thread priority.
- Then `HAKUX_PLC_WIPE=1` (priority on), then two plain default runs for
  the bar. The default goes last, so the device's env pref is left as
  shipped.

## Stop rule

The same failure twice for one cause: stop and report.

## Status

[lane.ralli2audio1018] working: instrument and priority change committed;
queueing the pilot once the Nova's current hold (gta3car1018) ends.
