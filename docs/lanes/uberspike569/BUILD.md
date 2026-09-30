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

## 9. Attempt 7 (2026-09-29 17:39 PDT): six of the seven re-queued requests were lost too

**Why attempt 6 did not finish.** It ended as a wait, correctly, on the seven requests of section
8. The same wipe took a second pass seconds after they were queued. hostops (addendum 17:38 PDT)
read `dispatch/logs/dispatcher.log`: the root cause was `selftest.d/50-arms-requeue.sh` and
`51-dispatch-hardening.sh` on PR #622's branch. Both ran `rm -rf` on the live `DISPATCH_DIR`,
which a lane session inherits. PR #624 (lane.dispatchguard) fixes it. `find_results.py` at 17:39
agrees:

| arm | id | state |
|---|---|---|
| E A | `1790724542-uberspike569-1360739` | **result dir exists** (ran 16:49); keep it, do not re-run |
| E H | `1790724547-uberspike569-1361951` | gone, never logged |
| DOA A | `1790724512-uberspike569-1350514` | gone (battery skip on the Nova, never run) |
| DOA B / H | `...-1353595` / `...-1354320` | gone (admitted on the Thor, never claimed) |
| Kabuki A / B2 | `...-1355381` / `...-1355882` | gone (admitted on the Thor, never claimed) |

**Not re-queued yet, by hostops' instruction:** re-queue after #624 folds and a device is free.
At 17:39, #624 is green, `fold-ready` and mergeable, and both devices are held for an
owner-authorized top-up, so a request queued now could not run before the fold anyway. This
attempt ends as a wait on #624's fold.

**On resume (after #624 is on master):** merge origin/master (it brings no emulator code, so the
refs and predictions stand; do not re-register), then re-queue the six with the same refs, flags
and predictions as section 8: E H (6bec23c3f4, the 36 suites, 2 runs), DOA A/B/H, Kabuki A/B2.
Pin the DOA and Kabuki soaks to the Nova (the Thor's thermal pause voids a soak). If any is lost a
third time after #624, that is a different bug: post the dispatcher.log evidence on #618. Then
the judging of section 8's last paragraph.

## 10. Attempt 8 (2026-09-29 18:10 PDT): the six queued a third time, after #624

**Why attempt 7 did not finish.** It ended as a wait on PR #624 (lane.dispatchguard), which is what
hostops asked for. #624 folded at 17:40 PDT (`dfa30e5780` on master).

**Merged origin/master.** It adds no emulator code (docs, jobs, routes), so the refs and the three
predictions stand unchanged (`host/predinfo.py`: doa-soak `642189382de2`, kabuki-soak
`dad936499521`, pixels `c5c0e63aed4e`). None was re-registered.

**Queued** with `host/requeue3.sh`, which uses section 8's refs and flags, output in `host/requeue3.log` (gitignored, local to the worktree).
The DOA and Kabuki soaks now carry
`--device nova --hard-pin`. In section 8 they carried a soft pin, and four were admitted on the
Thor, whose thermal pause voids a soak. The pilot gate admitted the batch on
`pilots/uberspike569.ok`.

| arm | ref | id |
|---|---|---|
| E A (kept, ran 16:49) | 23543417aa | `1790724542-uberspike569-1360739` |
| E H | 6bec23c3f4 | `1790730667-uberspike569-2559646` |
| DOA A | 23543417aa | `1790730667-uberspike569-2559714` |
| DOA B | 752b4f0f7b | `1790730668-uberspike569-2559794` |
| DOA H | 6bec23c3f4 | `1790730669-uberspike569-2559870` |
| Kabuki A | 8b15159b2f | `1790730670-uberspike569-2559946` |
| Kabuki B2 | d0152f9c44 | `1790730670-uberspike569-2560023` |

At 18:12 PDT all six sat in `queue/`. Both devices are held for the owner's top-up, and lane.local
releases the holds, so this attempt ends as a wait. If any of the six is lost after #624, post the
dispatcher.log evidence on #618.

**On resume:** `host/find_results.py` on the seven ids. Then `uberjudge.py --a --b --h` on the
three DOA arms, `kabjudge.py --a --b` on the two Kabuki arms, and
`ab_compare.py --a <E A> --b <E H> --expect docs/testing/predictions/uberspike569-gpl-pixels.json`
read per capture. Check E H's logcat for `[uber569] mode=4 links=N`, N > 0. Then the verdict, the
#569 post, and ready.

## 11. Attempt 9 (2026-09-29 22:11 PDT): still queued; offline protocol

**Why attempt 8 did not finish.** It ended as a wait on the six requests of section 10, and none
has run yet. `host/find_results.py` at 22:11 PDT: E A's result dir exists; E H, DOA A/B/H and
Kabuki A/B2 are all in `queue/`, so nothing was lost this time. The holds:
- the Nova is on `lanelocal-topup` (the owner charges it off the harness; lane.local releases it
  back at 60% or more). The soaks are hard-pinned there.
- the Thor is on `lanelocal-fanwait` (its fan is dead; no queued runs until the repair).

**Merged origin/master** at a3681ccb0b (routes, targets and titles docs; no emulator code), so the
refs and the three predictions stand as registered.

**GitHub is suspended (addendum 22:05 PDT).** PR #618 is now `PR.md` beside this file, at
`State: draft`. The #569 post goes to `OUTBOX.md`. Neither the arms job nor handback can comment
on #618, so E is judged by this lane as section 8 says.

**Before `State: ready`:** `offline_fold.py` requires a finished, non-void dispatch run built
from the branch's head commit. The judged arms are built from the variant refs, not the head.
So once the verdict is written and committed, queue one DOA smoke at the head (default 0, the
code that folds) and wait for it to finish. Then set `State: ready`.

**On resume:** the judging of section 10's last paragraph, then the verdict in this file and in
NOTES.md, the OUTBOX post, the head smoke, and ready.

## 12. Attempt 10 (2026-09-30 08:31 PDT): all seven arms read; the verdict

**Why attempt 9 did not finish.** It ended as a wait, correctly, on the six queued requests. The
Nova came off its top-up hold overnight and ran all six between 07:24 and about 08:20 PDT on
2026-09-30, each starting at 86-92% battery with a cleared shader cache. None was lost. The result
dirs carry a `1-` prefix, which `host/find_results.py`'s glob missed. `host/list_results.py`
lists them.

**Merged origin/master** at f7ceaebce9 (the hddcrash and cithrottle folds: dispatcher, selftest,
CI and docs; no emulator code), so the refs and predictions stand as registered.

### 12.1 E, pixel-inert with the uber stage held: PASS

`ab_compare.py` output: `results/ab-e.txt`.

| arm | ref | device | result |
|---|---|---|---|
| A (GPL 0) | 23543417aa | Thor | `1790724542-uberspike569-1360739` |
| H (GPL 4, held) | 6bec23c3f4 | Nova | `1-1790730667-uberspike569-2559646` |

- **Verdict:** PASS. All 1317 registered checks hold across the 36 suites:
  - 1313 captures are the same;
  - 4 are noise inside the measured band (`Vertex_shader_rounding_tests/GeometrySuperscreen_{0.0010,0.4999,0.5000,0.5626}` flicker across exact in both arms);
  - none is better or worse, and exact goes 513 -> 515, all flicker;
  - the byte-level check finds every one of the 1317 shared captures byte-identical between the arms.
- **The arm tested the uber stage.** H's logcat reads `[uber569] mode=4 links=2103 ... uncovered=0`
  in both runs, so the uber vertex stage drew every covered bind and declined none.
- **The pair is split across devices** (the dispatcher found no poolable lane to pin E). A leg that
  holds across a device split is strictly stronger than a same-device pair, so the split does
  not weaken this PASS.
- **Not covered:** `NoContraction` is not in the build. On lavapipe, 33 of 150 random vertex
  programs differ by a signed zero or 1-2 ulp (4.1). No capture in these suites shows that
  difference, but a title's program could. At a swap, such a pixel would pop by at most that much.

### 12.2 N1-N3 and G, cold DOA survey soaks on the Nova

`uberjudge.py` output: `results/uberjudge-doa.json`. All three arms cleared and reached
`mark play`.

| | A (GPL 0) | B (GPL 3, ladder) | H (GPL 4, held) |
|---|---|---|---|
| result | `1-1790730667-uberspike569-2559714` | `1-1790730668-uberspike569-2559794` | `1-1790730669-uberspike569-2559870` |
| draw-path create over the run (`pc_ms`) | 26 239 ms | 2 693 ms | 4 573 ms |
| first load after `mark play` (`dpc_ms`) | 2 880 ms | 52 ms | 47 ms |
| stall windows (`dpc_ms` >= 100 ms), summed | 25, 26 239 ms | 5, 2 303 ms | 3, 4 369 ms |
| play span: median GPU Tot ms / gfps | 18.8 / 45 | 22.5 / 35.5 | 70.9 / 13 |
| `[uber569]` (last line) | | links 641, cold 14, next >= 216/0/167 | links 129, cold 0 |

| leg | registered | measured | verdict |
|---|---|---|---|
| N1 | B/A pc_ms <= 0.25 | 0.103 | **PASS** |
| N2 | B/A first-load dpc_ms <= 0.20 | 0.018 | **PASS** |
| N3 | B stall windows <= cold + 2 = 16 | 5 | **PASS** |
| G | H/A GPU ms <= 1.50 and gfps >= 0.80 | 3.77 and 0.29 | **FAIL** |

- **The ladder takes the compile off the draw path.** The draw path waits 26.2 s on creates
  without it and 2.7 s with it, and the first fight load drops from 2.9 s to 52 ms.
- **The five stall windows left are cold misses, by design.** A cold miss is the first sight of a
  (family, GS, raster, formats) combination whose uber pre-raster library does not exist yet.
  It builds the monolithic pipeline inline (section 1) and queues that library.
- **G fails: the uber stage costs 3.8x the GPU time per frame while it stands in.** Held on every
  covered draw, DOA's fight runs 13 gfps against 45. **Confound:** H's pipelines are also
  fast-linked without link-time optimisation. gpl569's leg for that cost alone (D1) was voided
  by the Thor's thermal pause, so 3.8x is the uber stage **plus** the unoptimised link. It is an
  upper bound on the vertex interpreter's own cost, not a measurement of it.
- **In the ladder, the cost lasts until the swaps land** (`host/doa_series.py`, 30 s bins from
  `mark play`, `results/doa-series.txt`):

  | t+ s | A gfps / GPU ms | B gfps / GPU ms | B links, built/swapped |
  |---|---|---|---|
  | 0 | 42 / 20.7 | 43 / 21.1 | 71, 70/64 |
  | 30 | 59 / 13.4 | 59 / 14.4 | 71, 70/64 |
  | 60 | 59 / 12.7 | 59 / 10.5 | 129, 105/87 |
  | 90 | 37 / 23.7 | 32.5 / 25.8 | 129, 105/87 |
  | 120 | 39 / 23.2 | 30 / 28.0 | 157, 156/128 |
  | 150 | 59 / 11.2 | 28.5 / 25.1 | 641, 216/167 |
  | 180 | 43 / 20.3 | 39 / 17.1 | 641, 216/167 |
  | 210 | 44 / 18.9 | 59 / 14.2 | 641, 216/167 |

  - B tracks A while the scene's specialised pipelines are in place (0-60 s), and again from 180 s.
  - B runs 12-50% below A in the 90-150 s bins, where it links new uber pipelines (129 -> 641).
  - The route is timed and not aligned between arms: A spent 26 s more stalled than B, so the
    same bin is not the same content. Read this table for duration, not for per-bin ratios.
  - Over the whole play span, B's median is 0.79x A's gfps. That is the ladder's price on a cold
    cache: a dip for as long as the worker takes to catch up, where A instead freezes.

### 12.3 K0-K3, Kabuki's cold-cache fight on the Nova

`kabjudge.py` output: `results/kabjudge-k.json`.

| | A (GPL 0) | B2 (GPL 3, ladder) |
|---|---|---|
| result | `1-1790730670-uberspike569-2559946` | `1-1790730670-uberspike569-2560023` |
| draw-path create after `mark gameplay` | 133 418 ms, 780 misses | 27 ms, 425 misses |
| stall windows | 35 | 0 |
| longest gap between guest flips | 4 990 ms | 697 ms |
| `[uber569]` (last line) | | links 706, cold 79, next >= 706/0/512, uncovered 0 |

| leg | registered | measured | verdict |
|---|---|---|---|
| K0 | validity (cleared, both marked, A >= 100 misses, B links > 0) | yes | **PASS** |
| K1 | B's longest gap < 5000 ms | 697 ms | **PASS** (not discriminating: A is 4990) |
| K2 | B/A fight create ms <= 0.25 | 0.0002 | **PASS** |
| K3 | B/A longest flip gap <= 0.50 | 0.14 | **PASS** |

- **Kabuki's compile stall is gone in the fight.** Draw-path create falls from 133 s to 27 ms,
  there are no stall windows, and the longest gap between two guest flips falls from 5.0 s to
  0.7 s.
- **Kabuki's 79 cold misses all fall before `mark gameplay`** (in the menus and the load), so
  none of them stalled the fight.

### 12.4 Verdict

**The uber pre-raster libraries under GPL (the ladder, mode 3) give a first draw with no stall
for every miss whose combination has an uber library.** That covers all of Kabuki's fight and all
but DOA's 14 cold combinations. Both acceptance titles pass every discriminating stall leg,
with margins from 2.4x (N1) to about 1250x (K2) inside the registered bound, and the swap path is pixel-exact on all 1317 captures. **The cost is GPU time
while the uber stage stands in:** up to 3.8x per frame held (G fails its registered 1.5x), and
0.79x median fps over a cold DOA play span, recovering as the swaps land.

**Default stays 0 in this PR, as briefed.** Turning the ladder on for players is a separate change
with its own arms.

**Next, ranked by expected impact (probability x size of the win):**
1. **Separate the unoptimised-link cost from the uber stage's cost.** Queue one arm: GPL mode 1,
   specialised libraries fast-linked and not swapped, forced on the same DOA route on the Nova,
   against A. It decides whether the stand-in's price is the interpreter, to be optimised, or the
   missing link-time optimisation, to be fixed by LTO-linking the uber pipeline on the worker as
   rung 1. Probability of a useful answer: high (one arm, same instrument). Win: it chooses which
   of the two big fixes to build.
2. **Persist the uber combinations and prebuild them at boot** (section 5, not built by decision).
   That removes the cold misses: DOA's 5 remaining stall windows (2.3 s), and Kabuki's 79 creates
   in its load. Probability: high, since the mechanism is the inline create already measured. Win:
   the last draw-path creates. It needs a measure of cold that survives a persisted list, because
   a cleared cache would no longer be cold.
3. **`NoContraction` on both paths**, with its own pixel arm, before any default flip. The suites
   show no pop. Lavapipe shows 1-2 ulp on 22% of random programs.
4. **Then the default flip for mode 3**, on the owner's decision. The trade is a transient fps dip
   against the 26-133 s freezes it replaces.

### 12.5 Local checks, the head smoke, and the wait

- **Local checks, at this head:**
  - NDK type-check of the eight changed C files: rc 0, and every warning is in a line older than
    this branch;
  - both judges' `--selftest`: ok;
  - `preflight.sh --allow-tracker`: passed. Its coverage gate could not run, because it needs `gh`.
- **Merged origin/master** twice, at 146b8887db and 2c59b7bbba. Neither merge brings emulator code.
- **The head smoke.** `offline_fold.py` needs a finished, non-void run whose ref is the branch
  head. So the smoke is queued **after** the last commit: DOA, 150 s, Nova, GPL at its default of
  0, `--no-expect`, with purpose `#569 head smoke at <head>`. A smoke queued at 489a11bff2 was
  withdrawn when this note moved the head.
- **The wait.** At 08:46 PDT the Nova is the only device that takes runs (the Thor is on
  `lanelocal-fanwait`). Thirteen study-tier requests are ahead of the smoke, several of them
  1200-1550 s soaks, so it is hours out. `PR.md` says `State: ready`, and `offline_fold.py`
  refuses the fold until the smoke's result exists. **Do not commit to this branch until the
  fold:** a new head orphans the smoke.
