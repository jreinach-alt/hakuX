# lane.ibcache: inline jump-cache probe at lookup_and_goto_ptr, opt-in (HAKUX_IBC=1) (#507)
State: ready

Lane: ibcache            Issue: #507
Base: master @ 8e3b1f2ad2 (merged; branched from be05285c44). GitHub PR #591 until the 2026-09-29 suspension.
Files: accel/tcg/cpu-exec.c, include/accel/tcg/hakux-ibc.h, include/tcg/tcg-op-common.h, target/i386/tcg/translate.c, tcg/tcg-op.c, docs/lanes/ibcache/NOTES.md, docs/lanes/ibcache/OUTBOX.md, docs/lanes/ibcache/PR.md, docs/lanes/ibcache/bandread.py, docs/lanes/ibcache/ccheck.py, docs/lanes/ibcache/counters.py, docs/lanes/ibcache/forza-drive.route, docs/lanes/ibcache/gfps.py, docs/lanes/ibcache/gta-sa-shots.route, docs/lanes/ibcache/headread.py, docs/lanes/ibcache/idleread.py, docs/lanes/ibcache/jcmodel.py, docs/lanes/ibcache/legtable.py, docs/lanes/ibcache/noisecheck.py, docs/lanes/ibcache/out/bandread.out, docs/lanes/ibcache/out/ccheck-default-off.out, docs/lanes/ibcache/out/coldslot-5a-request.md, docs/lanes/ibcache/out/counters-r1.out, docs/lanes/ibcache/out/counters-r1b.out, docs/lanes/ibcache/out/gfps-pilot.out, docs/lanes/ibcache/out/gfps-r1-r1b.out, docs/lanes/ibcache/out/headread-5c.out, docs/lanes/ibcache/out/headread-5d.out, docs/lanes/ibcache/out/headread.out, docs/lanes/ibcache/out/idleread-5c.out, docs/lanes/ibcache/out/idleread-5d.out, docs/lanes/ibcache/out/idleread-gta.out, docs/lanes/ibcache/out/jcmodel-r1.out, docs/lanes/ibcache/out/jcmodel-r1b.out, docs/lanes/ibcache/out/jitmix-r1.out, docs/lanes/ibcache/out/jitmix-r1b.out, docs/lanes/ibcache/out/legtable-5c.out, docs/lanes/ibcache/out/legtable-5d.out, docs/lanes/ibcache/out/noisecheck-pixels.out, docs/lanes/ibcache/out/queue_5c.out, docs/lanes/ibcache/out/queue_5d.out, docs/lanes/ibcache/out/queue_5d_pilot.out, docs/lanes/ibcache/out/queue_crimson_nova.out, docs/lanes/ibcache/out/queue_head_forza.out, docs/lanes/ibcache/out/queue_head_gta.out, docs/lanes/ibcache/out/queue_jcsize.out, docs/lanes/ibcache/out/queue_leg4.out, docs/lanes/ibcache/out/requeue_after_wipe.out, docs/lanes/ibcache/out/rrcmp-r1-r1b-75.out, docs/lanes/ibcache/out/rrcmp-r1-r1b.out, docs/lanes/ibcache/out/soakread-5c.out, docs/lanes/ibcache/out/soakread-5d-pilot.out, docs/lanes/ibcache/out/soakread-5d.out, docs/lanes/ibcache/out/soakread-head.out, docs/lanes/ibcache/out/soakread-nova.out, docs/lanes/ibcache/out/spinshare-r1-r1b.out, docs/lanes/ibcache/out/sym-r1.out, docs/lanes/ibcache/out/sym-r1b.out, docs/lanes/ibcache/out/tbmap-r1.out, docs/lanes/ibcache/out/tbmap-r1b.out, docs/lanes/ibcache/out/tv-pilot.out, docs/lanes/ibcache/prbody.py, docs/lanes/ibcache/prmd.py, docs/lanes/ibcache/queue_jcsize.sh, docs/lanes/ibcache/queue_leg4.sh, docs/lanes/ibcache/queue_leg6.sh, docs/lanes/ibcache/readleg.sh, docs/lanes/ibcache/requeue_after_wipe.sh, docs/lanes/ibcache/rrcmp.py, docs/lanes/ibcache/soakread.py, docs/lanes/ibcache/spinshare.py, docs/testing/predictions/ibcache-probe-band.json, docs/testing/predictions/ibcache-probe-pixels.json
Prediction: docs/testing/predictions/ibcache-probe-band.json @ d7a7ddaa4c (PASS, all 69 checks); ibcache-probe-pixels.json (FAIL 9/3381, read as master's own flip band, see NOTES)
Needs device: yes    Needs NDK: yes

Release note (none): an opt-in vCPU switch (HAKUX_IBC=1), off by default; with the idle halt off it measured no fps gain and slightly higher energy per frame.

## What it does

At the one `lookup_and_goto_ptr` site in the x86 front end (`gen_eob`, DISAS_JUMP: RET, indirect JMP/CALL, a cross-page jump), `gen_ibc_probe()` emits `tb_lookup()`'s jump-cache hit test as TCG IR. On a hit it does `goto_ptr tb->tc.ptr`. On a miss it falls through to the unchanged `helper_lookup_tb_ptr`. It reads the existing `cpu->tb_jmp_cache`, with the same hash and the same key, so it inherits every invalidation `tb_lookup` honours: a wiped slot is empty, and a discarded TB carries CF_INVALID and fails the cflags compare. Every key field is read at run time. A hash-layout mismatch refuses the probe.

**Off by default.** `HAKUX_IBC=1` turns it on, and `2` adds a hit counter. Anything else, or unset, leaves it off. One `[ibc507] on=… layout=ok` line is printed at the first translation.

**Why it is off.** The probe does what it was built to do: the lookup share of the vCPU falls from 24.9% to 7.3% on GTA, and helper calls fall 93-98%. But on the Nova, with the idle halt off (the default), the vCPU time it frees did not become frames. Forza's guest idle share rose from 0.23 to 0.29, and its watts rose. No title gained fps, and J/frame was higher with the probe in three of four readings (table below). Leg 6, queued at this head, runs it with the idle halt on, where the freed time could become sleep.

No return-address stack, and no 16-bit jump cache. Both deepen the same saving, so they wait on leg 6 (NOTES).

## Legs

| leg | registered | reading | result |
|---|---|---|---|
| R1 go/no-go | lookup >= 8.0% of the vCPU thread on master | 24.9% (GTA, Thor, cold) | **GO** |
| 1 share | lookup <= half of R1, `helper_lookup_tb_ptr` <= a third | 7.3%, 0.83% (R1b) | **PASS** |
| 2 counter | `[rr425] hc` down >= 70% | -92.6% (GTA), -98.1% (Crimson); -93% GTA, -89% Forza on the Nova head runs | **PASS** |
| 3 pixels, full sweep | nothing moves | 9 of 3381 moved, all in master's own flip band | FAIL, read as noise (NOTES attempt 4) |
| 3b pixels, the flip band, three runs per arm | nothing moves outside the band | 0 captures self-identical in each arm and different between them | **PASS** (`[job.arms]`, 69 checks) |
| 4 title soaks, three titles | gameplay with the probe, no new crash or hang | GTA, Crimson Skies, Alien Hominid, Forza: all gameplay, no crash or hang (one Forza run pre-empted by an outside launch, not a crash) | **PASS** |
| 5a GTA, no regression | fps(B) >= fps(A) - 0.5; J/frame(B) <= 1.036 x A | Nova, n=2: fps 29.55 vs 29.62; J/frame x1.066 | **FAIL** on J/frame |
| 5b Forza, the gain | fps +5%, J/frame -4% | the car sat at 0 MPH in every play frame (the route never touched the throttle) | not evidence |
| 5c GTA, replication of 5a | as 5a, 3 fresh runs per arm, with window frames | fps +0.31; J/frame x1.021 (pooled with 5a, x1.040) | **PASS** |
| 5d Forza, driven | 5b's bars, on a throttle route | fps x0.98; J/frame x1.10; net +0.65 W | **FAIL** (the wrong direction) |
| 6 idle halt on, both arms | probe's extra watts <= +0.20 W (spin) or >= +0.45 W (the probe's own) | Nova, B A A B queued at this head | waiting (follow-up) |

Crimson Skies at n=1 per arm: both arms at the 30 fps cap, J/frame x0.972.

## Local checks (no CI while GitHub is suspended)

- `ccheck.py` (NDK compile of cpu-exec.c and translate.c at this head): rc 0, only the existing upstream warnings.
- `preflight.sh --allow-tracker`: see NOTES for the head it passed on.
- Device runs built from this head: leg 6's four Nova soaks.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
