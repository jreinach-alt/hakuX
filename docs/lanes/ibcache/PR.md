# lane.ibcache: inline jump-cache probe at lookup_and_goto_ptr (#507)
State: draft

Lane: ibcache            Issue: #507
Base: master @ 56c2a7b4a9 (merged at 6ea5744959; branched from be05285c44). GitHub PR #591 until the 2026-09-29 suspension.
Files: accel/tcg/cpu-exec.c, include/accel/tcg/hakux-ibc.h, include/tcg/tcg-op-common.h, target/i386/tcg/translate.c, tcg/tcg-op.c, docs/lanes/ibcache/NOTES.md, docs/lanes/ibcache/OUTBOX.md, docs/lanes/ibcache/PR.md, docs/lanes/ibcache/bandread.py, docs/lanes/ibcache/ccheck.py, docs/lanes/ibcache/counters.py, docs/lanes/ibcache/gfps.py, docs/lanes/ibcache/jcmodel.py, docs/lanes/ibcache/noisecheck.py, docs/lanes/ibcache/out/bandread.out, docs/lanes/ibcache/out/coldslot-5a-request.md, docs/lanes/ibcache/out/counters-r1.out, docs/lanes/ibcache/out/counters-r1b.out, docs/lanes/ibcache/out/gfps-pilot.out, docs/lanes/ibcache/out/gfps-r1-r1b.out, docs/lanes/ibcache/out/jcmodel-r1.out, docs/lanes/ibcache/out/jcmodel-r1b.out, docs/lanes/ibcache/out/jitmix-r1.out, docs/lanes/ibcache/out/jitmix-r1b.out, docs/lanes/ibcache/out/noisecheck-pixels.out, docs/lanes/ibcache/out/queue_crimson_nova.out, docs/lanes/ibcache/out/queue_head_forza.out, docs/lanes/ibcache/out/queue_head_gta.out, docs/lanes/ibcache/out/queue_jcsize.out, docs/lanes/ibcache/out/queue_leg4.out, docs/lanes/ibcache/out/requeue_after_wipe.out, docs/lanes/ibcache/out/rrcmp-r1-r1b-75.out, docs/lanes/ibcache/out/rrcmp-r1-r1b.out, docs/lanes/ibcache/out/soakread-nova.out, docs/lanes/ibcache/out/spinshare-r1-r1b.out, docs/lanes/ibcache/out/sym-r1.out, docs/lanes/ibcache/out/sym-r1b.out, docs/lanes/ibcache/out/tbmap-r1.out, docs/lanes/ibcache/out/tbmap-r1b.out, docs/lanes/ibcache/out/tv-pilot.out, docs/lanes/ibcache/prbody.py, docs/lanes/ibcache/prmd.py, docs/lanes/ibcache/queue_jcsize.sh, docs/lanes/ibcache/queue_leg4.sh, docs/lanes/ibcache/requeue_after_wipe.sh, docs/lanes/ibcache/rrcmp.py, docs/lanes/ibcache/soakread.py, docs/lanes/ibcache/spinshare.py, docs/testing/predictions/ibcache-probe-band.json, docs/testing/predictions/ibcache-probe-pixels.json
Prediction: docs/testing/predictions/ibcache-probe-band.json @ d7a7ddaa4c (PASS, all 69 checks); ibcache-probe-pixels.json (FAIL 9/3381, read as master's own flip band, see NOTES)
Needs device: yes    Needs NDK: yes

Release note (performance): the vCPU finds the next block of guest code inline instead of calling out for it, which cuts the emulator's lookup cost from about a quarter of the CPU thread to about 7% in GTA San Andreas, and leaves more headroom in CPU-bound scenes.

## What it does

At the one `lookup_and_goto_ptr` site in the x86 front end (`gen_eob`, DISAS_JUMP: RET, indirect JMP/CALL, a cross-page jump), `gen_ibc_probe()` emits `tb_lookup()`'s jump-cache hit test as TCG IR. On a hit it does `goto_ptr tb->tc.ptr`. On a miss it falls through to the unchanged `helper_lookup_tb_ptr`. It reads the existing `cpu->tb_jmp_cache`, with the same hash and the same key, so it inherits every invalidation `tb_lookup` honours: a wiped slot is empty, and a discarded TB carries CF_INVALID and fails the cflags compare. Every key field is read at run time. Switch `HAKUX_IBC`: unset or 1 is on, 0 is off, and 2 adds a hit counter. `[ibc507] on=… layout=ok` is printed once. A hash-layout mismatch refuses the probe.

No return-address stack: the probe serves RET already. Ranked and not built, see NOTES.

## Legs

| leg | registered | reading | result |
|---|---|---|---|
| R1 go/no-go | lookup >= 8.0% of the vCPU thread on master | 24.9% (GTA, Thor, cold) | **GO** |
| 1 share | lookup <= half of R1, `helper_lookup_tb_ptr` <= a third | 7.3%, 0.83% (R1b) | **PASS** |
| 2 counter | `[rr425] hc` down >= 70% | -92.6% (GTA), -98.1% (Crimson, Nova) | **PASS** |
| 3 pixels, full sweep | nothing moves | 9 of 3381 moved, all in master's own flip band | FAIL, read as noise (NOTES attempt 4) |
| 3b pixels, the flip band, three runs per arm | nothing moves outside the band | 0 captures self-identical in each arm and different between them | **PASS** (`[job.arms]`, 69 checks) |
| 4 title soaks, three titles | gameplay with the probe, no new crash or hang | GTA (Thor), Crimson Skies, Alien Hominid (Nova): all gameplay, no crash or hang | **PASS** |
| 5a GTA (capped), no regression | fps(B) >= fps(A) - 0.5; J/frame(B) <= 1.036 x A | Nova, head 946a78c8e9, B A A B queued 2026-10-01 | waiting |
| 5b Forza (below cap) | fps +5%, J/frame -4% | Nova, head 946a78c8e9, B A A B queued 2026-10-01 | waiting |

Crimson Skies at n=1 per arm on the Nova: both arms at the 30 fps cap, J/frame -2.8% (not gated).

## Local checks (no CI while GitHub is suspended)

- `ccheck.py` (NDK compile of cpu-exec.c, translate.c, tcg-op.c at the head's sources): rc 0, no new warnings.
- `preflight.sh --allow-tracker`: see NOTES for the head it passed on.
- Device run built from the head: the eight 5a/5b soaks at 946a78c8e9. The final head needs one more run before the fold.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
