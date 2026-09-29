# lane.uberspike569, the build: uber libraries under GPL (#569)

Branch `lane/uberspike569-gpl`, PR #618, stacked on PR #594 (lane/gpl569, GPL off by default)
and PR #581 (the spike, `NOTES.md` beside this file). Brief: the addendum of 2026-09-29 10:50
PDT.

## 1. What the device numbers say the build must do

From lane.gpl569's DOA soaks (Thor, cold) and this lane's spike:

| create | device cost | on the draw path today (GPL mode 1) |
|---|---|---|
| pre-raster library (VS + GS), specialised | 1607 ms | yes, per new VS |
| monolithic pipeline | 570 ms | yes, per miss (GPL off) |
| fragment library, specialised | 12.4 ms | yes |
| vertex-input / fragment-output library | 0.02 ms / 0 | yes |
| fast link | 0.06 ms | yes |

So the whole stall is the vertex side. A fragment library costs under a frame, which means the
fragment ubershader (the spike's `psh-uber.c`) is not needed to take a miss off the draw path
under GPL: a specialised fragment library can be built inline. **The value of the build is a
prebuilt uber pre-raster library.** The design:

- **Rung 0, on a miss:** fast-link
  - the uber pre-raster library for (uber VS family, the draw's GS module, rasterizer, formats),
    built earlier on the worker;
  - the specialised fragment library (get or create, ~12 ms), or the uber one if it exists;
  - the vertex-input and fragment-output libraries (get or create, ~0 ms).
- **In the background:** the specialised pipeline, monolithic, on the compile worker; swapped in
  at the next bind once it exists (the ladder of gpl569 D4, as the LTO swap does today).
- **When no uber pre-raster library exists yet** for that (family, GS, raster, formats): build the
  monolithic pipeline inline, as GPL off does (570 ms, gpl569 D7), and queue that uber library
  on the worker, so the next miss in the same combination is free. The combinations are
  persisted, so a second boot prebuilds them.

## 2. The uber vertex stage (`glsl/vsh-uber.c`)

One vertex shader per FAMILY. The family keeps only what a vertex shader must declare:
- which attributes arrive compressed (an `int` input);
- whether any attribute is a uniform (the `inlineValue` member of the UBO; it moves the
  offsets of the block, see 2.1);
- the interpolation qualifiers (`smooth_shading`, `noperspective`) and the output prefix (a GS
  follows);
- the build-time constants baked into the text (`surface_scale_factor`, `aa_offset_x`);
- whether the program writes its constant registers (a 3 KB private copy of `c`, which the
  common family should not carry).

Everything else is read from a uniform at run time: fixed function or program, the program
words (up to 136 slots), skinning, texgen, texture matrices, lighting and every light's type,
the colour-material sources, fog enable and generator, the specular flags, point parameters,
which attributes are uniforms, which are swizzled.

On DOA's 46 vertex modules (`host/vsh_fields.py` on the Nova key file): 31 fixed function and
15 programs of 2-30 slots. The fields that vary are exactly the ones above that become uniforms:
uniform-attribute masks (17 values), swizzle, fog, lighting and light types (6 sets), specular,
point parameters, texture matrices (3), texgen (4), skinning (2). So DOA has one family per GS
prefix.

### 2.1 One uniform block for both pipelines

The uber VS declares the specialised shader's `VshUniforms` block unchanged and appends its own
member (`ubVsh`, uvec4 array) at the end. The specialised block is a prefix of it, so one upload
(into the uber module's layout) serves the rung-0 pipeline and the specialised pipeline that
replaces it, whichever is bound when the draw executes.

### 2.2 Exactness

The interpreter replays the specialised generator's statement order slot by slot, including its
bug-compatible parts (an unpaired MAC's constant write is visible to its own register write,
because the specialised text re-reads the inputs). The fixed-function and lighting code uses the
same helper functions (`lt*`, `ff*`) as the specialised text, and the same expressions. Where the
specialised compiler folds a constant (a first skinning term added to zero), the uber text is
written in the folded form.

Checked on the host by rendering both shaders' outputs (all varyings, bit for bit) for DOA's 46
states and seeded random states. The device check is the pixel arm with the swap forced off
(rung 0 held for every draw).

## 3. State

(filled as the work lands)
