# RalliSport Challenge 2: audio dropouts and early-race freezes

RalliSport Challenge 2 (4D530039) on a Snapdragon 8 Gen 2 handheld,
2026-10-18:

| Measure | Value | Bar |
|---|---|---|
| fps_ok | 0.9873 | >= 0.90 |
| window median fps | 59.76 | |
| gameplay | 514 s | 600 s |
| audio_starve_share | 0.0134 | <= 0.001 |
| hitches over 500 ms after warm-up | 580, 1403, 774 ms | none |

## Audio dropouts: the voice processor runs at real time with no slack

The dropouts are the APU producer falling behind real time. The output sink
does not drain in bursts. Over each 5 s window, the audio produced falls
short of wall time by the amount that was zero-filled, to within one
callback: 916 ms produced short against 912 ms zero-filled in the worst
window.

The producer's own timing during a race:

| | before the race | in the race |
|---|---|---|
| active voices per 32-sample frame | 5 | about 120 |
| voice-worker time per 667 us frame | 103-106 us | 542-642 us |
| wall time per 5.33 ms block | 1.00 ms | 4.6-5.5 ms |
| audio lost | 0% | 0.2-11.7% per 5 s window |

With about 120 voices, the four voice workers take 81-96% of each frame's
real-time budget. The producer has no slack, so any other load on the CPU
tips it below real time: a shader-compile burst, or a few milliseconds of
run-queue wait. The windows that took longer than 5.33 ms per block are the
ones that lost 2.7-11.7% of their audio. Lock waits on the frame thread
(under 15 ms per window, one of 66 ms) and the frame thread's own CPU
(0.8 ms per block) are not the cause.

In a profile of a comparable voice-heavy race, the guest-memory accessors
took 36.9% of the voice workers' CPU. These are the RCU read lock,
address-space translation, and dirty and code-page bookkeeping on stores.
Each active voice reads and writes its registers in guest RAM a few dozen
times per frame, and every access paid for that path.

**Change:**

- The voice processor now reads voice registers and SSL entries directly
  from guest RAM, with a bounds check and a fallback above RAM. The
  sample and PRD reads already worked that way.
- It skips a register store whose value is unchanged. The envelope
  rewrites unchanged fields on every frame.

The output is byte-identical. Expected effect: voice-worker time falls to
about 390-450 us per frame, and the producer to about 65-75% of real time.

**Also:**

- The APU frame thread and its voice workers run at Android's audio thread
  priority (nice -16). Before, the frame thread was already at -16; the
  workers were at -4. `HAKUX_APU_PRIO=0` turns this off.
- `HAKUX_APU_CUSHION=N` (opt-in, 1-4) deepens the FIFO by N device periods.
  Each period adds 42.7 ms of latency.
- A `prod:` line beside each `starve:` line reports producer timing:
  - blocks, and free-run blocks;
  - wall and CPU per block, and the voice fork-join time per frame;
  - lock waits, and run-queue waits;
  - the sink's worst short.

## The 1403 ms freeze

The freeze is not a shader or texture compile: draw-thread creation took
0.1 ms in that frame. In the same seconds:

- the guest replaced code in memory;
- 2035 translated blocks were discarded and 18,607 translated;
- the disc was idle for 1.41 s, then read a 25.7 MB burst.

It is CPU re-translation of a level-section load. It cost one short audio
callback in 456. Removing it is CPU JIT work: cheaper translation, or
keeping translations across a reload of identical code.

## Shader hitches (580, 774, 410 ms)

These are first-race compiles:

- The 580 ms and 774 ms hitches are draw-thread builds of pipeline classes
  that had no general (uber) shader yet.
- The 410 ms hitch is 28 fragment-library compiles and 47 pipeline creates
  in one frame.

The launch pre-build replays recorded pipeline keys. Under the default
pipeline-library mode no keys are recorded, so the pre-build had nothing to
build for this title. The fix:

- record the keys on the pipeline-library path;
- persist the uber shader's combinations per title;
- pre-build both at launch.

## Status

The memory-access change and the priority change still need two runs of
the same race on the handheld. Each run is scored for audio_starve_share,
hitches and fps_ok.
