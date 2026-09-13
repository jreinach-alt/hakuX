# The corrected retranslation numbers (#69), and what they say about #68

Written 2026-09-13. This file exists because two counters measured the wrong
events, their quotient was published as the **2.8:1 retranslation waste
ratio**, and `performance-next-three.md` ranked its three levers on it. Both
documents retracted the figure. **Nobody had the corrected number.** This is
it, with its noise floor, and what it does to #68.

Read `AGENTS.md` §"A wrong zero stops work; a wrong ratio redirects it" first;
it is the general lesson. This is the arithmetic.

## What each counter counts, after `82e3967e54`

| name | EVENT | where it increments |
|---|---|---|
| `hakux_tb_gen_calls` | a **call** to `tb_gen_code` | top of the function, recycles included |
| `hakux_tb_codegen` | a **generation** | after `encode_search`, past every early return and both `goto`s |
| `hakux_tb_visited` | a **visit** by the whole-page invalidation loop | before `tb_phys_invalidate__locked` |
| `hakux_tb_discarded` | a **discard** | inside `do_tb_phys_invalidate`, past the `qht_remove` early return |
| `hakux_inval_already` | a visit that already carried `CF_INVALID` | in the loop, kept — it is what made #69 diagnosable |
| `hakux_inval_impossible` | **nothing.** Must read 0 | per visit, see below |

`hakux_tb_generated` was `hakux_tb_gen_calls` and `hakux_tb_invalidated` was
`hakux_tb_visited`. They were **renamed, not moved**, because both quotients
are worth reading: calls/generations is the recycle rate and
visits/discards is the page-list clog. What was wrong was a name that did not
say which event it counted, and an always-on line that printed the loose one
under the tight one's label. **Any log older than that commit has a call count
where it says "generated" and a visit count where it says "tossed".**

## The corrected waste ratio

Three 90 s Crimson Skies soaks, **one ref** (`848f98a6a6`), **one device**
(thor), first window dropped as boot. Run-level aggregates, because the
per-window ratio is unusable — see the noise floor below.

| quantity | run 1 | run 2 | run 3 | max/min |
|---|---|---|---|---|
| **`waste` = discards / generations** | **11.68** | **11.31** | **6.14** | **1.90** |
| what 2.8:1 was: visits / calls | 7.67 | 6.53 | 12.80 | 1.96 |
| `recycle` = calls / generations | 12.26 | 11.88 | 6.70 | 1.83 |
| `clog` = already-invalid / visits | 0.876 | 0.854 | 0.928 | 1.09 |
| `blk` = instructions / generation | 6.26 | 5.60 | 5.93 | 1.12 |
| generations (`cg`) | 3,465 | 3,442 | 3,392 | **1.02** |
| discards (`di`) | 40,479 | 38,944 | 20,838 | 1.94 |
| visits | 325,860 | 267,270 | 291,023 | 1.22 |

**The corrected ratio is 6 to 12 real discards per real generation, and it
cannot be quoted more precisely than that.** Its floor is the `em`/`pr` class
— a factor of two — not the `ev`/`sp`/`ov` ±5% class, because all of the
spread is on the discard side. `cg` is the most reproducible counter in the
whole set at 2%.

Three things follow, and the second is the one that matters:

**It is not 2.8.** 2.8:1 was Fuzion Frenzy's visits over calls. Crimson Skies'
visits over calls is 6.5–12.8, and its discards over generations is 6.1–11.7.

**The correction does not even have a consistent sign.** Runs 1 and 2 put
`waste` *above* the legacy ratio; run 3 puts it *below*, and the two are
anti-correlated across the three runs (run 3 has the lowest `waste` and the
highest legacy figure). That is because

    waste = waste_legacy x (1 - clog) x recycle

and `clog` and `recycle` move independently between runs of one binary. A
registered leg predicting the direction of the correction therefore **failed**,
and the failure is a stronger statement of the original defect than a
corrected number would have been: the retracted ratio was not a number with a
correctable error, it was a quotient of two quantities whose errors move in
opposite directions run to run.

**A discard is not a retranslation, so the ratio is not a waste ratio in
work.** A discarded block goes into `inv_htable` and 7–12 calls in 13 come
back out of it without codegen — that is what `recycle` measures. The cost of
a discard is `tb_link_page`, the arming walk, and the jump-cache flush below;
it is *not* a `tb_gen_code`.

## The impossible row, built on purpose

`xx` counts visits where live-ness and discard-ness disagreed. A live TB is
findable in `tb_ctx.htable` under the hash of its current cflags so
`qht_remove` succeeds; a TB already carrying `CF_INVALID` is not findable,
because `CF_INVALID` is an input to `tb_hash_func` and was clear at insertion.
Live iff discarded, per visit, so `xx` must read **0**.

It is not a tautology of the patch: it fires if the tier-1 soft invalidation
(`cpu-exec.c`, `c174c8bde8`) ever rehashes as well as setting the bit, if a
live TB is absent from the htable, or if anything clears `CF_INVALID` without
re-inserting. `tcg_pages.py` prints `CONTROL xx = 0` when it holds and **VOIDs
every ratio on the line** when it does not.

The aggregate form of the same identity, available one ref earlier:
**visits = discards + already-invalid, residual exactly 0 on all three runs**
(325,860 = 40,479 + 285,381, and twice more). `sp + ov` equals `di` exactly
too — the live population counted by two separate pieces of code.

## #68: the cost IS now established, and `sp_share` is 1.000 over live blocks

`sp_share` = 1.000 in **every window of every run**, over 20,835 to 40,476
**live** discarded blocks per run. A prior lane measured 1.000 and correctly
withdrew it, because its population included the dead blocks clogging the page
lists and a dead block has no reason to overlap the current write. This
measurement asks the question only of blocks without `CF_INVALID`, and the
answer did not move.

**Before citing a 1.000, what would a systematic error do?** Three checks, and
they are why this one is citable where the earlier one was not:

- **The predicate is not stuck at false.** `ov` is 3 in the same window index
  of all six runs, and 2 or 10 in the boot window. It fires, deterministically,
  where the title really does write over its own code, and nowhere else. An
  always-false predicate would give 0.
- **It cannot be an address-space mismatch.** `PAGE_FOR_EACH_TB` walks
  `p->first_tb` for the page `page_find(start >> TARGET_PAGE_BITS)` returned,
  so the TB extent and the written range are in the same page by construction,
  and `tb_overlaps_written_range` is upstream's arithmetic unmodified.
- **The denominator is large.** ~1,000–1,900 live discards per window, not a
  handful. A 1.000 over three blocks would not be a premise check.

- **A different instrument agrees.** The `off=LO..HI` fields on the same
  always-on line come from the notdirty write tracker, not from the overlap
  predicate, and they say the writes are confined to narrow windows of their
  pages: `pfn42c1` at `off=554..9e4` (1,168 bytes of 4,096) takes ~113,000 of
  the hits and `pfn43bd` at `off=1f8..414` (540 bytes) another ~41,000. Two
  hot data structures sharing a page with code. Any block outside those
  windows is spared, and that conclusion does not pass through
  `tb_overlaps_written_range` at all.

The stores are ≤ 8 bytes: every event arrives through
`tb_invalidate_phys_range_fast`, and `ev` equals the notdirty invalidator call
count exactly. So the finding is that Crimson Skies' stores into code pages
land on data sharing the page with code, essentially never on the code.

What that costs, per 90 s run:

| | run 1 | run 2 | run 3 |
|---|---|---|---|
| live blocks a range test would spare | 40,476 | 38,941 | 20,835 |
| page-emptying events it would prevent (`ws`/`em`) | 1.000 | 1.000 | 1.000 |
| arming TLB walks per emptying event (`pr`/`em`) | 1.001 | 1.000 | 1.001 |
| emptying events | 18,074 | 35,906 | 17,242 |
| blocks visited per event | 1.07 | 1.01 | 1.01 |

Pages hold **about one block** at invalidation time, 85–93% of visits are dead
blocks, and the range test would spare essentially all the live ones and
prevent **all** the page emptying. The ratios are stable to three decimals
even though the rates carry a factor-two floor.

**The two symbols that cost, and one of them is new.** From the 2026-09-11
`simpleperf` profile of the bounding thread (a different ref — treat these as
bounds on the prize, not values):

- `tlb_reset_dirty` **10.97% self**, under `physical_memory_test_and_clear_dirty`
  11.30% incl, which is `tlb_protect_code`, reached from `tb_link_page` 11.56%.
  That is the arming walk, one per page-emptying event.
- `tcg_flush_jmp_cache` **8.77% self**, under `do_tb_phys_invalidate` 10.72%
  incl. `target/i386/cpu.c:9325` sets `CF_PCREL` unconditionally, so
  `tb_jmp_cache_inval_tb` always takes the `CPU_FOREACH` branch and wipes the
  whole jump cache **per discarded block**. This is past the early return, so
  it scales with `di`, not with `visited` — which is exactly why the broken
  counters mattered: the old numerator was 7–8x too large, so this cost was
  being priced against the wrong rate.

So ~19.7% of one thread sits on events a range test removes. That is a
**bound** — one 20 s profile, one ref, one thread — and the established part
is the event rate and the two per-event ratios, not the share.

**Still do not restore the range test on this.** It is a five-year-old SMC
hedge (xemu `703566ce33`, no recorded reason) on every guest instruction. What
these numbers change is that #68 now has a measured size instead of a code
reading, so it can be *ranked*.

## What this does to `performance-next-three.md` §2

`blk` is **5.6 to 6.3 guest instructions per generated block**, floor 1.12.
The void row of rounds one and two (0.34–0.86, arithmetically impossible) is
gone. But the registered leg was `blk` median ≥ 16, on the reasoning that an
8-instruction cap is a no-op below it, and **that leg failed.** Blocks here
are already shorter than the clamp `HAKUX_SMALL_BLOCK_INSNS = 8` would impose,
so the small-block arm cannot pay on this title whatever happens to the range
test. §2's lever is dead on this workload for a second, independent reason.

## How to read a run

    docs/testing/perf/tcg_pages.py <result-dir> [...]
    docs/testing/perf/tcg_pages.py --ab A=<d1> A=<d2> A=<d3> B=<d4> ...

Three soaks per arm, one ref, one device; the replicate is the run, not the
window. The tool refuses arms that span handhelds or mix refs, drops the boot
window, voids the line if `xx` fires, and voids `blk` if it comes out below
1.00.

## The runs

| ref | runs | what it had | what it was for |
|---|---|---|---|
| `6b574e163e` | 3 | no `ai`/`di`/`cg` | round 1; produced the impossible 0.38 row |
| `848f98a6a6` | 3 | `ai`/`di`/`cg`, live-only `sp`/`ov` | round 2; **the corrected numbers above** |
| `d287c512d9` | 3 | renamed line, `xx` | round 3; the control, and an inertness check on the rename |

Legs: `docs/testing/predictions/tcg-whole-page-invalidation-3.json`,
registered before the ref was queued.
