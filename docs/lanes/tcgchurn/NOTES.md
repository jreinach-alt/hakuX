# lane.tcgchurn -- #68 translation-cache churn

Base: master @ 724a0dd868, merged with origin/master @ 90a8dc1c1a on
2026-09-25 (attempt 2). PR #309.

## Attempt 2 (2026-09-25): why attempt 1 did not finish

Attempt 1 wrote the `[tlb68]` instrument and the RD/JC switches below but
left all of it **uncommitted** in the worktree: no build, no push, no arm.
The session ended (turn cap) before the first commit. Nothing was lost; it is
committed as `5a492f7d6b`, unbuilt at the time. Lesson for the next attempt:
commit before building.

Attempt 2 was redirected by the host to **#311** (in-game collapse to 1-2
gfps; upstream v0.3.1 holds 29 on the same Thor). lane.ghoul311's model: ~200
code-arming walks (`tlb_reset_dirty`) a frame, each walking the whole dynamic
TLB, which grows. See "#311" below.

## What the 09-11 profile actually says (read before question (a))

The brief frames `tcg_flush_jmp_cache` (8.37% self) as the cost of *full TLB
flushes that clear the jump cache*. The inclusive profile of the same run
(`run-2026-09-11-crimson-profile-inclusive.txt`, local) does not support that
premise:

| symbol | incl | self |
|---|---|---|
| `do_tb_phys_invalidate` | 10.72% | 0.09% |
| `tcg_flush_jmp_cache` | 8.77% | 8.77% |
| `tlb_flush_by_mmuidx_async_work` | **0.01%** | 0.00% |
| `tb_link_page` | 11.56% | 0.11% |
| `tlb_reset_dirty_range_all` | 11.14% | 0.05% |
| `tlb_reset_dirty` | 11.02% | 10.97% |

So the jump-cache wipes come from **TB discards**, not TLB flushes:
`target/i386` sets `CF_PCREL` unconditionally, and `tb_jmp_cache_inval_tb()`
wipes every CPU's whole 4096-entry jump cache for every discarded PCREL block.
And `tlb_reset_dirty` is the **code-arming walk** (`tb_link_page` ->
`tlb_protect_code`), one per page that goes empty -> non-empty. Both were
already named in `tcg-counter-correction.md`; the brief's (a) is still counted
below, because a code reading of one profile is not a count.

The profile predates #73's fix. #73 raised the arming-walk rate (em/ev 0.06 ->
1.00, pr 930-1868 -> 2160-2199 per window, `tcg-invalidation-three-arm.md`), so
if anything the arming walk is a larger share now. No fresh lane.perfbase
profile exists yet (checked 2026-09-25; no open perfbase PR, nothing newer
than 09-11 under `docs/testing/perf/`).

## The instrument: one `[tlb68]` line every 2 s

Tag `hakuX`, priority WARN, prefix `[tlb68]` -- `hakuX` is in every runner's
LOGCAT_SPEC and `soak_title.sh` keeps it only at `:W`. A window without the
line is VOID. Emitted from `cpu_exec_loop` (clock read 1 in 1024 iterations).

| field | counts |
|---|---|
| `dt`, `cpu` | wall ms of the window; **vCPU thread CPU ms** (`CLOCK_THREAD_CPUTIME_ID`) |
| `ff`, `ffe` | full-flush async work calls; of which found no dirty mode |
| `cr3n`, `cr3s`, `cr0`, `cr4`, `a20`, `fo` | `ff` by cause: CR3 new value, CR3 same value, CR0, CR4, A20, other |
| `pf`, `pfl` | page flushes (INVLPG); mode flushes they forced because the page is inside a recorded large page |
| `jc`, `jct`, `jci`, `jcx`, `jcus` | jump-cache wipes; from a full TLB flush; from a PCREL discard; PCREL discards that skipped it (fix on); total us in wipes |
| `rd`, `rdc`, `rde`, `rdm`, `rdh`, `rdus` | `tlb_reset_dirty` on the vCPU thread; of which code arming; entries walked; modes walked; entries it changed; total us |
| `rdo`, `rdoe`, `rdous` | the same walk called from any other thread (nv2a dirty queries) |
| `sd` | `tlb_set_dirty` (notdirty write re-enabling a page) |
| `dm`, `sz` | dirty-mode mask now, and each dirty mode's fast-table size |
| `fx` | which fixes are on |

Times are the direct price the three-arm doc said the counters could not give
("Pricing it needs a direct timing instrument, not another soak").

## Two fixes, both exact rather than heuristic, both env-switchable

One binary carries both arms: `HAKUX_TCG68_RD=0` / `HAKUX_TCG68_JC=0` restore
the old paths (`request.sh --env`). Default on.

### RD: the dirty reset walks only the modes that can hold a live entry

`tlb_reset_dirty` walked all `NB_MMU_MODES` = 22 modes x (table + 8 victim).
i386 defines 8 mmu indexes and an Xbox title runs in ring 0 without SMAP, so
most modes are never filled; their 256-entry tables were walked every arm.
Now it walks `tlb.c.dirty`. `tlb_set_dirty` (every notdirty write) likewise.

- **What could go stale:** an entry left writable (no `TLB_NOTDIRTY`) on a
  page that now holds code, so a store to that code skips the notdirty slow
  path and the old translation keeps running.
- **Why it cannot:** a mode's `c.dirty` bit is set under `tlb.c.lock` by
  `tlb_set_page_full()` BEFORE it installs any entry in that mode. The only
  place a bit is cleared is `tlb_flush_by_mmuidx_async_work()`, in the same
  critical section that `memset(-1)`s that mode's fast AND victim tables.
  `tlb_init` starts all modes flushed with `dirty == 0`. So a clean mode holds
  only `-1` entries, which `tlb_reset_dirty_range_locked` already rejects on
  `TLB_INVALID_MASK`. Skipping them changes no entry. Victim swaps stay inside
  one mode, and resizes happen only inside a flush.
- **What would break it:** a new fill path that bypasses `tlb_set_page_full`,
  or a clear of a `c.dirty` bit without a flush. Neither is guest behaviour.

### JC: a PCREL discard no longer wipes the whole jump cache

- **What could go stale:** a jump-cache slot still pointing at the discarded
  TB, so a lookup at that virtual pc runs code the guest has rewritten.
- **Why it cannot:** the only reader of `jc->array[].tb` is `tb_lookup()`,
  which takes a slot only if `tb_cflags(tb) == s.cflags` exactly, and
  `s.cflags` never carries `CF_INVALID`. `do_tb_phys_invalidate()` sets
  `CF_INVALID` under `jmp_lock` before this point, so the slot misses on every
  lookup and the htable decides, as if it were NULL. A slot revives only if
  that same TB is **recycled** out of `inv_htable`, which needs
  `inv_tb_lookup_cmp`: the same phys page(s), key, and code bytes (ihash). The
  slot's virtual pc still maps to that page, because every TLB flush that
  could change the mapping clears the jump-cache page (per-page, range and
  full flush paths). That is the same invariant every PCREL jump-cache hit
  already relies on. TBs are never freed individually: `tb_flush` frees all
  and wipes every jump cache, and the tier-1 hot arena resets only there
  (`tcg_region_reset_all`).
- **One hole found and closed:** a recycled TB that loses the `tb_link_page`
  race is orphaned with `CF_INVALID` already cleared by the recycle, so a
  stale slot could run it forever after its page changes. `tb_gen_code` now
  re-sets `CF_INVALID` on that branch. It needs a second translating thread
  to reach.
- **What would break it:** a jump-cache reader that masks `CF_INVALID`, a
  path clearing `CF_INVALID` other than a recycle, or freeing one TB without
  `tb_flush`. None is guest-driven.

## Not done (yet), and why

- **(i) same-value CR3 / global pages.** A same-value MOV CR3 is
  architecturally a flush of all non-global entries. Skipping it is only legal
  for entries marked global under CR4.PGE, which QEMU does not track per
  entry. Priced after the counts: the profile puts the whole full-flush path at
  0.01%, so it is not built on a code reading.
- **(iii) the range test.** It is the larger prize (it removes discards and
  arming walks outright, not their unit cost), and its held form raised visits
  3,605x. A per-page code-granule bitmap that skips the page-list walk for
  stores that touch no code would address that. Deferred until RD and JC are
  measured, because they are exact and (iii) is not.

## Arm plan

- Counters and fixes in one commit. Both arms are the same binary:
  A = `HAKUX_TCG68_RD=0 HAKUX_TCG68_JC=0`, B = defaults.
- Crimson Skies soaks, both arms on one device (nova), three per arm.
- Pixel must-not-move: master vs this commit, eight unrelated suites, equality.

## #311: counters and the two candidate hunks (attempt 2)

### Counters added to the `[tlb68]` line

| field | counts |
|---|---|
| `tw` | entries walked by `tlb_reset_dirty`, every thread (= `rde` + `rdoe`) |
| `tn` | the largest fast-table size over ALL modes, at the line |
| `rs` | dynamic TLB resizes (either direction) in the window |
| `ka`, `kafb` | hunk (a): pages kept armed on emptying; disarmed later by its fallback |
| `fx=rd?jc?ka?tb?` | RD / JC env switches, and the two #311 build defines |

`tw / rdc` is ghoul311's `tw/pr` (entries per arming walk). Their
pre-registration (#311 comment 5839584187): `tw/pr` <= 4.2k at ~20 s, >= 64k
at ~120 s; refuted if it stays within 2x of its 20 s value while the frame
collapses. The A arm below measures it.

**RD and JC now default OFF** (attempt 1 had them on). They are unmeasured,
and the #311 arms must differ from master only by counters plus one hunk.
`HAKUX_TCG68_RD=1` / `HAKUX_TCG68_JC=1` turn them on for their own arm later.

### The hunks: one build define each, `#error` if both

`include/accel/tcg/hakux-tlb68.h`: `HAKUX_TCG311_KEEP_ARMED` (a) and
`HAKUX_TCG311_TLB_BOUND` (b), both default 0. A binary with both on does not
compile, so an arm names its hunk by sha.

**(b) bounds the walk.** Two parts in `cputlb.c`, both under the define:
1. **The cap.** The dynamic TLB grows to at most `1 << 13` entries per MMU
   index, against `CPU_TLB_DYN_MAX_BITS` = 20 for i386.
2. **An accounting fix,** found reading `tlb_set_page_full` (ghoul311 saw
   it too). A same-page refill takes the `tlb_hit_page_anyprot` branch, so it
   skips the decrement, but it still increments `n_used_entries`. An x86
   store to a page first filled by a load (to set PTE.D) is one such refill.
   The use rate that `tlb_mmu_resize_locked` reads therefore drifts up without
   more pages in use, and the table doubles at flushes. With the fix, a
   same-page refill does not count.

- **Correctness:** none at stake. A smaller direct-mapped TLB only misses
  more, and a miss refills through `tlb_fill`. The count only steers sizing.
- **Cost:** more TLB misses, if a title's working set exceeds 8k pages
  between flushes.

**(a) keeps an emptied page armed.** In `tb-maint.c`,
`tb_invalidate_phys_page_range__locked` does not `tlb_unprotect_code` when
the page empties. The next `tb_page_add` then calls `tlb_protect_code`.
`physical_memory_test_and_clear_dirty` finds the code bit already clear, so it
skips `physical_memory_dirty_bits_cleared` -> `tlb_reset_dirty_range_all`
(`system/physmem.c:1277`). No walk happens.

- **What could go stale:** nothing that can go stale today. The hazard in this
  area runs the other way: a page that HOLDS a block but is NOT armed, so a
  store skips `notdirty_write` and the block outlives the code it translated.
  Keeping a page armed only sends more stores through `notdirty_write`. That
  path invalidates whatever is on the page (here, nothing). It then sets dirty
  with `DIRTY_CLIENTS_NOCODE`, so the code bit stays clear. It calls
  `tlb_set_dirty` only when `!physical_memory_is_clean`, which is false while
  the code bit is clear.
- **Why it cannot go stale:** the next `tb_page_add` relies on one
  invariant: "code bit clear => no TLB entry writes this page without
  `TLB_NOTDIRTY`". A page that never emptied already relies on the same
  invariant. It holds because `tlb_set_page_full` adds `TLB_NOTDIRTY` whenever
  `physical_memory_is_clean`, and `tlb_set_dirty` is gated as above. DMA
  (`invalidate_and_set_dirty`) strips the code bit too. So does anything else
  that sets the code bit, such as the fallback's `tlb_unprotect_code`: the
  next `tb_page_add` then sees it dirty and walks, exactly as upstream. An
  empty-but-armed page is also not a new state: `tb_flush` empties every
  page list and disarms nothing.
- **What guest behaviour would break it:** none for correctness. For cost:
  a title that turns an ex-code page into a hot data buffer, because every
  store to it would take the slow path forever. That is why hunk (a) has a
  **runtime fallback**. A page that takes `HAKUX_TCG311_ARMED_IDLE_WRITES`
  (512) invalidation calls while empty is disarmed after all, which is the
  upstream path one step late. `kafb` counts those disarms. A high `kafb` with
  a low `ka` would mean the fallback carries the load and (a) is buying
  nothing.

**Which to arm first.** If ghoul311's since-when pair shows #73's unstrand
(`2af6def68a`) introduced the collapse, then (a) is the natural fix. It
reverses the re-arm churn #73 exposed, and it does not re-strand blocks: the
page list still empties, and only the dirty bit is left alone. (b) attacks the
unit cost instead, and would matter even if the re-arm rate were old.
