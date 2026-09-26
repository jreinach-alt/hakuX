# Audit pass 1: PR #332, lane/aasample (#286 class A, CENTER_CORNER_2 sample placement)

Head audited: `a53cd6b6e9`. Base: `origin/master` @ `8552e1ff89`. Mergeable, and CI
(`build` x2, `check`) is green on this head.

**Verdict: no HIGH, no MEDIUM, 4 LOW.** The only code change is an unused
`static inline` helper in `pgraph.h`, so this PR changes no binary. The `vk/draw.c`
hunk that would make it live is a patch file under `docs/lanes/aasample/`, not
applied.

## What the diff is

GitHub's file list for #332 shows ~80 files (accel/tcg, xbox lanes, jobs). That
list is stale: it was computed against an older merge base. The real three-dot diff
`origin/master...a53cd6b6e9` is 8 files, and they match the PR body's `Files:` line
exactly:

| file | change |
|---|---|
| `hw/xbox/nv2a/pgraph/pgraph.h` | +25: `pgraph_anti_aliasing_viewport_offset_x()`, which returns 0.5f for CC2 and 0.0f otherwise |
| `docs/testing/nv2a_index.json` | +1 REF site (`pgraph.h:612`), provenance |
| `docs/lanes/aasample/{NOTES.md, cc2_samples.py, points.py, price.py, tiedir.py, draw-c-viewport.patch}` | analysis |

## Checked

- **The helper is unused.** A grep for `pgraph_anti_aliasing_viewport_offset_x`
  finds only its definition. An unused `static inline` emits no code, so the PR's
  `Prediction: none` is correct. An arm now would measure a no-op.
- **The helper is safe for every anti-aliasing value.** It is a pure comparison
  with a 0.0f default. It cannot assert, unlike `pgraph_apply_anti_aliasing_factor`
  on an unknown value, and it reads the same field that function switches on.
- **`draw-c-viewport.patch` applies cleanly** to this head (`git apply --check`).
  It touches both `VkViewport` initialisers in `vk/draw.c`: 4496 (pipeline bind)
  and 5621 (reorder snapshot, replayed at 6096). The third `VkViewport` in the tree,
  `vk/display.c:1540`, is the presentation blit and must not take the offset. The
  patch leaves it alone, correctly.
- **The viewport is re-emitted whenever a CC2 surface is bound.** Viewport state
  is set only under `must_bind_pipeline`. A surface change ends the render pass,
  and `begin_render_pass` forces `must_bind_pipeline = true` (`draw.c:4471-4474`).
  So switching into or out of CC2 cannot keep a stale offset.
- **Edge coverage after the shift.** With `.x = 0.5*sf`, the clip volume maps to
  host x in [0.5sf, W+0.5sf]. Column 0's centre sits on the left clip edge, which
  is inclusive and a left edge under the top-left rule, so it stays covered. No
  column is lost.
- **Index.** `nv2a_index.py check` with no `--tests` reports no symbol or site
  drift. Its only complaint is that the suites were not checked, and CI's `check`
  covers that.
- **Scripts.** All four `.py` files compile. `price.py`, `points.py` and
  `tiedir.py` import `docs/lanes/cloud-286/decompose286.py`, which is on master.

## Findings

### LOW-1: the NOTES line numbers in section 2 have moved, but the NOTES say they have not
`NOTES.md` section 2 names the reorder replay at `vk/draw.c:5992` and the scissor
sites at `7058, 7143`. On this head they are at `6096`, `7171` and `7256`. Session 2
says "the line numbers in section 2 are unchanged". That holds only for 4496 and
5621, the two lines the patch touches.
*Scenario:* a reader applying the patch goes to 5992 to check that the replay uses
`e->viewport`, and finds unrelated code.

### LOW-2: the helper's comment states a modelled outcome as a fact
`pgraph.h:600-603` says the shift "is what makes a guest resolve that samples 2x+1
... byte-identical to a non-AA draw". That comes from `price.py`'s model, which sets
fixed ours(X) to ours(P). It has not been measured, because no arm has run.
*Scenario:* the section 4 arm shows a residual. The source comment then contradicts
the evidence, and nothing in it says it was a prediction. Suggest "should make ...
(modelled in docs/lanes/aasample/price.py; arm pending)".

### LOW-3: the head commit's subject names a fold that has not happened
`a53cd6b6e9` is titled "nv2a index: regenerate after folding #332". #332 is this
PR, and it is not folded.
*Scenario:* someone reading `git log` for when #332 folded finds this commit first
and dates the fold wrong. Cosmetic, and fixing it would need a history rewrite, so
it is recorded here only. Do not rebase to fix it.

### LOW-4: the GL renderer stays asymmetric
Once the patch lands, Vulkan shifts CC2 and `gl/draw.c:689` does not. NOTES name
this ("Named, not done"), and GL is not the Android renderer.
*Scenario:* a desktop GL run of `FBSurfaceWithCenterCorner2` keeps today's 352 px
mismatch while Vulkan's drops to 272. A cross-renderer comparison would then read
the difference as a regression. Out of scope for this PR, and recorded so pass 2
does not have to re-derive it.

## Not findings (checked, and they hold)

- The +258,221 px figure is a model and not a measurement. The PR and NOTES both
  say "priced", and the arm in section 4 is what tests it. That arm names its
  discriminating must-not-move set: the 40 plain `3D_primitive` captures and
  `FBSurfaceWithCenter1`.
- The Quads give-back of -18,912 and the Lines give-back of -1,259 are named, with
  owners (#38 and #13).

## For pass 2

There is nothing HIGH or MEDIUM to verify. Pass 2 should confirm LOW-1 and LOW-2,
or accept them as recorded. It should also confirm that the head still changes no
binary, meaning `draw-c-viewport.patch` has not been applied on this branch without
the section 4 arm being registered.
