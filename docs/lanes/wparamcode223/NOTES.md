# lane.wparamcode223 -- #223: the ff position carry and the zero-area rule, built

Brief: build the two hunks PR #304 (wparamff223) priced but did not compile:
(A) vsh-ff.c's 0 * x = 0 transform and homogeneous carry, and (B) geom.c's
"one-negative triangle with zero grid area draws nothing".  Land them
together, gate (B) on every capture a must-not-move glob covers, and arm it.

**Status (2026-09-25):** both hunks built, both compiled, prediction
`docs/testing/predictions/wparamcode223-carry-zeroarea.json` registered on
a = `6341ee6aa5` (master), b = `8555c013c6` (master + this lane), 23 suites.
Waiting on the arm.

## 1. Re-derived prices (ff_port.py, rerun here, unchanged tools)

| model | ff bitri coverage xor G | ff quad coverage xor G |
|---|---:|---:|
| today's port | 560,372 | 494,273 |
| carry, no 0 * x = 0 (`--no-nvmul`) | 128,829 | 178,517 |
| carry (A), ideal clipper | **1,601** | **2,126** |

These match #304's figures exactly.  The "ideal clipper" draws nothing for a
triangle with homogeneous determinant 0, which is what (B) buys on the
Adreno. So the carry row is the price of (A) + (B) together, not of (A) alone.

## 2. (B) as #304 wrote it drops a triangle silicon draws: bounded at 2^19

`b_gate.py` runs (B)'s precondition over every W_param triangle that can
have a negative w: ff_w_zero_inf through ff_port's tail (today and carry),
prog_w_zero_inf, w_gaps (strip and tris) and w_neg_strip.  w_pos_strip,
ff_w_zero and rcc have no negative w.

As written ("one w < 0, q finite, grid area exactly 0"), **(B) also fires on
tri2 of ff bitri w-0.96e-34 and w-3.08e-33.** tri2's negative vertex lands at
about 8e35 px, where float32 swallows the other two vertices' offsets. pz1 -
pz0 == pz2 - pz0, so kahan_det is exactly 0.  That tri2 is the golden's red
strip, which the host clipper draws correctly today (#304 section 2's natural
experiment).  (B) unbounded would have taken those two rows from ~146k to
~72k, not to ~0.  #304 missed it because its port checked NDC area first
(`host(area)`), while geom.c checks the grid area first.

**Fix: require every |pz| < 2^19.** Only there is pz the snapped 1/16 grid:
roundScreenCoords is the identity above it, which is the same bound (A)
carries at.  And only there are the float32 differences exact.  With the
bound, (B) fires on:

| capture | triangles | today (Thor) | what the golden has there |
|---|---|---:|---|
| ff bitri w-0.00, -1.50e-36, -1.88e-37, -3.76e-37, -7.52e-37, -0.96e-34, -3.08e-33 | tri1 | 68k-146k | nothing (tri1 degenerate on silicon, #304 section 1) |
| ff quad w-inf (carry model only) | both halves | 0 | nothing (golden is labels only) |
| w_gaps, w_gaps_tex_persp | the 12 one-negative | 145,687 | nothing: the golden's 1-px lines are the white LINE-mode passes (w_param_tests.cpp:243-269), and (B) is only in the FILL path |
| w_neg_strip (+tex) | strip2, strip3 (-0.1 vertex on a w=1 one) | 37,444 | nothing, and the capture draws nothing there today |

It fires on **no prog triangle.** So the brief's step 3 is answered: w_gaps'
lines are line-mode draws, not these triangles. The zero-area triangles
draw nothing on silicon, and (B) moves w_gaps toward the golden.

## 3. The hunks as landed

- **(A) vsh-ff.c position tail.** #304's hunk verbatim, braces added.
  - `scrPos` replaces the in-place `/= w; += vpoff`, with the same operations
    in the same order.
  - `ff_port.py` today-vs-carry: gl_Position changes **only** on vertices
    that were inf or NaN before. Every finite carried vertex is bit-identical
    (ff quad and bitri w-0.96e-34, w-3.08e-33).
- **(B) geom.c `emit_wedge()`,** after `garea`:
  `if (garea == 0.0 && max(pmax.x, pmax.y) < 524288.0) return true;`, with
  pmax the component max of |pz[0..2].xy|.  The header comment says when it
  applies.
- **Compiled:**
  - `vshemit/check.py` emits the whole FF vertex shader from vsh-ff.c, with
    skinning off and on and lighting off and on. It compiles all 4 for both
    vulkan1.0 and opengl (8/8) under the NDK glslc, and rejects a mutant
    (`vec3 p = tPosition * cm[j]`).
  - `geom_check.py` compiles all 15 `geom_dump` cases (15/15; (B) is in 5 of
    them) and rejects a mutant (`pmax < 524288.0`, a vec2 against a float).
  - Rerun:

        bash docs/lanes/wparamcode223/vshemit/build.sh
        python3 docs/lanes/wparamcode223/vshemit/check.py
        make -C docs/testing/geom_dump BUILD=$PWD/.scratch/geom
        python3 docs/lanes/wparamcode223/geom_check.py

## 4. The arm

Prediction: 19 better, 0 worse, and everything else bit-identical.  The
per-row tolerances are in the prediction's prose:

- the quad extremes, 79,174 -> ~314;
- the bitri extremes and w-inf / winf / w0.00, to under 2,000;
- w_gaps, to under 25,000.

What would move each must-not-move leg, by hunk line:

| leg | what would move it |
|---|---|
| ff_w_zero x4 | the carry `mix` (w = 0 clamps to 2^-64, so scrPos >> 2^19): moves only if the carry is not the identity where snapping was |
| w_neg_strip x2 | (B)'s `return true`: moves only if the Adreno drew something from those zero-area triangles today |
| ff quad w-inf | (A)'s 0 * x = 0 plus (B) (0 today, golden empty) |
| finite ff rows, prog, rcc, w_pos_strip | nothing reaches them (see section 2) |
| Lighting / Specular / Material / Shade / Texgen | the (A) branch or the carry failing to compile or to be a select |
| Depth_Clamp, Viewport, Texture_perspective, Front_face, Attrib_float, Fog_inf_coord, Degenerate_begin_end, Edge_flag, Overlapping_draw_modes | any non-finite or far-off ff position (A), or zero-area one-negative triangle (B), that I did not enumerate |

## For the next lane

- **A grid-area test is only a grid test below 2^19.** Above it pz is not
  snapped, and a far vertex swallows the others.  Any rule keyed on
  `garea == 0` needs the bound.
- **Do not trust a port's gate order.** Check the order geom.c evaluates
  in: `ff_port.gate` checks NDC area before grid area, and that hid (B)'s
  tri2 case.
- Do not build a w scale or a two-negative rule (#304, still true).
