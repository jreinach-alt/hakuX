# lane.brdf315b: #315, why the fitted BRDF rule did not survive rendering

Base: origin/master @ 6550967a5e. Data: lane.pshqueue's #315 arm,
`1790395945-arms-pshqueue-{base-1882405,fix-1882785}` (base a389648b0b, fix
e3b13f5b45 = brdf315-psh.diff). Goldens `~/goldens` @ 6e159f1, same as
brdf315.

**Answer: the rule is right. Its inputs were rewritten underneath it.** #283
(a5b4141064, 2026-09-25) splits a point-sampled R16B16 texel into its bytes
before any later stage reads it (`tex_bytes16`). It exempts only the stages
listed in `stage_consumed_raw()`, and BRDF is not on that list. So the BRDF
stage read `t0.r` = the theta field's **low byte** and `t0.g` = the phi
field's **high byte**, not the whole 16-bit fields that brdf315 fitted. #283
is in the arm's base (a389648b0b) and not in the fit's base (fab230935e).
When brdf315 fitted, the assumption was true of the shader it read. The next
day it was not.

## 1. The per-pixel diff: same pixels, wrong colours (the lookup world)

Status first: base `blank`, fix `ok` on all three captures. Both fix runs
are byte-identical with each other, and so are both base runs.

| capture | golden != base | fix != base | fix moved outside the wedge | fix != golden |
|---|---|---|---|---|
| BRDF_e0_l0 | 614 | 614 | 0 | 614 |
| BRDF_e0_l1 | 614 | 614 | 0 | 614 |
| BRDF_e1_l0 | 614 | 614 | 0 | 614 |

The moved set **is** the golden's wedge, pixel for pixel: bbox x 579..639,
y 460..479 in both. So coverage is exact and the defect is the colour. That
is the brief's "opposite world" (the same pixels, different colours). The
falsifier's failing world (right colours only at some pixels) did not happen.
Not one fix pixel equals its golden.

Colours: the golden has G = 246 (volume t = 61) everywhere and R 190..198
(s = 47..49). The fix has **G = 89 (t = 22) everywhere** and R scattered
4..222 (60 distinct texels against the golden's 14). B (the r axis) is close
to the golden's. At (639,479) the golden reads (198,246,222,255) and the fix
(178,89,222,255).

## 2. Which assumption broke: the t0/t1 channel contents, measured

`arm_model.py` rasterises the wedge with brdf315's model and predicts each
pixel's volume texel under two readings of what t0/t1 hold. It scores
whole-texel agreement (all three axes) over the 610 modelled pixels:

| reading of t0/t1 at the BRDF stage | vs arm capture (both runs) | vs golden |
|---|---|---|
| whole fields: `.r` = theta16, `.g` = phi16 (the fit) | 0 / 610 | **605 / 610** |
| #283 bytes: `.r` = theta & 255, `.g` = phi >> 8 | **598 / 610** | 0 / 610 |

The t axis decides it with one number. The light direction is constant, and
its cube texel holds theta = 0xf658. Read as a field, floor(0xf658/65535*64)
= 61, the golden's. Read as the low byte, floor(0x58/255*64) = **22**, the
capture's G = 89 on every pixel.

The r axis agrees about 90% under either reading, because (phi_l >> 8) -
(phi_e >> 8) is the phi difference quantised to 1/256. That is why B looked
"nearly right" and hid the mechanism.

`misses.py` explains all 12 remaining misses of the bytes model. In each of
them the GPU sampled the eye cube texel one step over (a texel-boundary tie
between our CPU raster and the GPU). A 3x3 neighbour search finds that texel
for 12/12. Priced under the whole-field reading, **every one of those 12
lands on the golden's texel.** The same happens with brdf315's own 5
boundary misses: 0 predicted misses on the 610 modelled pixels. At the 4
unmodelled edge pixels, the capture's r axis already equals the golden's. The
value falsifier (639,479) predicts (198,246,222), which is the golden's.

The other assumptions the brief listed, each checked against the capture:

| assumption | holds? | measured |
|---|---|---|
| `dots_needed 0` lets the stage emit | yes | 614 px moved, status blank -> ok (with 2 it emits NONE and nothing draws) |
| texSamp2 is bound as a 3D sampler under BRDF | yes | the capture's colours are volume texels at the bytes-model (s,t,r), 598/610 |
| volume filter is nearest | yes | 614/614 wedge px are exact texel colours, floor((x,y,z)*255/63), alpha 255 |
| wrap on r | moot | `fract()` in the shader; r agrees at 99.5% under the bytes model |
| **t0/t1 `.r`/`.g` are the 16-bit fields** | **no** | t = 22 (the low byte of 0xf658) on every pixel, where the fields give 61 |

## 3. The fix: `brdf315b-psh.diff`

brdf315's hunk unchanged, plus one case in `stage_consumed_raw()`: a BRDF
stage at j consumes stages j-2 and j-1 raw, so `tex_bytes16` leaves their
fields whole. It is the same path that bump and dot-product consumers
already take. The check is by mode and offset, not by `input_tex[j]`,
because BRDF does not read through `input_tex`.

- `make_patch.py` builds the diff from the tree's psh.c plus
  `../brdf315/brdf315-psh.diff`, in memory. psh.c is never written.
- `git apply --check` passes at 6550967a5e. `overlap.sh 373 367`: the patch
  also applies on top of the psh.c holders' heads (lane.fog278 PR #373 at
  232740a86d, lane.y16bump10 PR #367 at dda0fba410). Neither of them touches
  `stage_consumed_raw`, BRDF or `tex_bytes16`.
- `syntax_check.py`: `-fsyntax-only` on the patched copy with the desktop
  build's compile line: exit 0. The emitted copy contains both edits (grep
  count 2).
- **Side effect, not covered by any capture:** `stage_consumed_raw` also
  gates the `tex_signed` rewrite. A signed-flagged R16B16 feeding BRDF would
  now reach it unsigned. Texture_BRDF sets no sign flags, so the arm cannot
  see this either way.

## 4. Prediction, ready and NOT registered

This lane may not commit psh.c, so no b_ref can exist on this branch. A
board request (`$DISPATCH_DIR/board-requests/brdf315b.md`) asks for psh.c
once #373 and #367 fold, or for the patch to ride with the holder. Whoever
commits it registers after their last rebase, a_ref = its parent,
b_ref = the commit:

- **must_move**: `Texture_BRDF/BRDF_e0_l0`, `BRDF_e0_l1`, `BRDF_e1_l0`,
  better, 614 -> **<= 4 each** (only the 4 edge-rule pixels have no modelled
  s; the other 610 are predicted exact). Value falsifier: (639,479) =
  (198,246,222,255). A result of 614 -> 5..30 would mean the boundary-tie
  analysis is wrong, not the rule. A result of 614 -> 614 again with G still
  89 means the exemption did not reach the stage.
- **must_not_move**: every other `Texture_*`, `Pixel_shader/*`, `Combiner/*`
  and `Volume_texture/*` capture. The change that would move each: both
  edits are reached only when some `tex_modes[j] == PS_TEXTUREMODES_BRDF`,
  and only `texture_brdf_tests.cpp` sets BRDF (lane.pshqueue's
  `mode_users.py`). One of them moves only if the new
  `stage_consumed_raw` case fires for a non-BRDF mode (a wrong comparison),
  or if a stale shader-key cache serves a program from the other build.

## What the next lane should not repeat

- Do not refit the BRDF coordinates. The rule is confirmed twice: 605/610
  against the golden with fields, and 598/610 against our own render with
  bytes. The same model explains both, and the 12 misses are boundary ties.
- Before fitting a stage against a golden, date the fit against every
  landing in the stage's input path. #283 changed what every R16B16/Y16
  stage delivers to its consumers, one day after this fit.
- A mostly-right channel (B here, about 90%) can come from a quantised
  version of the right input. Check the constant channel first. One constant
  wrong value (G = 89) identified the mechanism.
