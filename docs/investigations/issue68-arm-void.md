# #68's arm is NOT void. The instrument was checking a retired identity.

**RETRACTION, 2026-09-14, `lane.tcgcount`.** This file previously concluded that
arm B's counters "disagree with themselves" and that `937848c9e7` must not fold
until the counters were reconciled. **The counters were coherent the whole
time.** What failed was `tcg_pages.py`'s consistency check, which hard-coded an
identity that the commit under test retires by design — and says so, in its own
message, before any of the six soaks ran.

The filename is kept because `docs/testing/nv2a_issues.toml` and the board
request chain both point at it. Read the retraction, not the name.

Nothing in this correction required a device. Every number below is off the six
soaks already on disk under `dispatch/results/*tcginval-arm*`.

## What the tool asserted, and why it was wrong

The check was:

```
sp + ov == di      "two separate counts of the live population on one log
                    line, so they must agree exactly"
```

`sp + ov` is the LIVE VISITED population: `tb-maint.c` splits every block the
invalidation loop walks into already-invalid (`ai`) or live, and splits live by
the overlap test into written (`ov`) and not-written (`sp`). `di` is the
DISCARD count.

Those are the same population **only while the loop discards every live block
it visits**, which is exactly what whole-page invalidation does and exactly what
`937848c9e7` stops doing. With the range test restored a live block the write
missed is *spared*: it is a visit, it is in `sp`, and it is not a discard. The
held commit's message states it outright — "`visits = discards + already` no
longer holds, deliberately, and the declaration says so".

So the tool applied a pre-#68 identity to a post-#68 build and reported the
change working as a broken counter.

## The counters reconcile exactly. Three identities, measured

Re-derived from the same logcats, per window, no slack terms:

| identity | arm A (`117203fe9b`) | arm B (`937848c9e7`) |
|---|---|---|
| `xx == 0` (the impossible row) | 0 over 22 windows × 3 runs | 0 over 22 windows × 3 runs |
| `di == ov + sp` (whole-page) | **holds 22/22, all 3 runs** | fails 22/22, all 3 runs |
| `di == ov + ai` (range-tested) | fails 22/22, all 3 runs | **holds 22/22, all 3 runs** |
| `visited == ov + sp + ai` | holds, ±4 worst window | holds, ±182 worst window |

Both discard identities are exact — every term is on one log line, so neither
carries a cross-thread or cross-line term. Each arm satisfies exactly one of
them, cleanly, in every window of every run. That is not a coincidence and it
is not a coherent-looking accident: it is the predicate change, read off the
counters.

`di == ov + ai` post-#68 is the restored predicate stated as arithmetic. The
loop discards on `tb_hit || !tb_live || tier >= 2 || superblock != NULL`; the
first two terms are `ov` and `ai`, and the second two are unreachable while
`XBOX_SUPERBLOCK_ENABLED` is 0. On the day that flag is flipped this identity
is what will break first, which is the right place for it to break.

`visited == ov + sp + ai` is the **population identity** and it is the one that
holds on both sides, because `tb-maint.c` makes both splits *before* applying
the discard predicate — deliberately, so that the predicate cannot select its
own population. That design decision is what makes the two arms comparable at
all, and it worked.

### The 160-million residual was a subtraction against the wrong model

The old report read `visits = discards + already` and found a residual of
160,836,959. That residual **is the spared count**. It is the change. Against
the population identity the residual is a per-window log slip of at most 182
blocks on a window walking ten million, and the slips come in cancelling pairs
(`-30/+30`, `-100/+96`, `-164/+182`) because `visited` and `ov/sp/ai` are
printed by two separate `__android_log_print` calls with the guest running in
between. The only uncancelled slip is the **final** window of a run, whose
partner window is never emitted; one soak's last window carried `-3544` of its
`-3536` run total.

## The arm, re-judged against its registered prediction

`docs/testing/predictions/tcg-range-test-restored.json`, registered by
`lane.tcginval` before any soak ran. Judged on the tool's stated rule: per-run
medians of per-window rates, every run in one arm against every run in the
other.

| leg | verdict |
|---|---|
| **G** — `xx == 0` on every arm, every window | **PASS**, both arms, all six runs |
| **73-1** — `ai/visits` ≥ 0.80 on A, ≤ 0.20 on B | numerically passes (0.93/0.86/0.86 → 0.000) but **NOT ATTRIBUTABLE**, see below |
| **73-2** — `di/visits` RISES on B | **FAILS as written** (0.143 → 0.000), and is not attributable either |
| **68-1** — `em` falls ≥ 5× | **PASS**, and by three orders of magnitude: run totals 21,845 / 42,274 / 42,456 → 12 / 12 / 12 |
| **68-2** — `pr` falls with `em`, `pr_per_em` in 0.95–1.05 on both arms | `pr` **FELL** (42,714 → 458, ~93×). `pr_per_em` **FAILS**: 1.000 on A, 38.2 on B. See below — the leg's denominator is destroyed by its own arm |
| **68-3** — visits per event RISES on C | **PASS** (1.015 → 52–55), and it is close to a tautology of the patch |
| **68-4** — slow stores RISE; report, and > 10× stops the fold | **PASS the threshold**: 864,826–912,607 → 3,443,162–3,547,511, a **3.8–4.1× rise**, below the 10× stop |

### 73-1 and 73-2 are not attributable, and this is a design fault of the run

The prediction specified **three** arms: A = `117203fe9b`, B = the #73 commit,
C = the #68 commit. **Two were run.** Arm "B" on disk is `937848c9e7`, which is
#68 sitting on top of #73. Both #73 legs are therefore confounded with #68, and
in the direction that manufactures a pass: #68 raises `visits` 500-fold, so
`ai/visits` collapses whether or not #73 did anything, and `di/visits` collapses
for the same reason. 73-1 reading 0.000 is consistent with #73 working and
equally consistent with #73 doing nothing.

**Separating them needs the missing middle arm**, three soaks at the #73 commit
alone. Nothing else on disk can do it.

### 68-2's `pr_per_em` is a ratio its own arm destroys

The leg's intent was sound — it is the check that the *relationship* between
page-emptying and arming walks did not change, and it read 1.000 across six
earlier runs. But 68-1 predicts `em` falls by at least 5×, and it fell to 12 per
run. A ratio whose denominator the arm is predicted to drive towards zero cannot
discriminate: `pr_per_em` on arm B is 38.2 over run totals and 0.000 over most
windows, because most windows have `em == 0`.

`pr` itself is fine and moved as predicted. **The leg should have been stated on
`pr` per generation, or `pr` per event — quantities whose denominator survives
the change.** This is the same shape as `ws`, which `937848c9e7` retired for
being true by construction; `pr_per_em` is not forced by the patch, but it is
*undefined* by it, which is the other way to be unmeasurable.

### 68-3 is nearly a tautology, and it is the cost leg in disguise

"Visits per event rises" is what sparing blocks *is*: a spared block stays on
its page list and is walked again by the next store to that page. The patch
forces it. `AGENTS.md` — "a falsifier your own change guarantees is not a
falsifier".

What it is *actually* measuring is the cost, and nothing registered bounds it:

```
visits per 120-frame window   arm A     13,270      arm B   7,469,151   (~560x)
invalidation events           arm A     13,202      arm B     103,751   (~7.9x)
visits per event              arm A          1.015  arm B          52.4
slow stores                   arm A     39,827      arm B     130,390   (~3.3x)
```

Each of those 7.5 million visits per window is a page-list link traversal plus a
`tb_overlaps_written_range()` call. **That is the uncosted half of #68**, and
leg 68-4 does not see it: 68-4 counts stores, and the per-store cost is what
rose. The 10×-stops-the-fold threshold was written against the store count and
the store count only rose 4×.

**It is a steady state, not a leak.** Visits per event plateaus at 70–95 from
window 5 onward, reproducibly in all three runs, rather than climbing. It is
bounded by whatever bounds page-list length — translation-buffer capacity and
flush, neither of which #68 controls — so the plateau is a property of this
title in a 90-second soak and **must not be quoted as a bound for a longer run
or a larger code buffer.**

### The other side of the ledger, which no leg asked for

```
calls to tb_gen_code          arm A      1,954      arm B          57   (~34x FALL)
recycle rate (calls/gen)      arm A         35.0    arm B           1.000
generations (cg)              arm A         58      arm B          57   (indistinguishable)
```

Blocks are no longer discarded, so there is nothing in `inv_htable` to recycle,
so `tb_gen_code` is barely called: calls collapse to generations. That is a
large real win on the codegen path, measured, and it was not predicted by any
leg either. **It also means #68 removes most of the `inv_htable` traffic that
audit M5 is about** — see the M5 counter work, which must be sized against a
build on the correct side of this fold.

## What this establishes

- **The arm is judgeable and mostly passes.** `937848c9e7` does what it said on
  `em`, `pr` and the store count, with `xx == 0` throughout and both population
  identities exact.
- **It does not license the fold**, and the reasons are unchanged from the
  commit's own "NOT ESTABLISHED" block plus two new ones: the ~560× rise in
  invalidation-loop visits is unbounded by any registered leg and is the cost
  side; and the correctness case still needs a title that overlay-loads code,
  because #68's failure mode is a stale translation executing and
  `nxdk_pgraph_tests` is nearly all static content.
- **The instrument is fixed rather than the run repeated.** `tcg_pages.py` now
  tests both discard identities, names which model the build matched, and VOIDs
  only a run matching neither. A cross-fold A/B is reported as such, with `di`
  and everything derived from it called incommensurable between the arms.

## Not established

- Whether #73 alone does what leg 73-1 says. Needs the missing middle arm.
- Whether the ~560× visit rise costs frame time. `gfps` ceiling and `G_min` are
  indistinguishable between the arms in these soaks, but a dispatcher soak
  injects no input and never reaches Crimson Skies' heavy sections, so this is
  the weakest measurement in the file and should not be read as "free".
- Whether the 70–95 visits-per-event plateau holds beyond 90 seconds.
- Anything about correctness. No corpus arm was run, and one would be weak
  evidence here regardless.
