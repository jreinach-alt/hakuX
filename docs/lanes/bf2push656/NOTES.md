# lane.bf2push656 notes

#656 (umbrella #433): build the push-constant fix bf2ubosize433 sized
(docs/lanes/bf2ubosize433/NOTES.md section 6), for Battlefield 2's serialized
per-draw cost (docs/lanes/bf2stall433/NOTES.md sections 7-8).

Base: master 7e1b471ef1.

## 1. What the code says before writing any (reading, no device)

- **The push budget.** The Mesa tree the project builds Turnip from
  (`mesa-turnipfork`, `tu_common.h`) has `MAX_PUSH_CONSTANTS_SIZE 256`, and
  `tu_device.cc` reports it as `maxPushConstantsSize`. 256 < 16 + 256, so on
  the Nova the inline attributes are NOT push constants
  (`use_push_constants_for_uniform_attrs` false) and the only range on every
  pipeline is the geometry stage's 16 B. Free: 240 B. The build logs the
  device's own value (`[push656]`, section 2) so the run settles it.
- **Every draw binds the UBO set**, not just the ones that uploaded:
  `bind_descriptor_sets()` re-binds with the current offsets on every draw
  that leaves the fast path. So pushing changed rows alone would remove the
  uploads and leave the binds; the fix also has to skip a bind that repeats
  the last one.
- **Where the churn is** (bf2ubosize433's run, `ubosz-top`, per 60 flips):
  by uniform `v.ltctxb` ~75k chunks, `v.c` ~52k, `v.ltctxa` ~43k, `v.ltc1`
  ~36k, `v.lightInfiniteDirection` ~14k, `v.specularParams` ~8k; by register
  c105, c112-c114 (~15-17k each), c115, c97, c98, c100. The lighting context
  arrays are 26 + 52 + 20 vec4, so a fixed mapping of the hottest 15 rows
  cannot hold them: the overlay has to carry WHICH row each pushed vec4 is.
  Same-binding uploads, all windows: 55% change one 16-byte chunk, 27% 3-4.
- **Draw paths.** In that run every upload came from
  `pgraph_vk_update_descriptor_sets` (`d`), none from the draw queue (`q0`),
  and the run's logcat says draw reorder and draw merge are OFF (the Android
  defaults). GPL (#569) is off by default (`HAKUX_GPL_DEFAULT 0`).
- **Pipeline-layout compatibility** (issue #34 finding 3): set 1 stays bound
  across pipelines only if every layout's push ranges are identical. Layouts
  are built in three places: `create_pipeline()` (draw.c), the 17
  push-descriptor templates (shaders.c), and the GPL layout
  (compile_worker.c, outside these files). The pre-build records (#569)
  build and destroy their pipelines, so their layouts never meet a draw.
- **The shader key.** `GenVshGlslOptions` is in `glsl/vsh.h` (outside these
  files) and its padding is taken. The overlay is a device property, so it is
  set once as a global in vsh.c and not keyed; vk/shaders.c reads back from
  each module's reflected push block (`ovIdx`) whether the overlay is in it.
  The SPIR-V cache is keyed by the GLSL text, so A and B builds do not share
  modules.

## 2. The fix (2d0d03edb6)

**Shader (glsl/vsh.c).** With the overlay on, the vertex shader declares

    layout(push_constant) uniform VshOverlay {
        layout(offset = 16) ivec4 ovIdx[3];   // 12 keys, -1 ends the list
        vec4 ovVal[12];
    };

and every read `NAME[E]` of an overlaid array (`c`, `ltc1`, `ltctxa`,
`ltctxb`, the four light vec3 arrays, `specularParams`: every array of
16-byte stride) becomes `ov4(NAME[E], id, int(E))` (`ov3` for vec3), which
returns the pushed value whose key is `id * 256 + E`, else the UBO's. The
rewrite is a textual pass over the generated header and body, after
generation, so vsh-ff.c and vsh-prog.c are untouched; it skips comments,
matches brackets, and leaves bare names alone (the generated code shadows
`c` with locals). The one bare use of the uniform, vsh-prog.c's
`vec4 c_rw[192] = c;` for a program that writes constants, becomes
`= ovCAll()`, a copy with the overlay applied.

**CPU (vk/shaders.c, `ubo_ov`).** The last upload of the bound binding is
the BASE. On a uniform change, if the binding is the base's, its module has
the overlay, no new UBO set is due, the pixel-stage layout equals the base's,
and every 16-byte row of the vertex layout that differs from the base is an
element of an overlaid array with at most 12 such rows: the overlay becomes
exactly that set of rows (rebuilt each time, so a row changed back holds no
slot), and nothing is uploaded. Otherwise upload as before; that upload is
the new base and the overlay empties. The upload's reasons are counted:
`set` (new UBO set, no base yet, a new command buffer, merge/reorder on),
`binding`, `psh`, `row` (a changed row outside the arrays), `full`.

**Binds (vk/draw.c).** `bind_descriptor_sets()` skips `vkCmdBindDescriptorSets`
when the set and both dynamic offsets equal the last bind in this command
buffer, and pushes the overlay when it changed or was not yet pushed in this
command buffer. Forgotten (bind again) at command-buffer begin, at finish, at
render-pass begin, after a new UBO set is written, and after the draw-merge
and reorder paths' own binds. Every pipeline layout and every push-descriptor
template gets the overlay's range `{VERTEX, 16, 240}`.

**On only when** the device's `maxPushConstantsSize >= 256`, the inline
attributes are not in push constants, and GPL is off; `HAKUX_UBO_PUSH=0`
turns it off. Logs `[push656] maxPushConstantsSize=... -> uniform overlay
on|off` on hakuX-build at init, and on perflog builds `ubopush[up push (n1
n2-4 n5-8 n9-12) why set/binding/psh/row/full bind skip pc]` on hakuX-stall
every 60 flips.

**What it cannot do:** a binding switch still uploads and rebinds (36% of
uploads in bf2ubosize433's run); so does any pixel-stage uniform change.
The overlay costs the vertex shader a short uniform loop per overlaid read
(it breaks at the first empty slot, so ~2 ops when nothing is pushed).

## 3. Local checks

- NDK clang type-check (`.scratch/cc_check.py`, the main tree's Android
  `compile_commands.json` pointed at this worktree), release and
  `NV2A_PERF_LOG=1`, shaders.c, draw.c, vsh.c: rc 0; every warning printed
  is on a line that was already there.
- Host GLSL check (`.scratch/ov/build.py` + `ovtest.c`, not committed): this
  worktree's vsh.c, vsh-ff.c, vsh-prog.c and common.c built with the desktop
  flags, generating the vertex shader with and without the overlay for (a) a
  fixed-function state with four lights of three kinds, specular, two-sided,
  radial fog, skinning, a texture matrix and eye-linear/reflection texgen;
  (b) a program with `c[A0+n]`, a plain `c[n]` and a constant write (the
  `c_rw` path); (c) the same program without the write.
  `glslangValidator -V --target-env vulkan1.1`: all six compile. The
  overlay versions read every overlaid array through `ov4`/`ov3` (71 reads
  in (a)); only the block declarations still name them bare.

## 4. Prediction and runs

`docs/testing/predictions/bf2push656-bf2-soak.json`, registered before any
run (5e2d4e8f70): one Nova soak per arm, A = master 7e1b471ef1, B =
2d0d03edb6, route bf2mc, 420 s, frames every 20 s, perflog, default regimen
(bf2stall433's recipe). Judged by `docs/lanes/bf2stall433/armread.py`
(heavy-view GPU ms) and `push656_read.py` (this dir: P0 line, binds per
draw, rebind rate, upload reasons). Legs: P0 overlay on; M1 rebind <= 0.45
and binds/draw B/A <= 0.60; P1 heavy GPU B/A <= 0.85 PASS, <= 0.95 PARTIAL,
else REFUTED; R1 light views not worse than x1.15 + 1 ms.

Prior: P1 PASS ~45%, PARTIAL ~20%, REFUTED with the mechanism engaged ~35%.

Queued 16:20 PDT: A `1790983118-lane.bf2push656-3848423`, B
`1790983118-lane.bf2push656-3848741`. Not yet registered (they wait on the
pilot, so a no-win does not spend Nova time on them): the pixel sweep (two
runs, every golden capture byte-identical) and the second draw-heavy title
(GTA SA, two runs). That is the brief's 6.
