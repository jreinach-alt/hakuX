# Audit pass 1: PR #309, lane/tcgchurn (#68, #311)

Auditor: job.cloud, 2026-09-25.  Head audited: `4ef1300091`.  Read against
`origin/master...HEAD`: `accel/tcg/cputlb.c` (+345/-6), `accel/tcg/tb-maint.c`
(+91), `accel/tcg/translate-all.c` (+26), `accel/tcg/cpu-exec.c` (+8),
`target/i386/helper.c` (+9), the new `include/accel/tcg/hakux-tlb68.h` (+75),
the three predictions and the lane NOTES.

**Result: no HIGH, no MEDIUM, four LOW.**  Next label: `needs-audit-2`.

## What runs at the head, checked

The PR ships four things, and only the first two run by default.

1. **The `[tlb68]` counters and timers** (always on under `XBOX`).
2. **The orphan fix in `tb_gen_code()`** (always on under `XBOX`).
3. **Two env switches**, `HAKUX_TCG68_RD` and `HAKUX_TCG68_JC`.  Both default
   off and are read once.
4. **The two #311 hunks** behind build defines.  Both are 0 at the head, and
   an `#error` stops a build that sets both.

- **`tlb_reset_dirty` / `tlb_set_dirty` with the switch off.** The loop became
  `for (walk = ALL_MMUIDX_BITS; walk; walk &= walk - 1) mmu_idx = ctz32(walk)`.
  `MMUIdxMap` is `uint32_t` (`include/hw/core/cpu.h:205`), so this visits
  exactly 0..NB_MMU_MODES-1, which is the old loop.
  `tlb_reset_dirty_range_locked()` now returns whether it set `TLB_NOTDIRTY`.
  Its only caller is this loop, and the entry update is unchanged.
- **`HAKUX_TCG68_RD` (off) is exact, as claimed.** `c.dirty` is written in
  three places (grep `c.dirty`, cputlb.c):
  - `tlb_init()` zeroes it with every mode flushed;
  - `tlb_set_page_full()` (:1451) sets the bit under `c.lock` before it
    installs an entry;
  - `tlb_flush_by_mmuidx_async_work()` (:613-621) clears exactly `to_clean`
    and flushes those same modes in the same critical section.

  The other flushes (large page, range) leave the bit set, which is the
  conservative direction.  So a mode with a clear bit holds only -1 entries.
  `tlb_reset_dirty()` reads the map under the lock, and it rejects -1 on
  `TLB_INVALID_MASK`.  `tlb_set_dirty1_locked()` matches only
  `addr | TLB_NOTDIRTY`, which -1 never is.
- **`HAKUX_TCG68_JC` (off): the argument holds for every reader.** Two sites
  store `jc->array[].tb`, `tb_lookup()` and `cpu_exec_loop()`'s miss path
  (cpu-exec.c:1017, :1757).  Only `tb_lookup()` reads it (:1003).  It requires
  `tb_cflags(tb) == s.cflags` exactly, and it asserts that `s.cflags` never
  carries `CF_INVALID`.  A stale slot to a discarded TB therefore misses until
  that TB is recycled.  A recycled TB carries the same phys page(s) and bytes,
  and the page-flush path still clears two jump-cache pages per flushed page
  (cputlb.c:799-800), so the revived slot runs correct code.
- **The orphan fix (translate-all.c, on by default) is inert without JC.**
  Only a *recycled* TB that loses `tb_link_page()`'s race reaches the new
  `else`.  Nothing references it afterwards: it is out of `inv_htable`, out of
  the htable, on no page list, and `tcg_tb_remove()` takes it out of the region
  tree.  Setting `CF_INVALID` on it changes nothing observable.  Its jmp_lock
  was initialised when the TB was first generated (recycle jumps past
  `qemu_spin_init`, but the lock is still live).
- **Cause tagging (helper.c).** `HAKUX_TLB68_SET_CAUSE` is an assignment to an
  int that always holds a valid enum.  `tlb_flush_by_mmuidx_async_work()`
  consumes it and resets it to OTHER, so the index into
  `hakux_tlb68_cause_n[]` is always in range.  Without `XBOX` the macro
  expands to nothing, and `same` is marked `G_GNUC_UNUSED`.
- **The tick.** It runs on the vCPU thread only, gated to one call in 1024
  loop iterations and to one line per 2 s by the clock.  The `sz[96]`
  builder stops at `off < 84`.  One entry is at most 11 characters
  (`,15:1048576`), so `snprintf` never truncates mid-entry and `off` never
  passes the buffer.  The table sizes it reads (`fast->mask`) change only on
  the vCPU thread.
- **Cost at the head.** There are two `get_clock()` reads per
  `tlb_reset_dirty()`, bracketing a walk of thousands of entries, and two per
  `tcg_flush_jmp_cache()`, bracketing 4096 stores.  There are plain increments
  elsewhere, and a counter test once per 1024 blocks in the exec loop.
- **Hunk (a)** (`HAKUX_TCG311_KEEP_ARMED`, 0): `tbs_seen` exists in
  `tb_invalidate_phys_page_range__locked` (tb-maint.c:1704).  `armed_idle` is
  under the page lock like `first_tb`, and the 512-call fallback disarms
  through the upstream `tlb_unprotect_code()`.  The "kept armed only sends
  more stores through notdirty" argument is the safe direction.
- **Hunk (b)** (`HAKUX_TCG311_TLB_BOUND`, 0): the ceiling changes only the
  growth branch of `tlb_mmu_resize_locked()`.  The `same_page_refill`
  bookkeeping skips one `n_used_entries++` for a slot that is already counted.
  Neither can make a lookup wrong.
- **PR body.** `Files:` matches `git diff --stat origin/master...HEAD` (10
  paths).  CI: build ×2 is green on this head.  GitHub reports the PR
  MERGEABLE.

## Findings

### L1: the `[tlb68]` line is unconditional in every XBOX build

`accel/tcg/cputlb.c:192-197,257` (`TLB68_LOG`), `accel/tcg/cpu-exec.c:1810`.

**Scenario:** every user build writes a WARN line to logcat every 2 s for the
life of the session.  On desktop it writes to stderr, so a user who runs from
a terminal sees a `[tlb68] w=... dt=...` line every 2 s forever.

**Why LOW:** the cost is negligible.  There is also precedent:
`tb_cache_maybe_log_stats()` is equally ungated, and soak tooling depends on
the line existing.

**Suggested:** gate the print (not the counters) on an env var or
`qemu_loglevel`, or record that it ships on purpose.

### L2: the header comment's thread claim is wrong for five counters

`accel/tcg/cputlb.c:121-122`.

**The claim:** "written from the vCPU thread except the rd*o ones".

**Why it is wrong:** five counters are also written by whichever thread
invalidates a TB:
- `hakux_tlb68_jc` and `hakux_tlb68_jc_ns` (`tcg_flush_jmp_cache()`, reached
  through `CPU_FOREACH` in `tb_jmp_cache_inval_tb()`);
- `hakux_tlb68_jci` and `hakux_tlb68_jcx` (tb-maint.c);
- `hakux_tlb68_ka` and `hakux_tlb68_kafb` (in
  `tb_invalidate_phys_page_range__locked`).

`address_space_write()` → `invalidate_and_set_dirty()` →
`tb_invalidate_phys_range()` reaches all of these from a device thread.

**Scenario:** a device thread writes guest RAM that holds code while the vCPU
flushes its jump cache.  The two non-atomic `++` race, and one of them is
lost, so `jc`/`jci` under-count by that event.

**Why LOW:** this is instrument accuracy only, on a path that is rare on
the Xbox's single vCPU.

**Suggested:** fix the comment, or use `qatomic_add` as the `rdo*` counters
do.

### L3: a flush cause set off the vCPU thread can be charged to the wrong flush

`include/accel/tcg/hakux-tlb68.h:58`, `target/i386/helper.c`.

**How it happens:** `hakux_tlb68_cause` is a single global.  The vCPU thread
consumes it in `tlb_flush_by_mmuidx_async_work()`.  But a CR0 or A20 update
can come from outside the vCPU thread, for example reset, or `loadvm`'s
`cpu_post_load`.  There, `tlb_flush()` queues the work asynchronously and the
cause stays set until the work runs.  Any vCPU-side flush that runs first
with an untagged cause (OTHER) takes the tag instead.

**Scenario:** reset sets CR0 from the main thread.  An untagged flush on the
vCPU is counted as `cr0`, and the queued one is counted as `fo`.

**Why LOW:** one misattributed count per such event, instrument only.

**Suggested:** record it in NOTES as a known limitation.

### L4: two refuted or void experiment hunks fold into master as dead code

`accel/tcg/tb-maint.c` (hunk (a), about 40 lines plus a `PageDesc` field) and
`accel/tcg/cputlb.c` (hunk (b)).

**What the PR's own verdict says:** Mb failed, Ma is void, and (a) "was not
re-queued" because it cannot reach the target.  Both hunks compile to nothing
at the head.

**Scenario:** a later lane sets `HAKUX_TCG311_KEEP_ARMED=1` on the strength of
the in-code rationale, which reads as endorsed.  The NOTES verdict that the
hunk cannot reach the target sits in another file.

**Why LOW:** this is dead code under a define, with an `#error` against
carrying both.

**Suggested:** either drop both hunks from the fold (their arm refs
`ea1e9f5a0d` and `1ce8693eb1` keep them reachable), or add one line at each
`#if` that states the #311 verdict and points to the NOTES.

## What pass 2 should check

No HIGH or MEDIUM findings need remediation.  Pass 2 should confirm that a
decision is logged for each of L1-L4, whether fixed or "reviewed, not fixed,
because X".  If any code changes for L2 or L4, it should re-read the diff.
