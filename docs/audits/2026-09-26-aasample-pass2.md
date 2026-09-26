# Audit pass 2: PR #366, lane/aasample (#286 class A, CC2 sample shift, live)

Head verified: `09144172a4`. It is the remediation `0eae1be8ca` plus the arm
registration `5944abf51a`, then a merge of master in which only the index conflicted,
then an index regen. Base: `origin/master`, fetched 2026-09-26. CI (`build` x2 and
`check`) is green on this head, and GitHub reports it MERGEABLE.

**Verdict: clean.** MEDIUM-1 can no longer occur. LOW-1 and LOW-2 are fixed, apart
from line-number drift that the master merge brought in (a residual LOW, below).
The clip-space arm `aasample-cc2-clip.json` has no `[job.arms]` verdict yet. A PASS
there should be a formality: at sf = 1 the new form puts every sample exactly where
the viewport form did, and the viewport arm passed.

## MEDIUM-1: host column(s) outside the clip volume at `surface_scale >= 2`

The scenario can no longer occur.

- **The viewport is back at `.x = 0`.** `git grep` finds no call to the offset
  helper in `vk/draw.c`. Both `VkViewport` initialisers (`:4496` bind, `:5621`
  reorder snapshot) are back to their master form. The x/y clip volume is therefore
  `[0, W_host]` at every scale, and every host column's centre lies inside it.
  Pass 1's table now reads "none" in every row (sf = 1, 2, 3, 4).
- **The shift is the same size, and now in clip space.** `vsh.c:1012` emits
  `gl_Position.x += (2 * 0.25 / surfaceSize.x) * oPos.w`. `surfaceSize.x` is
  `surface_binding_dim.width / aa_width` (`vsh.c:1180-1186`), the guest width W.
  That makes the NDC shift 0.5/W. The viewport is 2W·sf host px wide, so in window
  space the shift is 0.5/W × W·sf = 0.5·sf host px, which is half an AA px at every
  sf. That is the same window-space shift the viewport form gave. So at sf = 1
  rasterisation, `gl_FragCoord` and the interpolants match the arm that passed, up
  to float rounding of the shift. The one difference, the clip edge, was a no-op at
  sf = 1 (pass 1's table).
- **The paths that rebuild vertices from screen space.**
  - The wide lines are rebuilt from the unshifted `v_vtxPos`. `line_clip` and
    `line_clip_lerp` (`geom.c:636, 685`) add the same 0.25 guest px via
    `aaScreen()` before `lineNdcScale` (2/W, `draw.c:2760`), so the NDC shift is
    0.5/W again. The cap clip (`geom.c:1232-1247`) runs in unshifted screen space,
    and the whole polygon is then translated uniformly. That is equivalent to
    clipping against planes shifted the same way, so the clip and the translation
    agree.
  - `widen_lines` is gated on `opts.vulkan` (`geom.c:408`), so GL never gets
    `aaScreen`. That matches `vsh.c`, where the GL branch does not shift either.
  - The external-wedge path (`emit_wedge`, `geom.c:253-331`) works from
    `gl_in[i].gl_Position`, which is already shifted. It clips to the NDC square,
    which is the viewport-at-0 clip volume. No separate shift is needed there.
  - Every other geometry path emits `gl_in[i].gl_Position` directly. Points have
    no geometry stage.
- **Shader key and staleness.** `aa_offset_x` sits in `VshState`'s common region,
  before `fixed_function`, so it is inside the hash's `common_size`
  (`shaders.c:26`). It also sits in `GeomState`, which is hashed whole
  (`shaders.c:39`). `ShaderState` is memset before it is filled (`shaders.c:79`),
  so padding cannot split keys. The dirty check compares the offset
  (`shaders.c:128`). `SET_SURFACE_FORMAT` bumps `shader_state_gen` on an AA-mode
  change (`pgraph.c:2517`). `SHADER_STATE_LAYOUT_VERSION` goes from 2 to 3, so a
  persisted key stored without the field is wiped, not misread. A CC2 draw cannot
  reuse a non-CC2 shader, and a non-CC2 draw cannot reuse a CC2 one.
- **Non-CC2 output.** The `vsh.c` text is unchanged at offset 0. Wide-line
  geometry shaders now always carry `#define aaScreen(s) (s)`, which is the
  identity, so their output does not change. The layout-version bump already
  invalidates their cached keys.

**No sf = 2 capture exists.** `ab_compare.py` has no render-scale setting. The PR
body names this gap, and pass 1 allowed the arithmetic above instead.

## LOW-1: stale line numbers in NOTES section 2

Fixed at the remediation head. The master merge has since moved some of them again.
The glsl rows, `pgraph.h:619` and the viewport lines `vk/draw.c:4496, 5621` are all
correct on this head. The scissor lines (`4518, 5634`, now `4512, 5630`) and the
clears (`7176, 7262`, now `7225, 7319`) are a few lines off. This is a residual LOW:
those rows say "no change", so a reader who lands a few lines off loses nothing.

## LOW-2: no row for view-volume clipping

Fixed. NOTES section 2 has a "view-volume clipping" row. It explains why the
viewport stays at `.x = 0`, and it says a future SQUARE_OFFSET_4 offset must also go
in clip space.

## Still open, not a finding

- The `[job.arms]` verdict on `aasample-cc2-clip.json` (a_ref `db73a7fb99`,
  b_ref `2f98d87e20`) is pending. `git diff 2f98d87e20 HEAD -- hw/` is 4 files and
  34 lines, all added, and none of them touches the AA offset. So the arm measures
  this head's AA code. The `verified` label on the PR belongs to the viewport
  arm, as the remediation comment says. A `regressed` verdict still stops the fold
  (fold.sh), so folding now does not skip the check.

## Outcome

`needs-audit-2` → `fold-ready`.
