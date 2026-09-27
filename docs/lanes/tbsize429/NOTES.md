# lane.tbsize429 -- #429: smaller translation blocks on often-rewritten pages

Base: master @ deb0903b51. PR #459. Outcome: **blocked, the premise is refuted
by counters already on disk. No code change and no arm.**

## What already exists

The lever is already in the tree, switched off: `HAKUX_SMALL_BLOCK_INSNS`
(`accel/tcg/internal-common.h`, 0 = off), with the per-page latch
(`PageDesc.empties` / `small_blocks`, latched after 16 page empties) in
`tb-maint.c` and the narrowing in `tb_gen_code`. It was built on 2026-09-13
(`5aa253f12a`; `docs/investigations/performance-next-three.md` section 2).

**The brief's trap does not arise.** The narrowed extent goes into
`tb_gen_code`'s local `max_insns` and never into `cflags`. So the TB hash key
is bit-identical and both lookup sites (`cpu_exec_loop`,
`helper_lookup_tb_ptr`) find what they find today. There is no page-derived
value to reproduce at three sites, so no shared helper is needed.
Turning it on means changing one constant, and the constant lives in
`internal-common.h`, not in the two files this lane was given.

## The pilot: what the counters say (no device time used)

Reader: `docs/lanes/tbsize429/scan.py` (this lane). `tail` takes the median of
each `hakuX-pages` counter per 120-frame window, over the windows after the
route's `mark gameplay` (or over the second half of the log when a route has
no gameplay mark). `pages` sums the whole run.

Counters: `ov` = live blocks whose bytes a guest store actually touched. `di` =
blocks discarded. `cg` = real code generations. `ih` = blocks recycled from the
invalidated-TB cache without translating. `em` = page-emptying events.

### Crimson Skies, crimson-skies route, Thor (lane.tbchurn424's A/B)

A = `7e6a4ac88a` (whole-page invalidation, today's default). B = `1d1251aa4b`
(range test on).

| request | arm | gameplay windows | ev | **ov** | em | di | **cg** | ins | ih |
|---|---|---|---|---|---|---|---|---|---|
| `1790454893-lane.tbchurn424-3968865` | A | 40 | 25,345 | **0** | 25,345 | 188,572 | **129** | 721 | 188,580 |
| `1790454909-lane.tbchurn424-3969958` | A | 9 | 26,521 | **0** | 26,521 | 165,028 | 893 | 4,407 | 165,028 |
| `1790454911-lane.tbchurn424-3970176` | A | 38 | 25,925 | **0** | 25,925 | 192,740 | **117** | 646 | 192,740 |
| `1790454908-lane.tbchurn424-3969831` | B | 42 | 0 | **0** | 0 | 0 | **111** | 576 | 0 |
| `1790454910-lane.tbchurn424-3970059` | B | 43 | 0 | **0** | 0 | 0 | **132** | 630 | 0 |
| `1790454912-lane.tbchurn424-3970253` | B | 44 | 0 | **0** | 0 | 0 | **95** | 501 | 0 |

(`-3969958` is the A run that was slow for its whole span; 9 windows.)

### Blinx (survey route, second half; and the blinx372 gameplay captures)

| run | arm | windows | ev | **ov** | di | **cg** | ih |
|---|---|---|---|---|---|---|---|
| `1790454914-lane.tbchurn424-3970398` | A | 26 | 4,190 | **0** | 4,190 | 205 | 4,190 |
| `1790454916-lane.tbchurn424-3970610` | A | 30 | 1,730 | **0** | 1,934 | 186 | 1,934 |
| `1790454915-lane.tbchurn424-3970555` | B | 25 | 0 | **0** | 0 | 243 | 0 |
| `1790454917-lane.tbchurn424-3970654` | B | 27 | 0 | **0** | 0 | 195 | 0 |
| `perf/2026-09-26/blinx372/0-0-y-1790405024-titlebench-2` | master | 38 | 1,139 | **0** | 1,293 | 75 | 1,293 |
| `.../1790408374-blinx372-4032207` | master | 34 | 1,322 | **0** | 1,516 | 49 | 1,516 |
| `.../1790408373-blinx372-4030372` | master | 30 | 1,137 | **0** | 1,316 | 34 | 1,316 |
| `.../1790408376-blinx372-4033793` | master | 15 | 1,123 | **0** | 1,276 | 52 | 1,276 |
| `.../1790409163-blinx372-166381` | master | 35 | 1,144 | **0** | 1,382 | 63 | 1,382 |
| `.../1790409543-blinx372-195142` | master | 35 | 1,671 | **0** | 1,991 | 64 | 1,990 |

### Whole-run totals (Crimson, `scan.py pages`)

Over the whole run, including boot and loading, `ov` is 252-288 per A run and
36,250-38,040 per B run. B's larger count is not more code writes: under the
range test, `ov` counts only the blocks a write hits. Under whole-page, a
write discards every block, which `sp` counts instead. `cg` is 98,197-104,647
on A and 98,301-101,466 on B, **the same on both arms**. The average
generated block is 5.6-6.0 guest instructions on every run.

## Why this refutes the lever

Smaller blocks save work in exactly one way: a store that hits translated
bytes discards less code, so less is re-translated. Every table above
shows that this input is absent in gameplay:

1. **No store touches translated code in gameplay.** `ov` has a median of 0
   in every run, on both titles, on both invalidation modes. The pages #429
   calls "rewritten" are pages where code and written *data* share 4 KiB.
   The guest does not rewrite its code there.
2. **Real translation is about one block a frame, and it does not depend on
   invalidation.** Gameplay `cg` is 95-132 per 120 frames on Crimson. That is
   the same with whole-page (A) and with the range test (B), where nothing is
   discarded at all. Blocks average ~5.6 instructions already. Capping the
   extent at N cannot cut work that is not happening.
3. **The 19% `tb_gen_code` share is recycles, not translation.** On A,
   188-193k blocks are discarded per window and 99.9% come back through the
   invalidated-TB cache (`ih` ~= `di`), plus `tb_link_page` and the arming
   walk. Under whole-page invalidation every block on the page goes whatever
   its size. Smaller blocks mean more blocks per page, so **more** recycles
   and links per event. That makes the lever negative, not inert.
4. That cost is #424's, and #424 removes it. The range test (lane.tbchurn424,
   PR #434, folded opt-in; default flip in PR #456, lane.tbflip424) takes `di`
   to 0 and Crimson from 26 to 29 gfps (the game's cap). After it, with
   `ov` = 0, a smaller extent has nothing left to spare. The latch cannot trip
   either: B's pages empty 443 times in a whole run (`em`).

The brief's falsifier ("tb_gen_code's share does not drop") is answered before
any arm is built. The share is recycle work that block size cannot reduce, and
the part block size *can* reduce (re-translation of overwritten code) measures
0 in gameplay. A device A/B would spend about 90 minutes of handheld time to
measure a lever whose input is 0. This lane does not queue it.

## What would reopen #429

A title whose gameplay windows show `ov` > 0 at a meaningful rate: genuine
self-modifying code, or code patched at runtime, on a page with other live
blocks. Run `scan.py tail <run ids>` on a soak of that title. If `ov`
per window is in the thousands **with the range test on**
(`HAKUX_TCG424_RANGE=1`, or default after #456), the arm is one commit: set
`HAKUX_SMALL_BLOCK_INSNS` to 8 or 16 in `internal-common.h`. The latch should
then count overlapping stores, not empties. That hunk is in `tb-maint.c`,
lane.tbflip424's file.

## For the next lane

- Do not rebuild the mechanism. It exists, it is off, and it needs no `cflags`
  helper.
- Do not read `tb_gen_code`'s profile share as translation. On this fork most
  calls return a recycled block (`generated N of M calls` on the
  `hakuX-pages` line). `cg` is the real count.
- Do not arm it with whole-page invalidation. More blocks per page makes each
  event more expensive.
