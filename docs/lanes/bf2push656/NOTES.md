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
`1790983118-lane.bf2push656-3848741`. Held back until the pilot showed a
win, so that a no-win would not spend Nova time on them: the pixel sweep
(two runs, every golden capture byte-identical) and the second draw-heavy
title (GTA SA, two runs). Together that is the brief's 6.

## 5. The pilot pair: halving the UBO binds moved no GPU time (16:35 PDT)

A `1790983118-lane.bf2push656-3848423` (master 7e1b471ef1), B
`1790983118-lane.bf2push656-3848741` (2d0d03edb6). Both reached
`mark gameplay` (A 16:25:20, B 16:32:59). Neither crashed; B's logcat has no
VK_ERROR and no fatal signal.

`armread.py --a A --b B`:

| | A master | B overlay |
|---|---|---|
| rows / heavy rows (BE >= 1800) | 32 / 15 | 31 / 13 |
| heavy-view GPU ms, median | 38.3 | 42.3 |
| GPU ms, BE 1800-2400 (n) | 37.6 (9) | 40.2 (7) |
| GPU ms, BE >= 2400 (n) | 41.9 (6) | 42.8 (6) |
| fit GPU ms per draw | 0.0153 | 0.0149 |
| fit intercept, ms | 3.8 | 9.0 |
| light-view GPU ms (BE < 1200) | 17.8 | 21.0 |
| heavy-view fps | 14.6 | 14.9 |

`push656_read.py --a A --b B`, heavy windows:

| | A | B |
|---|---|---|
| UBO set binds per draw | 0.916 | **0.453** (B/A 0.495) |
| uniform changes pushed instead of uploaded | -- | 573,113 of 1,322,782 (0.433) |
| binds skipped as repeats | -- | 696,503 |
| rebind = binds / (uploads + pushes) | -- | 0.573 |
| overlay size n1 / 2-4 / 5-8 / 9-12 | -- | 64,819 / 438,528 / 36,160 / 33,606 |
| upload reasons set / binding / psh / row / full | -- | 0.92 / 0.00 / 0.08 / 0.00 / 0.01 |

Legs as registered:

- **M0 PASS**: 15 and 13 heavy rows, >= 8 each.
- **P0 PASS**: `[push656] maxPushConstantsSize=256 attrs_in_push=0 gpl=0
  env=- -> uniform overlay on (12 slots, 240 B at 16)`. **The Nova's limit
  is 256 B**, as the Mesa tree says (section 1).
- **M1 FAIL** on its rebind half: 0.573 against <= 0.45. Its other half
  passes: binds per draw B/A 0.495 against <= 0.60. So by the letter P1 is
  not read as a test of the rebind hypothesis.
- **P1** (reported, not judged): heavy-view GPU B/A = 42.3 / 38.3 = 1.104.
  Not lower in either heavy BE bin.
- **R1 PASS**: light views 21.0 <= 17.8 x 1.15 + 1.0 = 21.5.
- **C0 PASS**.

What the pair shows, whatever M1's letter:

- **B removed half of the UBO binds from BF2's heavy-view draws (0.92 to
  0.45 per draw) and the GPU cost per draw did not move** (fit 0.0153 to
  0.0149 ms per draw, -3%; collapse433's GMEM and sysmem soaks, same
  renderer, differ by 2% in this slope, 0.0119 against 0.0121). The
  heavy-view medians went up, not down.
- **A bound, not a value**: if the whole -3% slope change is the binds,
  one UBO bind costs ~0.9 us of the 15 us a heavy-view draw takes. If
  instead B's +3.2 ms in light views is all the overlay's own vertex-shader
  cost and it hides an equal saving in heavy views, the removed binds were
  worth at most ~4 ms of 38 (~10%): at most ~4 us per bind. Either way the
  per-draw UBO rebind is not what makes BF2's draws cost 12-15 us each.
  bf2stall433's U (section 3 there) is refuted as the main cause.
- **Why the rebind rate stayed at 0.57**: 92% of the uploads B still made
  were `set`, a new UBO set due. `r->shader_bindings_changed` is cleared only
  at the top of `pgraph_vk_bind_shaders()` (shaders.c) and in one draw.c
  path, and `bind_shaders` runs only when the shader state is dirty. After a
  binding switch the flag stays true for every following draw until the
  next shader-state change, so each of those draws writes a new UBO
  descriptor set (`vkUpdateDescriptorSets`), uploads, and misses the super
  fast path (`sfp_miss_shader_changed`). That is a CPU cost on master,
  noted here and not chased: no GPU win to unlock behind it.

The emulator change is reverted on this branch (the three files restored
from master); it stays in history at 2d0d03edb6. The pixel and GTA
predictions were never registered and nothing else was queued. Runs used:
2 of 6.

## 6. Next, for whoever picks up BF2's per-draw cost

Ruled out so far, each by a measurement that moved its mechanism: the
vertex fetch path (bf2stall433 section 6), the per-draw UBO rebind (this
lane), the GPU clock and the render mode (collapse433). The draws are
serialized (bf2stall433 section 7). What is still unmeasured, in the order
I would test it:

1. **Is the GPU front end (CP) busy or waiting per draw?** Adreno's own
   counters separate a command processor working through each draw's state
   from shader cores stalled on something. One perflog soak with the CP and
   SP busy counters (fdperf or a Perfetto GPU-counter capture, read-only)
   answers it. It decides between the two that follow; without it, every
   candidate below is another guess like U was.
2. **Per-draw state volume.** Every draw still re-pushes texture
   descriptors when bindings change, binds a vertex buffer, an index buffer
   at a new offset, and on 808 of ~2,150 draws a pipeline with every dynamic
   state re-issued (bf2stall433 section 1). If the CP is the bottleneck, the
   cost is the state emitted per draw, and the lever is emitting less of it
   (dynamic state only on change, one index buffer bind per command buffer
   with `firstIndex`).
3. **Shader-side latency per draw** (the preamble's constant loads, a
   texture-cache cold start per draw): if the SP is busy, this.

## Do not repeat

- Pushing changed uniform rows to remove the per-draw UBO bind, for BF2's
  GPU cost: built and measured (section 5), binds per draw halved, no GPU
  change.
- Lowering the UBO rebind rate further (the sticky `shader_bindings_changed`
  set reason, a uniform layout shared across shaders): the binds it would
  remove are worth a few us each at most.
- Assuming the Nova's `maxPushConstantsSize`: it is 256 (P0 line).

