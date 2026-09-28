Lane: dirtytlb            Issue: #548 #461
Base: master @ 503b901ee4 (merged through `lane/dirtytlb` @ 68cfc51e10), stacked on #549
Files: accel/tcg/cputlb.c, system/physmem.c, include/system/ram_addr.h, docs/lanes/dirtytlb/NOTES.md, docs/lanes/dirtytlb/pr-body.md, docs/lanes/dirtytlb/pr-body-rd.md, docs/lanes/dirtytlb/rdc_read.py, docs/lanes/dirtytlb/walk_read.py, docs/lanes/dirtytlb/typecheck.py, docs/lanes/dirtytlb/register_pixels.sh, docs/lanes/dirtytlb/register_signed.sh, docs/lanes/dirtytlb/register_rd.sh, docs/lanes/dirtytlb/register_rd_black.sh, docs/lanes/dirtytlb/queue_counter.sh, docs/lanes/dirtytlb/queue_rd.sh, docs/lanes/dirtytlb/queue_rd_black.sh, docs/lanes/dirtytlb/requeue_crimson_b.sh, docs/lanes/dirtytlb/jpf.py, docs/testing/predictions/dirtytlb-counter-pixels.json, docs/testing/predictions/dirtytlb-counter.json, docs/testing/predictions/dirtytlb-counter-signed.json, docs/testing/predictions/dirtytlb-rd.json, docs/testing/predictions/dirtytlb-rd-pixels.json, docs/testing/predictions/dirtytlb-rd-signed.json, docs/testing/predictions/dirtytlb-rd-black.json
Prediction: docs/testing/predictions/dirtytlb-rd.json @ 92ebdf9de2619d8f (hand-queued Crimson pair, read: every leg passes); docs/testing/predictions/dirtytlb-rd-pixels.json @ ec9a5c0cd3f4b252 (arms job, running); docs/testing/predictions/dirtytlb-rd-signed.json @ 98b2fe4003f7490b (arms job, 3 runs per arm, queued). Those three: A 249ea8fd05, B 052551bdd3. docs/testing/predictions/dirtytlb-rd-black.json @ 7eabb78738a649de (hand-queued Black pair, queued): A 68cfc51e10, B a0d75c9a40.
Needs device: yes    Needs NDK: yes

Release note (performance): about 6 ms less CPU work per frame in Crimson Skies on the Ayn Thor (3.4 ms on the render thread, 3.0 ms on the emulated CPU's thread). The frame rate is unchanged at 29, because the game caps at 30, and battery use per frame did not measurably change.

This PR is the fix #548's counter points to. It is stacked on #549 (the counter), and its own change is one line of `accel/tcg/cputlb.c` in commit 052551bdd3: `HAKUX_TCG68_RD` is on unless the environment sets it to 0.

**What it changes.** `tlb_reset_dirty()` and `tlb_set_dirty()` scan every entry of every MMU mode, 22 of them, on each call. With the switch on they scan only the modes that can hold a live entry (`tlb.c.dirty`). The switch has been in the tree since #68 (PR #309), where it was audited as exact; it was turned off by default for #311's arms and never measured.

**Result: every registered leg of `dirtytlb-rd.json` passes.** Crimson Skies on the Thor, regimen max, 240 s, 4,320 flips in each arm. A `1-1790620928-lane.dirtytlb-1387249` (`249ea8fd05`), B `1-1790620928-lane.dirtytlb-1386630` (`052551bdd3`), B first.

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

**What the pair does not show.**
- No fps gain and no energy gain. Crimson held 29 in both arms. Net power is the same to 0.2%, and `j_per_frame` is 0.9% lower, inside the 3% two unchanged runs differ by.
- The walks account for 2.92 of the 3.35 ms on the render thread. B also made 6% fewer render-thread walks and hashed 12% less texture per flip, so the two scenes differ a little.
- One pair on one title. The late-flip figure is reported, not judged.

**Pixels.** No pgraph capture may move. `dirtytlb-rd-pixels.json` covers 11 suites through the vertex and texture paths and `dirtytlb-rd-signed.json` runs the twelfth three times per arm. The arms job is running them; this PR stays a draft until both are judged.

**A second title, Black** (`dirtytlb-rd-black.json`, queued). Black has the largest render-thread walk cost on record: 236 walks and 17.1 ms per flip at 7 fps (lane.slowtier2's reading, `titleroutes-3358750`). Its live table is 4,096 entries, so the empty modes are 56% of each walk, against Crimson's 75%, and a walk costs three to seven times as much per entry. The pair measures that instead of carrying Crimson's ratio over. Midtown Madness 3 is priced offline at 5.2 ms of a 320 ms frame and gets no pair.

**Proof of the build.** NDK clang type-check of `cputlb.c` and `physmem.c` with the shared tree's compile lines: no error, and no warning that master does not have. `check_android_guards.py` passes, and so do `walk_read.py --selftest` and `rdc_read.py --selftest`. The desktop build was not run (AGENTS.md: not possible on this host).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
