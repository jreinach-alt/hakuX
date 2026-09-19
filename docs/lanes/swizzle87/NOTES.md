# lane.swizzle87 -- #87 and #85

## Why the previous attempt did not finish: it DID finish, and was merged

The resume prompt asked me to record why attempt 1 did not finish. The honest
answer is that it finished and the board could not see it.

PR #101 from this branch is **MERGED**. Before it, `c807592d02` -- the fix for
both #87 and #85, both backends -- was already merged into `master`. So the
"unfinished lane" the board re-dispatched had in fact shipped twice over.

I re-verified every one of those claims at the tip rather than taking the
previous session's word for it:

| claim | how I checked | result |
|---|---|---|
| #87 fix in master, both backends | `git merge-base --is-ancestor c807592d02 origin/master` | YES, `gl/surface.c` +82 / `vk/texture.c` +32 |
| #85 fix in master | `mem_dirty` absent from `update_surface_part()` at `origin/master` | gone; only the explanatory comment remains |
| prediction registered & committed | `docs/testing/predictions/issue87-surface-to-texture-layout.json` in `origin/master` | present, control partition verbatim |
| falsifier landed | `docs/testing/swizzle_morton_fit.py` in `origin/master` | present |
| #87 closed | `gh issue view 87` | CLOSED 2026-09-18T23:11:31Z |

**The actual re-dispatch trigger is two stale records, not missing work:**

1. **#85 is still OPEN on GitHub** although its fix is in `master`. PR #101
   flagged exactly this and asked for it to be closed. Nobody did, so the lane
   still reads as owing an issue.
2. **`[lane.swizzle87]`'s `note` in `territory.toml` is still the wave-87
   text** ("NOW IMPLEMENT -- it was dispatched analysis-only"). The brief I was
   handed is that note word for word. The `files` field has moved on --
   `gl/surface.c` was released by this lane at wave 94 and the row now lists
   only `vk/texture.c` -- but the prose did not, and the prose is what the
   brief is generated from.

So the brief was stale in three separate ways: it told me to write a fix that
exists, granted me a file this lane had already released, and told me not to
queue an arm that had already run and passed. **A lane cannot fix either of
these** -- both files are barred to lanes -- which is why this is a board
request (below) and not a commit.

`preflight.sh`'s own coverage gate names this failure mode and names #87
specifically: *"Finished work reading as available is how an issue gets
re-dispatched."* It has now happened to this lane twice.

## What I did instead, and it is not nothing

### 1. Audited the landed fix. Nobody had.

`c807592d02` went into `master` with `[skip ci]` and was never code-reviewed.
It is live. I checked it by reading, exhaustively rather than by spot-check:

- **Every admitted format pair is correct.** The new predicate is
  `surface->swizzle == pgraph_get_color_format_info(fmt).linear` -- i.e.
  "refuse when the two agree", which is right because `swizzle` and `linear`
  are opposite senses. I enumerated all 9 `return true` pairs in GL's switch
  **and** all 16 in `android_surface_to_texture_rgba8_compatible()`, and
  confirmed each texture format is present in `kelvin_color_format_info_map`
  with the correct `.linear`.
- **The table holes are harmless, and I checked why.**
  `pgraph_get_color_format_info()` is bounds-checked and returns a zeroed
  `undefined_format` (`.linear == false`) for anything missing. A hole would
  be *harmful* for an `LU_IMAGE_*` format -- it would both regress the valid
  linear/linear fast path and fail to fix #87 for it. All six admitted
  `LU_IMAGE_*` formats are present with `linear = true`, so there is no hole
  where one would matter. An `SZ_*` hole is inert, since `undefined_format`
  and a real `SZ_*` entry agree at `false`.
- **Both placements are right.** GL's is *before* the `#ifdef __ANDROID__`
  early return (which returns true on its own, so a check after it is inert on
  the one platform measured); Vulkan's is *after* the `!surface->color` return,
  keeping zeta out of scope.
- **`surface_is_texture_source()` (vk) is correctly left alone.** It only
  selects a pad-alpha view swizzle, and answers "is this surface the source",
  which a layout mismatch does not change -- the memory is the same either way.
  Same shape of argument as PR #101's for GL's `surface_to_texture_can_fastpath()`.

**Conclusion: the fix is sound on both backends.** No change needed, and I made
none to either C file.

### 2. Re-measured the arm from the captures, independently of `ab_compare.py`

| arm | ref | differing px vs golden |
|---|---|---|
| A (pre-fix) | `048f0a29af` | **10,240** of 307,200 |
| B (post-fix) | `4fba887182` | **0** of 307,200 |

Exact, as predicted. The falsifier also still reproduces the run-length
signature term for term at the tip: `80px x32, 64px x96, 32px x32, 16px x32`
observed and predicted, Morton 100% on both wrong quads where the identity
scores 68.75% and loses on both right ones.

### 3. Fixed a real defect in the falsifier -- the one thing here that is a code change

`swizzle_morton_fit.py` had **two exit statuses for three outcomes**. Its
byte-identical-capture path returned **0**, the same as MODEL HOLDS, while its
own docstring promised *"Exit status is 0 only if the model fits the wrong
quads, loses on the right ones, and reconstructs the golden byte for byte."*
That sentence was false: the clean-capture path satisfies none of those three
and still exited 0.

Why it matters rather than being pedantry: **#87's fix is in `master`, so the
clean capture is now the common case.** Every fresh `Surface_pitch::Swizzle`
run takes that branch. Anyone wiring this in as a regression check --
`swizzle_morton_fit.py cap.png && echo holds` -- gets "holds" from a run that
scored no leg at all. The script's default outcome had become a free green,
which is the exact failure it exists to argue against.

Now: **0 held, 1 refuted, 2 not exercised**, with the docstring corrected.

I did not take the status split on faith. I built a mutant and confirmed each
status is reachable:

```
=== armA     exit 0 (want 0) OK   VERDICT: MODEL HOLDS
=== armB     exit 2 (want 2) OK   NOT EXERCISED
=== mutant   exit 1 (want 1) OK   VERDICT: MODEL REFUTED
```

The mutant is the golden with the affected quads carrying a **random**
permutation rather than the Morton one -- identical colour multiset, so it
defeats a multiset test and only the real map can reject it. It scores 61.5%
where the true capture scores 100%. That also re-confirms, from the other
direction, the multiset argument the script was written to make.

## What the next lane should not repeat

- **Do not re-derive #87.** It is fixed, measured, folded and now audited. If
  you were handed a brief saying otherwise, the brief is the wave-87
  `territory.toml` note and it is stale; check `git log` for `c807592d02`
  first. This is the second time this lane has been re-dispatched onto
  finished work.
- **Do not re-run the registered prediction expecting `b_ref` to resolve.**
  `b_ref` is `4fba887182`, which a later rebase took off every lineage; it
  survives only via tag `arm/4fba887182`. Same patch-id as `c807592d02`. A
  re-run needs a fresh prediction naming fresh refs.
- **Do not read the arm's PASS as broad coverage.** Carried forward from
  PR #101 because it is still true and still not visible in the totals:
  `Blend_tests` scored **105 of 1,673** goldens, so that must-not-move leg is a
  floor and the 1,673-capture claim in the control partition has *not* been
  made. The three `TexFmt_*_L` captures registered MAY MOVE **did not move at
  all**, so the measured effect of this change on this disc is exactly **one
  capture**. And the **GL half is compiled but never measured** -- the device
  runs Vulkan. My audit above is reading, not measurement, and does not change
  that.
- **The mirror direction is still unmeasured.** A linear surface aliased by a
  swizzled texture is refused by the same predicate, but no capture on the disc
  exercises it. Predicted inert here, unmeasured on titles.

## Board request -- neither file is a lane's to edit

1. **Close #85.** Its fix is in `master` inside `c807592d02`; the `mem_dirty`
   term is gone and the reachability question is answered (deleted, with the
   `vk/draw.c:117` argument for why make-reachable was the wrong branch). It
   being open is what re-dispatched this lane.
2. **Rewrite `[lane.swizzle87]`'s `note`,** or retire the row. It still says
   "NOW IMPLEMENT ... dispatched analysis-only", which is what generated this
   stale brief. The `files` field should also drop `vk/texture.c` -- #87 is
   done and I changed neither C file. Note `check_territory.py` separately
   observes that #59's blocker names `vk/texture.c`, which this lane holds
   without owning #59, and `lane.remote` has a standing by-name request for
   `gl/surface.c` (already released at wave 94).
3. **Consider gating on the note, not just the row.** Both re-dispatches came
   from prose that no machine checks while the machine-checked `files` field
   beside it was correct and current.
