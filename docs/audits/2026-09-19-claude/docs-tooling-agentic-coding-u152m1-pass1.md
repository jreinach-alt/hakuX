# Audit pass 1 — PR #162, `claude/docs-tooling-agentic-coding-u152m1`: the GL surface pad-bit write side (#158), and #60 re-measured

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #162, branch `claude/docs-tooling-agentic-coding-u152m1`, tip
**`44b35be1eb`**, over its stated base **`6db8217cdb`**.
**Date** 2026-09-19. **Records** `2026-09-19-claude/docs-tooling-agentic-coding-u152m1-pass1.{md,json}`.

**1 HIGH. 1 MEDIUM. 4 LOW.**

The diff is 7 files: three in `hw/` (+118/−6), one prediction, one regenerated
index, two documents. The three `hw/` files are the whole of the behavioural
change and are where H1 and M1 live.

## What I checked and found correct, so remediation does not re-derive it

* **The mechanism is right and the pairing is right.** `psh.c` stamps the pad
  constant into index 0's alpha *after* the alpha test and after #43's fold,
  copies the combiner's alpha to index 1, and `gl/draw.c` substitutes
  `GL_SRC1_ALPHA`/`GL_ONE_MINUS_SRC1_ALPHA` for the colour factors only,
  forcing the alpha half to `ONE/ZERO/ADD`. That is `vk/draw.c`'s
  `pad_write_color_factor()` and its call sites, not a re-invention.
* **The "one derivation read twice" claim is true.** `gl/draw.c:426-429` and
  `psh.c:3859-3862` both read
  `pgraph_glsl_surface_pad_alpha_mode(pg->surface_shape.color_format)` gated on
  `pgraph_glsl_dual_src_pad_supported()` — the same expression
  `pgraph_vk_effective_blend_reg()` folds into its synthetic field
  (`vk/draw.c:638-641`). The blend state and the shader cannot disagree about
  which draws stamp.
* **`DST_ALPHA` cannot read the stamp.** All four formats
  `pgraph_glsl_surface_pad_alpha_mode()` covers (`psh.c:254-265`) are also in
  `surface_color_format_dst_alpha_is_one()` (`gl/draw.c:109-123`), so the
  Ad = 1.0 fold replaces both destination-alpha factors before
  `pad_write_color_factor()` is ever consulted. The PR's paragraph explaining
  why that fold stays is correct, and the ordering in the function is what the
  paragraph claims.
* **`GL_SRC_ALPHA_SATURATE` is genuinely safe here**, though not for the reason
  the comment gives — see L2. `min(As, 1 − Ad)` is 0 for both pad variants once
  Ad is folded to 1, so leaving it unsubstituted is correct.
* **Absence really is a refusal to enable, at run time.** With
  `g_dual_src_pad_supported` false, `psh.c:2018` declares no index-1 output,
  `psh.c:3568` emits no stamp, `psh.c:3859` stages `PSH_PAD_ALPHA_NONE`, and
  `gl/draw.c:437-439` takes the `glBlendFunc`/`glBlendEquation` branch that is
  byte-for-byte the pre-#158 code. A part without
  `GL_ARB_blend_func_extended` is unchanged. (The *compile* is a different
  question: H1.)
* **No blend-state leak.** The non-stamping branch calls `glBlendFunc` and
  `glBlendEquation`, which write both halves, so a stamping draw cannot leave
  `SRC1` factors behind for the next one. `gl/display.c`'s blend save/restore
  is `#ifdef __ANDROID__` only and the desktop display path runs in
  `g_nv2a_context_display`, so nothing outside `pgraph_gl_draw_begin` can
  inherit a `SRC1` factor.
* **The shader disk cache cannot serve a pre-#158 program to post-#158 blend
  state.** `shader_load_from_disk()` rejects an entry whose recorded
  `xemu_version` or GL vendor string differs (`gl/shaders.c:614-631`), and the
  flag is a constant of the build-plus-driver within one version.
* **The prediction's refs and hash are sound.** `a_ref dcefe557` and
  `b_ref 7ffcd2bc` both exist on the branch and `7ffcd2bc` is the change
  itself; the file's sha256 is
  `29eb63008be367c497d943d5c7f1d91ca2b08aede2d2523feada4b2bae776cfa`, which is
  what the PR body's `Prediction:` line carries. Nine `expect` keys, all in
  `Suite_dir/TestName` form. This is not the inert-leg class: nine legs name
  nine captures and one of them is pinned as not moving.
* **The index regeneration is a pure line-number refresh.** `tests_commit`
  (`91a0de45ca`), `suites` (103), `sites` (2839), `gaps` (498) and `symbols`
  (951) are all unchanged; every one of the 304 changed lines but three is a
  `"loc"`. This is not the #157 class — no suite was lost. (The three
  non-`loc` lines are L4.)
* **The #60 section is honest.** The prediction was refuted, kill condition 1
  is the one that fired, and the PR says so in its own headline rather than
  reporting the recovered 393,374 px alone.

## HIGH

### H1 — the Android build does not compile: `GL_SRC1_ALPHA` is not a GLES token, and `pad_write_color_factor()` is not `#ifndef __ANDROID__`

`hw/xbox/nv2a/pgraph/gl/draw.c:147-155`

The runtime exclusion of GLES landed in two places and the compile-time one
landed in neither. `gl/renderer.c:204-229` wraps the
`pgraph_glsl_set_dual_src_pad_supported()` call in `#ifndef __ANDROID__`;
`psh.c:2018` and `:3568` add `&& !ps->opts.gles`. But
`pad_write_color_factor()` is compiled unconditionally, and it names
`GL_SRC1_ALPHA` (`:151`) and `GL_ONE_MINUS_SRC1_ALPHA` (`:153`), which the
GLES headers do not define — they are `EXT_blend_func_extended` tokens with an
`_EXT` suffix there, and the extension is not core in GLES 3.0. The function
body is dead code on Android, but dead code still has to parse.

This is not a prediction. The PR's own CI says it:

```
hw/xbox/nv2a/pgraph/gl/draw.c:151:16: error: use of undeclared identifier
    'GL_SRC1_ALPHA'; did you mean 'G_ASCII_ALPHA'?
hw/xbox/nv2a/pgraph/gl/draw.c:153:16: error: use of undeclared identifier
    'GL_ONE_MINUS_SRC1_ALPHA'
ninja: build stopped: subcommand failed.
```

— job 105940793656 of run 35459540297, the arm64-v8a `xemu` target, `BUILD
FAILED in 2m 23s`. The rollup on #162 is `build FAILURE`, `build SUCCESS`,
`check SUCCESS`: the desktop build and the checks are green and the Android
build is red, which is exactly the shape a desktop-only token produces.

The comment at `gl/renderer.c:217-222` says *"Android is excluded deliberately
and not by omission"*, and for the flag that is true. For the token it is the
omission. The PR's definition of done says `preflight.sh` was green end to end
on the branch; `preflight.sh` evidently does not build for Android, so the
claim is true and does not cover this.

**Failure scenario.** Any Android build of this branch — the Gradle
`arm64-v8a` target, which is a CI job on every PR — fails at
`xemu_core.dir/.../gl/draw.c.o` and produces no APK. Since `fold.sh` folds a
head whose checks are green and this head's are not, the PR cannot fold as it
stands; and if it were folded, `master` would stop building for Android until
someone pushed over it.

**Remediation.** Guard both the helper and its call site the way the setter is
guarded, so the GLES exclusion is one fact expressed in three consistent
places rather than two:

```c
#ifndef __ANDROID__
static GLenum pad_write_color_factor(GLenum factor) { ... }
#endif
```

and take the `pad_stamped` branch at `:426-440` inside the same guard (or make
`pad_stamped` `false` under `#ifdef __ANDROID__` before the `if`). Do not fix
it by defining the tokens locally: that would make the Android build compile a
path whose shader has no index-1 output. Whichever form is chosen, confirm it
by the Android CI job going green, not by the desktop build.

## MEDIUM

### M1 — only half of #59's write side was ported: the GL clear still writes alpha 1.0 to a `_Z` surface

`hw/xbox/nv2a/pgraph/gl/draw.c:240`

#59's write side has two halves, and `vk/draw.c:705-733` says so in its own
heading — *"THE CLEAR STAMPS THE PAD CONSTANT TOO, AND THAT IS MEASURED RATHER
THAN ASSUMED"* — with the goldens that measured it: `Clear::TestSurfaceFmt`
gives `SCF_X8R8G8B8_O8R8G8B8` against `_Z8R8G8B8` at **98,342 px differing,
RGB identical, alpha 255 against 0**, and the 1555 pair at 49,274 px, every
difference exactly the bit-15 constant. Vulkan implements it in
`pgraph_vk_get_clear_color()` (`vk/draw.c:894-907`), which overrides alpha to
0.0 for `PSH_PAD_ALPHA_ZERO` and 1.0 for `PSH_PAD_ALPHA_ONE`.

The GL clear path calls the shared `pgraph_get_clear_color()` raw, whose alpha
switch (`pgraph.c:4650-4675`) has no case for the four pad formats and falls
to `default: *a = 1.0f`. That was tolerable before this PR — GL stamped
nothing, so the surface was uniformly un-stamped. It is not tolerable now: as
of `7ffcd2bc` a GL `X8R8G8B8_Z8R8G8B8` surface holds alpha **0 where the
raster drew** and alpha **1 where the clear wrote**, in the same surface, and
hardware holds 0 in both.

The PR body names one deliberate omission (`sampled_pad_alpha`, correctly, with
its `vk/texture.c:1367`/`:1378` WITHDRAWN citation). It does not name this one,
and it describes the change as "the GL renderer gains the surface pad-bit write
side" — a scope that covers the clear half. `vk/draw.c:729-733` is explicit
that the reason the fix went into `vk/draw.c` rather than into the shared
`pgraph.c` was that the GL renderer's half "was never wired up", so changing
the shared helper "would be a half-change on a renderer this arm does not
measure". This PR is the event that retires that reason, and it is the natural
place either to take the clear half or to record why not.

This is MEDIUM and not HIGH because it is an unfixed defect rather than a new
one: every drawn pixel moved toward hardware and no pixel moved away from it.
The measurement is consistent with that — 227 of 236 captures byte-identical,
0 worse — which is also why it is invisible in the result table.

**Failure scenario.** A guest sets `X8R8G8B8_Z8R8G8B8`, issues `CLEAR_SURFACE`
with the colour and alpha write bits, draws over part of the surface, then
binds it as a texture through a stage that reads alpha (which is precisely what
`Clear::TestSurfaceFmt` does: clear, a 4×4 centre mark, then sample the whole
surface through `LU_IMAGE_A8B8G8R8` with the final combiner taking alpha from
TEX0). GL returns 255 over the cleared area and 0 over the drawn area; hardware
and the Vulkan renderer return 0 over both. The renderer-divergence figure the
PR reports (18 → 9) is measured on a disc where this path did not move; it is
not evidence that the two renderers now agree on the clear.

**Remediation.** Either (a) add the GL equivalent of
`pgraph_vk_get_clear_color()` — a four-line override at `gl/draw.c:240`,
reading the same `pgraph_glsl_surface_pad_alpha_mode()` expression the raster
side now reads, so the two halves cannot disagree — and register a prediction
for the `Clear` suite before running it; or (b) state in the PR body and in
`docs/lanes/remote/NOTES.md`, beside the `sampled_pad_alpha` paragraph, that
the clear half is deliberately not taken here and why, naming the captures it
leaves wrong. Taking (a) without a registered prediction is the thing to avoid;
`Clear::SCF_X8R8G8B8_Z8R8G8B8` and `Clear::SCF_X1R5G5B5_Z1R5G5B5` are the keys
that would bind it.

## LOW

### L1 — `pad_stamped` omits the `!opts.gles` term the two `psh.c` gates carry

`hw/xbox/nv2a/pgraph/gl/draw.c:426-429`

`psh.c` now gates on `g_dual_src_pad_supported && !ps->opts.gles` in both
places; `gl/draw.c` gates on the flag alone. Today that cannot diverge —
`gl/shaders.c:357/360` makes `gles` a compile-time `true` exactly when
`__ANDROID__` is defined, and `gl/renderer.c` only calls the setter when it is
not — so this is LOW rather than a live defect. It is worth naming because it
is the same asymmetry H1 is: the three sites do not agree on how GLES is
excluded, and the one that disagreed is the one that broke. If the exclusion
ever becomes a run-time decision (a GLES-capable desktop build, ANGLE), this is
the site that silently names a `SRC1` factor against a shader that has no
index-1 output — which the GL spec leaves undefined rather than erroring, so it
would arrive as corrupted colour and not as a diagnostic.

### L2 — the `GL_SRC_ALPHA_SATURATE` comment reproduces the justification `vk/draw.c`'s own pass-1 audit retired

`hw/xbox/nv2a/pgraph/gl/draw.c:143-145`

The new comment says the factor is left alone because *"no capture on this
fleet reaches it on a stamping format"*. `vk/draw.c:675-694` records that this
is the wording audit pass 1 corrected as finding L2, in terms worth quoting:
*"This paragraph used to say the opposite and audit pass 1 corrected it (L2):
the code was right and the justification was wrong, which is worth fixing
precisely because a wrong comment is believed."* The derivation that replaced
it is that `min(As, 1 − Ad)` evaluates to 0 for **both** pad variants once the
stamp lands — `_Z` because As is 0, `_O` because Ad is folded to 1 — so nothing
needs substituting whatever the corpus contains. The GL copy reverts to the
argument from absence. No behaviour is affected; the code is right either way.

**Remediation.** Copy the derivation, not the retired sentence, and keep the
corpus observation as the secondary note it is in `vk/draw.c`.

### L3 — the prediction's stated kill condition names `Surface_pitch::Swizzle`, and no leg binds it

`docs/testing/predictions/2026-09-19-gl-pad-bit-write-side.json:5`

The prose ends: *"if the nine land at Vulkan's values but Swizzle or
DstAlpha_XA_O1A7RGB8 also moves, the change reached a path this model says it
cannot"*. `DstAlpha_XA_O1A7RGB8` is bound — it is the tenth `expect` key,
pinned at 90,112, which is the right way to express it. `Surface_pitch/Swizzle`
appears in no `expect`, no `must_not_move` and no `must_not_regress`, so half
of the named kill condition could not have fired. `must_not_move` holds three
suite globs, none of which covers `Surface_pitch`.

It is LOW because the check was in fact made, by hand and in the open:
`NOTES.md` reports Swizzle at 12,224 and the full-disc comparison at 227 of 236
byte-identical, and the earlier `#60` section already records Swizzle as moving
within 13,160–15,360 on GL regardless — which is the reason it was left
unbound, and is a good reason. The gap is that the registered artifact does not
say so.

**Remediation.** A `must_not_regress` entry, or one sentence in the prose
saying Swizzle is excluded from the machine legs because its GL value is not
stable run to run, so the kill condition on it is a manual check. The second is
honest and costs nothing.

### L4 — the regenerated index records `/home/user/…` provenance paths

`docs/testing/nv2a_index.json` (provenance)

Three of the 304 changed lines are not `"loc"`: `emulator_commit` (expected),
and `tests_root` / `support_dirs[0]`, which go from `/home/justin/…` to
`/home/user/…`. The index was rebuilt somewhere with a different home, so the
committed provenance now names two paths that do not exist on the host the
sweeps run on, and the next regeneration there will flip them back. Nothing
breaks: `cmd_check()` (`nv2a_index.py:1065-1130`) compares `symbols`, `sites`
and `suites`, never `provenance`, and `tests_provenance_gate()` reads only
`tests_commit`, which is unchanged and correct. It is churn in a committed
artifact, and it makes `provenance.tests_root` useless as the thing a reader
would use it for.

**Remediation.** Nothing required for this PR. If it recurs, the field wants to
be relative or omitted rather than an absolute path from whichever machine last
built it.

## Disposition

H1 and M1 → **`needs-remediation`**.

H1 is the one that blocks everything else: the head is red, and a red head does
not fold. M1 is a scope question as much as a code one — taking the clear half
needs a registered prediction and a run, so declaring it out of scope in the PR
body and `NOTES.md`, with the captures it leaves wrong named, is an acceptable
resolution and may be the better one for this PR. Either answer closes it; an
unstated omission does not.

The three `hw/` files' mechanism, gating, format coverage and control argument
are sound, and pass 2 should not re-derive them.
