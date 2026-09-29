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

## 3. What is built

The switch is gpl569's `HAKUX_GPL`, two values up. Default 0, as on master:
- **3, the ladder.** A miss whose vertex state the uber stage covers links the uber pre-raster
  library and draws this frame. The worker then builds the specialised pipeline (monolithic), and
  `create_pipeline()` swaps it in.
- **4, held.** The same, but the uber link is kept, and a missing uber library is built on the
  draw thread. Every covered draw then runs the uber vertex stage. This is for the exactness and
  GPU-cost arms only.

| piece | where |
|---|---|
| uber vertex stage generator; coverage; family; uniform values | `glsl/vsh-uber.{c,h}` |
| exported helper text (unchanged output) | `glsl/vsh.c` `pgraph_glsl_vsh_common_header`, `glsl/vsh-ff.c` `pgraph_glsl_append_vsh_ff_header`, `glsl/vsh-prog.c` `pgraph_glsl_vsh_prog_helpers` |
| module key flag `GenVshGlslOptions.uber` (in padding; static-asserted) | `glsl/vsh.h`, `vk/shaders.c` |
| a covered binding's uber module; the upload layout (`vsh.upload_info`); `ubVsh` staging | `vk/shaders.c`, `vk/renderer.h` |
| `pgraph_vk_gpl_uber_create_pipeline`: find the uber PR library, link, queue the swap; the two worker jobs (uber library, specialised next) | `vk/compile_worker.c` |
| `gpl_get_lib` creates with the lock dropped (gpl569 D7); pinned libraries survive the table flush | `vk/compile_worker.c` |
| the swap at every place `create_pipeline()` settles (`gpl_take_next_pipeline`) | `vk/draw.c` |
| the zero vertex buffer at binding 16 for the uber link's missing attribute locations | `vk/draw.c`, `vk/renderer.h` |
| modes 3 and 4 accepted | `vk/instance.c` |

**The vertex input.** The uber stage declares all 16 attribute inputs, because which ones are
uniforms is a run-time value. Vulkan requires every input location the vertex shader consumes to
have a vertex attribute. So the uber link's vertex-input library adds, for every location the
draw sends as a uniform, an attribute at binding 16 with stride 0, reading a 64-byte zero buffer.
The stage selects the uniform value there, so what it reads is never used. The specialised
pipeline's vertex input is unchanged.

**Logs** (tag `hakuX-perf`): `vsh-uber: family module N: B bytes GLSL, T ms` once per family;
`[uber569] mode= links= cold= libs= lib_fail= lib_ms= next=done/fail/swapped next_ms=
uncovered= queued=`, running totals, on every uber library built, every cold miss, the first and
every 32nd link, and at each power-of-two count of swaps.

## 4. Host checks

- **Type-check:** every changed C file compiles with the NDK clang line (`host/typecheck.py`,
  `-Wall`): rc 0, no new warnings.
- **Exactness, lavapipe** (`host/vshuber/vshcheck.py`): see 4.1.

### 4.1 Exactness on lavapipe

Each pair is the specialised shader and the family's uber shader for one vertex state, run over
the same 64 vertices and the same uniform block, with every output dumped word by word (13 vec4
a vertex: D0 D1 B0 B1, fog/fogSpecial/triMZ/point size, T0-T3, Pos0, gl_Position, gl_PointSize).
The check can see a wrong answer: with the uber uniform mutated (a flag in fixed function, every
slot's input-A swizzle in a program), 15 of 15 pairs differ (`--mutate`).

`vshcheck.py --keys <DOA's Nova key file> --random 300`, log in
`results/vshcheck-doa-rand300.tsv`:

| states | pairs | byte-identical | differ |
|---|---|---|---|
| DOA's own (31 fixed function, 15 programs) | 46 | **46** | 0 |
| random fixed function (skinning, texgen, lights, sources, fog, points) | 150 | **150** | 0 |
| random programs (1-24 slots, pairing, A0, constant writes) | 150 | 117 | 33 |

The 33 are all random programs, and all of one kind: a signed zero (0 against -0) or 1-2 ulp,
in the position, a texture coordinate or fog. That is section 4.1 of NOTES.md again, for vertex
programs: the specialised compiler sees constant registers and operand equalities the
interpreter cannot see, and folds or reassociates on them. DOA's 15 programs are not affected.
On the device, the spike's combiner check was exact where lavapipe was not (NOTES 6.1). So the
device pixel arm decides this. `NoContraction` on both paths is still the way to guarantee it.
