Lane: dirtytlb            Issue: #548 #461
Base: master @ 01e62d8d1c (merged in 0794c79011)
Files: system/physmem.c, include/system/ram_addr.h, accel/tcg/cputlb.c, docs/lanes/dirtytlb/NOTES.md, docs/lanes/dirtytlb/pr-body.md, docs/lanes/dirtytlb/rdc_read.py, docs/lanes/dirtytlb/typecheck.py, docs/lanes/dirtytlb/register_pixels.sh, docs/lanes/dirtytlb/register_signed.sh, docs/lanes/dirtytlb/queue_counter.sh, docs/lanes/dirtytlb/requeue_crimson_b.sh, docs/lanes/dirtytlb/jpf.py, docs/lanes/dirtytlb/queue.log, docs/lanes/dirtytlb/read-blinx.txt, docs/lanes/dirtytlb/read-blinx-pair461.txt, docs/lanes/dirtytlb/read-crimson-A.txt, docs/lanes/dirtytlb/read-pixels.txt, docs/testing/predictions/dirtytlb-counter-pixels.json, docs/testing/predictions/dirtytlb-counter.json, docs/testing/predictions/dirtytlb-counter-signed.json
Prediction: docs/testing/predictions/dirtytlb-counter-pixels.json @ e8a16cbad1887af2 (arms job, judged: FAIL 1 of 337); docs/testing/predictions/dirtytlb-counter.json @ 45a38f378e23c692 (hand-queued soaks); docs/testing/predictions/dirtytlb-counter-signed.json @ 29826cf5732abeae (arms job, 3 runs per arm)
Needs device: yes    Needs NDK: yes

Release note (none): instrumentation only, a hakuX-perf counter line.

This PR adds a per-caller count of the `tlb_reset_dirty` walks made off the vCPU thread. It names the ~103 resets per flip that #461's `[tlb68]` `rdo` could not attribute. It only counts: no walk is added or skipped.

**The count.** One `[rdc]` line on hakuX-perf every 60+ guest flips. Every walk goes through one door (`physical_memory_dirty_bits_cleared` → `tlb_reset_dirty_range_all`), so the caller is tagged there. `vtx` is the Vulkan vertex RAM sync and `tex` is `check_texture_dirty`. Each other physmem site has its own tag, and `oth` counts untagged walks (must read 0). Each site reports calls, walk µs, pages and hits (TLB entries re-armed). `vr` counts vertex walks that repeat within one sync call; that is the price of one walk per draw over the span of its ranges. `tcpu` is render-thread CPU per window. The line also reports its own measured cost (`ovh`, `tk`).

**Blinx (Nova, hands-off `survey` scene; no route reaches gameplay), per flip:**

| site | calls | µs | pages | hits | µs/call |
|---|---|---|---|---|---|
| vtx | 23.0 | 293 | 42.7 | 5.8 | 12.7 |
| tex | 0.2 | 3 | 19.6 | 6.0 | 20.8 |
| snap | 0.2 | 4 | 68.9 | 0.0 | 16.0 |
| total (rdo/rdous) | 23.4 | 300 | | | |

The render thread's CPU is 49.2 ms per flip, and gfps is 10 in both arms. `vr` is 0, and `oth`, `dx` and `vga` are all 0. On Blinx the walks take 0.6% of render CPU, and the vertex sync already makes one walk per draw. There is nothing here worth removing.

Every leg passed except one. **H FAILS as registered:** the counter costs 129 ns per call, 1.21% of rdous against a 1% bar. Blinx's walks are cheap (12.7 µs each), so the ratio is high; in absolute terms the cost is 3.6 µs per flip.

**The pixel arm FAILS as registered on one capture of 337.** `Texture_signed_component_tests/txt_A8R8G8B8_ADD` reads 168,960 px in A and 153,427 in B; B's upper quads show a stale texture. The other 336 captures are byte-identical. There are no unreadable rows and no UtilAcceptVsock. The counter changes only timing, and this capture has moved under unrelated changes before, but one run per arm cannot tell those apart. `dirtytlb-counter-signed.json` reruns that suite with three runs per arm.

**Crimson (Thor):** A is valid (gfps 29, j_per_frame 0.193). The first B run aborted with the displays off before the route's first input. It is requeued as `1-1790619096-lane.dirtytlb-936387`, and Crimson decides the fix.

**Proof of the build.** NDK clang type-check of both C files with the shared tree's compile lines (no new warnings). `check_android_guards.py` passes, and so does `rdc_read.py --selftest`. The desktop build was not run (AGENTS.md: not possible on this host).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
