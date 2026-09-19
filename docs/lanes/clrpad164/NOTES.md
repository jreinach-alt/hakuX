# lane.clrpad164 — #164, the clear half of #59's write side on GL

Branch `lane/clrpad164`, PR #172. One file of substance:
`hw/xbox/nv2a/pgraph/gl/draw.c`, plus a mechanical `nv2a_index.json`
regeneration that my own insertion forced.

## What landed

`pgraph_gl_get_clear_color()`, mirroring `pgraph_vk_get_clear_color()`, called
from the clear site in place of the raw shared `pgraph_get_clear_color()`.
Gated on `pgraph_glsl_dual_src_pad_supported()` and excluded on GLES, which is
the fourth site to make that exclusion (audit pass 1, H1).

## Reachability, checked before writing the fix — and it is not inert

lane.remote's caution on the issue was #62's finding 2, a fix to a path that
could not execute. Checked in this order, and every step held:

1. `pgraph_gl_clear_surface` is the registered renderer op
   (`gl/renderer.c:350`), reached from `pgraph.c:4440`. The `write_color` arm
   sets `glClearColor()`; the function issues `glClear(gl_mask)` with
   `GL_COLOR_BUFFER_BIT`.
2. **The alpha write bit is actually set on the live path.** `glColorMask`
   keys alpha off `NV097_CLEAR_SURFACE_A`, and `Clear::TestSurfaceFmt` pushes
   only `NV097_CLEAR_SURFACE_COLOR` — which is `0xF0` (`nv2a_regs.h:1389`) and
   therefore *contains* `NV097_CLEAR_SURFACE_A` (`1 << 7`). This was the step
   most likely to have made the whole thing inert and it is the one worth
   re-checking if anything here is ever doubted.
3. The host surface can hold the alpha: `X8R8G8B8_Z8R8G8B8` → `GL_RGBA8`,
   `X1R5G5B5_Z1R5G5B5` → `GL_RGB5_A1`.
4. **The stored alpha is what a later sample returns, on GL.** The readback
   override `sampled_pad_alpha` is Vulkan-only (`vk/constants.h`,
   `vk/texture.c`); `gl/renderer.h:361` says GL has no `host_fmt` at all.
5. The capture geometry makes the cleared area essentially the whole picture:
   `clear_tests.cpp:323-345` clears a 128×128 pad-format surface, draws a 4×4
   centre mark, and samples the whole surface through `LU_IMAGE_A8B8G8R8`.

## Three things in the brief that were wrong, and what they would have cost

The brief and the issue were unusually complete, and still three of the
falsifier's four concrete instructions were wrong. All three were caught by
reading the sources rather than by re-deriving the argument.

**1. A prediction key that matches no golden.** Both name
`Clear::SCF_X1R5G5B5_Z1R5G5B5`. The suite spells it **`SFC_`** — a
transposition upstream affecting exactly two tests (`SFC_A8R8G8B8`,
`SFC_X1R5G5B5_Z1R5G5B5`) while its own `_O` twin is `SCF_X1R5G5B5_O1R5G5B5`.
Confirmed three ways: `run-2026-09-10-clear-adreno.tsv`,
`surface-pad-bits-are-written-not-read.md:260`, and the test source
`clear_tests.cpp:39-46`. Registered as briefed it would have been refused at
queue time for matching no golden.

Worth noting for whoever touches this suite next: the test's own doc comment
at `clear_tests.cpp:156` says `@tc SFC_X1R5G5B5_O1R5G5B5` while the table at
`:41` says `SCF_`. **The table string is what names the capture file**, and
the adreno TSV agrees with the table, not the comment. Two of the three
`SFC_`/`SCF_` spellings in that file are inconsistent with each other; take
the table.

**2. The quoted absolutes are golden-versus-golden, not scored rows.** 98,342
and 49,274 come from the investigation's table headed *"In the goldens"*,
which compares the `_O` golden image against the `_Z` golden image. They are a
property of the reference files and **no arm can move them**. The scored rows
are different and device/commit-dependent — 49,152 and 81,840 on thor at
`23be8223f5`, 98,304 and 49,152 on adreno at `baab7ad5dc`. Registering the
prose figures as `expect` values would have failed this arm on arithmetic with
nothing wrong with the change. This is the repo's own "a figure in prose is
not a scored row" arriving once more.

**3. On Vulkan this exact change scored zero.** The #59 clear arm came back
`better 0 worse 0 same 217` while 49,104 px had in fact moved: green went
49,152 → 48 and the score stood still because #48's readback swizzle
overwrote the alpha half. A prediction phrased as "the score improves" was not
safe on that precedent alone. **GL has no such swizzle** (reachability 4), so
here the alpha half should move too — and that asymmetry is the sharpest thing
this arm can test, so it is registered as the falsifiable claim.

## The measuring configuration, which decides whether the arm sees anything

This change lives inside `#ifndef __ANDROID__` and is gated on a flag whose
setter `gl/renderer.c:204` keeps inside the same guard. **On a GLES build it
is a no-op by construction and would read exactly like a refuted prediction.**

That is not hypothetical: the same guard means #158's raster half is also
inert on GLES, and #158 was nonetheless measured — on **desktop OpenGL**
(`docs/lanes/remote/NOTES.md`, H1 section: *"a full disc run on desktop
OpenGL, before and after, byte-identical on 235 of 236"*). So this arm must
run desktop OpenGL too. **If the arms job returns "nothing moved", establish
which renderer it ran before reading that as a refutation.**

## What the prediction registers, and what it deliberately does not

`docs/testing/predictions/issue164-gl-clear-pad-alpha.json`,
`a_ref 11ddd94a66` → `b_ref 2ffd961764`.

* **`must_not_move` (9 globs)** is the machine-read half, and it needs no
  baseline because it is an A-versus-B identity. `Blend_surface/*` and
  `Surface_format/*` are pinned only after checking in the test sources that
  no `CLEAR_SURFACE` reaches a pad-format surface in either suite:
  `Surface_format` prepares its scratch surface with a CPU `memset`
  (`surface_format_tests.cpp:216`) and issues its only `PrepareDraw` at `:145`
  *before* the pad format is bound at `:153`; `Blend_surface` calls
  `PrepareDraw` at `:287`/`:494` before `RenderToSurfaceStart` at `:299`/`:500`.
  The `_O` twins and the `X1A7R8G8B8` pair are pinned as model checks — the
  first would catch a transposed ZERO/ONE mapping, the second would catch the
  change reaching a format `pgraph_glsl_surface_pad_alpha_mode()` calls NONE.
* **`must_not_regress: Clear/*`** — nothing in the suite may get worse.
* **No `expect` absolutes**, for reason 2 above. I could not measure a
  baseline: **a lane sandbox cannot reach the dispatch directory**, so
  `ab_run.sh`/`request.sh` are not available from here and the arms job is the
  only route. Registering a value I could not measure would have been a guess
  wearing a number's clothes.
* **No `expect_counts`.** It is a global tally over the whole disc, and
  `Surface_pitch::Swizzle` moves on its own — it was the single mover in a
  compile-only no-op arm otherwise byte-identical on 235 of 236 (the #71
  race). A `worse=0` leg would have failed on it while saying nothing about
  this change, which is the #67 failure verbatim.
* **No `disc` block**, because that field guards absolutes and there are none;
  the two arms sharing a disc is enforced separately by `check_comparable()`.
  This lane does not choose the disc the arms job uses.

The prediction was re-registered once with `--force`, before any arm ran, to
add the paragraphs recording the last two decisions. No leg changed.

## What the next lane should not repeat

* **Do not take a capture key from prose.** Three documents and a brief all
  carried `SCF_X1R5G5B5_Z1R5G5B5`; the suite has never had such a test. The
  table in the test source is the only authority, and it disagrees with its own
  doc comment one line group away.
* **Do not read #59's Vulkan numbers as this change's expected numbers.** The
  two renderers differ in exactly the component that decided the Vulkan
  result: the readback swizzle.
* **Do not conclude "inert" from a flat total on this family.** It already
  happened once here — 49,104 px moved under a score that did not — which is
  why the prediction asks for the per-channel reading and not only the class.
* `nv2a_index.json` will go stale on any edit to `hw/xbox` that shifts line
  numbers. Regenerating is safe *only* after checking
  `provenance.tests_commit` against the local `nxdk_pgraph_tests` checkout;
  mine matched (`91a0de45`), and suites/sites/symbols were 103/2839/951 before
  and after with no suite added or removed.

## State

Preflight green (`--allow-tracker`). Fix, index and prediction pushed. The arm
is the arms job's to run from the committed prediction; this lane cannot queue
it. Awaiting `[job.arms]` on PR #172 for the two movers' measured before/after.
