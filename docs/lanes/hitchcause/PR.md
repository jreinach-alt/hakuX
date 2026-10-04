# hitchcause: the unexplained 330 ms hitches in MTV sit on IDE sector-read bursts; cause not yet separated

State: ready

Lane: hitchcause            Issue: #433 (0.5: 50 Playable)
Base: origin/master @ 10f14d301d
Files: docs/lanes/hitchcause/NOTES.md, docs/lanes/hitchcause/OUTBOX.md, docs/lanes/hitchcause/PR.md, docs/lanes/hitchcause/hitchwin.py, docs/lanes/hitchcause/blockread.py, docs/lanes/hitchcause/ide_wake.py, docs/lanes/hitchcause/rr_split.py, docs/lanes/hitchcause/pc_exits.py, docs/lanes/hitchcause/g_conc.py
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

Release note (none): analysis only; no emulator code changed.

## What I found

The 330 ms hitches in MTV Celebrity Deathmatch (Nova, held run 10-04) are not
vCPU-side waits for the most part. Each hitch of 200 ms or more has an IRQ14
(Xbox primary IDE) sector-read burst in its own 2 s span or the next one. The
IRQ14 busy time against the worst frame gives r = 0.74 over 344 spans; the
spans under 100 ms have no IRQ14 wakes at all. Two of the five 330 ms hitches
also have the vCPU thread asleep on the host for about 300 ms (83 to 85% on
CPU); the other three run on CPU at 92 to 94%.

Offline telemetry cannot separate the on-CPU hitches into guest-side load
(a spin or compute behind the disk stream) and host-side per-word IDE cost. The
telemetry that would separate them is in `hw/ide/`, which is outside this lane's
Files, so no device run was queued. Section 6 of NOTES.md ranks the next steps by
P x win; the first one is a grant for an `hw/ide` perflog line.

## Table (full in NOTES.md section 2)

| hitch (PDT) | worst ms | route | IRQ14 wakes / busy | vCPU on-CPU |
|---|---:|---|---|---:|
| 14:05:57 | 349 | menu | 151 + 316 / 618 + 389 ms | 84.7% |
| 14:08:39 | 346 | play | 53 + 339 / 186 + 346 ms | 92.8% |
| 14:10:25 | 344 | play | 374 / 672 ms | 94.1% |
| 14:13:15 | 331 | menu | 230 + 257 / 924 + 76 ms | 83.5% |
| 14:15:21 | 330 | play | 130 + 287 / 602 + 82 ms | 92.7% |

Other checks: Orta's 277 and 386 ms hitches sit on IRQ14 bursts too (r = 0.46).
Blood Wake's 1 to 3 s stalls are a separate class (two of the four have no IRQ14
wakes at all).

## Checks run

- Offline scripts in this directory, all stdlib python, over the logs named
  in NOTES.md (`perf/2026-10-04-mtv-hitches/logcat.txt`, Orta's
  `panzer-dragoon-hold3/logcat.txt`, Blood Wake's `lanelocal-3321881/logcat.txt`).
- No emulator code, no harness file, no prediction: selftest and the
  prediction gate do not apply.
- No CI run (offline; GitHub suspended). This PR has no device-facing change.

## Next

1. A grant for `hw/ide/core.c` and `hw/ide/mmio.c`: one perflog line per span
   (per-word read count and ns; storage latency per sector), one build, one MTV
   hold of 700 s. P 0.9 that it decides; no win by itself.
2. If the latency dominates: read-ahead of the next sector in the IDE PIO path.
   P 0.6; win: the 200 to 350 ms burst stall on every HDD stream.
3. If the per-word cost dominates: batch the data port or use bus-master DMA.
   P 0.3; the same win; larger change.
