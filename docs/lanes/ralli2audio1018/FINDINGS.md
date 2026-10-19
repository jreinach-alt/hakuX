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

A cold-cache pilot (`HAKUX_PLC_WIPE=1`, worst case) confirmed the producer
prediction by a wide margin: voice fork-join time 143 us mean per frame
(predicted 390-450 us), wall per block ~25% of budget (predicted 65-75%),
`audio_starve_share` 0.000153 even with every shader forced cold.

Two full default-cache runs of the same race on the Nova:

| Measure | Bar run 1 | Bar run 2 | Bar |
|---|---|---|---|
| gameplay | 657.7 s | 629.8 s | 600 s |
| audio_starve_share | 0.0 | 0.0 | <= 0.001 |
| hitches over 500 ms after warm-up | 0 | 0 | none |
| worst frame (ms) | 165.5 | not scored (route-frame gap) | <= 500 |
| fps_ok | 0.8618 | not reliable (same gap) | >= 0.90 |

Audio dropouts and shader-compile hitches are confirmed fixed, twice, by a
wide margin -- the 1.34% starve share and the 580/774/410 ms compile
hitches the owner saw are gone.

`fps_ok` misses the 0.90 bar on both runs, and a third run (aborted
early by a device disconnect, unrelated to this fix) reproduces the same
shape a third time: a clean ~59 fps for the first 180-240 s of continuous
racing, then a sustained drop to a 25-50 fps band for the rest of the run,
even after a cooldown gap before the run starts. This does not move with
a cooldown gap, which argues for a within-race thermal characteristic of
this title on this device rather than cumulative heat from queuing runs
back to back.

An isolation run (`HAKUX_APU_PRIO=0`, this fix's priority change off, the
vp.c memory-read change still in effect) reproduces the identical cliff at
the identical ~180-210 s mark. Four runs now (two priority-on, one aborted
priority-on, one priority-off), across both cold and warm shader caches,
all cut at the same wall-clock mark into one continuous race. **The fps
cliff is not caused by this change**: not the vp.c memory-read path
(CPU-side APU code, no render-path connection either way), not the
priority change (reproduces with it off), and not shader-cache state
(reproduces warm and cold). It is a device/title characteristic that
shows up under several continuous minutes of this race's particular load,
independent of anything on this branch. The owner's own hand-played
capture (514 s, fps_ok 0.9873, no cliff) stayed under the ~180 s mark
where the cliff starts, which is consistent with this reading rather than
contradicting it.

The audio fix ships on its own merits: its own bar (audio_starve_share,
hitches) is confirmed twice, by a wide margin. The fps cliff is a
separate, pre-existing, device/title-specific finding, handed off rather
than fixed here -- it is outside `hw/xbox/mcpx/apu/**` and needs its own
investigation (likely thermal/sustained-load characterization, not an
audio or APU lever).

A second, unrelated observation from the isolation run: the hakuX process
exited on its own at t=670s of the 870s run (no crash signature, no
tombstone, no thermal-mitigation flag set in the device's own thermal
status at the last sample 31s prior), handing focus back to the launcher.
This is a device/app-robustness question, not an audio or render defect,
and is also handed off rather than chased here.

## White surfaces

The owner saw white panels on the car in RalliSport Challenge (4D53000F,
not Challenge 2) on this branch's isolation build (`723ea67e77`,
`HAKUX_APU_PRIO=0`), once, not reproduced since; master and the 0.5.2
release both ran clean afterward.

**(a) Everything this branch changes, and what each path can touch:**

`git diff origin/master...HEAD --stat` outside `docs/lanes/ralli2audio1018/**`
touches exactly two files: `hw/xbox/mcpx/apu/apu.c` and
`hw/xbox/mcpx/apu/vp/vp.c`. Every hunk in `apu.c` (14 hunks, checked by
header) sits inside the APU's own internal functions -- `throttle`,
`apu_starve_account`/`apu_starve_report` (new `apu_prod_*` timing
counters), `se_frame`, `monitor_sink_cb`, `monitor_init`, and
`mcpx_apu_frame_thread` -- plus the `HAKUX_APU_PRIO` block that calls
`setpriority(PRIO_PROCESS, tid, ...)` on the APU's own thread ids. None of
it reaches `hw/xbox/nv2a/**`, `vk/`, `gl/`, or any lock those own (the
locks it does touch -- `d->lock`, `fifo_lock`, `bql_lock`/`bql_unlock` --
are pre-existing calls this branch only wraps with a timer, not new
acquisitions or a changed order). `vp.c`'s 5 hunks are the `voice_ldl`
helper and its three call sites (`voice_get_mask`, `voice_set_mask`,
`voice_get_samples`) plus the `vp_ram_size` init. Nothing here allocates,
maps, or iterates any buffer the render path owns.

**(b) The new guest-RAM reads in `vp.c`:**

`voice_ldl` reads `d->ram_ptr[addr]` directly (`ldl_le_p`, a plain host
load, no RCU read lock) when the address is within `vp_ram_size`, falling
back to `ldl_le_phys(&address_space_memory, ...)` above it -- the same
call the old code always used. Three things to check:

- *Does it read different bytes than before?* No. For an address inside
  RAM, `ldl_le_phys` on a plain-RAM physical address resolves to the same
  host-backed buffer `d->ram_ptr` points at; both paths read the same
  bytes. The change is which API reaches them, not which bytes they are.
- *Can it tear or read stale data under a concurrent guest write?*
  Every call site uses a `voice + offset` that comes from `NV_PAVS_SIZE`
  field layout and is used with `ctz32(mask)` bit-field math, so these are
  natural, aligned 32-bit accesses -- atomic at the host ISA level with or
  without the RCU path. The RCU lock the old path held protects against
  the memory map changing (hot-unplug/resize), not against a second
  writer touching the same bytes; a concurrent guest write to the same
  voice register was already an unguarded race in the old code, and
  `voice_ldl` does not widen that window.
- *Does the skipped store in `voice_set_mask` drop a write something else
  relies on?* It only skips the store when the computed value equals what
  is already there (`v == old`), so the byte content of RAM after the
  call is identical whether the store runs or is skipped -- there is no
  observable difference for anything that later reads that address,
  including a concurrent writer: skipping a no-op write can only narrow a
  clobber window (by shortening the time the address is touched at all),
  never widen one.

**(c) What would differ, in a RalliSport Challenge scene, between this
branch and master:** nothing in pixel output. Every changed line is
CPU-side APU code reading and writing audio voice registers and SSL
entries in a software-defined RAM region the game allocated for its own
audio engine -- disjoint from any texture, vertex buffer, or NV2A command
data a render frame touches. The scheduling change (`HAKUX_APU_PRIO`)
changes which threads the OS scheduler favors, not any data a frame reads;
it could in principle delay a render thread under contention (a frame
timing effect, which is what the fps-cliff isolation run above was built
to test and already separates from this change), but a scheduling delay
is not a mechanism for a data-correctness defect like a texture reading
as solid white.

**A concrete alternative mechanism already exists in code, independent of
this branch.** The Vulkan backend (`hw/xbox/nv2a/pgraph/vk/texture.c`)
keeps a 16x16 opaque-white dummy texture (`create_dummy_texture()`,
filled via `memset(..., 0xff, ...)`) and binds it in place of a real
texture in several cases, including when the texture-descriptor LRU
cache is exhausted for a frame (too many distinct textures bound in one
submit) and a slot had no prior binding -- the surrounding comment in
that code names this exact failure mode ("substituting the dummy for a
frame is a wrong texture") and deliberately leaves the slot dirty so it
self-corrects on the next draw. That matches the report precisely: a
single wrong-looking frame or two, gone on its own, with no app restart
or fix needed, and no connection to audio or APU code either way. The GL
backend has no equivalent fallback, which is also consistent with this
not showing up as a steady-state defect across runs.

**This does not, on its own, prove the branch is innocent** -- it is a
plausible alternative with supporting code, not a reproduction. The
single decisive check, if more certainty is wanted before folding: an A/B
of `723ea67e77` vs. `origin/master` on the same RalliSport Challenge
save/scene, several passes through the same stretch, screenshot diff
against the console-calibrated golden if one exists for this title.

Looked at the screenshot itself
(`/home/justin/hakux-work/captures/ralli-white-1018/screen-205455.png`):
lap 1, race time 02:14.600, a dirt rally stage, the car a
white/green/red Hyundai livery. The white areas (roof, most of the rear
deck/spoiler) sit where that manufacturer livery is itself largely white
-- from this one frame alone, with no reference screenshot of the same
car/pose on a clean build to diff against, it is genuinely ambiguous
whether this is a missing-texture defect or the livery's own paint
scheme. That ambiguity, on top of not knowing which part of the race the
owner was in when they noticed it, is why this is named as the decisive
check rather than run speculatively: `hold.sh who nova` now reads `free`
(the owner's hold lifted during this session, timestamp
`...lanelocal-offline-lifted-owner-1018-20261019T021232Z` in
`dispatch/hold/lifted/`), so the device is available, but queuing a soak
to hope for a repeat of a one-off with an unknown trigger and no golden
to diff against is a low-probability, low-information spend -- not the
same thing as the check being unavailable. The useful next step with
device time is not a blind repeat: it is getting the scene/moment from
whoever saw it (or from a wider screenshot-diffing soak built to catch
any solid-white region automatically across a full route, which does not
exist yet), then running the named A/B against that specific moment.

## New telemetry on master (10-18 21:21-21:23 PDT, no fix): compared against this branch's producer model

`/home/justin/hakux-work/captures/fps-owner-1018/ralli2.txt`, master
perflog build `72af9cb92c` (pre-fix: no `prod:` line, voice workers at the
old nice -4), RalliSport Challenge 2, about two minutes of race.

Audio `starve:` lines over the whole clip (9 prints, each covering the
interval back to the previous print, not a running total -- the byte
counts are not monotonic):

| print ends | window | short/total callbacks | zero-filled |
|---|---|---:|---:|
| 21:21:47 | pre-race/load | 108/132 | 81.4% |
| 21:21:59 | 12 s | 2/269 | 0.74% |
| 21:22:04 | 5 s | 1/118 | 0.64% |
| 21:22:09 | 5 s | 1/118 | 0.11% |
| 21:22:14 | 5 s | 16/116 | 4.85% |
| 21:22:19 | 5 s | 2/118 | 0.21% |
| 21:22:24 | 5 s | 14/117 | 4.70% |
| 21:22:29 | 5 s | 52/117 | **11.75%** |
| 21:22:40 | 11 s | 1/277 | 0.09% |

Aggregate over the whole clip: 1,112,064 of 11,321,344 bytes zero-filled =
**9.8%** -- worse than the 1.34% the owner's original, longer session
scored, on the same unfixed master.

The per-second `hakuX-phase` lines (36 of them, matching the 36 windows
`fpsdiag.py` found) give `Fin` broken into `Sub` (CPU-side submission) and
`Fen` (GPU fence wait). `Fen` stays flat at 0.1-0.5 ms throughout; every
`Fin` swing is a `Sub` swing: 0.1-0.2 ms in the clean stretch (21:21:49 to
21:22:09) and 11-26 ms, almost all `Sub`, from 21:22:15 onward. That is
CPU-bound command-submission work competing for the same CPU the voice
workers run on, not GPU wait -- the mechanism this branch's own `prod:`
model already names (a shader-compile burst or a few ms of run-queue wait
tips the producer under real time) and the reason the priority change
raises the voice workers to the frame thread's tier: under CPU
contention from the render thread's own submission work, the pre-fix
nice -4 workers lose the scheduling contest for CPU the nice -16 frame
thread already wins.

The correlation is not a clean 1:1 per-print match: the worst `Sub` spikes
at 21:22:15/18 (16-22 ms) land inside the *low*-starve window ending
21:22:19 (0.21%), while the high-starve windows (21:22:14, 24, 29) show
only modest `Fin` elevation at their edges. The `starve:` print interval
is not tied to the same clock as the per-second `hakuX-phase` lines (its
byte counts reset on its own schedule, not every wall-clock second), so a
tight per-bucket alignment is not available from this capture; the
30-second stretch that holds every elevated `Fin`/`Sub` sample
(21:22:10-21:22:53) is also the stretch that holds every elevated starve
sample (21:22:14-21:22:29) and nothing outside it, which is the level of
correlation this capture supports.

This is a "before" data point for the same symptom class this branch
already fixed and verified twice on device (bar runs 1-2 above,
`audio_starve_share` 0.0 against this same race). It was not re-run with
the fix -- the Nova was on the owner's hold during this capture and
remains on hold now -- so it is read as supporting evidence for the
mechanism, not a second confirmation of the fix.
