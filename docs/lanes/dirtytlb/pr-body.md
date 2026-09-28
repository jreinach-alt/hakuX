Lane: dirtytlb            Issue: #548 #461
Base: master @ 9d777502fad74be5933aac4330fb4cdd9fc1b51e
Files: system/physmem.c, include/system/ram_addr.h, accel/tcg/cputlb.c, docs/lanes/dirtytlb/NOTES.md, docs/lanes/dirtytlb/pr-body.md, docs/testing/predictions/dirtytlb-counter.json
Prediction: pending (docs/testing/predictions/dirtytlb-counter.json)
Needs device: yes    Needs NDK: yes

Per-caller count of `tlb_reset_dirty` calls and time off the vCPU thread, to name the ~103 resets per flip that #461's `[tlb68]` `rdo` cannot attribute. In progress.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
