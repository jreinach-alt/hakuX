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

One reduced by reading (pair 51, `rand5prog`): the signed zero is `DST(_opos_tmp, xyw, v2.yyz,
R8.ywxz)`, whose y is `v2.y * R8.w`. No slot before it writes R8.w, so the specialised compiler
knows it is the constant 0 and folds `x * 0.0` to `+0.0`. The interpreter multiplies at run time
and gets `-0.0` for a negative `v2.y`. Only a program that reads a register it never wrote, or a
constant the compiler can see, hits this. `precise` on both paths stops NIR from folding it.

## 5. State (2026-09-29, attempt 3)

- Built and pushed at 3f61a459c3 (CI pending). The NDK type-check is clean.
- **Device smoke, queued on the Nova at plain priority** (no prediction: a crash check and the
  counters, before any leg is registered):
  - `1790706856-uberspike569-1023537`: DOA, 150 s, `HAKUX_GPL=4`;
  - `1790706856-uberspike569-1023583`: DOA, 150 s, `HAKUX_GPL=3`.
- **After the smoke, register and queue the legs** (judge `uberjudge.py`, `--selftest` passes):
  - E: the pixel arm. A is the build at default 0; B is the test variant, one commit setting
    `HAKUX_GPL_DEFAULT 4` (instance.c). That variant has all three mechanisms: its own sha and
    APK; a `#define` the commit changes; and a runtime reader, the `[gpl569] ... mode=4` and
    `[uber569] mode=4 links=N` lines. The suites are gpl569's 27 plus the vertex-stage ones
    (Lighting, Specular, Fog, Texgen, Texture Matrix, Point, Vertex shader, Weight setter, W
    param, Material).
  - N1-N3 and G: cold DOA soaks on the Nova. A is `HAKUX_GPL=0`, B is `=3`, H is `=4`.
    Registered factors: B's draw-path create ms <= 0.25 x A's over the run and <= 0.20 x A's over
    the first load after `mark play`. B's stall windows (dpc_ms >= 100 in a window) <= its cold
    misses + 2. H's GPU ms <= 1.50 x A's and gfps >= 0.80 x A's.
- **Not built, by decision:** the persisted list of uber combinations and a boot prebuild. A
  cold soak clears caches, so a persisted list would make "cold" warm. A canonical set needs
  the GS states, which only a run shows. The smoke's `cold=` count prices it.

## 6. Attempt 4 (2026-09-29): the smoke read, the legs registered

**Why attempt 3 stopped.** It finished as a wait: it posted `[lane.uberspike569] waiting:` on the
two smoke soaks and stopped, and handback resumed it once both result dirs existed.

**The smoke** (`host/smoke_read.py`, Nova, DOA 150 s, ref 3f61a459c3, apk 177eb15f0904):

| run | mode | crash / VK_ERROR | family module | last counters |
|---|---|---|---|---|
| `1790706856-uberspike569-1023537` | 4 (held), cache cleared | none / 0 | 44646 B GLSL, 19.4 ms | gpl links=12, uber libs=2, lib_ms=2122.9 (on the draw thread, as mode 4 does by design) |
| `1790706856-uberspike569-1023583` | 3 (ladder), cache kept | none / 0 | 44646 B GLSL, 4.8 ms | links=11, cold=2, libs=2, next=11/0/4, next_ms=1219, uncovered=0 |

Both ran to the end with no crash and no Vulkan error. The ladder linked 11 misses, built all 11
specialised pipelines behind them with no failure, and swapped 4 in. A swap happens at the next bind,
so the other 7 are read as not bound again before the run ended (not checked per pipeline). `uncovered=0`: the uber stage covered every vertex state DOA reached.
The smoke was not on the survey route and did not reach `mark play`, so it prices nothing.

**Merged origin/master** at 23543417aa (the index regenerated with the fold pins, 104 suites,
`check` clean).

**The refs:**

| ref | what |
|---|---|
| `23543417aa` | A: the build, `HAKUX_GPL_DEFAULT 0` |
| `752b4f0f7b` | B: one line, `HAKUX_GPL_DEFAULT 3` (the ladder) |
| `6bec23c3f4` | H: one line on B, `HAKUX_GPL_DEFAULT 4` (held) |
| `b93d585979` | the revert: default 0 again (the branch head's code) |

The variants have their three mechanisms: their own sha and apk; the `#define` the commits change;
and a runtime reader, the `[gpl569] ... mode=` and `[uber569] mode=` lines.

**Registered:**
- `uberspike569-gpl-pixels.json`, leg E: A 23543417aa against H 6bec23c3f4, runs_per_arm 2, 36
  suites must not move (the vertex-stage suites, plus 3D_primitive, Clear, Depth_buffer,
  Texture_format, Window_clip, Shade_model, Front_face, Viewport). The arms job queues it.
- `uberspike569-gpl-doa-soak.json`, legs N1-N3 and G: A, B and H, cold DOA survey soaks of 440 s on
  the Nova, judged by `uberjudge.py`. Queued by hand (the arms job leaves soaks to their lane).
  The three are separate perflog apks, so each starts cleared.

**Queued (attempt 4), the soak arms on the Nova, in order:**
- A `1790714390-uberspike569-2903782` (23543417aa, default 0)
- B `1790714395-uberspike569-2904221` (752b4f0f7b, default 3)
- H `1790714395-uberspike569-2904335` (6bec23c3f4, default 4)

The arms job queues the E pixel arm from `uberspike569-gpl-pixels.json`, and posts its verdict as a
`[job.arms]` comment on PR #618. Preflight passes on the branch (`--allow-tracker`).

**Attempt 4 ended as a wait** on those four results. On resume:
- run `uberjudge.py --a --b --h` on the three dirs;
- read E per capture;
- read E's B logcat for `[uber569] mode=4 links=N` with N > 0; without it, E is void;
- then the verdict, the #569 post, and mark the PR ready.

## 7. Attempt 5 (2026-09-29 16:10 PDT): the Kabuki leg

**Why attempt 4 did not finish.** It ended as a wait, correctly: the three DOA soak arms and
the E pixel arm were queued behind the Nova's release-tier queue. At 16:10 PDT none had run
(all five requests still in `queue/`, about 23 release-tier requests ahead of them). The
resume came from the 16:10 addendum (Kabuki as an acceptance title), not from a result.

**Merged origin/master** at 8b15159b2f. It brings no emulator code (docs and jobs only).

**What K1 on master already shows** (lane.kabukistall's cold Kabuki run
`1-1790702688-lane.kabukistall-194847`, read with `kabjudge.py` as both arms,
`results/kabjudge-k1-self.json`; the window table in `host/k1_windows.txt`):
- 718 pipeline misses after `mark gameplay`, 126.4 s of draw-path create, 22 stall windows;
- **the longest gap between two guest flips is 4.4 s.** The 68.6 s window flips about once a
  second (60 frames), each gap about 20 creates of ~200 ms.

So the addendum's criterion, "no flipless gap over 5 s", already passes on master since B1
(#580) halved the create. It cannot show the ladder did anything. It is registered as K1 with
that said, and the claim rests on K2 and K3.

**Registered** `uberspike569-gpl-kabuki-soak.json` (judge `kabjudge.py`, `--selftest` covers both
sides of each leg and a pre-mark stall that must not count):

| leg | reads | registered |
|---|---|---|
| K0 | validity | A and B cleared, both reach `mark gameplay`, A >= 100 misses after it, B `[uber569] mode=3 links>0` |
| K1 | B's largest G max after the mark | < 5000 ms (the addendum's wording; not discriminating) |
| K2 | B's fight create ms / A's | <= 0.25 |
| K3 | B's longest flip gap / A's | <= 0.50 |

| ref | what |
|---|---|
| `8b15159b2f` | A: the merge, `HAKUX_GPL_DEFAULT 0` |
| `d0152f9c44` | B2: one line, `HAKUX_GPL_DEFAULT 3` |
| `0818a5f9f4` | the revert: default 0 again |

**Queued on the Nova** (kabuki-warriors route, 600 s, perflog), behind the DOA arms:
- A `1790723587-uberspike569-1071671`
- B2 `1790723590-uberspike569-1073743`

The pilot file got this build's verdict appended (the two smokes of section 6, read clean).

**On resume:** `find_results.py` on the seven ids; `uberjudge.py` on the DOA three; `kabjudge.py`
on the Kabuki two; E per capture from the `[job.arms]` comment; then the verdict, the #569
post, and ready.

## 8. Attempt 6 (2026-09-29 16:25 PDT): every queued request was lost; re-queued

**Why attempt 5 did not finish.** It ended as a wait, correctly, on the five soak arms and the E
pixel arm. None of them ran, because at 16:15 the Nova sat at 36% battery and the admission floor was
38-39%. Between 16:22:59 and 16:26 PDT, **every entry in the live `$DISPATCH_DIR/queue/*.req` and
`$DISPATCH_DIR/results/*` was removed.** This lane's seven requests went with it: the arms job's
E pair `1790716235-arms-uberspike569-{base,fix}-*` and the five soaks. So did every earlier
result dir (the smokes of section 6, and lane.kabukistall's K1). The only activity at that minute
was lane.hddsplit's dispatcher fixtures (`wt/hddsplit/.st/dh/`, 16:25:17-29). That is flagged on
PR #622 as a likely cause, not a proven one. `results/kabjudge-k1-self.json` and
`host/k1_windows.txt` hold what this lane read from K1.

**Re-queued** with the same refs, flags and predictions:

| arm | ref | new id | replaces |
|---|---|---|---|
| DOA A | 23543417aa | `1790724512-uberspike569-1350514` | `1790714390-uberspike569-2903782` |
| DOA B | 752b4f0f7b | `1790724521-uberspike569-1353595` | `1790714395-uberspike569-2904221` |
| DOA H | 6bec23c3f4 | `1790724524-uberspike569-1354320` | `1790714395-uberspike569-2904335` |
| Kabuki A | 8b15159b2f | `1790724526-uberspike569-1355381` | `1790723587-uberspike569-1071671` |
| Kabuki B2 | d0152f9c44 | `1790724528-uberspike569-1355882` | `1790723590-uberspike569-1073743` |
| E A (36 suites, 2 runs) | 23543417aa | `1790724542-uberspike569-1360739` | `1790716235-arms-uberspike569-base-3233746` |
| E H | 6bec23c3f4 | `1790724547-uberspike569-1361951` | `1790716235-arms-uberspike569-fix-3233820` |

The arms job's pair record for E (`pairs/c5c0e63aed4e...json`) still names the deleted ids, and a
pair judges only when both of its result dirs exist, so the job will never judge it. So E is
queued under this lane, and the lane judges it itself on resume:
`ab_compare.py --a <A dir> --b <H dir> --expect docs/testing/predictions/uberspike569-gpl-pixels.json`.
The prediction file is unchanged (sha256 `c5c0e63aed4e`).

**On resume:** `host/find_results.py` on the seven new ids; `uberjudge.py` on DOA A/B/H;
`kabjudge.py` on Kabuki A/B2; `ab_compare.py` on E, read per capture, and E's H logcat for
`[uber569] mode=4 links=N`, N > 0; then the verdict, the #569 post, and ready.
