# alwaystelemetry (#433): every run carries its own cause telemetry

Part 1 of the brief: measure the perflog overhead, inventory the counters, design the always-on tier.
No emulator edits in this part.

## Pre-registered prediction (committed before any device run)

Subject: ToeJam & Earl III, golden profile, route `toejam-earl-3`, ref `6c828f9860` (origin/master),
plain build vs `--perflog` build, 600 s each, same env.

- **P1 (perflog costs frame rate above the noise):** the perflog arm is worse than plain by at least
  2% fps_ok OR at least 0.5 fps on the gfps median. Probability 0.7.
- **Mechanism behind P1:** `NV2A_PERF_LOG` puts `nv2a_clock_ns()` (qemu_clock_get_ns) around every
  method in the puller (`hw/xbox/nv2a/pgraph/profile.c` comment at line ~615, `pgraph.c` line ~2406
  histogram) and around each draw phase (`hw/xbox/nv2a/pgraph/vk/draw.c`, `texture.c`, `surface.c`).
  Two clock reads per method at tens of ns each, times the method count per frame, lands in the
  low-ms range per guest frame, which is 5-15% of a 16-ms frame if the puller is on the critical path.
- **Falsifier:** if the two arms are within both thresholds, perflog is below the noise on this title and
  the owner's "make perflog the default" option is supported for this title (still one title; not general).
- **Not a pixel claim:** no `ab_compare.py --register` (this measures rate, not frames). The reference
  shas are the arm refs in the queue lines.

## Plan

1. Queue the two arms (plain, perflog) through lane.local's title queue (`overnight-queue.tsv`).
2. Inventory every counter the perflog build emits and every one the plain build emits; classify cost
   source; mark which ones `decompose.py` and `title_verdict.py` read.
3. Design the always-on tier and the deep tier; name files and functions; state expected cost.

## Queued (10:40 PDT)

Two rows appended to `~/hakux-work/pm/overnight-queue.tsv` (python3), keys `alwaystelemetry-toejam-plain`
and `alwaystelemetry-toejam-perflog`: ref `6c828f9860`, 600 s, the same env as the ToeJam perflog row
(`PERF_REGIMEN=default HAKUX_PREBUILD=0 HAKUX_PLC_WIPE=1 HAKUX_GPL=3`), the second with `--perflog`.
Not yet run: no request ids exist yet. Result: pending.

## Attempt 2 (14:06 PDT): why attempt 1 did not finish

Attempt 1 queued the pair (rows 11 and 12 of `overnight-queue.tsv`, now in `overnight-queue.done`) and then
wrote `WAITING: time 2026-10-03T14:00`. That was a guess at when the pair would run, not a condition on a run.
The lanewaker resumed this lane at 14:00 PDT (lanelocal-log, 14:03), and nothing had changed: no request id
exists for either key. `dispatcher.log` has no `alwaystelemetry` request. The Nova has been held by
`lane.pathfind` since 21:00Z (14:00 PDT), and the queue runner is ordered behind kabuki-perflog, the ToeJam
pair and tron-inlevel-perflog. Lane.local's own estimate is ~15:00-15:30 PDT for this pair.

So attempt 1 ended on a time that did not match its wait, and attempt 2 is the same wait with a corrected
condition: nothing here can run until lane.local submits the two rows, and I have no run id to name yet.

Also this attempt: merged `origin/master` (638a3f478c) into the branch, so the design is checked against
current code, not the 6c828f9860 tree. The registered ref `6c828f9860` is still an ancestor, and the prediction
is unchanged. Verified against the merged tree: `decompose.py` is on master (it was not, when the OUTBOX premise
note was written); `nv2a_profile_inc_counter` has 64 call sites in code, not 66 (69 grep hits, minus the two
definitions in debug.h, two OUTBOX mentions and one docs line); the hakuX-phase and xemu-work prints are at
profile.c 727 and 737; the LOGCAT allow-list is at dispatcher.sh 2010.

## Attempt 3 (16:03 PDT): why attempt 2 did not finish

Attempt 2 wrote `WAITING: time 2026-10-03T16:00` and no run id existed. The lane had waited on a guessed
time again. The real cause is in `logs/overnight-queue.log` (13:34 PDT): both ToeJam rows were **refused, not
queued**, by the route guard: `toejam-earl-3.route declares no # state: returning|first-run|any`. Attempts 1
and 2 never read that log, so they waited on a queue that had already refused the rows. The runner then put
both keys in `overnight-queue.done`, so they are now skipped. lane.local fixed the route at 14:2x (the queue
copy in `wt/lanelocal-queue` now carries `# state: returning`, golden 71a91de8b905). Nothing re-queued them.

What changed in attempt 3:

1. **Keys replaced:** `alwaystelemetry-toejam-plain` / `-perflog` become `alwaystelemetry-toejam-r3-plain` /
   `-r3-perflog` in `pm/overnight-queue.tsv`. The old keys are in `.done`, so they would be skipped.
2. **Ref moved:** `6c828f9860` becomes `a971c31220` (this branch, = origin/master 5426f4d874 merged).
   Both arms are on the same ref. No device run has happened yet, so the change is before the measurement.
   The prediction (P1) is unchanged.
3. **Env changed: `HAKUX_GPL=3` becomes `HAKUX_GPL=0`.** The brief's steady-title reference (fps_ok 0.99
   plain) is the GPL=0 profile. ToeJam at GPL=3 carries the #687 ubershader slow stretch at 7-12 min, which
   would confound the overhead number. This is an error in the attempt-1 row, corrected before any run.

Design check against master 5426f4d874: `nv2a_profile_inc_counter` and the `NV2A_PHASE_TIMER_*` macros are
no-ops without `NV2A_PERF_LOG` (`hw/xbox/nv2a/debug.h` 537-549), so the plain build reads 0 for every
`xemu-work` counter and every phase. The `hakuX-phase` and `xemu-work` prints are inside
`#if defined(__ANDROID__) && NV2A_PERF_LOG` (`pgraph/profile.c` 723-737). The always-on design in OUTBOX.md
still holds.

Queue state at 16:04 PDT: **the r3-plain row was refused again**, this time by the golden check:
`toejam-earl-3.route assumes a profile, and 5345000F's golden 71a91de8b905 is title data only, no save
directory` (`logs/overnight-queue.log`, 16:04:08). The route's `# state: returning` line (lane.local, 14:2x)
says the golden 71a91de8b905 carries the profile; the queue's check says it does not. The two statements
conflict, and the route and golden are lane.local's data, outside this lane's territory. The r3-perflog row was
not reached, so it is in the same state.

**BLOCKED on lane.local:** which ToeJam golden or route state the A/B should use. Options for lane.local to pick:
(a) a golden with a save directory for `toejam-earl-3` (`returning`); (b) a route declared `# state: any`
(savestate433 folded: a settings-only refusal names `# state: any` as its fix), which needs a first-run route
that reaches play; (c) a different steady title whose golden already has a save directory. This lane does not
pick (c) itself: the A/B's title is the owner's brief, and the choice of golden is lane.local's.

No run id exists. The rows stay in `overnight-queue.tsv` under the new keys, so they run as soon as the
guard is satisfied.

## Revision to the mechanism (read after the prediction was committed; the prediction is unchanged)

I cited a clock read per method as the cost. On aarch64 `nv2a_clock_ns()` is `mrs cntvct_el0` plus a
multiply (`hw/xbox/nv2a/debug.h` ~462-478), a few ns with no syscall. So the clock reads are probably
NOT the cost. The perflog cost candidates, from reading the code, are:

| Source | Where | Per | Expected cost |
|---|---|---|---|
| Per-method histogram and slow-path counts | `pgraph/pgraph.c:242-293, 2406` | method | small, but per method |
| Per-draw phase timers (35 sites) | `pgraph/vk/draw.c`, 2 clock reads each | draw | a few ns each |
| GPU timestamps per render pass (vkCmdWriteTimestamp, readback) | `pgraph/vk/renderer.c:273` (early return unless NV2A_PERF_LOG), `draw.c:3659,3673,4094,4512` | render pass | unknown: a command in the CB plus a readback |
| `[lock474]` MMIO wait accounting | `pgraph/pgraph.c:900-` | MMIO wait | unknown, Android-only |
| Per-draw ubosz counters | `pgraph/vk/draw.c` `pgraph_vk_ubosz_note_*` | upload/bind | counted, not timed |
| Extra counters in texture/surface paths | `texture.c`, `surface.c` `#if NV2A_PERF_LOG` | event | small |

So the prediction P1 (0.7) rests on the GPU timestamps and the per-draw bookkeeping, not on the
clock reads. The A/B result decides it. If perflog is within noise, the prediction is refuted and the
measurement points at the bookkeeping, not at per-method cost.

## Attempt 4 (18:16 PDT): why attempt 3 did not finish, and the result

**Why attempt 3 did not finish:** it ended correctly, on an `owner` wait. The ToeJam golden had no save
directory, and the choice of golden belongs to lane.local. Lane.local picked option (c) at 16:3x: the same A/B on
Castlevania: Curse of Darkness, returning route, golden 20235e93867b, 960 s, ref a971c31220 for both arms. It queued
the rows itself (keys `alwaystelemetry-cv-plain` / `-cv-perflog`). Both runs finished before this attempt:

| arm | request | ran (PDT) | verdict |
|---|---|---|---|
| plain | 1-1791070366-lanelocal-968308 | 16:32-17:05 | PASS Playable, fps_ok 1.0 |
| perflog | 1-1791072308-lanelocal-1173788 | 17:05-17:22 | FAIL: one 1426 ms stall at mark+187 s |

This attempt reads that pair. It also merged origin/master (b9e33845bd). No emulator file changed since
a971c31220, so the line references in the design still hold.

### How it was read

`abread.py` (this directory) reads both result dirs. Its output, and a plain-against-plain noise control, are in
`ab_castlevania.md`. Castlevania runs at the 60 fps vsync cap, so an fps tie only bounds the cost. The cost shows
in headroom, and two headroom readers exist in BOTH builds:
- `[rdc] tcpu=`: the render thread's own CPU time per window;
- `Ri:` on the gfps line: renderer idle ms per flip.

After the mark the route runs a `repeat forever` walk loop timed on the wall clock, so the two arms' paths
diverge. The primary window is therefore +30..+180 s after the mark: both arms on the same walk, no compiles in
either. The steady window is every second of the run with no pipeline compile within 3 s.

### Measured

| | plain | perflog | delta | noise (plain vs plain, 1-1791063303) |
|---|---|---|---|---|
| fps_ok (verdict) | 1.0 | 0.9965 | -0.35 pt | -- |
| gfps window median (verdict) | 59.94 | 59.94 | 0 | -- |
| gfps mean (verdict) | 59.87 | 59.86 | -0.01 | -- |
| pace max ms, median, +30..+180 | 19.7 | 18.4 | -1.3 | +-1.4 |
| **render-thread CPU ms/s, +30..+180** | **248.2** | **321.7** | **+73.5 (+30%)** | 14 |
| render-thread CPU ms/s, steady | 247.5 | 326.2 | +78.7 | 12 |
| **renderer idle ms/flip (Ri), +30..+180** | **8.02** | **6.90** | **-1.12** | 0.18 |
| Ri, steady | 8.12 | 6.52 | -1.60 | 0.17 |
| vCPU run % ([idlehalt]) | 98.4 | 98.6 | +0.2 | 0.2 |
| net W (verdict) | 6.832 | 6.968 | +2.0% | plain runs 6.43-6.86 |
| J/frame (verdict) | 0.1141 | 0.1167 | +2.3% | plain runs 0.1073-0.1146 |

**Perflog costs about 1.2 ms of render-thread time per frame on this title.** The CPU figure (+73.5 ms/s over
59 frames/s = 1.25 ms/frame) and the idle figure (Ri -1.1 to -1.6 ms/flip) are two independent readers, and they
agree. Both are 5-9x the plain-against-plain spread. The control spans a ref change (34e6e8dcba to a971c31220),
so it overstates the noise, if anything.
- The render thread's busy time per frame goes from about 8.7 to 9.8 ms (+13%) in the same-scene window, and
  from about 8.6 to 10.2 ms (+19%) in the steady window.
- Castlevania hides this under the vsync cap, with 8 ms of renderer idle to spare. A title whose render thread
  is the bound would lose up to that share of its frame rate.
- The vCPU side does not move: run % stays at 98.4-98.6. The cost sits on the puller/render thread, where the
  per-method and per-draw timers run.

**The FAIL is a confound, not perflog's cost.**
- At mark+186..+224 s the perflog arm compiled 26 first-time pipelines: pm went from 50 to 76, and one window
  had dpm=15 and dpc_ms=1349.7.
- The plain arm compiled nothing after +28 s and ended at pm=50.
- Frames f00018 show why. The perflog arm's player had walked to the castle gate (new content), while the plain
  arm's player was still in the courtyard. The wall-clock walk loop took the two arms to different places.
- Compile cost per pipeline was the same in both arms: 90 ms (1349.7/15) against 94-103 ms in plain's own
  compile windows. So perflog did not slow the compile; the arm reached content the other never did.
- That stall is the known #569 first-compile problem (ubershader off), and the -0.35 pt fps_ok is that one stall.

**Prediction P1 (registered before the run): as worded, not met.** fps_ok fell 0.35 pt (bar 2 pt), and the gfps
median tied (bar 0.5 fps). On a vsync-capped title the fps metric cannot see a render-thread cost that fits inside
the idle; the lane.local addendum said this in advance. The mechanism P1 named is confirmed in headroom:
per-draw and per-method bookkeeping on the render thread, about 1.2 ms/frame. The refined mechanism (bookkeeping,
not clock reads) is only partly supported, as the estimate below shows.

### Per-section cost: not separable from one pair (estimate only)

Event rates in the perflog arm (medians over the run):
- 201 draws per frame (xemu-work BE), so about 12k draws/s;
- 3925 puller method calls per frame (hakuX-cpu M), so about 235k/s, of which 3160/frame on the fast path;
- about 5060 UBO uploads/s (ubosz n);
- about 5300 texture binds/s (txr bt);
- 13 render passes per frame.

The clock reads, taken one family at a time:
- per method: 2-4 reads, about 0.7M/s;
- per draw: 35 phase-timer sites, 2 reads each, about 0.85M/s;
- per texture bind: about 10 reads, 0.05M/s.

That makes about 1.6M `cntvct_el0` reads per second. At 5-25 ns each (not measured on the Nova), that is 8-40 ms/s,
or 10-55% of the measured 74 ms/s. The rest is the bookkeeping these reads feed, plus three per-upload or per-bind
attributions:
- the read-modify-write of `g_nv2a_stats` fields;
- the slow-method histogram;
- `pgraph_vk_ubosz_note_upload`'s per-upload diff (shaders.c 590-, 895);
- the #461 texture-hash reason tracking (texture.c 1925-2366);
- the #474 bind_textures wall timers (texture.c 52-).

A per-section split would take one arm per section. It does not change the decision below, so it is not queued.

**Paid but unread:** three perflog tags are printed and then dropped by the dispatcher's logcat filter
(`docs/testing/dispatcher.sh:2010`): `xemu-vsync`, `xemu-pace` (`profile.c` 730-735) and `hakuX-mhist`
(`pgraph.c` 270). None of the three appears in the perflog logcat.

### Decision

The overhead is above the noise in the units that matter for a render-bound title: +30% render-thread CPU and
1.1-1.6 ms per frame. So **do not make perflog the default.** Do the two-tier change: the design is in OUTBOX.md,
updated 18:xx with these numbers.
- The always-on tier's budget is < 1% of a 60 fps frame: 0.17 ms/frame, about 10 ms/s of render-thread CPU.
- That is below the 12-14 ms/s plain-against-plain spread. So its own A/B can only show "within noise", and the
  tier must also time itself, the way `[shd413] dins_us` and `[rdc] ovh=` already do.

### Next (P x win)

1. **Two-tier change, Opus slot (recommended).**
   - P about 0.8 that the tier fits under 10 ms/s. Evidence: the always-on tier keeps counters (adds, no clock
     reads), per-frame phase timers (hundreds of reads/s, against 1.6M in perflog), and a 1-in-16 sampled draw
     timer. `[shd413]` already runs an instrument of this shape at 2-55 us/s (dins_us).
   - Win: every miss carries its cause, so no second run per miss. Under the owner's 10-03 rule each perf miss
     currently costs one more device run of about 20-30 min.
   - Cost: one Opus session, then one Nova pair (2 x ~20 min) on the same Castlevania route, judged on `tcpu`,
     `Ri` and the tier's self-time.
2. **Perflog as default.** P about 0.1 that it is acceptable. Measured: +30% render-thread CPU, which would make
   every verdict on a render-bound title up to 13-19% pessimistic. The win is the same telemetry with zero code.
   Rejected on the measurement.
3. **An uncapped render-bound A/B to put an fps number on perflog.** It decides nothing: the headroom already
   decides between 1 and 2. Not queued.
4. **Per-section split of perflog (one arm per section).** Only useful for promoting a deep item into the always-on
   tier. P about 0.5 that it promotes something, small win. Defer until the tier 1 arm reports its self-time.
