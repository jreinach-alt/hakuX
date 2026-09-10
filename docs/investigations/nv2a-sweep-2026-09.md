# NV2A structural sweep, September 2026

A read-only inventory of the NV2A emulation, run to give
[`docs/testing/nv2a_index.py`](../testing/nv2a_index.py) its input and to find
the couplings that make accuracy work expensive. No emulator source was
modified.

Everything below was **re-checked by hand against the code** after the sweep
reported it. The raw per-subsystem inventories in [`sweeps/`](sweeps/) contain
more, unverified. Two claims in those reports were wrong and are corrected here.

## The fact that decides several of these

**On Android the renderer is Vulkan, not the configured default.**
`config_spec.yml:230` sets `default: OPENGL`, and the Android layer overrides it
— `android/app/src/main/cpp/xemu_android.cpp:616` inserts `"vulkan"`, and
`android/app/src/main/cpp/xemu_settings_android.cc:69` sets
`CONFIG_DISPLAY_RENDERER_VULKAN`.

So every VK-only gap below is live on device, and every GL-only one is not. This
is worth stating because several code comments in the tree describe the split
backwards.

---

## Renderer-conditional shader state (#21, #11)

`glsl/psh.c` computes three pieces of shader state only for one renderer:

| state | site | computed for | consequence on the other |
|---|---|---|---|
| `snorm_tex[i]` | `psh.c:219` | OpenGL only | VK never sets it |
| `window_clip_count` | `psh.c:67-68` | non-OpenGL only | GL emits no clip block |
| `depth_needed` | `psh.c:120-126` | non-OpenGL only | GL emits no `gl_FragDepth` write |

### The comment at `psh.c:223` is wrong about its own condition

It reads `/* VK/desktop GL: snorm_tex left at default (false) — FIXME */`, and
the rationale above it says *"GLES uploads as unsigned RGBA8"*. Neither holds:

- `include/xemu-config.h:7-12` defines only `NULL`, `OPENGL`, `VULKAN`. There is
  no GLES enum — desktop GL **is** `CONFIG_DISPLAY_RENDERER_OPENGL` and does get
  `snorm_tex` set. Only Vulkan is excluded.
- `SZ_R6G5B5` is absent from `android_texture_needs_rgba8_upload`
  (`gl/texture.c:81-115`), so GLES uploads it as `GL_RGB8_SNORM` exactly like
  desktop GL (`gl/constants.h:277`).

### VK applies the signed remap twice — candidate for #21's bump-map regression

**VERIFIED.** On Vulkan:

1. `vk/constants.h:246` uploads `SZ_R6G5B5` as `VK_FORMAT_R8G8B8_SNORM`,
2. over CPU-converted **signed** bytes from `pgraph/texture.c:387-394`,
3. but `snorm_tex` stays false (`psh.c:219`),
4. so `psh.c:1257` / `psh.c:1283` take the `sign3()` branch,
5. and `sign3()` (`psh.c:936-939`) multiplies by 255 and reinterprets — the
   transform for an *unsigned* byte carrying a signed value.

Already-signed SNORM data is remapped a second time, on every `BUMPENVMAP` draw
sampling this format, on the renderer the device actually uses.

**INFERRED:** this is a candidate mechanism for #21's observation that an
unsigned decode fixed blue while making `BumpMap_R6G5B5` *worse*. Not
established — that needs a device run with both suites enabled.

Note the `BUMPENVMAP_LUM` branches differ in **two** places, not one: the
luminance `.r` gets `sign3_to_0_to_1()` in the signed branch and raw in the
other. The index is `input_tex[i]` — the source stage, not `i`.

---

## Window clip: the code contradicts #19's conclusion (#11, #19)

#19's second comment concluded *"we implement inclusive clip as exclusive"* and
moved `Window clip` to #11 as a concrete defect. **The code does not support
that on Vulkan.**

**VERIFIED:** `glsl/psh.c:1041-1085` emits genuinely different GLSL for the two
modes — exclusive discards inside a region; inclusive accumulates
`clipContained` and discards outside all regions. They are distinct.

What is actually missing:

- **The clip rectangles never trigger shader regeneration.**
  `NV_PGRAPH_WINDOWCLIPX0`/`Y0` are written at `pgraph.c:2249` and `:2257`, and
  appear in **no** register category — the table at `pgraph.c:117-140` covers
  `shader_regs[]`, the combiners and the texture registers, and omits them. The
  region *count* `wc_count` is compiled into the shader source as a loop bound
  (`psh.c:1067`), so a change in how many regions are active cannot regenerate
  the shader that depends on it. The clip *type* does regen, being a field of
  `NV_PGRAPH_SETUPRASTER` (`pgraph.c:286`), which is in `shader_regs[]`.

- **A clip write broadcasts to every higher slot.**
  `SET_WINDOW_CLIP_HORIZONTAL` (`pgraph.c:2245-2251`) and `..._VERTICAL`
  (`:2253-2259`) loop `for (; slot < 8; ++slot)` writing the *same* parameter
  into every remaining region register. **UNRESOLVED** whether this is faithful
  to hardware broadcast behaviour or a defect; it is inherited, not
  fork-introduced, and it directly determines `wc_count`.

- **GL does not do shader-based clipping at all**, by design —
  `psh.c:66-68` says GL uses `glScissor` instead. A single scissor rectangle
  cannot express multi-region or exclusive clipping. Not live on device.

**This reopens the question #19 closed.** A VK run should show the two modes
differing; the measurement showed them byte-identical even in isolation. Both
cannot be right, and resolving it is cheap: re-run the `rI_`/`rE_` solo discs
and confirm which renderer was active.

---

## Dirty-bit consumption is wider than #19 records (#19)

#19's hypothesis 2 — `memory_region_test_and_clear_dirty` consumes the bit
across a page-aligned range, so the first caller clears it for everything
sharing those pages — is **VERIFIED**, and there are six consumers of the same
bitmap with no coordination between them:

```
gl/surface.c:2712   memory_region_test_and_clear_dirty(...)
gl/texture.c:517    memory_region_test_and_clear_dirty(...)
gl/vertex.c:66      memory_region_test_and_clear_dirty(...)
vk/texture.c:480    memory_region_test_and_clear_dirty(...)
vk/surface.c:2789   bitmap_test_and_clear_atomic(...)    <- hand-inlined
vk/draw.c:5119      bitmap_test_and_clear_atomic(...)    <- hand-inlined
```

**Two of them bypass the API**, open-coding the page walk against the dirty
blocks directly. Grepping the function name — the obvious investigation — finds
four of six. Any fix applied to the shared helper will not reach the other two.

---

## Texture address and border colour never mark the cache dirty (#3, #19)

**VERIFIED.** `SET_TEXTURE_ADDRESS` (`pgraph.c:2118-2122`) and
`SET_TEXTURE_BORDER_COLOR` (`pgraph.c:3739-3743`) write their register and do
not touch `texture_dirty[slot]`. Every neighbouring texture handler does
(`pgraph.c:3639, 3679, 3687, 3696, 3705, 3714`).

Both are fields of the VK cache key — `TextureKey.address` and
`.border_color`, `vk/renderer.h:684-685`.

The gate is total: `check_textures_dirty` (`vk/texture.c:1942-1952`) returns true
only when a binding is missing or `texture_dirty[i]` is set; otherwise
`pgraph_vk_bind_textures` returns early at `vk/texture.c:1986` without
recomputing the key at all.

**INFERRED:** a draw changing only wrap mode or border colour reuses the previous
binding and sampler. That predicts #3's `Texture_border` (18/18 failing) and
`TextureWrapMode` (1/1), and #19's largest substitution group,
`Texture_cubemap` at 44. It is a candidate until a pair/solo isolation run says
so — the methodology #19 established.

---

## The dump path cannot dump the format #21 is about (#21, #6)

**VERIFIED.** `vk/texture_dump.c:41-53` re-declares the `VkFormat` enum by hand
rather than including the header. Checked against the in-tree
`vulkan_core.h:1411-1540`:

| symbol | file says | actual |
|---|---|---|
| `R8G8B8_SNORM` | 25 | **24** |
| `A8B8G8R8_UNORM_PACK32` | 50 | **51** |
| `R5G6B5_UNORM_PACK16` | 84 | **4** |
| `A1R5G5B5_UNORM_PACK16` | 86 | **8** |
| `BC1_RGBA_UNORM` | 131 | **133** (131 is BC1_**RGB**) |

`R8G8B8_SNORM` is R6G5B5's host format, so R6G5B5 textures fall to `default:`
and are **silently never dumped** — with no error. Anyone debugging #21 by
dumping the texture gets nothing back. The BC1 slip misclassifies BC1_RGB as
BC1_RGBA, which touches #6.

---

## The fast path diverges from the handlers it replaces (fork-introduced)

hakuX carries a second dispatch path beyond upstream's table: `method_fast[0x800]`
(`pgraph.c:343-642`) and a **lockless** `pgraph_method_try_fast`
(`pgraph.c:727-793`) called without `pgraph.lock`. It arrived in `1666e81`
*"nv2a: comprehensive profiling fixes, GPU overhead reduction, and perf
optimizations"* — this fork's own, and a divergence surface upstream does not
have.

**VERIFIED divergence:** `SET_DEPTH_MASK`. The slow handler
(`pgraph.c:2504`) performs `pg->surface_zeta.write_enabled_cache |=
pgraph_zeta_write_enabled(pg);` before the register write. The fast entry
(`pgraph.c:640-641`) is `MF_MASKED(NV_PGRAPH_CONTROL_0, 50)` — the register
write alone. The cache update is dropped whenever the fast path takes the
method.

The comment above that entry names `SET_DEPTH_WRITE_ENABLE`, which is not a
symbol in `nv2a_regs.h`; the address `0x035C` is `SET_DEPTH_MASK`.

---

## Unimplemented state is silent, not fatal

**VERIFIED**, and it corrects a common assumption:

- `NV2A_UNIMPLEMENTED(...)` compiles to `do {} while (0)` in default builds
  (`hw/xbox/nv2a/debug.h:67`). It does not abort. It does not even log.
- `assert()` always aborts — `include/qemu/osdep.h:311` makes `NDEBUG` an
  `#error`, so assertions cannot be compiled out.

So the 17 `NV2A_UNIMPLEMENTED` sites pass unnoticed, while asserts kill the run.
Widening a sweep means making the first group *visible*, not making the second
survivable — the opposite of the obvious fix.

---

## Corrections to the raw sweep reports

Recorded because the reports in [`sweeps/`](sweeps/) still contain them:

1. **`sweep-surface.md`** cites `vk/surface.c:2789` and `vk/draw.c:5119` as calls
   to `memory_region_test_and_clear_dirty`. They are hand-inlined
   reimplementations calling `bitmap_test_and_clear_atomic`. The substance holds
   and the real form is the more significant finding.

2. **`sweep-shaders.md`** states that `Bump map` does not carry `SZ_R6G5B5`,
   only `Bump env lum`, because `bump_map_tests.cpp` never names the format. It
   iterates `kTextureFormats[i]` (`src/tests/bump_map_tests.cpp:40`) and builds
   names via `MakeTestName(format, ...)` — which is how `BumpMap_R6G5B5`, cited
   by #21's own measurement table, exists. The index is right.

Both were caught by checking the claim against the code, which is the only
reason to prefer a sweep that reports over a sweep that annotates.

---

## Unresolved

- Which renderer the baseline sweep ran under. Android forces Vulkan, but the
  runs predate this note and the window-clip contradiction turns on it.
- Whether the window-clip slot broadcast is hardware behaviour or a defect.
- Whether any pgraph test actually trips the aborting asserts catalogued in the
  raw reports, or whether they are unreachable in practice.
- Method-side and register-side field widths disagree for
  `TEXTURE_FORMAT_COLOR` (8 vs 7 bits), `DIMENSIONALITY` (4 vs 2) and
  `TEXIMAGERECT` (16 vs 13), and `PG_SET_MASK` truncates. Faithful widths or
  transcription errors — undetermined from code alone.
