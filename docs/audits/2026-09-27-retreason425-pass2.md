# Audit pass 2: PR #460, lane.retreason425 (#425 return-split counters)

Head verified: `f300d62551`. Pass 1: `2026-09-27-retreason425-pass1.md` at
`3700b87707`. Auditor: job.cloud, 2026-09-27.

**Result: clean.** None of the pass-1 scenarios can occur at this head. The
new `[rr425w]` code that pass 1 never read has no HIGH or MEDIUM. Next state:
`fold-ready`.

## Pass-1 findings

### M1: refuted idle-halt code folds with a comment that says it is safe. Cannot occur.

The scenario was that a later lane sets `HAKUX_IDLE_HLT=1`, the title wedges
at boot, and nothing in the tree warns it. At `f300d62551`:

- `git grep -n -i -E 'idle_hlt|IDLE_HLT|RR_IH|spinning until' -- accel target include hw`
  returns nothing. `f13290431e` removes `idle_hlt_check`, `idle_hlt_on`, the
  `getenv("HAKUX_IDLE_HLT")`, the `RR_IH` enum and its `ih=` field, the
  `idle_hlt_armed` clears in `rr425_book` and `cpu_exec_longjmp_cleanup`, and
  the block comment that claimed spinning and waiting are the same. No code
  reads the variable any more, so setting it does nothing.
- The only mention left is in `docs/lanes/retreason425/NOTES.md`. §4 is headed
  as removed, and line 181 records the pilot
  `1-1790515918-retreason425-1213231` as **wedged at boot**. That is the
  record pass 1 asked for. `d259abab29` keeps the code in history.
- `retreason425-idlehlt-inert.json` still names `d259abab29`. That arm was
  judged (PASS, 593 checks). The file is a record, not a way to turn the flag
  on.

### L1: always-on diagnostic in the hot path. Decided.

NOTES §7 records that the counters stay always-on in XBOX builds until #425
and #412 close, as `[jc425]` does. This was the decision pass 1 asked for.

### L2, L3: idle-pc cache invalidation and read failures. Cannot occur.

The code these findings were about is gone. The new `rrw_sti` handles both
cases correctly anyway. The window's bytes are checked again every 2 s
(`rrw_tick` clears `rrw_idle_ok`), and a failed `cpu_memory_rw_debug` returns
without caching the pc.

## New code since pass 1 (`f13290431e`: `[rr425w]`)

I read the diff to `accel/tcg/cpu-exec.c`, `hw/xbox/nv2a/nv2a.c` and
`target/i386/tcg/system/seg_helper.c`.

- **Guards.** All the `rrw_*` state and functions sit inside the
  `#ifdef XBOX` block at `cpu-exec.c:1109-1456`. The `cpu_handle_interrupt`
  hooks, the `extern` in `seg_helper.c` and the store there are each under
  `#ifdef XBOX`. `hakux_nv2a_irq_units` is only built in `hw/xbox`.
- **Locking.** `rrw_wake` runs inside `cpu_handle_interrupt`'s
  `bql_lock()`/`bql_unlock()` span, so the NV2A pending/enabled reads happen
  with the BQL held. PGRAPH's pending word can also be written by the PGRAPH
  thread. For a diagnostic, a racy read of one `uint32_t` can at worst
  mislabel one wake; it cannot change emulation.
- **Bounds.** `rrw_slot` is a linear probe over 64 slots and counts overflow
  in `drop`. A NULL slot is handled on every path (`rrw_wake` sets
  `rrw_open = NULL`). In `rrw_tick`, `snprintf` is bounded by
  `sizeof(buf) - off`. One entry can in principle exceed the 96-byte
  headroom, but then `off` passes the loop guard and the loop stops. It never
  writes out of bounds. The stack cost is about 6 KB (a 4 KB copy plus a
  2 KB buffer) once every 2 s on the vCPU thread.
- **Semantics.** The vector is reset to -1 before `cpu_exec_interrupt`, so a
  wake that is not a PIC wake (for example an NMI) gets key `ff`, as the
  comment says. A busy period that is open at a window edge is split, and the
  open key's slot is re-created after the `memset`.
- **Pixel coverage.** `retreason425-wake-inert.json` registers the
  must-not-move leg (`6e4dee6a28` vs `e156fcdf02`). Its `[job.arms]` verdict
  has not arrived at this writing. The fold job's own gates decide whether it
  must arrive first. This audit does not.

### LOW (new, no action required)

- **N1.** An idle stretch ends only in `rrw_wake`. If the guest leaves the
  window by some other route, for example a longjmp or a reset while
  `rrw_idle` is set, the stretch keeps running until the next interrupt and
  books the time between as idle. This affects the readout only, and on a
  single vCPU the NT idle loop leaves only on an interrupt.
- **N2.** `rr425_tick`'s first call takes the `goto reset` path, which skips
  `rrw_tick`. The first `[rr425w]` window therefore also covers everything
  from boot to the second tick. The lane's reader already starts from a
  window range (`--from`), so this does no harm.
