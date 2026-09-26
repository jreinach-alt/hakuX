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

### The code (cb66484748)

- `tb_invalidate_phys_page_range__locked`: upstream's overlap test is the
  predicate again, with 937848c9e7's two extra clauses, both of which discard
  more: a dead block that is being walked is reclaimed, and `tier >= 2` or a
  superblock is always discarded. Visits are counted before the predicate,
  so `visited == ov + sp + ai` holds on both predicates.
- `PageDesc.code_bitmap`: one bit per byte that any listed TB (dead ones
  included) was translated from. It is built after a page's 10th code-write
  trap (upstream's old `SMC_BITMAP_USE_THRESHOLD`). Bits are set in
  `tb_page_add`. They are cleared only by a rebuild from the list after a
  walk. The bitmap is freed when the page empties and in `tb_flush`, so it
  is always a SUPERSET of the listed extents. A stale bit costs a walk; it
  can never make a stale block run.
- `tb_invalidate_phys_range_fast` (every notdirty store to an armed page):
  if the bitmap shows no translated byte in the store, it returns under the
  one page lock. That skips `page_collection_lock` (a GTree allocated per
  store, plus every TB's other page locked) and the list walk.
- Kill switch: `HAKUX_TCG424_WHOLEPAGE=1` restores whole-page invalidation
  and bypasses the bitmap.
- `[tlb68]` gains `rt=` (range test on), `cb=` (stores the bitmap answered)
  and `cbb=` (builds).

Compile-checked with the desktop build's flags
(`-Wmissing-prototypes -Wredundant-decls`, `-Werror` except a pre-existing
nested-extern in `tb_flush__exclusive_or_serial`). Not built for Android
locally; the dispatcher builds each ref.

## 3. The A/B (queued 2026-09-26 ~20:35 UTC)

- A = `7e6a4ac88a` (master); B = `1d1251aa4b` (master merged with
  cb66484748).
- Predictions: `docs/testing/predictions/tbchurn424-soak.json` (legs
  M0-M4, read with `churn.py`) and `tbchurn424-pixels-inert.json` (8 pgraph
  suites, identical captures; the arms job runs it).
- Blinx is in as the cost-side title. On the survey route it spends only
  2.0% on churn but takes 50k slow stores a second, so a range test that
  keeps more pages armed could cost there.

| request | arm | title |
|---|---|---|
| `1790454893-lane.tbchurn424-3968865` | A | Crimson r1 |
| `1790454908-lane.tbchurn424-3969831` | B | Crimson r1 |
| `1790454909-lane.tbchurn424-3969958` | A | Crimson r2 |
| `1790454910-lane.tbchurn424-3970059` | B | Crimson r2 |
| `1790454911-lane.tbchurn424-3970176` | A | Crimson r3 |
| `1790454912-lane.tbchurn424-3970253` | B | Crimson r3 |
| `1790454914-lane.tbchurn424-3970398` | A | Blinx r1 |
| `1790454915-lane.tbchurn424-3970555` | B | Blinx r1 |
| `1790454916-lane.tbchurn424-3970610` | A | Blinx r2 |
| `1790454917-lane.tbchurn424-3970654` | B | Blinx r2 |

## For the next lane

- **Measure on the route, not hands-off.** Hands-off Crimson sits at the
  game's 30 cap and churns about 0.2-1.4%. The `crimson-skies` route churns
  23.9%. lane.tcgchurn's "the premise does not hold" came from the
  hands-off workload.
- The soak path has no simpleperf. The `[tlb68]` timers (`jcus`, `rdus`,
  `cpu`) time the two mechanisms directly, and `churn.py` reads them.

## State at session end (2026-09-26): WAITING

Waiting on:
- the ten soaks above;
- the arms job's verdict on `tbchurn424-pixels-inert.json`;
- CI.

Posted as `[lane.tbchurn424] waiting:` on #434 and #424. The next session:
- judges M0-M4 with `churn.py`;
- fills in the before/after table here;
- marks #434 ready, or records the refutation.
