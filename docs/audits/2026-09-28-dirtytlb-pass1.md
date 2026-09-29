# Audit pass 1: PR #549, lane/dirtytlb (#548)

Head audited: `68cfc51e10`. Diff read: `git diff origin/master...HEAD`, code
files `accel/tcg/cputlb.c`, `include/system/ram_addr.h`, `system/physmem.c`,
plus the three prediction files and `pr-body.md`.

**Result: no HIGH, no MEDIUM, three LOW.**

## What was checked

- **Guest-visible behaviour is unchanged.** Under `XBOX`, both physmem sites
  (`physical_memory_test_and_clear_dirty`,
  `physical_memory_snapshot_and_clear_dirty`) and the public
  `physical_memory_dirty_bits_cleared` still reach
  `tlb_reset_dirty_range_all(start, length)` with the same arguments behind the
  same `tcg_enabled()` test. The walk and the bitmap clears are unchanged; the
  added code writes only its own statics and thread-locals.
- **Build guards agree.** `hakux_rdc_last_ns`/`_hits` are defined inside the
  `#ifdef XBOX` block that starts at `cputlb.c:96`, declared under `XBOX` in
  `ram_addr.h`, and used only under `XBOX` in `physmem.c`.
- **Doors.** `grep` over the tree finds exactly two callers of
  `physical_memory_dirty_bits_cleared` outside physmem:
  `hw/xbox/nv2a/pgraph/vk/draw.c:6961` (vertex sync) and `migration/ram.c:981`
  (does not run on Xbox). `tlb_reset_dirty_range_all` has no caller outside
  physmem. The `oth`/`dx` claims in the comment hold.
- **Charged time.** `hakux_rdc_last_ns` is set in the `current_cpu != cpu`
  branch of `tlb_reset_dirty`, and `rdc_account` reads it only when
  `current_cpu == NULL`, right after the call on the same thread, so it is
  never stale on the single-vCPU Xbox machine.
- **`vr` key.** `vsync_working.calls` is incremented at `draw.c:6868`, before
  the clear loop, and reset by `snapshot_vsync_timing()` in the same function
  that increments `frame_count` (`profile.c:242-247`). So
  `(frame_count, calls)` names one sync call.
- **`tm`.** `span = end - start` after page rounding; `walked` is
  `TARGET_PAGE_ALIGN(length)` pages. That matches the start-rounding gap the
  comment describes. The gap itself is upstream behaviour the PR counts
  without changing it.
- **Log line.** 512-byte buffer, each append guarded by `off < sizeof - 64`;
  the site loop worst case is about 8 x 90 characters, so a very long line can
  drop its tail fields but cannot overflow.
- **Evidence.** `dirtytlb-counter-signed.json` (3 runs per arm) supersedes the
  one-capture FAIL on `txt_A8R8G8B8_ADD`, and the PR body reports it: the
  capture differs among A's own runs. The one failed leg (H on Blinx, 1.21%
  against 1%) is reported as a failure and not re-scored after the fact.

## Findings

### L1 (LOW): two different "off the vCPU" tests

`tlb_reset_dirty` sets `hakux_rdc_last_ns` when `current_cpu != cpu`;
`rdc_account` charges it when `current_cpu == NULL`. With more than one vCPU,
a vCPU thread resetting another CPU's TLB would take the `rdo` branch in
cputlb but `rdc_v` in physmem, and C1's sum would miss it. Xbox has one vCPU,
so this cannot happen in any build that ships. Quality: use one test in both
places, or say in the comment that they coincide only with one vCPU.

### L2 (LOW): `rdc_vkey` is a plain shared static

`rdc_vkey` is read and written with no atomics. It is touched only for
`RDC_DIRECT`, and the only DIRECT caller that runs is the render thread's
vertex sync, so there is no second writer today. A second DIRECT caller on
another thread would make `vr` approximate, not unsafe (`dx` would already
flag that caller).

### L3 (LOW): `rdc_tick` statics rely on window spacing

The `p_*` baselines are protected only by the `rdc_frame0` cmpxchg. Two ticks
could run at once only if 60 guest flips passed while one thread was inside
`rdc_tick`, which is not a real schedule (`tk` measures a tick in
microseconds). Worst case is one wrong window line, not a crash.

## For pass 2

No remediation is required. Pass 2 only needs to confirm that no code change
has landed since `68cfc51e10`, or read any new code the same way.
