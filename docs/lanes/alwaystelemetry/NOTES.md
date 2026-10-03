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
