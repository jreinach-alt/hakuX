# Audit pass 2b — PR #141, `lane/linecap13`: the wide-line cap rule, derived from the goldens and drawn

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #141, branch `lane/linecap13`, tip **`3beca48079`**, three
commits over pass 2's tip `1d4e5aa14b`: master merged at `f2bd66fb44`, the
half-pixel deadband and `--quantise` at `36e85c96c9`, the prediction
re-registered at `3beca48079`. Mergeable, all three CI checks green
(`build` ×2, `check`). Labelled `regressed`, from the FAIL that
`36e85c96c9` is the answer to.
**Date** 2026-09-19. **Records** `2026-09-19-linecap13-pass2b.{md,json}`.

**Pass 2's three findings CLOSED. Pass 1's eight stay closed. 1 new MEDIUM.**

Pass 2 raised N1 (HIGH), N2 and N3 (LOW). All three are closed, and N1 is
closed structurally rather than by assertion: below `w = 24` the clip now does
not bite **at all**, so `emit_line()` hands the rasteriser master's own four
corners and the device cannot score those captures differently. I checked that
by building the generator twice — once against `origin/master`'s `glsl/geom.c`
and once against this tip — and diffing the emitted GLSL case by case, which
also settles two claims the prediction rests on.

The new MEDIUM is in the deadband's derivation, not its direction. `0.5` is
half a **guest** pixel; the rasteriser samples **device** pixels, and
`geom_line_params()` says in its own comment that the geometry stage works in
guest pixels with one guest pixel being `surface_scale_factor` device pixels.
At the user-selectable Rendering Scale of 2 the nearest sample to a bound is a
quarter of a guest pixel away, not half, and the shipped deadband suppresses
191 plane-clips across 26 captures that such a device would have sampled. The
error is always in the direction that suppresses too much, never too little, so
it cannot reintroduce N1 — which is why this is MEDIUM and not HIGH.

---

## Pass 2's three findings, each verified closed

### N1 — the clip biting below `w = 24` where the comments said it could not — **CLOSED**

`cap_clip()` (`geom.c:579-585`) now measures the polygon's deepest violation of
the plane before doing anything else and returns `np` untouched below half a
pixel:

```glsl
float deep = 0.0;
for (int i = 0; i < np; i++) {
  deep = max(deep, -dir * ((xmaj ? P[i].y : P[i].x) - bound));
}
if (deep < 0.5) { return np; }
```

**The expression is the right one.** I checked it against both call sites
rather than against the comment. Call 1 passes `bound = floor(min(m) - w/2)`,
`dir = +1`, and the clip keeps `da = dir * (coord - bound) >= 0`, i.e.
`coord >= bound`, so the violation is `bound - coord = -dir * (coord - bound)`.
Call 2 passes `bound = ceil(max(m) + w/2) + 1`, `dir = -1`, keeps
`coord <= bound`, and the violation is `coord - bound`, which is again
`-dir * (coord - bound)`. Both `bound`s are integers by construction. So `deep`
is the max violation depth on either plane and the early-out is the identity —
`P` and `T` are `inout` and are not written on that path.

**Pass 2's scenario cannot occur.** `line_cap_phase.py --quantise`, run here
against `~/goldens/results`, counts bites per capture at the shipped tie:

| capture | w | bites, shipped | bites, pre-deadband | quantised px moved, shipped | pre-deadband |
|---|---:|---:|---:|---:|---:|
| `Line_0000.5` | 0.625 | **0** | 3 | 0 | 1 |
| `Line_0001.0` | 1.000 | **0** | 9 | 0 | 1 |
| `Line_0004.0` | 4.000 | **0** | 17 | 0 | 0 |
| `Line_0007.0` | 7.000 | **0** | 11 | 0 | 1 |
| `Line_0009.0` | 9.000 | **0** | 11 | 0 | 1 |
| `Line_0014.0` | 14.000 | **0** | 20 | 0 | 0 |
| `Line_0016.0` | 16.000 | **0** | 20 | 0 | 0 |
| `Line_0024.0` | 24.000 | 12 | 25 | 5 (= exact) | 5 |

Every capture below `w = 24` is at zero bites. The three legs report

```
the deadband costs no pixel the exact model scores: PASS
where the clip cannot move a sample it moves no quantised px: PASS
the pre-deadband geometry trips that leg: PASS
```

and the mutant is real, not decorative: with the deadband at 0, four captures
move 4 quantised px, and `Line_0001.0`, `Line_0007.0` and `Line_0009.0` are on
the device's own mover list from the failing arm. I read `quant_check()` rather
than only its PASS — `variants` scores `("base", inf)` as the unclipped
parallelogram, leg 2 is restricted to captures where the exact model does not
move, and leg 3 fails the whole check if the mutant moves nothing.

Leg 2 is trivially satisfied wherever the deadband suppresses every bite, which
is everywhere it applies here — the load-bearing column is `bites, shipped`,
and it is zero. That is a regression guard rather than a discriminating
measurement, and it is the right shape for one.

**The bit-for-bit claim, checked by building the generator twice.** N1 was
ultimately a claim about emitted geometry, so I built `geom_dump` against
`origin/master`'s `glsl/geom.c` as well as this tip (the swap lives entirely
under `scratch-audit2b/`; the real path was never touched) and compared the
emitted GLSL:

| case | master vs this tip |
|---|---|
| `tri_fill_smooth_vk` | **byte-identical** |
| `lines_smooth_gl` | **byte-identical** |
| `tri_polymode_line_smooth_gl` | **byte-identical** |
| `lines_flat_vk`, `lines_smooth_vk`, `lines_smooth_zpersp_cylwrap_vk`, `tri_polymode_line_flat_vk`, `tri_polymode_line_smooth_vk` | differ (the change) |

and read the widened path's emission order against master's. Master emits
`i0+n+tie`, `i0-n+tie`, `i1+n+tie`, `i1-n+tie`; the strip loop at `np == 4`
visits `j = 0, 3, 1, 2`, which is `P0, P3, P1, P2` — the same four corners in
the same order. The per-vertex body is one shared format string with master's,
differing only in `vtxFogSpecial`'s index (`fs` vs `index`), and under
first-vertex provoking both triangles of the four-corner strip provoke from
`P0` and `P3`, which are both `i0` vertices — so master delivered
`v_vtxFogSpecial[i0]` to fragments too. The four-corner case is therefore
identical to master in what the rasteriser sees, not merely equivalent.

All six Vulkan cases still compile (`glslc -fshader-stage=geom
--target-env=vulkan1.0`, NDK 29.0.14206865): six OK, zero failures. That is the
check the new lines in `cap_clip()` most needed, since a geometry shader that
fails to compile draws nothing and fails silently on this path.

Nothing the exact model scores moved: `--rivals` still reads 495 → 102 with
`floor + 1` at 115 and the centre band at 645, `--shader` still reads 544 px
against the goldens at the 1/256 tie, and `--depth` is still PASS/PASS at worst
error 1.11e-16. So every figure `geom.c` quotes survives the deadband, which is
leg 1 confirmed from outside the check.

**The two comments are corrected.** `geom.c:764-779` now says the first capture
whose *coverage* changes is `w = 24` and states explicitly that this does not
mean the change cannot reach a narrower line, naming the earlier version as
wrong and the deadband as what makes the inertness a property of the emitted
geometry. `:434-441` qualifies the bit-for-bit paragraph the same way.

### N2 — `--controls` counting the boundary that cannot separate the two rules — **CLOSED**

`controls()` splits the population and rests the claim on the high side alone.
Run here:

```
5472 cap boundaries (m_min - w/2, m_max + w/2) over the same captures
  landing on a whole pixel INDEX: 1104  (617 low side, 487 high side)
    the population that separates tie=ceil from tie=floor1 is the HIGH side
    alone -- the low bound is np.floor() under every tie: 487
```

617 + 487 = 1104, and 487 is the figure pass 2 computed independently. The
zero-guard now tests `ties_int_hi`, so it fires on the population the sentence
names rather than on the total. `predictions/line-cap-clip.json` carries both
halves in `cites`.

### N3 — the PR body still asserting the two retired figures — **CLOSED**

The body's derivation paragraph now reads "…scores 645 px on `--rivals`, worse
than the 495 it was meant to fix. (An earlier version of this paragraph said
497 against 412…)". The retraction is at the point of assertion, not only in
the appendix sixty lines below. `497` and `412` appear nowhere in `geom.c` or
`NOTES.md` as live figures.

## Pass 1's eight findings — still closed

`f2bd66fb44`, `36e85c96c9` and `3beca48079` touch none of the code pass 2
verified, and I re-ran the instruments rather than assuming so: `--depth`
PASS/PASS (H1), `lines_flat_vk` still emits the six interpolated varyings below
both shade-mode arms (H2), `emit_vertex_fs`'s `fs` argument and every call
site's `i0` are unchanged (M1), `float t = tl` under `NOPERSPECTIVE` with no
`line_lerp_t` in the case (M2), `--controls` measures `pen=1.0, tie="ceil"`
(M3), and the `line_cap_phase.py` / `NOTES.md` citations and `instance.c`'s
figure are intact — the latter now reads 18, moved with `max_vertices` (L1-L3).

## The re-registered prediction — sound, and its legs bind

`3beca48079` retires `expect_counts: {"worse": 0}` and replaces it with
`must_not_move` over every capture the deadband says is bit-identical. I
checked the parts a prediction usually fails on:

* **Every glob binds.** Expanded against `~/goldens/results` with `fnmatch`:
  `Line_0000.*` 8, `Line_0001.*` 8, `Line_000[3-9].0` 7, `Line_001[0-6].0` 7,
  `Line_0064.*` 8, `Line_FFFFFFFF` 1, `Fill_*` 3, `Blend_tests/*` 1673. None
  matches nothing, which is what `ab_compare` refuses at queue time and what
  would otherwise make the whole file inert.
* **The cover is complete.** No `Line_*` capture below `w = 24` is left out of
  `must_not_move` — the suite has no `Line_0002.*` and nothing between
  `Line_0016.0` and `Line_0024.0`, so the 42 `Line_width` entries are exactly
  the set the deadband's claim covers.
* **`runs_per_arm` is honoured**, not decoration: `jobs/arms.sh:669` reads it
  and defaults to 1 only when absent or malformed.
* **The claim about `must_not_move` is correctly scoped.** The file says
  ab_compare's *byte-identity half* only fails on multi-run evidence. That is
  right — `ab_compare.py:930` gates the byte leg on
  `pixels_moved_attributable`, while the score half at `:908` fails on any
  `better`/`worse` class regardless of run count. Keeping `Fill_*` after
  `Fill_0032.0` moved is a deliberate, argued choice, and the shader diff above
  supports it: the fill-mode case is byte-identical to master, so nothing in
  this branch can reach it and a second movement would be device noise worth
  knowing about.
* **The refs are live and correctly ordered.** `a_ref 28a3805b93` is an
  ancestor of `b_ref 36e85c96c9`, which is an ancestor of the pushed head, so
  the arms job can reach both and the two arms differ by this branch alone.
  The body's `Prediction:` sha256 `82cbbed7e047…` matches the file on disk.

---

## MEDIUM

### A1 — the deadband is half a **guest** pixel, but the rasteriser samples **device** pixels; at Rendering Scale 2 it suppresses 191 clips it should take

`geom.c:548-559` derives the constant, and this is the load-bearing sentence:

> The bounds below are WHOLE PIXEL INDICES … and this renderer rasterises at
> one sample per pixel, at the pixel CENTRE (every rasterizationSamples in
> pgraph/vk/ is VK_SAMPLE_COUNT_1_BIT). **The nearest centre to an integer
> bound is half a pixel away**, so the removed sliver of a shallower cut
> provably contains no sample.

The MSAA half is right: every `rasterizationSamples` under `pgraph/vk/` is
`VK_SAMPLE_COUNT_1_BIT`, so there is one sample per device pixel at its centre.
The step that does not hold is the last one, because the two sentences are in
different coordinate spaces.

The geometry stage works in **guest** pixels. `geom_line_params()`
(`vk/draw.c:2756-2786`) says so in its own comment —

> One subpixel quantum, expressed in the guest pixels the geometry stage works
> in: the rasteriser's grid is 1/2^subPixelPrecisionBits of a DEVICE pixel, and
> one guest pixel is `surface_scale_factor` of those.

— and divides by `surface_scale_factor` to produce `lineTieBias` for exactly
that reason. `out[2] = pg->line_width / 8.0f` is guest pixels too, and
`glsl/vsh.c` uses `surface_scale_factor` only to scale `oPts`, never the vertex
position. So `v_vtxPos.xy`, `bound`, and therefore `deep`, are all guest pixels.

Device sample centres are `1/scale` apart in guest coordinates, so the nearest
one to an integer guest bound is `0.5 / scale` guest pixels away — 0.5 only at
`surface_scale_factor == 1`. The deadband is a fixed 0.5 and does not read the
scale, which is available: `lineTieBias` already carries it.

**Failure scenario.** `g_config.display.quality.surface_scale` is the
user-facing Rendering Scale (`vk/surface.c:92-100`; the menu is
`ui/xui/main-menu.cc:749-762`). Set it to 2 and draw the `Line_width` suite. A
cap overhang of 0.4 guest pixels past the low bound is skipped by the deadband
(`0.4 < 0.5`), so the footprint keeps the corner and lights the device sample
at guest coordinate `bound - 0.25` — which lies in guest pixel index
`bound - 1`, the pixel the derived rule says must be dark. The cap fix silently
does not apply there, while the comment tells the reader it provably removes no
sample.

Measured over the same 48 non-void captures, counting plane violations in
`[0.5/scale, 0.5)` — the clips the shipped deadband skips and a device at that
scale would have sampled:

| `surface_scale_factor` | correct deadband (guest px) | plane-clips suppressed | captures affected |
|---:|---:|---:|---:|
| 2 | 0.2500 | **191** | 26 |
| 3 | 0.1667 | 293 | 29 |
| 4 | 0.1250 | 338 | 30 |

At scale 2 the affected captures run from `Line_0010.0` to `Line_0063.7`,
including all of `Line_0024.0` upward where the clip is the whole point of the
change.

**Why MEDIUM and not HIGH.** The error is one-directional. `0.5 > 0.5/scale`
for every `scale >= 1`, so the deadband only ever suppresses *more* clipping
than it should, never less. A suppressed clip emits master's own four corners,
so no configuration is made worse than master — N1's re-quantisation regression
cannot come back through this, and there is no crash or unsafety. What is lost
is part of #13's improvement at Rendering Scale > 1, silently, under a comment
that says it cannot be lost.

**Remediation.** Either is fine and both are small:

1. **Scale the deadband.** `0.5 / surface_scale_factor` in guest units. The
   shader does not have the scale today and `lineParams` is a full `vec4`, so
   this costs a push-constant component — note `instance.c`'s own warning that
   the range is declared on every graphics pipeline.
2. **Or keep 0.5 and state its precondition**, since the direction is safe:
   say in `geom.c` that the bound is half a guest pixel, that the guarantee is
   exact at `surface_scale_factor == 1` and conservative above it, and that the
   cost above it is the table here. Then it is a known, written-down limit
   rather than a proof with a missing hypothesis.

Whichever is chosen, `line_extent_subpixel.py` already takes a `--scale`
argument documented as "surface_scale_factor; one guest px is this many …", so
the lane's own toolbox has the fact the derivation missed.

**This need not cost the pending arm.** The harness pins `surface_scale = 1`
(`desktop_channel.sh:454`), so option 1 is a provable no-op at the scale the
arm runs at and option 2 touches no code at all. If the fix is a comment, or a
`0.5 / scale` that reduces to 0.5 at scale 1, say so on the PR and let the
queued arm on `36e85c96c9` stand rather than re-registering — a new
registration restarts a ~90-minute arm for a change the device cannot see. That
is the lane's call and the board's, not the auditor's.

---

## On the `regressed` label and the pending arm

This is not an audit finding, and it is not this pass's to clear. The FAIL of
2026-09-19 16:50 was judged on `b_ref 9fdc6b5d70`; `36e85c96c9` is the answer to
it and `3beca48079` registers the new pair. No `[job.arms]` verdict on that
pair has arrived, and `arms.sh state lane/linecap13` still reports
`STATE=regressed` — correctly, since it is a function of the verdicts on disk.

Pass 2 read `roles/board.md`'s "a `regressed` PR is not fold-ready" as prose.
It is now enforced: `fold.sh:503-510` refuses to fold a `regressed` PR, keeps
`fold-ready` in place, and folds the moment the label clears, and `arms.sh`
computes the label from the verdicts rather than by hand. So the label is a
machine gate on the fold and not a gate on the audit, and the disposition below
turns on A1 alone.

## What I ran

* `line_cap_phase.py --quantise` against `~/goldens/results` — the table above,
  three legs PASS, mutant fires on 4 px over 4 captures.
* `--depth` (PASS/PASS, 75 cases, worst 1.11e-16), `--controls` (393 removed /
  393 golden-dark / 0 golden-lit; 1104 = 617 + 487), `--rivals` (495 / 102 /
  115 / 645), `--shader` (544 px against the goldens) — every figure `geom.c`
  quotes, reproduced on this host at this tip.
* `docs/testing/geom_dump`: `make clean && make`, then all six `*_vk` cases
  through the NDK's `glslc`. Six OK, zero failures — compiled, not parsed.
* The same generator rebuilt against `origin/master:glsl/geom.c` and the
  emitted GLSL diffed case by case (the table under N1).
* `must_not_move` expanded against the goldens with `fnmatch`; `arms.sh`,
  `ab_compare.py` and `fold.sh` read for `runs_per_arm`, the byte leg's
  multi-run gate, and the `regressed` gate.
* The A1 table: per-capture count of plane violations in `[0.5/scale, 0.5)`
  over the same 48 captures, using `cap_clip()`'s own violation expression.

Scratch scripts lived in `scratch-audit2b/` and are deleted; nothing outside
`docs/audits/` is touched by this pass.

## Disposition

Pass 2's N1, N2 and N3 are closed, N1 structurally — below `w = 24` the clip
does not bite, and the emitted four-corner strip is master's own, which I
verified by diffing the generator's output against `origin/master` rather than
by reading the commit. Pass 1's eight stay closed. The re-registered prediction
is sound and its legs bind.

One new MEDIUM: the deadband's `0.5` is half a guest pixel where the sample
grid is device pixels, so the derivation holds only at `surface_scale_factor`
1 and the comment states it as a proof. The direction is safe, the fix is a
comment or one push-constant component, and the PR cannot fold until the arms
job clears `regressed` in any case.

**`needs-remediation`.**
