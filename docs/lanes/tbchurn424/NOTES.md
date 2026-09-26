# lane.tbchurn424 -- #424 translation-cache code-write invalidation and dirty re-arm churn

Base: master @ 15d9406b81. PR #434.

## 1. What remains on master (measured before any change)

Reader: `docs/lanes/tbchurn424/churn.py` (this lane). It sums the build's own
`[tlb68]` timers (`jcus`, `rdus`, `cpu`) and the `hakuX-pages` counters over a
soak's gameplay span, from the route's `mark gameplay` + 30 s to the end of
the log. The shares are **timed directly** by the build around each call:
they are not simpleperf samples, and they do not include the TLB refills and
jump-cache misses a flush causes afterwards.

| run | ref | device | route | gfps median | G ms | jc% | rd% | **churn%** | rdo%* | discards/s | arming walks/s | slow stores/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `0-0-y-1790433159-titleplay-p1-crimson` | `a5b5b628f2` (master; no accel change to 15d9406b81) | thor | crimson-skies | **23** | 39.8 | 10.6 | 13.4 | **23.9** | 13.8 | 21,683 | 3,001 | 6,717 |
| `0-0-c-1790377875-lane.tcgchurn-101077` | `ea1e9f5a0d` | thor | none (hands-off) | 29 | 33.3 | 0.2 | 0.0 | 0.2 | 0.3 | 628 | 522 | 18,980 |
| `0-0-c-1790377876-lane.tcgchurn-101313` | `1ce8693eb1` | thor | none (hands-off) | 29 | 33.3 | 0.2 | 1.2 | 1.4 | 0.3 | 636 | 527 | 5,631 |

\* `rdo%` is `tlb_reset_dirty` called from other threads (the nv2a dirty
queries), divided by the vCPU CPU total for scale. It is not on the vCPU
thread.

**Why lane.tcgchurn saw almost nothing and perf-baseline saw 20%.** The
workload decides it. Hands-off Crimson sits at the game's own 29-30 cap and
discards about 630 blocks a second. The `crimson-skies` route (A-mash into the
first flying section) discards 21,700 a second, 35x as many. On the route,
the two #424 mechanisms take 23.9% of the vCPU thread's CPU. That is the same
order as perf-baseline-2026-09's sampled 11.1-11.4% (`tlb_reset_dirty`) plus
8.5-8.6% (`tcg_flush_jmp_cache`) on the Nova.

**On the route, every discard is of code the guest never wrote.** In every
120-frame window, `ov=0` (live blocks whose bytes the store touched) and
`em == pr == ev`: every invalidation event empties its page, and every
emptied page is re-armed by a full TLB walk on the next translation there.
Codegen calls are almost all recycles (`generated 202 of 169354 calls`), so
the guest re-translates the same bytes it just threw away.

**The lever's share is a BOUND, not a gain.** 23.9% is what the two timed
functions cost now. Removing them cannot return more than that. What it
actually returns depends on:
- what replaces them: pages that keep their code stay armed, so stores to
  the data sharing those pages trap every time;
- whether the vCPU thread bounds the frame on this route. At 23 gfps with
  G 39.8 ms, it looks like it does.

## 2. The change

Restore upstream's range test in `tb_invalidate_phys_page_range__locked`. It
was held as `937848c9e7` on 2026-09-14 (never folded). That commit's own soaks
showed `em` falling from 42k to 12 per run and `pr` falling 93x. It was held
for two unmeasured costs:
1. the page-list walk per store (visits per event 1 -> ~80);
2. slow stores rising 3.8-4.1x.

This lane adds the answer to (1): a per-page code bitmap, and a fast path
that answers a store which touches no translated byte under the one page
lock, without `page_collection_lock` (a GTree allocation per call) and
without the walk. (2) is measured, not assumed away: it is a leg.
