# lane g8b8285: #285, `Surface_format::Fmt_G8B8` (32,552 px)

**Classification: a live defect, not a stale capture or a golden problem.**
B8 and G8B8 surfaces store the combiner's **r** in their B byte, where silicon
stores its **b**. G is right. The cause is the host format: `R8_UNORM` /
`R8G8_UNORM` put fragment `.r` in byte 0, and byte 0 is the guest's B. Both
rows in `vk/constants.h` are marked `// FIXME: Map channel color` (lines 660
and 668). GL has the same fault (`GL_R8`/`GL_RG8`, `gl/constants.h:409-412`).
The fix is one uniform-gated swizzle at the end of the generated pixel shader
(`g8b8-bswap.diff`). Priced offline: Fmt_G8B8 goes 32,552 -> ~0.

## 1. Dating (step 1 of the brief)

- Golden `~/goldens/results/Surface_format/Fmt_G8B8.png`: commit `6e159f1`,
  2026-08-11 (nxdk_pgraph_tests#307 results). It is older than every capture,
  so the golden cannot be newer than the run.
- Captures: 49 scored rows on disk, 2026-09-13 to 2026-09-25, from thor (28),
  nova (17) and unlabelled (4), across apk shas from `fb4dfafc6d38` to
  `a7b9d28e6b84`. **Every one is 32,552 differing, max_rgb 255, status ok.**
  The value is constant across builds and devices, so no fix in range
  (#271/PR #306, #184) touched it. It is not stale.
- The issue's 31,820 is the structural figure (32,552 minus 732 off-by-one).

## 2. The diff by region and channel (step 2)

Run on `1790347539-xbox-region200-dryrun` (thor, `a7b9d28e6b84`), the issue's
capture F:

| channel | px differing |
|---|---:|
| R | 32,552 |
| G | 0 |
| B | 32,552 |
| A | 0 |

The difference is confined to the four quad images in each half:
x 92-547, y 48-351. It is all in R and B, which is where the test puts
the surface's B bytes.

**How the test reads the surface.** `SurfaceFormatTests` renders tex3 into a
G8B8 surface (pitch 1280, blending off), then samples that memory as a
640x480 A8R8G8B8 texture. Each texel packs two surface pixels:
`texel (B, G, R, A) = (B[2x], G[2x], B[2x+1], G[2x+1])`. That is the source
of the test's "R equals B, A equals G". So texel R and B are both the
surface's stored B, and texel G and A are both its stored G. Ours gets G
exactly right and B wrong everywhere.

**What the golden does with B.** tex3 is `GenerateRGBRadialATestPattern`:
four 64x64 copies of `(R, G, B) = (255 - yn, xn, yn)`. The model is scored
on the bottom (opaque) half, which shows the stored bytes directly, with
label columns excluded (`derive_g8b8.py`):

| rule for the stored B byte | vs our capture | vs golden |
|---|---:|---:|
| B <- src.r (what our R8G8 target stores) | **15** | 16,399 |
| B <- src.b (silicon) | -- | **15** |

The same 15 pixels miss under both rules, so they are a model edge, not
signal. Each rule is exact against its own image. Because src.r = 255 - src.b
here, the defect reads as a vertically flipped B ramp. That is why it looks
like a geometry fault at a glance.

**Fmt_B8 is the same defect.** Its status is `label-differs`, so it is void
as a scored leg. The same model gives B <- src.r: 15 vs our capture, and
B <- src.b: 15 vs the golden (6,927 for the wrong rule). The fix moves it
too.

## 3. The rule and where it lives (step 3)

Silicon: a B8 surface stores the combiner's b. A G8B8 surface stores b in
byte 0 and g in byte 1. The host formats put fragment r in byte 0. No
attachment swizzle exists in VK or GL, so the output has to be routed in the
shader.

| file | holder | hunk |
|---|---|---|
| `glsl/psh.h` | lane.texvol283 (claimed 2026-09-25T21:02Z) | `DECL(S, surfaceBSwap, int, 1)` in `PSH_UNIFORM_DECL_X` |
| `glsl/psh.c` | lane.wbufdepth24 (#268); also named by other open PRs | `psh_convert()`: after the #59 pad block, emitted unconditionally: `if (surfaceBSwap != 0) fragColor.rb = fragColor.br;`. In `pgraph_glsl_set_psh_uniform_values()`, beside `padAlphaMode`: stage `surface_shape.color_format` is B8 or G8B8 |

A uniform and not `PshState`, for #59's stated reason: nothing invalidates a
shader on a surface-format change. It sits last so the alpha test, the #43
signed fold and the #59 index-1 copy all see the unswizzled colour. Blending
is off on these formats on silicon (the test says enabling it raises a
hardware exception), so the index-1 source is never consumed here. The hunk
is in both backends because `psh.c` is shared, and it fixes GL the same way.

Checked: `-fsyntax-only` against the desktop build's own compile line with
the patched `psh.h`/`psh.c` returns 0. `PshUniform_surfaceBSwap` exists only
in the patched header, so the check did use it. **Not built or run on a
device.**

Readers of the host image after the change: the download path copies host
bytes to guest memory unchanged, so byte 0 now holds b as silicon's does. A
G8B8 surface later sampled as a G8B8 texture then agrees with its own guest
bytes, which it did not before. Not covered: B8/G8B8 clears (`pgraph.c:5018`,
fallback magenta, which is r = b and so unaffected).

## 4. The arm, ready to register (not registered)

**Not registered.** Its b_ref needs `psh.c` and `psh.h`, and this lane may
commit neither. A board request asks for the two files, or for the hunk to go
to their holders. Whoever lands it applies `g8b8-bswap.diff`, merges master,
and registers after the last rebase:

- **must_move**: `Surface_format/Fmt_G8B8` 32,552 -> <= 100. The bottom half
  goes to 0 by the model. The top half is the same texels blended over the
  checkerboard with alpha = stored G, which already matches, so R/B should
  follow. The ceiling is loose because the top half is modelled by argument,
  not by pixels.
- **moves, not scorable**: `Surface_format/Fmt_B8` (label-differs, void). The
  model says its quad pixels go to 0. Read its capture by eye.
- **must_not_move**, each with what would move it:
  - `Surface_format/Fmt_{A8R8G8B8, R5G6B5, X8R8G8B8_{Z,O}, X1R5G5B5_{Z,O},
    X1A7R8G8B8_{Z,O}}`, `Clear/*`, `Blend_surface/*`: the gate is a
    two-value compare on the live `surface_shape.color_format`. They move
    only if the uniform reaches a non-B8/G8B8 draw. The suite's tests run in
    `std::map` name order (A8R8G8B8, B8, G8B8, R5G6B5, X1A7..., X1R5...,
    X8...), so a stale uniform would hit **`Fmt_R5G6B5`** first. It is exact
    (0) today, and it is the discriminating must_not_move leg.
  - `Surface_clip/*_G8B8`, `*_B8` (18 rows, all 0 today): **an inert
    control, not a measurement.** They draw into G8B8/B8, but only in
    (0.1, 0.6, 0.1) and (0, 1, 0), where r = b, so the swap cannot change
    them. The only r != b quad is the red one outside the clip rect. They
    move only if clipping leaks, not through this hunk.
  - Check `status` for `unreadable` on every leg, and the run's coverage line.

Only Surface_format and Surface_clip set SCF_B8/SCF_G8B8 anywhere in
`nxdk_pgraph_tests/src`, so no other capture can reach the gate.

## What the next lane should not repeat

- Do not read this as a pitch or geometry bug because the quads look
  flipped. It is one byte's source channel: src.r = 255 - src.b makes a
  wrong channel look like a vertical flip.
- Do not reach for `vk/constants.h`'s format row. No host format stores
  G8B8's byte order with a writable R8G8 layout, and VK has no attachment
  swizzle. The shader is the place.
- Do not key it on `PshState`: it would be served stale across a surface
  format change (the #59/#43 lesson, written at `psh.c:3569-3574`).
