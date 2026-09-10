# psh-differ

Answers one question, in about three seconds and without a console:

> If the guest changes this piece of pixel-shader state, does the shader we
> hand the GPU actually change?

`pgraph_glsl_gen_psh()` turns a `PshState` into GLSL and reads nothing else --
no `PGRAPHState`, no globals, no VRAM. That makes it directly callable. So the
tool builds a `PshState`, generates a shader, changes one field, generates
again, and compares the text.

If the text is identical, that state never reached the GPU.

```
cd docs/testing/psh_differ
make
./build/psh-differ
```

No configured QEMU tree, no ROMs, no device. `make` compiles the real `psh.c`
straight out of `hw/xbox/nv2a/pgraph/glsl/`.

## Reading the output

Every probe lands in one of five buckets.

| bucket | meaning |
| --- | --- |
| `changed` | the GLSL differs. The state reaches the shader. |
| `unimpl` | identical, but the generator logged `NV2A_UNIMPLEMENTED`. A gap that is already written down in the source. |
| `same` | identical, and silent. Nothing in the generator looks at it. |
| `abort` | the generator asserted. Reachable state that kills the frame instead of drawing it wrong. |
| `skipped` | the baseline already held that value, so the probe was a no-op. |

`same` is the bucket worth reading, and it is **not** a bug list. A field can
be inert for three quite different reasons:

1. The emulator ignores state the hardware acts on. A real defect.
2. The bit does not exist. `shader_stage_program` holds four five-bit texture
   modes, so bits 20 and up are padding and nothing should read them.
3. The field is unreachable by construction. `snorm_tex[]` is indexed through
   `input_tex[]`, and a texture can only feed a *later* combiner stage, so
   `snorm_tex[3]` can never be consulted.

Only the first is worth an issue. Check the register against `docs/nv2a/` and
the nxdk_pgraph_tests suite before filing one -- and the tool can help:

```
./build/psh-differ --show 'shadow_depth_func=4'
./build/psh-differ --show 'alphakill[2]=1' --baseline textures --dump-dir /tmp/d
```

`--show` prints the diff between the two shaders for one probe, per baseline
and renderer, and `--dump-dir` leaves both full shaders behind to read.

## Baselines are the whole game

A probe can only show an effect on a code path it reaches. `compare_mode[][]`
is read in exactly one place -- inside `PS_TEXTUREMODES_CLIPPLANE` -- so until
a baseline used clip planes, all sixteen entries looked dead. They were not;
the tool was.

That is why there are nine baselines, each aimed at a region of the generator:

| baseline | what it reaches |
| --- | --- |
| `off` | nothing enabled: no stages, no textures |
| `basic` | one combiner stage, one 2D texture, an alpha test |
| `stages` | all eight combiner stages, so the later stage registers are live |
| `textures` | bump mapping and the dot-product texture modes |
| `surface` | shadow maps, window clipping, point sprites |
| `clipplane` | `PS_TEXTUREMODES_CLIPPLANE`, and only it reads `compare_mode` |
| `border` | the four-texel texture border, which shadow maps bypass |
| `bumpenv` | bump stages wired so `snorm_tex[1]` and `[2]` are reachable |
| `misc` | cube maps, passthrough, the dependent AR/GB lookups |

Each runs under all three renderer configurations (`gl`, `vk`, `gles`), and a
field counts as reaching the shader if **any** of the 27 scenarios shows a
diff.

**When something lands in `same`, suspect the baselines first.** Adding one is
a dozen lines in `differ.c`: fill in a `PshState`, add it to the `baselines[]`
table, rebuild. That is the intended way to use this tool -- a `same` result is
a claim about coverage, and coverage is yours to extend.

## How it builds without QEMU

`psh.c` has two halves. One turns a `PshState` into GLSL. The other fills a
`PshState` in from a live `PGRAPHState`, and that half needs the real
`pgraph.h`, which needs a configured QEMU tree.

So `carve.py` writes a copy of `psh.c` with the `PGRAPHState` functions blanked
out -- three in `psh.c`, one in `glsl/common.c` -- line for line, so the numbers in compiler diagnostics still match
the original file. `psh.c` on disk is never touched. `shim/` then supplies the
little that remains -- libc and glib in place of `qemu/osdep.h`, an opaque
`PGRAPHState`, the two warning macros. The register constants come from the
real `nv2a_regs.h`, because those are the values under test.

Two things follow. `carve.py` fails loudly rather than guessing if a signature
changes or a new function starts reading emulator state -- it will name the
function. And `NV2A_UNIMPLEMENTED` is always live here and records instead of
printing, where upstream compiles it out unless `DEBUG_NV2A_FEATURES`; that is
what separates the `unimpl` bucket from `same`.

## Other flags

```
--baseline NAME    only this baseline
--renderer NAME    only gl, vk or gles
--json PATH        per-probe results, for diffing between commits
--all              also list the probes the baselines could not vary
--verbose          let the crashing child processes speak
```

Probes run in a forked child. A bad `PshState` does not always fail politely:
some values trip an assert, and some used to run off the end of an array and
corrupt memory before anything noticed. Neither can be caught in-process and
recovered from honestly, so when a child dies the parent records which probe
killed it and starts a fresh child on the next one.

## What the first run found

- **A stack buffer overflow, guest-reachable.** The combiner stage count is
  the low byte of `NV097_SET_COMBINER_CONTROL`, unmasked all the way from the
  push buffer. Arrays sized for eight stages were indexed up to 255, in three
  places. Fixed by clamping at all three (`psh_num_combiner_stages()`).
- **`surface_zeta_format` is in the shader cache key but not in the shader.**
  `depth_format` carries the information that matters; the zeta format is only
  compared in `shaders.c` to decide whether to regenerate. Changing it costs a
  shader recompile that produces byte-identical GLSL.
- **A NULL dereference, also guest-reachable.** `PS_REGISTER_EF_PROD` is a
  read-only register, and naming it as a combiner *output* sends `get_var()`
  down a path that reads `ps->varE` and `ps->varF` before the final combiner
  has set them. `--show 'rgb_outputs[4]#1' --baseline stages` is the repro.
- **Fifty-five more probe values that abort the generator**, all of them plain
  register contents: combiner input register codes 6 and 7, dot-mapping modes
  8 through 15, texture stage modes above `0x12`, one-dimensional textures.
  The emulator asserts where it could draw something wrong and say so. Whether
  that asymmetry is worth closing is issue territory, not a per-site decision.
