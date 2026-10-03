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
