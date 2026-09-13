# The corrected retranslation numbers (#69), and what they say about #68

Written 2026-09-13. This file exists because two counters measured the wrong
events, their quotient was published as the **2.8:1 retranslation waste
ratio**, and `performance-next-three.md` ranked its three levers on it. Both
documents retracted the figure. **Nobody had the corrected number.** This is
it, with its noise floor, and what it does to #68.

**Read [`docs/investigations/tcg-retranslation-measured.md`](../../investigations/tcg-retranslation-measured.md)
first.** That is the performance lane's device half of #69: legs M1-M5, the
noise floor, the byte-identical corpus arm, and the verdict on the three
levers. Everything there was derived independently of this file and the
numbers agree throughout. **This file is only what is additive**:

1. the corrected waste ratio, which that document does not state;
2. that generations are a near-constant of the title and discards are not,
   which is where all the ratio's noise lives;
3. the direction of the correction, which is not fixed;
4. a second instrument for `ov` approximately 0, one that does not use the
   overlap predicate — which is the check that lane asked for by name;
5. `tcg_flush_jmp_cache`, a cost symbol that scales with discards;
6. why `blk` cannot settle the block-extent lever's feasibility on its own.

Read `AGENTS.md` §"A wrong zero stops work; a wrong ratio redirects it" for
the general lesson. This is the arithmetic.

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

Six 90 s Crimson Skies soaks, **two refs of three runs each**, one device
(thor), first window dropped as boot. Run-level aggregates; the per-window
ratio is far noisier and is reported separately by the tool.

| quantity | round 2 (`848f98a6a6`) | round 3 (`d287c512d9`) | within-ref max/min |
|---|---|---|---|
| **`waste` = discards / generations** | **11.68 / 11.31 / 6.14** | **4.96 / 4.88 / 4.98** | 1.90 · **1.02** |
| what 2.8:1 was: visits / calls | 7.67 / 6.53 / 12.80 | 12.12 / 12.07 / 12.49 | 1.96 · 1.03 |
| `recycle` = calls / generations | 12.26 / 11.88 / 6.70 | 5.60 / 5.53 / 5.61 | 1.83 · 1.02 |
| `clog` = already-invalid / visits | 0.876 / 0.854 / 0.928 | 0.927 / 0.927 / 0.929 | 1.09 · 1.00 |
| `blk` = instructions / generation | 6.26 / 5.60 / 5.93 | 5.76 / 5.99 / 5.93 | 1.12 · 1.04 |
| generations (`cg`) | 3,465 / 3,442 / 3,392 | 4,134 / 4,216 / 4,003 | 1.02 · 1.05 |
| discards (`di`) | 40,479 / 38,944 / 20,838 | 20,523 / 20,559 / 19,948 | 1.94 · 1.03 |
| calls | 42,463 / 40,900 / 22,741 | 23,167 / 23,295 / 22,454 | 1.87 · 1.04 |
| `sp_share` | 1.000 / 1.000 / 1.000 | 1.000 / 1.000 / 1.000 | 1.00 · 1.00 |

The two refs differ by the renames, the `xx` counter and nothing that can
touch `di` or `cg`.

### The number, and why it needs two sentences

**The corrected waste ratio is 4.9 to 11.7 real discards per real
generation.** It is **bimodal by run**, sitting near 5 or near 11.5, and it is
*not* noisy within a mode: round 3's three runs agree to **2%**.

**And that is the trap.** Three runs of one ref all landed in one mode and
reported a 2% floor, which would have licensed quoting "4.96 ± 2%". Round 2,
three runs of a ref that cannot differ in these counters, says 6.14 to 11.68.
**Three replicates of one ref are not enough to find this quantity's floor,
because they can all land in one mode.** The registered noise-floor leg
(three run medians spanning under 2x) *passed* on round 3 at 1.10 and would
have *failed* on round 2 at 2.34. A within-ref floor is a lower bound on the
floor, never the floor.

### Where the variation lives, and where it does not

`cg` — real generations — is 3,392 to 4,216 across all six runs, a factor of
**1.24**, while `di` and `calls` move by **1.94** and **1.87** and move
*together*. They move together for a reason that is an identity rather than a
coincidence: **`di` ≈ `calls` − `cg`.** Every block recycled out of
`inv_htable` was put there by a discard, so in steady state discards and
recycles are the same event counted at two ends.

So: **the amount of code Crimson Skies causes to be generated in 90 s is
roughly fixed; what is bimodal is how many times that code is thrown away and
recycled.** All of `waste`'s spread is on the numerator. A lever aimed at
generation cost is aimed at the one quantity in this family that does not
move, and `cg` at 4,134 per 21 windows is about **0.5 generations and 3 guest
instructions per frame** — so whatever `tb_gen_code`'s 19.1% of the bounding
thread is in this scene, it is not the cost of translating code. It is the
recycle lookup and the link-and-arm path around it, which is where
`tb_link_page` at 11.56% inclusive sits.

### It is not 2.8, and the correction has no fixed sign

2.8:1 was Fuzion Frenzy's visits over calls. Crimson Skies' visits over calls
is 6.5 to 12.8 and its discards over generations is 4.9 to 11.7.

The correction's *direction* is regime-dependent. Because

    waste = waste_legacy x (1 - clog) x recycle

and `clog` and `recycle` move independently, round 3 puts `waste` well below
the legacy figure (4.96 against 12.12, all three runs) while round 2 puts it
*above* on two runs of three (11.68 against 7.67). **The registered leg
predicting the direction passed on its own arm and does not hold on the
other.** That is a stronger statement of the original defect than a corrected
number would be: the retracted ratio was not a number with a fixable error,
it was a quotient of two quantities whose errors move independently.

**And a discard is not a retranslation.** Five to twelve calls in six to
thirteen come back out of `inv_htable` without codegen. The cost of a discard
is `tb_link_page`, the arming walk and the jump-cache flush below — not a
`tb_gen_code`.

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

**Measured: `xx = 0` in every one of the 60 windows of all three round-3
runs.** That is the control the performance lane asked for by name before the
range test is touched, and the same runs reproduce `ov` at a median of 0 and a
maximum of 4, which was its other condition.

Two aggregate identities go with it, and the difference between them is worth
a paragraph because it cost two wrong comments:

- **`sp + ov == di`, exactly, in every window of all six runs, zero
  mismatches.** Two separate pieces of code counting the live population, and
  they are emitted on *one* log line, so this one is exact and it is the
  tightest control here after `xx`.
- **visits = discards + already-invalid, to ±1 and not exactly.** Round 2 gave
  0/0/0; round 3 gave −1/−1/+1 over ~280,000 visits. `visited` is printed on
  the **first** `hakuX-pages` line and `ai`/`di` on the **second** — two
  separate log calls from the nv2a thread with the guest CPU thread running in
  between — so a visit in flight lands on one side of the subtraction only,
  and each window boundary can slip any of the three by one in either
  direction. Round 2's three exact zeros were luck, and reading them as the
  contract is what made two successive versions of this check wrong: first
  "expected 0", then "negative only". The tool now allows one per window
  boundary and voids the line beyond that.

## #68: the cost IS now established, and `sp_share` is 1.000 over live blocks

`sp_share` = 1.000 in **every window of every run**, over 20,835 to 40,476
**live** discarded blocks per run. A prior lane measured 1.000 and correctly
withdrew it, because its population included the dead blocks clogging the page
lists and a dead block has no reason to overlap the current write. This
measurement asks the question only of blocks without `CF_INVALID`, and the
answer did not move.

**Before citing a 1.000, what would a systematic error do?** Four checks, and
they are why this one is citable where the earlier one was not — the last is
the one that carries weight, because it does not use the predicate:

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
gone, which is the first thing this instrument has said about block length
that is arithmetically possible at all.

The registered leg was `blk` median ≥ 16, on the reasoning that an
8-instruction cap is a no-op below it, and **that leg failed.** But the leg
was the wrong test, and saying so is worth more than recording the failure:
**`blk` mixes two populations.** `hakux_gen_insns` and `hakux_tb_codegen`
count every generation, including the forced one-shot blocks — the
`cflags_next_tb = 1 | CF_NOIRQ` after a `current_tb_modified` store, the
`phys_pc == -1` single-insn TB, `cpu_io_recompile`'s n of 1 or 2, the
breakpoint and precise-SMC paths. Those are short by construction. A mean of
6 over the mixture does not say what a *permissive* block's length is, and it
is only the permissive path that `HAKUX_SMALL_BLOCK_INSNS` narrows.

How much this matters is bounded, and the bound is reassuring rather than
otherwise. If a fraction *f* of generations are forced-short one-shots and
the permissive ones average *P*, then *f*·1 + (1−*f*)·*P* = 6.2. For *P* to
reach the clamp's 8 needs *f* ≥ 0.26; for 16, *f* ≥ 0.65. So **the lane's
feasibility verdict survives unless at least a quarter of all generations are
forced one-shots.** That is not obviously false — `do_st_mmio_leN` is 6.43%
of the bounding thread, so MMIO stores are frequent and `cpu_io_recompile`
asks for n of 1 or 2 — but nothing measured here reaches 0.26.

So the honest state of §2's lever is: it is dead because no store can miss a
block (#68), which is established; whether an 8-instruction cap would *also*
be a no-op is **probably true and not established**, and `blk` cannot settle
it. The measurement that would is one more counter pair — instructions and
generations restricted to calls whose request was `CF_COUNT_MASK == 0` —
which is two lines in `tb_gen_code` beside the narrowing branch that already
tests exactly that condition. **No device time is asked for it**: the lever
ships at 0 either way, and this is a note for whoever revisits it, not a
reopening.

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

## Pixel-inertness: inherited, not re-measured

The performance lane's corpus arm (`9eb64cbcc3` against `6b574e163e`, eight
suites, one disc, both on the thor, arms proven distinct by APK hash) came
back with **all 593 capture PNGs byte-identical by md5** and all nine scored
columns identical. That establishes the *round-two* counters are pixel-inert.

**It does not, strictly, establish it for the patch in this file**, which adds
one `tb_cflags` read and one global compare per visited TB. The argument that
carried that leg applies to this change with room to spare — the only route
from a counter on a slow path to a pixel is perturbing timing enough to flip
an nv2a race, and this adds strictly less work per event than the counters
that were measured — but it is an argument, not a measurement, and no device
time is being asked for it. Said here so that nobody later reads the
byte-identical result as covering a commit it predates.

## A soft-invalidated block IS found and executed (#73, reading only)

`tcg-retranslation-measured.md` flags, unverified, that `tb_lookup_cmp` masks
`CF_INVALID` off before comparing, so the tier-1 soft invalidation's stated
intent — "so it won't be reused from cache" — may not hold. **Reading the
three sites settles it, at no device cost. It does not hold.**

1. `tb_lookup`'s jump-cache fast path tests `tb_cflags(tb) == s.cflags`
   **exactly**, unmasked. Setting `CF_INVALID` in place therefore makes that
   path miss, every time, forever.
2. `tb_htable_lookup_common` then hashes with `s.cflags`, which comes from
   `curr_cflags()` and never carries `CF_INVALID` — **the bucket the TB was
   inserted under** — and `tb_lookup_cmp` masks `CF_INVALID` off. So the
   stale block is found, returned, and written back into the jump cache,
   where step 1 will reject it again next time.
3. `cpu_exec_loop` runs `cpu_loop_exec_tb()` on it and only *afterwards* does
   `if (tb->cflags & CF_INVALID) last_tb = NULL;`, which suppresses
   **chaining**, not execution.

Two consequences, and the second is the one to take to #73:

- The invalidation this is diagnosing costs a permanent htable lookup per
  execution of every soft-invalidated block, on top of the ~112 futile
  `qht_remove` attempts a frame the lane measured.
- `tier1_consume_request()` is called from **inside `tb_gen_code`**
  (`translate-all.c:527`), and `tb_gen_code` runs only when `tb_lookup`
  returns NULL. If the lookup never returns NULL for that PC, the request is
  never consumed and `CF_TIER1` is never set — so the promotion the soft
  invalidation exists to trigger may not happen at all until a real page
  invalidation removes the block.

**This is a code reading, not a measurement, and it is #73's, not this
lane's.** The cheap confirmation needs no new instrument: `tier1_consume_request`
already logs `consume #N: ... -> CF_TIER1` under tag `hakuX-tier1` at
priority DEBUG, and that tag is **absent from `LOGCAT_SPEC`** in
`dispatcher.sh`, `run_disc.sh` and `soak_title.sh`. Adding `hakuX-tier1:D`
to the spec would show on the next soak anybody runs whether consumption ever
happens. Nothing here should be fixed before that line is read.
