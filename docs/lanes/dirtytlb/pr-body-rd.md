Lane: dirtytlb            Issue: #548 #461
Base: master @ 7e6c069702 (merged; #549, the counter, folded there as be05285c44)
Files: accel/tcg/cputlb.c, docs/lanes/dirtytlb/NOTES.md, docs/lanes/dirtytlb/pr-body-rd.md, docs/lanes/dirtytlb/queue_rd.sh, docs/lanes/dirtytlb/queue_rd_black.sh, docs/lanes/dirtytlb/register_rd.sh, docs/lanes/dirtytlb/register_rd_black.sh, docs/testing/predictions/dirtytlb-rd.json, docs/testing/predictions/dirtytlb-rd-pixels.json, docs/testing/predictions/dirtytlb-rd-signed.json, docs/testing/predictions/dirtytlb-rd-black.json
Prediction: docs/testing/predictions/dirtytlb-rd.json @ 92ebdf9de2619d8f (hand-queued Crimson pair: every leg passes); docs/testing/predictions/dirtytlb-rd-pixels.json @ ec9a5c0cd3f4b252 (arms job: PASS, 318 of 318); docs/testing/predictions/dirtytlb-rd-signed.json @ 98b2fe4003f7490b (arms job, 3 runs per arm: PASS, 19 of 19). Those three: A 249ea8fd05, B 052551bdd3. docs/testing/predictions/dirtytlb-rd-black.json @ 7eabb78738a649de (hand-queued Black pair: E, T, U pass; X FAILS; C, F, J void): A 68cfc51e10, B a0d75c9a40.
Needs device: yes    Needs NDK: yes

Release note (performance): about 6 ms less CPU work per frame in Crimson Skies on the Ayn Thor (3.4 ms on the render thread, 3.0 ms on the emulated CPU's thread). The frame rate is unchanged at 29, because the game caps at 30, and battery use per frame did not measurably change.

The change is one line of `accel/tcg/cputlb.c` (commit 052551bdd3): `HAKUX_TCG68_RD` is on unless the environment sets it to 0. The counter it was measured with is #549, now on master.

**For the audit: one registered leg fails.** Leg X of `dirtytlb-rd-black.json` (the second title) fails on `sd` per flip, and that prediction says a failing X means the switch does not land. The section on Black below gives the reading and why this PR is offered anyway. Every leg of the other three predictions passes.

**What it changes.** `tlb_reset_dirty()` and `tlb_set_dirty()` scan every entry of every MMU mode, 22 of them, on each call. With the switch on they scan only the modes that can hold a live entry (`tlb.c.dirty`). The switch has been in the tree since #68 (PR #309), where it was audited as exact; it was turned off by default for #311's arms and never measured.

## Crimson Skies: every registered leg of `dirtytlb-rd.json` passes

Thor, regimen max, 240 s, 4,320 flips in each arm. A `1-1790620928-lane.dirtytlb-1387249` (`249ea8fd05`), B `1-1790620928-lane.dirtytlb-1386630` (`052551bdd3`), B first.

| per flip | A (all 22 modes) | B (live modes) | |
|---|---|---|---|
| entries scanned per walk | 7,772 | 1,923 | ×0.25 |
| µs per walk, render thread | 21.70 | 4.83 | ×0.22 |
| µs per walk, vCPU thread | 15.03 | 2.41 | ×0.16 |
| walk ms, render thread | 3.70 | 0.77 | −2.92 |
| walk ms, vCPU thread | 3.55 | 0.58 | −2.97 |
| render-thread CPU ms | 19.79 | 16.44 | −3.35 |
| vCPU walk share of its CPU | 11.2% | 1.8% | |
| gfps median | 29 | 29 | |
| flips taking 3+ VBLANKs | 4.3% | 0.8% | |
| `j_per_frame` | 0.1995 | 0.1977 | ×0.991 |

| leg | bar | read | |
|---|---|---|---|
| W | A's `[tlb68]` lines read `fx=rd0`, B's `fx=rd1` | every line | PASS |
| E | B scans its live entries (within 15%), at most 0.6 × A's | 1,923 against 1,834 live; ×0.25 | PASS |
| X | entries re-armed per walk and `sd` per flip within 15% of A's | vtx 1.03 / 0.97, vCPU 1.00 / 1.00, sd 473.3 / 469.1 | PASS |
| T | µs per render-thread walk at most 0.75 × A's | ×0.22 | PASS |
| U | µs per vCPU walk at most 0.75 × A's | ×0.16 | PASS |
| C | render-thread CPU per flip down by at least 1.0 ms | −3.35 ms | PASS |
| F | gfps not down by more than 1 | 29 / 29 | PASS |
| J | `j_per_frame` at most 1.03 × A's | ×0.991 | PASS |
| K1 | thermal parity | 39 cooling devices, every highest state equal | PASS |
| K2 | same scene, M within 10% | 11360 / 12001 | PASS |

Both run logs have no UtilAcceptVsock and no thermal pause, and both gameplay frames show the same tutorial prompt.

What the pair does not show:
- No fps gain and no energy gain. Crimson held 29 in both arms. Net power is the same to 0.2%, and `j_per_frame` is 0.9% lower, inside the 3% two unchanged runs differ by.
- The walks account for 2.92 of the 3.35 ms on the render thread. B also made 6% fewer render-thread walks and hashed 12% less texture per flip, so the two scenes differ a little.

## Pixels: both arms PASS

| prediction | suites | read |
|---|---|---|
| `dirtytlb-rd-pixels.json` | 11, through the vertex and texture paths, one run per arm | 318 of 318 captures byte-identical |
| `dirtytlb-rd-signed.json` | Texture signed component tests, three runs per arm | 19 of 19 byte-identical, none outside A's band |

## Black: the price is confirmed, the gain is not shown, and X fails

`dirtytlb-rd-black.json`. A `1-1790625921-lane.dirtytlb-4014378` (`68cfc51e10`), B `1-1790625918-lane.dirtytlb-4014114` (`a0d75c9a40`), Thor, regimen max, 760 s, window 500 to 760 s, B first.

Both gameplay frames show the first mission. Both arms reached the thermal pause inside the window: at +594 to +627 s in A and +690 to +724 s in B. That, and K2, void C, F and J as registered.

| leg | | read |
|---|---|---|
| G, V, W | PASS | both arms in the mission; 129 and 130 `[tlb68]` lines; `fx=rd0` / `fx=rd1` |
| E | PASS | entries per walk 9,458 / 4,158 (×0.44); B live 4,176 |
| X | **FAIL** | hits per walk vtx 0.83 / 0.93, vCPU 1.00 / 1.00 (inside 15%); `sd` per flip 125.3 / 162.0 (+29%) |
| T | PASS | µs per render-thread walk 49.77 / 16.71 (×0.34) |
| U | PASS | µs per vCPU walk 66.86 / 20.47 (×0.31) |
| C | void | 14.66 / 13.85 ms, −0.80 against a bar of −1.0; it would fail |
| F | void | gfps 22 / 24 |
| J | void | no `j_per_frame` in either arm |
| K1 | PASS | every highest cooling state equal (both paused) |
| K2 | FAIL | M 3911 / 4670, ×1.19 |

**On X.** The clause that fails is `sd` (calls to `tlb_set_dirty`) per flip. These readings are not registered legs:
- `sd` per walk is 1.209 in A and 1.209 in B over the window.
- Inside arm A, which has no switch, `sd` per `[tlb68]` line runs from 2,367 to 9,863 as the walks run from 2,019 to 8,038 (r = 0.997). So `sd` per flip follows how much the scene draws.
- B's scene draws more: 118.8 render-thread walks per flip against 85.7, and 3,044 KiB of texture hashed against 2,492. The route is timed presses, and the two arms already face different ways at the gameplay mark.
- An inexact walk leaves entries writable, which gives fewer `sd` and fewer hits per walk. B shows the same and more.

So the clause cannot tell an inexact walk from a heavier scene, which is a fault in how the leg was written. The registered verdict stays FAIL. The exactness evidence this PR rests on is the two pixel arms (337 captures byte-identical) and Crimson's X. NOTES.md gives the replicate that would test a per-walk X as a registered leg (24 min of the Thor); it is not queued.

**The pause-free part of the window, 500 to 590 s** (2,280 flips per arm; not registered):

| per flip | A | B | |
|---|---|---|---|
| entries scanned per walk | 9,456 | 4,160 | ×0.44 |
| µs per walk, render thread | 32.75 | 13.96 | ×0.43 |
| µs per walk, vCPU thread | 27.03 | 12.01 | ×0.44 |
| walks, render thread | 85.8 | 133.6 | |
| walk ms, render thread | 2.81 | 1.87 | |
| render-thread CPU ms | 10.70 | 13.56 | +2.86 |
| M | 3,961 | 5,196 | ×1.31 |
| gfps median | 26 | 24.5 | |

- Time follows entries on Black. At A's 85.8 walks per flip the saving is about 1.6 ms per flip on the render thread and 0.2 on the vCPU, of a 40 ms frame.
- No fps or CPU gain is shown on Black. B's scene is heavier, its render thread used more CPU per flip and its gfps was 1.5 lower; with the scenes 31% apart the pair cannot assign that.
- The registered ×0.34 and ×0.31 overstate the gain, because A's window holds more paused time and a walk costs more than twice as much under the pause.
- The prediction expected 236 walks and 17 ms per flip at 7 fps, from a run on `a593d8eb85`. On master `503b901ee4` arm A reads 86 walks and 2.8 ms at 26 fps, so the expected 5 to 10 ms was not there to save.

Midtown Madness 3 is priced offline at 5.2 ms of a 320 ms frame and gets no pair.

## Proof of the build

NDK clang type-check of `cputlb.c` and `physmem.c` with the shared tree's compile lines: no error, and no warning that master does not have. `check_android_guards.py` passes, and so do `walk_read.py --selftest` and `rdc_read.py --selftest`. The desktop build was not run (AGENTS.md: not possible on this host).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
