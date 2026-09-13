# The retranslation counters, measured — and what it does to the three levers

Measured 2026-09-13. AYN Thor, Crimson Skies, six 90 s dispatcher soaks in two
rounds of three, each round one ref so the round is also its own noise floor.
Read with `docs/testing/perf/tcg_pages.py`. Legs pre-registered in
`docs/testing/predictions/tcg-whole-page-invalidation.json` and `-2.json`.

This is the device half of #69. It settles `performance-next-three.md`
section 2 and it does not settle it the way section 2 expected.

## Round one was void, and the void row was the finding

Three runs on `6b574e163e` reported mean guest instructions per generated
block of **0.38**. A block cannot hold less than one instruction, so the row
was not small, it was impossible — and per `AGENTS.md`, a measurement that
disagrees with the arithmetic is the instrument until proven otherwise. Two
counters were measuring the wrong events, both of them pre-existing and both
feeding published numbers. That is #69 and the renames landed separately.

Round one's headline, `sp_share = 1.000` in all 21 windows, was **withdrawn
rather than cited**: the overlap question was being asked of every TB the
invalidation loop walked, most of which are dead, and a dead block cannot
overlap the current write. A systematic instrument error would look exactly
like 100%.

## Round two: the legs

Three runs on `d0dc45a130`, which adds `di=` (real discards), `cg=` (real
generations) and restricts the overlap question to blocks without `CF_INVALID`.

| leg | registered | run 1 | run 2 | run 3 | verdict |
|---|---|---|---|---|---|
| **M1** visits = discards + already-invalid, residual 0 | 0 | **0** | **0** | **0** | **PASS, exactly** |
| **M2** clog `ai/visits` | ≥0.80, fails ≤0.20 | 0.88 | 0.85 | 0.93 | **PASS** |
| **M3** `sp_share`, live blocks only | ≥0.30, fails ≤0.10 | 1.000 | 1.000 | 1.000 | **PASS** |
| **M4** `pr_per_em` | 0.95–1.05 | 1.000 | 1.000 | 1.000 | **PASS** |
| **M5** `blk` median | ≥16, fails <8 | 6.70 | 6.14 | 6.17 | **FAIL** |

M1 closing to exactly zero on all three runs is what licenses reading the
rest; without it the counters could still have been on the wrong events.

## M5 kills the block-extent lever outright, on feasibility

**The mean generated block is already 6.1 to 6.7 guest instructions**, every
window between 3.97 and 12.29, all three runs agreeing. `HAKUX_SMALL_BLOCK_INSNS`
was written at 8. **Eight is above the existing mean, so the clamp would
essentially never bind.**

That is independent of the mechanism argument in section 2 and it is the
simpler objection: there is no headroom to shrink. A lever that caps block
length cannot recover 4 ms from blocks that are six instructions long. The
mechanism ships at 0 and should stay there.

Note what this also means for the profile: with `cg` at 20–64 real generations
per 120-frame window, code generation in this scene is about **0.5 generations
and 3 guest instructions per frame.** Whatever `tb_gen_code` costs at 19% of
the bounding thread, in *this* title and scene it is not the cost of
translating code. It is the recycle lookup and the link/arm path around it.

## M3 sizes the real lever, and the number is stark

Restricted to live blocks, `ov` — blocks discarded whose bytes the guest
actually wrote — has a median of **0** and a maximum of **3 per window**,
against `sp` at 604–3,044. Out of roughly 40,000 live blocks discarded per
run, **essentially none had a written byte in them.**

So the whole-page invalidation this fork does instead of upstream's
range-precise one is discarding live translated code that the guest did not
touch, at a rate indistinguishable from 100%.

And `ws_share` is 1.000 with `pr_per_em` 1.000 across six runs: **every
page-emptying event would have been prevented by a range test, and each one
costs exactly one arming TLB walk.** At 7.5–15 walks a frame, restoring the
range test would remove essentially all of them.

`tlb_reset_dirty` is 10.6% self of the bounding thread — but that figure is
Fuzion Frenzy gameplay and these rates are Crimson Skies unattended, so **the
millisecond figure does not transfer** and must be measured on the title it is
claimed for. What transfers is the mechanism and the ~100% share.

The precondition for restoring it is in `performance-next-three.md`: the
superblock mechanism records only A's byte extent, so a restored range test
must never spare a TB with `superblock != NULL`. `XBOX_SUPERBLOCK_ENABLED` is
0 today, so nothing forms one.

## Why the page lists are clogged, and it is not the invalidator's fault

M2 says 85–93% of the invalidation loop's visits are blocks that already carry
`CF_INVALID`. The mechanism is fully determined by reading two sites:

- `accel/tcg/cpu-exec.c`, tier-1 promotion, sets `CF_INVALID` **in place** —
  "Mark the old TB as invalid so it won't be reused from cache, but DON'T
  unlink its jumps." No `qht_remove`, no move to `inv_htable`, no `tb_remove`.
- `do_tb_phys_invalidate` then reads `orig_cflags = tb_cflags(tb)`, which now
  **includes** `CF_INVALID`, and hashes with it. `CF_INVALID` is an input to
  `tb_hash_func`, and the TB was inserted under a hash without it, so
  `qht_remove` misses and the early return fires — *before* `tb_remove`.

The block is therefore stranded on the page list with `CF_INVALID` set, and
every later store to that page walks it, fails the same `qht_remove`, and
returns. Permanently. Measured cost: roughly 1.01 visits per invalidation
event of which ~90% are this, so about **112 futile hash lookups plus
spinlock acquisitions per frame** achieving nothing.

That is a pure bookkeeping loss with no correctness content, unlike the
discarding, which section 2 correctly said is warranted. It is **not** fixed
here: the reasoning belongs to whoever owns the tier-1 mechanism, and the
soft-invalidation comment's intent ("won't be reused from cache") deserves
checking on its own terms — `tb_lookup_cmp` masks `CF_INVALID` off before
comparing, so the htable path may still find and execute such a block, which
if true is a correctness question and not a performance one. **Unverified, and
flagged rather than chased.**

## The noise floor, which this stream did not have

Three runs of one ref, per-window medians across runs:

| quantity | round one | round two | floor |
|---|---|---|---|
| `ev`, `sp`, `ov` | 14,383 / 14,312 / 13,176 | — | **±5%** |
| `em`, `pr` | 897 / 909 / **1,844** | 904 / 1,856 / 905 | **factor of 2** |
| `pr_per_em` | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | **±1.8% within-run** |
| `blk` | void | 6.70 / 6.14 / 6.17 | **±5%** |

**Any claim about the arming-walk rate must beat 2x on an unattended soak.**
The ratios are far tighter than the rates, which is why the tool judges on
them.

Cost leg, all six runs: gfps median 29, p90 30–33, max 35–37. Crimson Skies
unattended sits at its own 30 cap, so **a dispatcher soak cannot show a
frame-time gain in this title** — there is no headroom in the scene a soak can
reach, and a soak injects no input to reach another.

## The corpus arm: byte-identical

`9eb64cbcc3` against `6b574e163e`, eight unrelated suites, one disc
(`8-suites:1b7a732f`), both arms on the thor, arms proven distinct by APK hash
(`e012501e58cd` against `42775a326995`).

- **593 tests, all nine scored columns identical — `diff` returns nothing.**
  Totals 10,798,925 differing pixels and 5,719,201 off-by-one in both arms.
- **All 593 capture PNGs byte-identical by md5.** The only differing file in
  the two capture sets is `pgraph_progress_log.txt`, which records timestamps.

The leg was registered as equality rather than no-regression, because the only
route from counters-on-a-slow-path to a pixel is perturbing timing enough to
flip an nv2a race, and a no-regression leg would have passed exactly that run.
And the captures were compared as bytes, not as scores: a flat count cannot
show inaction, since a change that returns a different wrong answer is
invisible in the totals.

## Where this leaves the three levers

1. **Audio voice lock** — fixed and validated, unchanged.
2. **Smaller blocks on thrashing pages** — **dead.** No mechanism under
   whole-page invalidation, and M5 says no headroom anyway: blocks are already
   ~6 instructions. Keep `HAKUX_SMALL_BLOCK_INSNS` at 0.
3. **Threaded draw path** — unchanged, still recommended against.

**The lever that replaces number 2** is restoring the range test, now measured
at ~100% of live discards and ~100% of arming walks, with a named precondition
and a five-year-old unexplained SMC hedge to clear first. The corpus is the
oracle for the hedge. A second, smaller and entirely safe item is the stranded
`CF_INVALID` blocks above.
