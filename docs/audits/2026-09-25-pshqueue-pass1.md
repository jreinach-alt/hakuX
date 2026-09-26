# Audit pass 1: PR #347, lane.pshqueue

Head audited: `e00d25530b` (lane/pshqueue). This is the diff against
`origin/master` (`git diff origin/master...HEAD`). GitHub's file list for the
PR shows 56 files, but 46 of them are master's own and came in through the
merges. The lane's diff is 10 files: `glsl/psh.c` (+30 -1), `glsl/psh.h` (+1),
the regenerated `nv2a_index.json`, two predictions (#279, #285), and the lane
directory `docs/lanes/pshqueue/` (NOTES plus four scripts).

**Verdict: no HIGH, no MEDIUM, five LOW.** The two hunks do what their
predictions say, and their arms passed: #285 went to 89/89 with both
captures exact, and #279 went to 9/9 with DotZW moving from 65,536 to 165. The
#315 hunk and its prediction were reverted by new commits (65a5a65ae4,
17dc41b0a7), so neither the code nor the arms job carries it.

## What was checked

- **#279 DOT_ZW** (`psh.c:3176-3184`). `zvalue` and `zfloor` are declared in
  `clip` in both depth branches (perspective `:2618/:2632`, and
  non-perspective `:2876-2877`). The final shader is assembled
  as clip, then vars, then code (`:3783-3787`). So the assignment in `vars`
  replaces the interpolated value, and the depth-format switch (`:3674` on)
  reads it. `dot(i-1)` exists because `stage_consistent(..., 2, 3, 1, ...)`
  requires the previous dot stage. The hunk is inside `depth_needed`, so the
  GL renderer is unchanged: `depth_needed` is only set off-GL (`:315-320`),
  as the NOTES say. D16 and D24 read `zfloor`, clamped to `[0, clipRange.y]`.
  F16 and F24 read `zvalue`, which their own encoders bound with `max(,0)`
  and `min(,max)`.
- **#285 swap** (`psh.c:3649-3661`, `:3955-3961`, `psh.h:210`). This is the
  last write to `fragColor`: only the depth switch follows it, and that does
  not touch colour. The swap comes after `fragColorSrc1 = fragColor`, so the
  dual-source copy is unswapped. The only dual-source substitution in
  `vk/draw.c` is `SRC1_ALPHA` (`pad_write_color_factor`), and alpha is not
  swapped, so the substitution is unaffected. There is no `SRC1_COLOR` use
  anywhere in `vk/`. The signed-blend fold is per channel and symmetric, so it
  is order-independent with the swap. The uniform is set from the live
  `surface_shape.color_format` next to `padAlphaMode`, which has the same
  staging and was verified by #59. It is not part of the shader key, so a
  format change cannot serve a stale program.
- **Arms.** #279's ceiling was "~137, far above refutes". It measured 165,
  which is 28 px over. The lane reads the misses as all +-1 depth word
  (`dotzw_fit.py`, 100% within 1, both runs identical), and cloud-279's NOTES
  predicted that float-divide shape. I accept that reading. It is not a
  finding.
- **Scripts.** `syntax_check.py`, `mode_users.py` and `latest_scores.py` are
  read-only helpers. `register.sh` is covered by L4.

## Findings

### L1 (LOW): DOT_ZW does not guard a zero or NaN divisor

`zvalue = dot(i-1) / dot(i)` has no guard. At a pixel where `dot(i) == 0`,
it gives +-inf, or NaN for 0/0. For D16 and D24, `clamp(floor(NaN), 0,
clipRange.y)` is undefined in GLSL. The ordinary W path handles this case
explicitly (`:2628-2631`, NaN -> FLT_MAX), and the override skips that
handling.

Failure scenario: a texm3x2depth draw whose dot-mapped source texel is the
zero vector (e.g. a (128,128,128) normal-map texel under a signed dot mapping).
The two dots are then 0/0, and the depth written is up to the driver, so it
can differ between Adreno and Mali. That breaks the per-capture agreement
between Thor and Nova.

This is LOW rather than MEDIUM because cloud-279's NOTES already list
"w <= 0 and 0/0" as something the only test cannot constrain: no DotZW pixel
has w = 0. Nobody knows what silicon writes there, so a guard would pick a
value without evidence. Worth an issue: a deterministic guard (for example
NaN -> clipRange.y, as the W path does) plus a test with w = 0.

### L2 (LOW): the DOT_ZW depth skips depth clipping and the clip-range clamp

The depth-clip `discard` and the `[clipRange.z, clipRange.w]` clamp (`:2880-2889`) are
applied to the interpolated z, before the override. The DOT_ZW value is then
clamped to `[0, clipRange.y]`, not to the guest's clip min and max.

Failure scenario: a guest sets a non-zero clip min, and a DOT_ZW pixel has a
ratio below it. Today that writes a depth below clip min. The ordinary path
would clamp it to clip min, or discard it with ZCLAMP_EN_CULL.

This is LOW because it is also a stated limit in cloud-279's NOTES ("whether
depth clipping or discard applies to the DOT_ZW value are unobserved"), and
the test's clip range is 0..2^24.

### L3 (LOW): #285 swaps the value, but not the write mask or the blend constant

The swap puts the combiner's b into host R. The host write mask is still built
from the guest's RED enable into `VK_COLOR_COMPONENT_R_BIT` (`vk/draw.c:2402-2409`,
`:4715-4722`), and `blendConstants[0]` is still the guest's red
(`:2468-2469`, `:4566-4570`).

Failure scenario: on a G8B8 surface with BLUE_WRITE_ENABLE clear and
RED_WRITE_ENABLE set, byte 0 receives b, where silicon presumably keeps
it. Similarly, a CONSTANT_COLOR blend weights byte 0 by the constant's red, not
its blue.

Neither is a regression: before the hunk, byte 0 held r under the same mask
and constant, which was wrong in the same cases. No capture exercises either
case. The GL renderer also receives the swap without a measurement. Its host
formats (`GL_R8`/`GL_RG8`, `gl/constants.h:409-412`) have the same byte
layout, so the swap should be correct there too. Worth an issue alongside the
`// FIXME: Map channel color` notes in both `constants.h` files.

### L4 (LOW): `register.sh` still registers the refuted #315 prediction

`docs/lanes/pshqueue/register.sh` still registers `pshqueue-315-brdf.json`,
and its trailing Python rewrites it. If the script is re-run and the result
committed, the refuted prediction comes back. Its refs are still live, so the
arms job would run it again. Drop the #315 block, or note in the script that
it is historical.

### L5 (LOW): the PR title still says the PR includes #315

The title reads "#279 DOT_ZW, #285 G8B8, #315 BRDF psh.c hunks". #315 was
reverted, and the fold commit will carry this title. It should read "#279
DOT_ZW, #285 G8B8" (the body is already right). Set it with the REST PATCH,
not `gh pr edit`.

## What pass 2 should verify

Nothing here blocks the fold. For pass 2: L4 and L5 are one-line edits to
check. L1 to L3 are recorded limits, and each should have a follow-up issue
before `fold-ready`, or be accepted as recorded. CI on `e00d25530b`: `check`
passes and both `build` jobs were pending when this was written.
