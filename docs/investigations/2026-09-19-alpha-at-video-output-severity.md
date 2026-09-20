# #111's alpha-at-video-output quirk, and what it is actually worth to #89

Written 2026-09-19 by `lane.cloud-111`, offline, at `master` `9472a18d33`.
No device, no code change. Everything below is either a citation into this
tree or a citation into a prior measurement on this board; where it is
neither, it says so in the sentence.

## The short version

#111 says the NV2A's video output discards the framebuffer's alpha, and
draws the inference that **"if alpha never reaches the screen, #89's residual
is invisible to a player and only matters where a later draw reads the
surface back as a texture."**

The premise is plausible and unconfirmed. **The inference is too strong, and
the reason is checkable without hardware: direct scanout is one of five
consumers of a colour surface's alpha in this tree, and the quirk exempts
only that one.** Texture readback is not the only survivor; it is the
*second* survivor. The first is the blend unit, which reads the destination
alpha out of the framebuffer on every draw that selects a `DST_ALPHA`
factor — an entirely on-screen, entirely RGB-visible path that the encoder
never enters.

So #89's residual does drop out of one severity bucket, and it does not drop
out of the others. The note this produces for #89 is in
`docs/lanes/cloud-111/board-request.md`.

## Two questions #111 runs together

**(Q1) Is #89's 141,125 a real defect?** The quirk has no bearing on this at
all, and #111 says so itself: "the goldens are framebuffer captures, so the
encoder's behaviour does not explain the difference; a wrong alpha in the
framebuffer is still wrong against a framebuffer golden." That concession is
correct and worth restating in the strong form: the goldens are PNGs the
*guest* writes by reading surface memory, and the hardware goldens were made
the same way, on hardware whose encoder — under #111's own premise — also
never saw that byte. Confirming the quirk moves this number by zero.

**(Q2) What does the residual cost a player?** This is the question the quirk
bears on, and it is the one the severity note is about. The rest of this
document is Q2.

## The five consumers of a colour surface's alpha, read at the tip

Enumerated by reading `hw/xbox/nv2a/` at `9472a18d33`. The column that
matters is the last one.

| # | consumer | site | exempted by #111's quirk? |
|---|---|---|---|
| 1 | destination-alpha blending | `pgraph.c:2855-2899`, `vk/draw.c:316-318`, `gl/draw.c:186-188` | **no** |
| 2 | the surface re-sampled as a texture | `vk/texture.c:1359`, `:1443`, `:1483`, `:1961-1991`, `:2338` | **no** |
| 3 | alpha test over a sampled surface | `glsl/psh.c:281-284`, `:3455-3460` | **no** (downstream of 2) |
| 4 | guest CPU readback of surface memory | the surface download path; this is how every golden in this harness is made | **no** |
| 5 | direct scanout | `gl/display.c:215`, `vk/display.c` display path | **yes**, if the quirk is confirmed |

### 1. Destination-alpha blending — the hole in the inference

`NV097_SET_BLEND_FUNC_{S,D}FACTOR_V_DST_ALPHA` and their
`ONE_MINUS_` partners are decoded at `pgraph.c:2855-2858` and `:2896-2899`
and mapped to `VK_BLEND_FACTOR_DST_ALPHA` / `..._ONE_MINUS_DST_ALPHA` at
`vk/draw.c:316-318` (GL: `gl/draw.c:186-188`). On any draw selecting one of
them, the blend unit reads the **stored** alpha of the destination pixel and
multiplies an **RGB** contribution by it. The encoder is downstream of that
and cannot undo it.

Put #89's residual through it. The observable is: 141,125 cleared pixels
carry `0xFF000000` where the hardware golden holds `0x00000000` — our
framebuffer says *fully opaque* where hardware says *fully transparent*, over
141,125 of 307,200 pixels, **45.9% of the frame**. A subsequent blended draw
over that region:

| factor | hardware (`Ad = 0.0`) | this tree (`Ad = 1.0`) |
|---|---|---|
| `DST_ALPHA` | source contributes **nothing** | source contributes **in full** |
| `ONE_MINUS_DST_ALPHA` | source contributes **in full** | source contributes **nothing** |

That is not a shade difference, it is a presence/absence flip of a whole
draw, in RGB, on screen. `vk/draw.c:263-267` records that this board has
already measured exactly this shape from the other direction: the
`Blend surface` swatches build `result = S x Ad` precisely to read `Ad` out
of the framebuffer, and read 255 in all four columns for `DST_ALPHA` and 0 in
all four for `ONE_MINUS_DST_ALPHA`. The channel is live and this project has
already used it as an oracle.

### 2. The surface re-sampled as a texture — live, and not blunted by the pad override

This is the survivor #111 names, and it is worth being precise about *when*
the stored byte is what gets sampled, because a pad-alpha override sits in
the path.

`surface_sampled_pad_alpha()` (`vk/texture.c:1359`) substitutes the format's
pad constant for the sampled alpha — but only for pad formats, and it returns
`VK_COMPONENT_SWIZZLE_IDENTITY` outright when
`pgraph_glsl_dual_src_pad_supported()` (`vk/texture.c:1440-1443`), because on
those devices the write side stamps the constant into memory instead. Two
consequences:

- For **`A8R8G8B8`** — `PSH_PAD_ALPHA_NONE` at `glsl/psh.c:254-266`, taking
  neither branch of the switch — there is no override at all, on any device.
  The stored byte is the sampled value.
- **#89's surface is `A8R8G8B8`.** `color_zeta_overlap_tests.cpp` sets
  `SCF_A8R8G8B8` at all six of its `SetSurfaceFormat` sites (`:53`, `:199`,
  `:212`, `:234`, `:267`, `:292`), with a TODO saying the `_O` format is not
  used yet — checked in the tests tree by `lane.blitsafe` and recorded in
  `docs/testing/predictions/issue89-clear-pad-alpha-shape.json`.

So #89's residual is **not** a pad bit in a channel the format says is
meaningless. It is the alpha channel of a format whose alpha is a real
guest-visible quantity, which is a strictly worse place for it to be, and it
is exactly the case the pad override does not cover.

### 3. Alpha test over a sampled surface

Once route 2 has delivered a wrong alpha into a shader, `ALPHATESTENABLE` /
`ALPHAFUNC` (`glsl/psh.c:281-284`, emitted at `:3455-3460`) turn it into a
**discard/keep** decision. Like route 1 this is binary rather than graded:
`0xFF` against `0x00` under any threshold func is the difference between a
fragment existing and not existing.

### 4. Guest CPU readback

Titles read surface memory back for render-to-texture staging, for
save-game thumbnails and for their own compositing. This is also how every
golden in this harness is made, which is why Q1 is unaffected.

### 5. Direct scanout — the one the quirk exempts, and this tree does not model it

**This tree passes framebuffer alpha straight through the display path.**
The GL display fragment shader is `out_Color.rgba = texture(tex, texCoord);`
(`gl/display.c:215`) — `.rgba`, not `.rgb` with a forced opaque alpha. There
is no alpha handling in the display path in either direction, which matches
#111's "State in this tree: absent".

One nearby fact, because it is the only place in the output path where this
tree already takes a position on the hardware's alpha and it is unsourced:
PVIDEO colour keying compares **RGB only**, at `gl/display.c:221`
(`out_Color.rgb == pvideo_color_key`) and `vk/display.c` (`state.color_key =
d->pvideo.regs[NV_PVIDEO_COLOR_KEY] & 0xFFFFFF`, with the comment "PVIDEO
color keying ignores alpha"). If that masking is right it is a second,
independent instance of "the output path does not read alpha"; if it is
wrong it is a defect of its own. Nothing on this board sources it. It is the
sharpest externally observable discriminator available for #111's own claim,
and the hardware prediction is built on it:
`docs/testing/predictions/2026-09-19-alpha-at-video-output.md`.

## What confirming #111 would and would not license changing

Worth writing down before somebody implements it, because the obvious fix is
the wrong one.

**Right:** force alpha opaque (or ignore it) **at the display stage only** —
`gl/display.c:215` and the Vulkan display path, downstream of everything in
routes 1-4.

**Wrong, and it would be a regression:** stop *storing* alpha, or zero it
earlier in the pipeline. Routes 1-4 all read stored alpha, on hardware as
much as here. #111's premise is about what the RAMDAC reads out of the
framebuffer, not about what the raster writes into it.

There is precedent for this exact confusion costing something on this board:
`vk/draw.c:735-737` records that reverting #59's clear pad-alpha stamp
"restores a different defect", because the clear always wrote 1.0 before it.
A write-side change made to satisfy a read-side observation is how that
happened.

## Severity, stated as a bound rather than a value

**What is exempted:** #89's residual is invisible through route 5. If #111 is
confirmed, a frame carrying the residual and scanned out directly, with
nothing sampling or blending against it afterwards, looks correct to a
player.

**What is not:** routes 1-4. On any of them a 45.9%-of-frame `Ad = 1.0` where
hardware holds `0.0` is a presence/absence flip of whatever reads it, in RGB.

**What nobody has measured, and the severity note must not imply otherwise.**
The blast radius on record is *one capture in 4,522*, across 47,250 scored
rows and 886 runs (`AGENTS.md`, "Blast radius, measured rather than feared").
That number bounds **what the corpus would catch**. It is not a statement
about titles, for two reasons that are both properties of the instrument:

- The trigger condition — **two or more captures in suites preceding the
  capture's own** — is a property of a *test disc's* composition. Nobody has
  named what the equivalent state is in a running title, or established that
  a title reaches it at all. The mechanism is still unnamed and five
  candidates are dead by their own pre-registered falsifiers
  (`AGENTS.md`); until it is named, the title-side trigger cannot be derived.
- The corpus has **no coverage** for the case that would cost the most: a
  `DST_ALPHA` blend over a region cleared under the trigger condition.
  `Blend_tests` (1,673 goldens) has no same-ref two-disc pair at all, and 89
  of 100 suites have no composition coverage (`AGENTS.md`). A zero from an
  instrument that cannot see the case is not evidence about the case.

So the honest severity is: **narrow where measured, unknown where it would
cost most, and #111 does not shrink it to zero in either place.**

## One thing found while reading that is not about severity

**#89 is closed and its row reads `status = "fixed-verified"`, and the
141,125 is live at the tip.** This is a statement about the record, not a new
measurement, and every part of it is quotable:

- PR #102's own per-issue table: "**#89** — Patch + arm PASS, 44/44, 42 of 42
  captures byte-identical. **Untouched by this attempt.**"
- The prediction that arm judged,
  `docs/testing/predictions/issue89-clear-pad-alpha-shape.json`, is titled
  "**AN INERTNESS CLAIM, REGISTERED AS ONE** … it predicts that NOTHING
  moves", registers `must_not_move` only and no absolute anywhere, and says
  in terms: "Nothing about #89's 141,125 … **this change is a correctness
  narrowing, NOT a fix for the 141,125**."
- The same prediction registers `Swap_ZB` as a **positive control** that the
  residual is still there: "on this disc it should read 141,125 in BOTH arms
  … A leg reading '141,125 -> 0' would be a fit."
- The judged verdict (`[job.arms]` on PR #102, 2026-09-19T05:34:33Z) reports
  `Color_zeta_overlap 9 caps, better 0 worse 0 same 9, differing A 387,179
  differing B 387,179` and "every checked capture is byte-identical between
  the arms".

A PASS on an inertness prediction says the patch changed nothing. It was read
into the tracker as a fix verdict — `status_note`: "PR #102 merged with the
pad-alpha-format narrowing landed and its arm PASS (44/44 …) — status set to
`fixed-verified`". Byte-identical-between-arms is the *strongest possible*
statement that the residual did not move.

This matters to #111 directly: #111 is a severity note on a residual, and a
severity note attached to a row that says the defect is fixed and verified
reaches nobody. The correction is in the board-request.

## For the next lane

- **Do not test #111 with a flat cleared field.** Both models predict the
  same picture; see the prediction file's "the void program".
- **Do not plan a pgraph golden for this.** Every capture in this harness is
  a guest readback of surface memory. The video output is downstream of the
  framebuffer and the guest cannot read back what the RAMDAC emitted — on
  hardware or here. `lane.cloud-110` established the same thing for the
  PVIDEO overlay (`docs/lanes/cloud-110/NOTES.md`). This question needs an
  external capture and **cannot be an `ab_compare` arm**.
- **`vk/texture.c`'s pad override is not a general alpha shield.** It is off
  for `PAD_ALPHA_NONE` formats and off entirely where
  `pgraph_glsl_dual_src_pad_supported()` holds.
