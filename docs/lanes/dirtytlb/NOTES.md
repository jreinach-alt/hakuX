# lane.dirtytlb (#548)

Who calls `tlb_reset_dirty` off the vCPU thread, per flip, and what each
caller costs. #461 pair 1 (Crimson, Thor, master `f131dd11`) read ~175 such
walks per flip at ~27 us each, 4.7 ms per flip, with the texture path at most
41% of them.

## What the code says, before any run

- `tlb_reset_dirty()` has one caller, `tlb_reset_dirty_range_all()`
  (system/physmem.c), whose only caller is `physical_memory_dirty_bits_cleared()`.
  So one door, and every caller can be tagged there.
- Render-thread callers on the Vulkan backend:
  - **vertex RAM sync**, `pgraph/vk/draw.c` (~6961): calls
    `physical_memory_dirty_bits_cleared()` directly, once per dirty merged
    range, per draw.
  - **`check_texture_dirty()`**, `pgraph/vk/texture.c` (~636):
    `memory_region_test_and_clear_dirty(..., DIRTY_MEMORY_NV2A_TEX)`, which
    walks only when a bit was set.
  - The **surface check** (`pgraph/vk/surface.c` ~4377) clears NV2A bits only
    under `!tcg_enabled()`, so it never walks. Of lane.remote's two
    candidates, only the vertex sync is live.
- **A tail-page gap, upstream's too.** `tlb_reset_dirty_range_all()` rounds
  `start` down to a page and passes the caller's `length` unchanged, and
  `tlb_reset_dirty_range_locked()` tests each entry's page start against
  `[start, start + length)`. A range that starts mid-page and ends in the next
  page within the same offset walks one page short: that page's writable TLB
  entry survives while its bits read clean, so guest stores through it set no
  dirty bit. Texture ranges are page-aligned by `check_texture_dirty()`, so
  the exposure is the unaligned vertex ranges (whose own bitmap loop also
  stops a page short). Counted as `tm` on physmem's sites; not changed.

## The counter (commits c911c012db .. 111c7fea74)

`[rdc]` on hakuX-perf, one line per 60+ flips, every field this window's:

    [rdc] f= dt= tid= tcpu= rdo= rdous= vtx=n/us/pg/h nv2a= tex= vga= code=
          mig= snap= oth= v= dra= dx= tm= ovh=ns/n tk=

- `<site>=calls/us/pages/hits`. The us are the walk time `tlb_reset_dirty()`
  already took for rdous (a thread-local, no second clock read); hits are the
  entries the walk set `TLB_NOTDIRTY` on, i.e. whether the walk did anything.
- `tcpu`: the printing thread's CPU ms over the window. The render thread
  prints (its walks are what cross the window), so this is render-thread CPU
  per window; `-` when a different thread printed the previous line.
- `oth` must be 0 (an untagged door); `dx` must be 0 (a second outside caller).
- **Overhead, measured not argued**: one walk in 64 times the accounting
  between two clock reads (`ovh`), and each line reports the previous line's
  own cost (`tk`). `rdc_read.py` turns them into us per flip against rdous.
- Built: NDK clang type-check of physmem.c and cputlb.c from the shared
  tree's compile_commands (`typecheck.py`), no new warnings;
  `check_android_guards.py` ok. Desktop not built (AGENTS.md: unmeetable here).

## Predictions

- `dirtytlb-counter-pixels.json`: 12 suites through the vertex and texture
  paths, must not move, A master `9d777502fa`, B `111c7fea74`. Queued by the
  arms job.
- `dirtytlb-counter.json`: the soak legs (V, C1, C2, H, N1, N2, X, F, K1, K2),
  hand-queued, B first then A, 240 s perflog: Crimson on the Thor, Blinx on
  the Nova. Judge: `rdc_read.py --pair A B` (selftest: `--selftest`).

## The fix (not yet chosen)

What the counts would point to:
- vtx dominant and **hits well below calls**: the walks mostly re-arm nothing
  (the page was already NOTDIRTY because the guest has not written it since
  the last clear). Clear once per flip for the vertex client instead of per
  draw, in draw.c (lane.forza414's file: ask by board request).
- vtx dominant and **hits near pages**: each walk is needed; fewer, merged
  clears per flip is the only lever.
- A walk-skip inside physmem ("skip the walk if some other client's bit was
  already clean, since then no entry can be writable") looks exact but is
  not: a guest notdirty store on the vCPU can make the entry writable between
  the check and the clear. Not pursued.

## Runs

Queued 2026-09-28 ~12:45Z behind the battery holds (docs/lanes/dirtytlb/queue.log):

| request | title | device | arm |
|---|---|---|---|
| 1-1790599436-lane.dirtytlb-41378 | Crimson Skies | thor | B 111c7fea74 |
| 1-1790599437-lane.dirtytlb-41484 | Crimson Skies | thor | A 9d777502fa |
| 1-1790599438-lane.dirtytlb-41557 | Blinx | nova | B 111c7fea74 |
| 1-1790599438-lane.dirtytlb-41609 | Blinx | nova | A 9d777502fa |

The pixel arm is the arms job's (dirtytlb-counter-pixels.json).
