# #67: the swatch quads are not mis-rasterised. The guest's `floorf` is wrong.

Written 2026-09-13. Everything below is offline, against the silicon goldens
(`/home/justin/goldens/results`, Sep 9), the `Blend_tests` captures of dispatch
`1789300545-blend43-region-agent-209081` (Sep 13 05:05, the #43 region arm) and
the `Point_size` captures of `1789268617-bytegrid-fix-1396332`. Both capture
sets postdate every change to the vertex and rasterisation path, so neither is
stale. Zero device runs.

Reproduce with:

    docs/testing/guest_frndint_rounding.py \
        ~/hakux-work/dispatch/results/1789300545-blend43-region-agent-209081 \
        --point-results ~/hakux-work/dispatch/results/1789268617-bytegrid-fix-1396332

## Result

#67 is real, its region is exactly the one the #43 lane measured, and its
mechanism is **not** in the graphics pipeline. The over-extent is x87 `FRNDINT`
ignoring the guest's rounding-control field, so the guest's `floorf` returns
round-to-nearest. The geometry #67 calls mis-rasterised is geometry the *guest*
computed wrongly and we drew faithfully.

    target/i386/tcg/fpu_helper.c:266
    #define floatx80_round(a, s)           ((void)(s), rint(a))
    #define floatx80_round_to_int(a, s)    ((void)(s), rint(a))

`rint()` rounds per the *host* FP environment, which QEMU leaves at
nearest-even; `(void)(s)` discards the guest `float_status`. `helper_frndint`
(same file, ~line 2945) is `ST0 = floatx80_round_to_int(ST0, &env->fp_status)`,
so the argument that carries the guest's mode is the argument being thrown
away. nxdk's `floorf` is the textbook x87 sequence — save the control word, set
RC = round-down, `FRNDINT`, restore — and with RC discarded `floorf` **is**
`rint`.

The mode itself is not the problem: `cpu_set_fpuc` calls `update_fp_status`,
which is compiled `#ifndef USE_HARD_FPU` and is therefore a single global
function shared by both helper sets, so `env->fp_status.float_rounding_mode` is
correct at the moment `FRNDINT` runs. Only the macro ignores it.

Scope of the block: `#if defined(XBOX) && defined(__aarch64__)` under
`USE_HARD_FPU`, i.e. the **Android FP JIT path only**
(`g_config.perf.fp_jit`, default on; `xemu_android.cpp` reads the `fp_jit`
pref with a default of `true`). The x86_64 hard path does not override
`floatx80_round_to_int`, so it stays softfloat and is correct — which predicts
that this whole class is invisible on the desktop/lavapipe lane, and that the
soft path (`fp_jit` off) is correct too.

## How it was decided, and why it is not a fit

`blend_tests.cpp` computes the whole `TestSpot` layout from three `floorf`
calls:

| line | expression | argument | `floor` | `rint` |
|---|---|---:|---:|---:|
| 186 | `test_width = floorf((512 - 16) / 5)` | 99.2 | 99 | **99** |
| 189 | `test_height = floorf((480 - 72) / 3)` | 136.0 | 136 | **136** |
| 190 | `color_swatch_size = floorf(test_width / 4)` | 24.75 | 24 | **25** |

One parameter moves. `test_width` staying 99 is confirmed independently — the
cell pitch is 103 in the goldens *and* in our captures — and `test_height`
staying 136 likewise, the cell rows being at 136 and 272 in both. Those two are
not assumptions: they are the two calls where floor and round-to-nearest agree,
and they are what makes this a rule rather than one fitted constant.

With `color_swatch_size` = 25 the entire cell follows, and every edge below was
read off the captures as a **region** — the end of a full run of one colour
along a scan line — not as a point sample:

| feature | source expression | silicon | ours |
|---|---|---:|---:|
| `DrawColorStack` quad | x `[0, s)` | 0..23 | 0..24 |
| `DrawColorAndAlphaStack` quad | x `[s, 2s)` | 24..47 | 25..49 |
| colour-stack row boundaries | y `s*k` | 24 / 48 / 72, block ends 95 | 25 / 50 / 75, block ends 99 |
| `DrawAlphaStack` ring 0 | `[2s, 2s+q)`, `q = 99-2s` | x 48..98, y 0..50 | x 50..98, y 0..48 |
| ring 1 | inset 4 | x 52..94, y 4..46 | x 54..94, y 4..44 |
| ring 2 | inset 8 | x 56..90, y 8..42 | x 58..90, y 8..40 |
| ring 3 | inset 12 | x 60..86, y 12..38 | x 62..86, y 12..36 |

This is also why the shape looked so strange when read as a rasterisation rule:
the rings keep their right and top edges and lose two pixels on the left and
bottom **because `q = test_width - 2s` shrinks by 2 when `s` grows by 1**, and
the ring stack is anchored at the cell's right edge, which `test_width` fixes.
Read as a coordinate transform the edge map is non-monotone — y 48 → 50 in the
colour stack while y 51 → 49 in the ring stack — so no per-vertex rule, fill
convention or half-pixel offset can produce it, and that is the argument that
sent the search to the guest.

### The decisive measurement: ownership, not colour

`guest_frndint_rounding.py` builds the primitive-ownership map of one cell from
`blend_tests.cpp` alone — the rectangles painted in draw order, no capture
consulted — under `s = 24` and `s = 25`, and reports where ownership changes:

    ownership changes on 1276 px of the 136x99 cell under swatch 24 -> 25

**1,276** is the number the #43 lane measured from the captures, per cell,
before anyone knew what it was. Derived here from the test source with one
parameter.

Over all **75 unsigned `#spot_*` captures**, fifteen cells each:

    1,168,902 differing px inside the change set, 0 outside
    union over all cells and captures: 1276 px
    ownership-change set:                1276 px
    intersection:                        1276 px

Union *equals* the predicted set, to the pixel, not merely in cardinality — the
two masks were compared as sets, which is the check two equal-cardinality
masks require. And the prediction is one-directional on purpose: ownership is
not colour, so two primitives can agree on a pixel and leave it undisturbed
(per-cell counts run 372 to 1,276). What the leg tests is that **nothing
differs outside** it — any second defect in the swatch area would land there.

### Confirmation from a suite with no blending in it

A single suite's geometry can be curve-fitted by a single parameter, so the
rule is re-decided on `Point_size`, which shares no code with `Blend_tests`:

| line | expression | argument | `floor` | `rint` |
|---|---|---:|---:|---:|
| 387 | `increment = floorf((640 - 32 - 8) / 7)` | 85.714… | 85 | **86** |
| 323 | `cy = floorf((480 - 64) / 3)` | 138.666… | 138 | **139** |

    SmallestPointSize_FF: silicon spacing {85}, ours {86}, differing 14 px
    SmallestPointSize_VS: silicon spacing {85}, ours {86}, differing 14 px
    LargestPointSize_FF:  silicon green rows (102, 307), ours (103, 309)
    LargestPointSize_VS:  silicon green rows (102, 307), ours (103, 309)

`SmallestPointSize` draws nine one-pixel points at `16 + increment*k`. Seven of
the nine move, two pixels each, and **14 pixels is the entire residual of both
captures** — the geometry error is all of it. `LargestPointSize` puts a ruler
bar at `cy - 36` and runs the whole lambda again at `2*cy`, so the topmost and
bottom-most green rows are `cy - 36` and `2*cy + 31`: 102 and 307 for cy = 138,
103 and 309 for cy = 139. Both predicted from the source before being read.

Three call sites, three different fractional parts (0.75, 0.714, 0.667), three
independent suites, every one decided the same way, and no free parameter.

## What it is not

- **Not the fill path, and not a fill convention.** The fill rule and sample
  point are pinned exactly by the ten passing `Viewport` captures
  (`viewport-9-16-boundary.md`): axis-aligned 100-px quads at integer screen
  coordinates are gold-exact on every edge. Nothing here asks the rasteriser to
  change, and this answers #67's "does the fill path have this generally?" —
  **it does not have it at all.**
- **Not `prim_rewrite.c`.** The quads are `PRIMITIVE_QUADS`, so they do pass
  through the rewrite, but it only re-indexes: it cannot move a vertex. Read
  and excluded rather than assumed.
- **Not the render-to-texture blit.** The 512×512 target is composited 1:1 at
  (64, 64) and its own edges land at 64 and 575 in both arms; any resampling is
  monotone in position and cannot reproduce a non-monotone edge map. Checked
  numerically against a 25/24 nearest-neighbour magnification, which predicts
  the ring bands at 50..54 / 55..58 / 59..62 where they measure 50..53 / 54..57
  / 58..61.
- **Not a stale golden or a different build of the suite.** The goldens' own
  layout is the current source evaluated with a correct `floorf` — pitch 103,
  swatch 24, ring stack 51 — so the source that produced them and the source we
  build are the same source. `TestSpot`'s printed label is identical in both
  arms.
- **Not #43 and not #50**, and the #50 separation is now two-directional.
  #67 measured that #50 does not reach the `#spot_` captures; the converse also
  holds, from the source rather than from a capture. `TestDetailed` -- #50's
  region -- calls `DrawAlphaStack`/`DrawColorStack`/`DrawColorAndAlphaStack`
  with their default arguments, which are the literals `256.f`, `24.f` and
  `64.f` (`blend_tests.h:79-88`). No `floorf` appears anywhere in its geometry,
  so this mechanism **cannot** reach #50's 16,384-px strip even if
  `TestDetailed` were ever renderable. The lavapipe oracle run
  (`blend-oracle-on-lavapipe.md`) is the same story from the other side: its
  1,568 captures are `TestDetailed`, its fifth-quad defect reproduces on two
  rasterisers, and none of its geometry is fractional.

## The fix, and where it lives

`target/i386/tcg/fpu_helper.c` is `target/**`, which `docs/testing/territory.toml`
wave 10 assigns to `lane.remote`. **Nothing was edited.** The diff, against the
two macros at lines 266–267:

```c
-#define floatx80_round(a, s)           ((void)(s), rint(a))
-#define floatx80_round_to_int(a, s)    ((void)(s), rint(a))
+/*
+ * FRNDINT rounds per the guest's control-word RC field. rint() rounds per the
+ * HOST FP environment, and (void)(s) threw the guest mode away -- so nxdk's
+ * floorf (save CW, RC=down, FRNDINT, restore) became round-to-nearest. See
+ * docs/investigations/guest-frndint-ignores-rounding-mode.md.
+ */
+static inline double floatx80_round_to_int_nds(double a, float_status *s)
+{
+    switch (s->float_rounding_mode) {
+    case float_round_down:    return floor(a);
+    case float_round_up:      return ceil(a);
+    case float_round_to_zero: return trunc(a);
+    default:                  return rint(a);
+    }
+}
+#define floatx80_round(a, s)           floatx80_round_to_int_nds((a), (s))
+#define floatx80_round_to_int(a, s)    floatx80_round_to_int_nds((a), (s))
```

The `default` arm still leans on the host environment being nearest-even, which
QEMU never changes; that is the one assumption left in it and it is worth a
comment rather than a rewrite.

### The legs to register before queueing it

The arm is one disc carrying `Blend tests`, `Point size` and a guard suite; the
guard must be on the *same* disc, because an unmatched `must_not_move` fails
`ab_compare` and a prediction naming captures from two discs cannot pass on any
single arm.

    ab_compare.py --register docs/testing/predictions/guest-frndint-rounding.json \
        --a-ref <tip> --b-ref <fix sha> \
        --expect-value 'Point_size/SmallestPointSize_FF=0' \
        --expect-value 'Point_size/SmallestPointSize_VS=0' \
        --expect-value 'Blend_tests/#spot_srcA_ADD=0' \
        ... all 75 unsigned #spot_* at 0 ... \
        --expect-value 'Blend_tests/#spot_0_SADD=96855' \
        ... all fifteen #spot_*_SADD at 96855 ... \
        --must-not-move 'Viewport/*' --must-not-move 'Stencil/*'

- **75 unsigned `#spot_*` → 0 differing px each**, total 1,168,902 → 0. The
  seam is their entire residual, so they must become bit-exact. Constrained by
  the goldens, not by the patch: anything else wrong in that region leaves this
  non-zero.
- **`Point_size::SmallestPointSize_FF`/`_VS` → 0**, and the recovered spacing
  → 85. The mechanism-shaped half: a count of 0 and a spacing of 84 would mean
  the model is wrong in the same direction as the fix.
- **Fifteen `#spot_*_SADD` → 96,855 px each**, from 104,205. That is #43's ink
  set under the corrected 24-swatch geometry (6,457 px × 15 cells), i.e. the
  sign fold with the seam removed. They must **not** go to zero; #43 is
  untouched.
- **`Viewport/*` and `Stencil/*` must not move.** Both compute their geometry
  from `floorf(320)` and `floorf(240)`, exact integers, so the fix cannot reach
  them. This is a real leg: it fails in any world where the change perturbs
  `FRNDINT` for arguments that were already integral.

Not a falsifier, stated so it is not counted: the thirty signed captures
remaining non-zero is forced by #43 being open, not by this change.

## An adjacent defect in the same block, deliberately not bundled

    fpu_helper.c:248
    #define floatx80_to_int32(a, s)        ((void)(s), (int32_t)(a))
    #define floatx80_to_int64(a, s)        ((void)(s), (int64_t)(a))

A C cast truncates toward zero. These back `helper_fist_ST0`,
`helper_fistl_ST0` and `helper_fistll_ST0`, and x86 `FIST`/`FISTP` must round
per RC — nearest-even by default — so `FISTP` of 2.75 stores 2 where hardware
stores 3. The round-to-zero variants on the next two lines are correct and must
stay truncating; only the two above are wrong. Same file, same block, same
cause, different instruction, and no capture in this corpus is known to reach
it — so it is a separate issue and a separate arm, not a second hunk in this
one.

## Corrections to #67's own numbers

- **1.44 M px is an upper bound, not the corpus total.** 19,140 px/capture is
  `1,276 × 15`, the per-cell union, and only the captures that hit every cell
  reach it (`#spot_srcA_ADD` and `#spot_srcRGB_ADD` do, at exactly 19,140). The
  measured total over all 75 unsigned captures is **1,168,902 px**, and the
  per-capture range is 6,154 (`#spot_0_SUB`) to 19,140.
- **The thirty signed captures are not all 104,205.** `#spot_1-cA_SREVSUB`
  measures 103,440 on this arm. #43's claim of one number was made over the
  fifteen `SADD` captures, and it holds there; it does not extend to `SREVSUB`.

## Least certain

That nxdk's `floorf` is `FRNDINT`-with-RC rather than something else that our
hard path also rounds to nearest. The *behaviour* is measured — three arguments,
three suites, `floor` on silicon and nearest-even on ours — and the macro that
produces it is read from our source, but the guest-side instruction sequence was
inferred from the standard x87 idiom and not disassembled out of the XBE. If
`floorf` reaches the same outcome by some other route, the fix above may not be
sufficient, and the leg that would catch that is the one that matters:
`SmallestPointSize` failing to reach 0.
