Lane: dirtytlb            Issue: #548 #461
Base: master @ 01e62d8d1c (merged in 0794c79011)
Files: system/physmem.c, include/system/ram_addr.h, accel/tcg/cputlb.c, docs/lanes/dirtytlb/NOTES.md, docs/lanes/dirtytlb/pr-body.md, docs/lanes/dirtytlb/rdc_read.py, docs/lanes/dirtytlb/walk_read.py, docs/lanes/dirtytlb/typecheck.py, docs/lanes/dirtytlb/register_pixels.sh, docs/lanes/dirtytlb/register_signed.sh, docs/lanes/dirtytlb/queue_counter.sh, docs/lanes/dirtytlb/requeue_crimson_b.sh, docs/lanes/dirtytlb/jpf.py, docs/testing/predictions/dirtytlb-counter-pixels.json, docs/testing/predictions/dirtytlb-counter.json, docs/testing/predictions/dirtytlb-counter-signed.json
Prediction: docs/testing/predictions/dirtytlb-counter-pixels.json @ e8a16cbad1887af2 (arms job, judged: FAIL 1 of 337); docs/testing/predictions/dirtytlb-counter.json @ 9958108858b87deb (hand-queued soaks, both pairs read); docs/testing/predictions/dirtytlb-counter-signed.json @ 29826cf5732abeae (arms job, 3 runs per arm, judged: PASS, 19 of 19, and it supersedes the FAIL)
Needs device: yes    Needs NDK: yes

Release note (none): instrumentation only, a hakuX-perf counter line.

This PR adds a per-caller count of the `tlb_reset_dirty` walks made off the vCPU thread. It names the ~103 resets per flip that #461's `[tlb68]` `rdo` could not attribute. It only counts: no walk is added or skipped.

**The count.** One `[rdc]` line on hakuX-perf every 60+ guest flips. Every walk goes through one door (`physical_memory_dirty_bits_cleared` → `tlb_reset_dirty_range_all`), so the caller is tagged there. `vtx` is the Vulkan vertex RAM sync and `tex` is `check_texture_dirty`. Each other physmem site has its own tag, and `oth` counts untagged walks (must read 0). Each site reports calls, walk µs, pages and hits (TLB entries re-armed). `vr` counts vertex walks that repeat within one sync call; that is the price of one walk per draw over the span of its ranges. `tcpu` is render-thread CPU per window. The line also reports its own measured cost (`ovh`, `tk`).

**Crimson Skies (Thor, gameplay, 4,140 flips), per flip:**

| site | calls | µs | pages | hits | µs/call |
|---|---|---|---|---|---|
| vtx | 126.3 | 3052 | 262.4 | 137.9 | 24.2 |
| tex | 50.1 | 1228 | 6626.7 | 74.3 | 24.5 |
| total (rdo/rdous) | 176.4 | 4280 | | | |

The vertex sync makes 72% of the walks and the texture check 28%. No other caller makes any (`vga`, `oth` and `dx` are 0). The render thread's CPU is 21.58 ms per flip, so the walks are 19.8% of it. Every registered leg passes on this pair, including H (the counter costs 216 ns per call, 0.91% of rdous). gfps is 29 in both arms, and j_per_frame is 0.193 in A and 0.190 in B.

**Blinx (Nova, hands-off `survey` scene; no route reaches gameplay), per flip:**

| site | calls | µs | pages | hits | µs/call |
|---|---|---|---|---|---|
| vtx | 23.0 | 293 | 42.7 | 5.8 | 12.7 |
| tex | 0.2 | 3 | 19.6 | 6.0 | 20.8 |
| snap | 0.2 | 4 | 68.9 | 0.0 | 16.0 |
| total (rdo/rdous) | 23.4 | 300 | | | |

The render thread's CPU is 49.2 ms per flip, and gfps is 10 in both arms. On Blinx the walks take 0.6% of render CPU. Every leg passed except one. **H FAILS as registered on Blinx:** the counter costs 129 ns per call, 1.21% of rdous against a 1% bar. Blinx's walks are cheap (12.7 µs each), so the ratio is high; in absolute terms the cost is 3.6 µs per flip.

**What the counts point to.** `vr` is 0 on both titles, so one walk per draw over the span of its ranges saves nothing. On Crimson nearly every vertex walk re-arms an entry (1.09 hits per walk), so those walks do needed work. The cost is in the walk itself: `walk_read.py` reads 7,204 to 7,992 entries scanned per walk across all 22 MMU modes, of which 1,793 to 2,620 are in the two modes that hold entries. The fix is on `lane/dirtytlb-rd`, stacked on this branch, with its own prediction.

**The pixel arm.** The 12-suite arm failed as registered on one capture of 337: `Texture_signed_component_tests/txt_A8R8G8B8_ADD` read 168,960 px in A and 153,427 in B, one run each. The other 336 captures were byte-identical, with no unreadable rows and no UtilAcceptVsock. `dirtytlb-counter-signed.json` reran that suite with three runs per arm and **passes**, 19 checks of 19. The capture varies inside arm A, which is master with no counter: A's run 1 differs from its runs 2 and 3 in 512 px, and B's three runs all match A's runs 2 and 3. So the capture moves run to run on its own. The arms job counts the earlier FAIL as superseded and labels this PR `verified`.

**Proof of the build.** NDK clang type-check of both C files with the shared tree's compile lines (no new warnings). `check_android_guards.py` passes, and so do `rdc_read.py --selftest` and `walk_read.py --selftest`. The desktop build was not run (AGENTS.md: not possible on this host).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
