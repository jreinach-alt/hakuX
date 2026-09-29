# Audit pass 2: PR #549, lane/dirtytlb (#548)

Head verified: `9a09c00029` (pass-1 head `68cfc51e10` plus the pass-1 audit
file). `git diff 68cfc51e10 9a09c00029` touches only
`docs/audits/2026-09-28-dirtytlb-pass1.md`, so no code has changed since
pass 1.

**Result: clean. No HIGH or MEDIUM in pass 1; the three LOWs still cannot
fire in a build that ships. fold-ready.**

## Pass-1 scenarios, re-checked on this head

- **L1 (two "off the vCPU" tests).** The scenario needs a vCPU thread that
  resets another CPU's TLB. `hw/xbox/xbox.c:467` sets `m->max_cpus = 1`, so
  `CPU_FOREACH` in `tlb_reset_dirty_range_all` (`physmem.c:1273`) visits one
  CPU. `cputlb.c` sets `hakux_rdc_last_ns` only when `current_cpu != cpu`;
  with one CPU that means `current_cpu == NULL`, which is the same test
  `rdc_account` uses (`physmem.c:1228`). The two tests agree on every
  schedule the machine can run. Still LOW (quality).
- **L2 (`rdc_vkey` a plain static).** Written only for `RDC_DIRECT`
  (`physmem.c:1239-1248`). The callers of `physical_memory_dirty_bits_cleared`
  outside physmem are still only `hw/xbox/nv2a/pgraph/vk/draw.c:6961`
  (render thread) and `migration/ram.c:981` (does not run on Xbox), so there
  is one writer. A second DIRECT caller would make `vr` approximate and would
  already show in `dx`. Still LOW.
- **L3 (`rdc_tick` statics).** Unchanged: the `rdc_frame0` cmpxchg at
  `physmem.c:1130` still gates the window. A double tick needs 60 flips
  inside one tick. Worst case is one wrong log line. Still LOW.

The guest-visible path is also unchanged: `tlb_reset_dirty(cpu, start1,
length)` is still called with the same arguments for every CPU, and the added
code writes only its own counters and thread-locals.

## Verdict

Nothing to remediate. Remove `needs-audit-2`, add `fold-ready`.
