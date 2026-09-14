# #73 and #68 separated: the three-arm measurement

Nine 90 s Crimson Skies soaks on the Thor, three per ref, 2026-09-14.
Prediction registered and committed before any arm ran:
`docs/testing/predictions/tcg-three-arm-visited-bound.json`,
sha256 `24576e6cabfe654f5e801fa64c7a393cfe2d610288906c4a8a429eab30490d2f`,
recorded in all nine requests as `expect_sha`.

## Why this was re-run

The first attempt ran **two arms for a three-arm question**. Its `73-1` and
`73-2` came back NOT ATTRIBUTABLE because arm "B" on disk was `937848c9e7`,
which is #68 **stacked on** #73, and nothing isolated #73. The chain is
linear, and each arm differs from the one before it by exactly one commit --
verified by `rev-parse` of each ref's *parent*, not by ancestry against a
cherry-picked copy:

    117203fe9b   neither #73 nor #68        apk 28799396301b
    a94386a3c8   #73 ALONE                  apk 7b3d8f9c8fe2   <- the missing middle
    937848c9e7   #73 + #68 (held)           apk 67f083f5e657

## What the arms measured

Per 120-frame window, per-run medians, three runs per arm.

| | A: neither | B: #73 alone | C: #73 + #68 |
|---|---|---|---|
| `ev` events | 14519 / 13245 / 14491 | 2199 / 2162 / 2160 | 109179 / 101214 / 100360 |
| `visited` | 14633 / 13310 / 14602 | 2203 / 2175 / 2176 | 8518199 / 7443124 / 7844104 |
| visits/event | 1.01 / 1.00 / 1.01 | 1.00 / 1.00 / 1.00 | 83.6 / 72.6 / 79.1 |
| `em` = `pr` | 930 / 1868 / 929 | 2199 / 2162 / 2160 | 0 / 0 / 0 |
| `em`/`ev` | 0.064 / 0.141 / 0.064 | **1.000 / 1.000 / 1.000** | 0.000 |
| `ai`/`visited` | 0.928 / 0.856 / 0.929 | **0.000 / 0.000 / 0.000** | 0.000 |
| `stores` | 41136 / 39883 / 41131 | 28843 / 28802 / 28788 | 135803 / 127857 / 127083 |
| gfps max | 35 / 37 / 37 | 33 / 35 / 35 | 35 / 34 / 37 |

Every registered leg holds. The two that matter most:

**#73 is a large net REDUCTION in invalidation work and a RISE in the arming
walk.** It removes the stranded-block population outright -- `ai/visited`
0.93 -> 0.000 -- and with it 85% of the events and 85% of the visits. But
with nothing stranded to block it, **every** event now empties its page:
`em/ev` goes 0.064-0.141 -> **1.000 on all three runs**, and `pr == em`
exactly, so the arming TLB walk rises from 930-1868 to 2160-2199 per window.

**So #68's prize is measured from B, not from A, and it is bigger than the
two-arm run said.** The A-vs-C pair credited #68 with `pr` 1846 -> 0. The
real figure is **2162 -> 0**: #73 alone raises the very cost #68 exists to
remove.

**And #68's `visited` cost is six times larger than the A-vs-C figure.** The
often-quoted ~560x is A-to-C. Because #73 alone cuts `visited` to 2,176, the
rise attributable to #68 is **3,605x**, which decomposes as

    visited  3605x   ~=   ev 46.8x   x   mean page-list length 79.1x

(the two factors multiply to 3,703 rather than 3,605 because a median of
per-window ratios is not the ratio of the medians; the split, not the 3%, is
the point)

Only the first factor is visible in `stores`; leg `68-4` of the previous
prediction counted `stores` and could not see the second at all.

## The bound on `visited`

Three registered thresholds could have stopped the fold. None fired.

* **Plateau.** `visits/event`'s last-third median over its middle-third
  median is 0.995 / 0.901 / 0.968 against a registered bound of 1.25. The
  page list reaches steady state by window 5 and stays there; it is not a
  leak bounded only by translation-buffer flush.
* **Capacity.** `visits/event` is 83.6 / 72.6 / 79.1 against
  `B_page = 4096 / ((bytes/ins) * blk)` = 219.8 / 190.9 / 209.7, computed per
  run from its own log line: the blocks that fit in a 4 KiB guest page at
  that run's own mean block size. The list holds about a third of the page's
  capacity, so its entries are the page's live code and not accumulated
  superseded translations.
* **Stores.** 4.44x against a registered stop of 10x.
* **Frame ceiling** (one-way): silent, and a silent result here establishes
  nothing -- a dispatcher soak injects no input and Crimson Skies' guest CPU
  thread is not its critical path (#44).

### What the exchange actually costs

R = **3,627 visits added per arming walk removed**
(`(visited_C - visited_B) / (pr_B - pr_C)`).

R is not a verdict on its own, so it is put into like units. `tlb_reset_dirty`
(`accel/tcg/cputlb.c:917`) loops over `NB_MMU_MODES` and, inside each, over
`tlb_n_entries(fast)` plus `CPU_VTLB_SIZE`. `NB_MMU_MODES` is **22**, fixed
for all targets (`include/hw/core/cpu.h:204`) whatever i386 uses;
`CPU_VTLB_SIZE` is 8; `tlb_mmu_init` starts every mode at
`1 << CPU_TLB_DYN_DEFAULT_BITS` = 256 and only ever grows. So one walk touches
**at least 22 x (256 + 8) = 5,808** TLB entries, and more once the TLB
resizes.

    removed by #68:  >= 2162 x 5808  =  12.6M entry touches per window
    added by #68:            7.84M   =   7.84M page-list visits per window
    also added:              99,055  =   extra slow stores per window (4.44x)

So the trade is **at least 1.6 entry-touches removed per visit added** -- and
that is a LOWER bound, because a grown TLB makes the walk bigger.

**This does not license the fold, and the reason is stated rather than
implied.** The two touch counts are not equivalent work: `tlb_reset_dirty`
scans a contiguous array, which is sequential and prefetchable, while the
page-list walk is a linked-list pointer chase of dependent loads. Per touch
the list is plausibly several times dearer, which is enough to invert a 1.6:1
count ratio. And the 99,055 extra slow stores per window are on neither side
of it. A soak yields no per-visit and no per-walk time, so **the counters
bound this trade and cannot settle it.** Pricing it needs a direct timing
instrument, not another soak.

## Two controls failed, and both are the instrument

Registered rule: a failed control voids every ratio. Both were run down before
anything above was quoted.

**C2** (`visited == ov + sp + ai`) exceeded `tcg_pages.py`'s own slack in 3
windows of 2 arm-C runs: residuals +76, -106, +106 against slacks of 70-74, on
`visited` values near 10^6 -- a relative error of 1e-4, at the boundary of the
slack itself. All three are in w1/w2, where the event rate ramps hardest
(w1 ~700k visits, w4 ~4.4M), and the residual **changes sign between adjacent
windows of the same run**. That is the in-flight slip the tool's own docstring
names: `visited` prints on the first `hakuX-pages` line and `ov`/`sp`/`ai` on
the second. Benign; the slack is marginally tight during the ramp.

**C3** called arm A run 1 `MIXED` rather than `WHOLE-PAGE`. From the raw log:

    w7  ev=14528 ov=0 sp=1055 em=963  pr=964  ai=13565 di=1056   di-(ov+sp) = +1
    w8  ev=14431 ov=0 sp=1130 em=1006 pr=1005 ai=13425 di=1129   di-(ov+sp) = -1

Two of twenty-one windows, off by exactly one, with opposite signs -- and
`pr` vs `em` slips by the same +1 / -1 in the same two windows. Two
independent counter pairs off by one in the same window, in matching
directions, is one invalidation straddling the window boundary; a counter
defect would not do that. `em + ai == ev` stays exact even in those windows
(963+13565 = 14528; 1006+13425 = 14431), because both terms are on one line.

C3's purpose was build identity, and build identity is established
**independently** by a second instrument: the dispatcher recorded
`apk_sha` 28799396301b on all three A runs, 7b3d8f9c8fe2 on all three B,
67f083f5e657 on all three C, each matching its ref. The classifier's
disagreement is +/-1 in 2 of 21 windows while the competing model is off by
~12,500 in 21 of 21. The conclusion did not move; a different instrument was
brought to it.

**This is a residual of the defect `lane.tcgcount` just fixed.** That fix
stopped `sp + ov == di` being a hard-coded invariant. `discard_model()` still
compares both models with **exact equality and no tolerance**, so a ±1
window-boundary straddle can label a correct whole-page build `MIXED`. The
population check next to it already carries a `max(8, n*1e-4)` slack for
exactly this reason. `tcg_pages.py` is `lane.toolsmith`'s and was not edited
here; this is a board request.

## What could not be established

* **No corpus arm, and no leg here needed one.** #68 makes invalidation do
  LESS, so its failure mode is a stale translation executing after a guest
  write the range test wrongly spared. `nxdk_pgraph_tests` is nearly all
  static content, so byte-identical captures would be necessary and not
  sufficient. A title that overlay-loads code is the instrument for that.
* **The per-visit and per-walk times.** See above; this is the gap that keeps
  `937848c9e7` from folding on measurement alone.
* **73-C is the thinnest leg in the set.** It holds by the registered
  run-median rule -- every B run (2160-2199) above every A run (929-1868) --
  but the margin over A's high run is 15.6%, and the within-arm spread on
  `em`/`pr` is a registered factor of **2**, reproduced here (929/930 against
  1868 on the same binary). The mechanism claim is safe at 1.000 vs
  0.064-0.141 on `em/ev`, which is 7-15x with no overlap; the *absolute* rise
  in `pr` is the net of two large opposing moves (`ev` down 6x, `em/ev` up
  15x) and carries that uncertainty.
* **One title.** A cost measured on one workload is a fact about that
  workload. Crimson Skies' guest CPU thread is not its critical path, which
  is why the frame ceiling can see nothing here and why a second title would
  say something this one cannot.
* Desktop build not run: `libcurl4-openssl-dev` is the known, named gap.
