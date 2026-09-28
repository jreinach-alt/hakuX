Lane: dirtytlb            Issue: #548 #461
Base: master @ 01e62d8d1c, stacked on #549 (`lane/dirtytlb` @ 249ea8fd05)
Files: accel/tcg/cputlb.c, system/physmem.c, include/system/ram_addr.h, docs/lanes/dirtytlb/NOTES.md, docs/lanes/dirtytlb/pr-body.md, docs/lanes/dirtytlb/pr-body-rd.md, docs/lanes/dirtytlb/rdc_read.py, docs/lanes/dirtytlb/walk_read.py, docs/lanes/dirtytlb/typecheck.py, docs/lanes/dirtytlb/register_pixels.sh, docs/lanes/dirtytlb/register_signed.sh, docs/lanes/dirtytlb/register_rd.sh, docs/lanes/dirtytlb/queue_counter.sh, docs/lanes/dirtytlb/queue_rd.sh, docs/lanes/dirtytlb/requeue_crimson_b.sh, docs/lanes/dirtytlb/jpf.py, docs/testing/predictions/dirtytlb-counter-pixels.json, docs/testing/predictions/dirtytlb-counter.json, docs/testing/predictions/dirtytlb-counter-signed.json, docs/testing/predictions/dirtytlb-rd.json, docs/testing/predictions/dirtytlb-rd-pixels.json, docs/testing/predictions/dirtytlb-rd-signed.json
Prediction: docs/testing/predictions/dirtytlb-rd.json @ 92ebdf9de2619d8f (hand-queued Crimson pair); docs/testing/predictions/dirtytlb-rd-pixels.json @ ec9a5c0cd3f4b252 (arms job); docs/testing/predictions/dirtytlb-rd-signed.json @ 98b2fe4003f7490b (arms job, 3 runs per arm). A 249ea8fd05, B 052551bdd3.
Needs device: yes    Needs NDK: yes

Release note (performance): less CPU time per frame spent re-arming memory write tracking; the measured figure for Crimson Skies on the Ayn Thor is added here when the arm is read.

This PR is the fix #548's counter points to. It is stacked on #549 (the counter), and its own change is one line of `accel/tcg/cputlb.c` in commit 052551bdd3: `HAKUX_TCG68_RD` is on unless the environment sets it to 0.

**What it changes.** `tlb_reset_dirty()` and `tlb_set_dirty()` scan every entry of every MMU mode, 22 of them, on each call. With the switch on they scan only the modes that can hold a live entry (`tlb.c.dirty`). The switch has been in the tree since #68 (PR #309), where it was audited as exact; it was turned off by default for #311's arms and never measured.

**What the counter measured (both arms with the switch off):**

| run | live entries | entries per walk | µs per walk, render thread | µs per walk, vCPU |
|---|---|---|---|---|
| Crimson, Thor, 479870 | 1,793 | 7,204 | 21.11 | 14.19 |
| Crimson, Thor, 936387 | 2,620 | 7,992 | 24.25 | 16.44 |
| Blinx, Nova, 480001 | 606 | 5,882 | 14.53 | 13.98 |
| Blinx, Nova, 479942 | 612 | 5,881 | 12.83 | 13.04 |

On Crimson the render thread makes 170 to 177 walks per flip (3.6 to 4.3 ms) and the vCPU thread 237 to 242 (3.4 to 4.0 ms, 10.6 to 12.1% of its CPU). Two of the 22 modes hold entries. The other 20 are empty tables, and they are 67 to 75% of what each Crimson walk scans.

**What is predicted** (`dirtytlb-rd.json`, Crimson on the Thor, 240 s, B first):

| leg | bar |
|---|---|
| W | A's `[tlb68]` lines read `fx=rd0`, B's `fx=rd1` |
| E | B scans its live entries (within 15%) and at most 0.6 × A's entries per walk |
| X | entries re-armed per walk and `sd` per flip within 15% of A's: the walks still do the same work |
| T, U | µs per walk at most 0.75 × A's, on the render thread and on the vCPU thread |
| C | render-thread CPU per flip down by at least 1.0 ms |
| F | gfps not down by more than 1 |
| J | `j_per_frame` at most 1.03 × A's |
| K1, K2 | thermal parity, same scene |

No pgraph capture may move: `dirtytlb-rd-pixels.json` covers 11 suites through the vertex and texture paths, and `dirtytlb-rd-signed.json` runs the twelfth three times per arm.

**Results.** None yet: the pair and the two pixel arms are queued, not run.

**Proof of the build.** NDK clang type-check of `cputlb.c` and `physmem.c` with the shared tree's compile lines: no error, and no warning that master does not have. `check_android_guards.py` passes, and so do `walk_read.py --selftest` and `rdc_read.py --selftest`. The desktop build was not run (AGENTS.md: not possible on this host).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
