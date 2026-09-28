Lane: dirtytlb            Issue: #548 #461
Base: master @ 9d777502fad74be5933aac4330fb4cdd9fc1b51e
Files: system/physmem.c, include/system/ram_addr.h, accel/tcg/cputlb.c, docs/lanes/dirtytlb/NOTES.md, docs/lanes/dirtytlb/pr-body.md, docs/lanes/dirtytlb/rdc_read.py, docs/lanes/dirtytlb/typecheck.py, docs/lanes/dirtytlb/register_pixels.sh, docs/testing/predictions/dirtytlb-counter-pixels.json, docs/testing/predictions/dirtytlb-counter.json
Prediction: docs/testing/predictions/dirtytlb-counter-pixels.json @ e8a16cbad1887af2 (arms job); docs/testing/predictions/dirtytlb-counter.json @ 45a38f378e23c692 (hand-queued soaks)
Needs device: yes    Needs NDK: yes

A per-caller count of the `tlb_reset_dirty` walks made off the vCPU thread, to name the ~103 resets per flip that #461's `[tlb68]` `rdo` could not attribute. Counter only: no behaviour change.

**The count.** One `[rdc]` line on hakuX-perf every 60+ guest flips. Every walk comes through one door (`physical_memory_dirty_bits_cleared` → `tlb_reset_dirty_range_all`), so the caller is tagged there. `vtx` is the Vulkan vertex RAM sync, `tex` is `check_texture_dirty`, and the other physmem sites get their own tags. `oth` counts untagged walks and must read 0. Each site reports calls, walk µs (the time `tlb_reset_dirty` already measures for rdous, so there is no second clock read), pages, and hits (TLB entries the walk actually re-armed). The line also carries render-thread CPU per window (`tcpu`) and its own measured cost: one walk in 64 is timed (`ovh`), plus the cost of printing the line (`tk`).

**From reading the code.** The Vulkan surface check clears dirty bits only under `!tcg_enabled()`, so it never walks. That leaves the vertex sync as the only live candidate beside textures. Separately, `tlb_reset_dirty_range_all` (upstream code) rounds `start` down but keeps `length`. An unaligned range therefore walks one page short, leaving that page's writable entry in place while its dirty bits read clean. This PR counts that gap (`tm`) and does not change it.

**Proof so far.** NDK clang type-check of both C files with the shared tree's compile lines (no new warnings). `check_android_guards.py` passes. `rdc_read.py --selftest` passes. Desktop was not built (AGENTS.md: not possible on this host).

Pending: the pixel arm (arms job), then the four soaks (Crimson on the Thor, Blinx on the Nova, B first), which are queued behind the battery holds.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
