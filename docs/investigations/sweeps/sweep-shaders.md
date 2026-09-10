> **Machine-generated inventory. NOT verified.**
>
> This is the raw output of a read-only sweep agent, preserved because the
> container it ran in is ephemeral. It is a lead list, not documentation.
> Citations are mostly accurate and at least two claims across this set were
> wrong — see the Corrections section of
> [`../nv2a-sweep-2026-09.md`](../nv2a-sweep-2026-09.md), which holds the
> subset re-checked by hand.
>
> Check any claim here against the code before acting on it.

# Sweep: NV2A shader & register-combiner code generation (hakuX)

Read-only inventory. Repo root: `/home/user/hakuX`. All paths below are relative to that root.
Every claim carries a `file:line`. Claims are tagged **[V]** (verified: I read the exact line)
or **[I]** (inferred: reasoning over verified lines, not directly observed at runtime).

**Scope covered:** `hw/xbox/nv2a/pgraph/glsl/` (psh.c, psh.h, vsh.c/.h, vsh-ff.c/.h,
vsh-prog.c/.h, geom.c/.h, common.c/.h, shaders.c/.h), `pgraph/vk/shaders.c`,
`pgraph/vk/glsl.c`, `pgraph/gl/shaders.c`, plus the register/method definitions in
`hw/xbox/nv2a/nv2a_regs.h` and the combiner enums in `hw/xbox/nv2a/pgraph/psh_regs.h`.

---

## Concepts owned

### Guest methods (NV097_*) that feed the combiner/shader compiler

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Combiner stage count + flags | method | `NV097_SET_COMBINER_CONTROL` | nv2a_regs.h:1291 |
| Per-stage RGB input CW | method | `NV097_SET_COMBINER_COLOR_ICW` | nv2a_regs.h:1087 |
| Per-stage RGB output CW | method | `NV097_SET_COMBINER_COLOR_OCW` | nv2a_regs.h:1290 |
| Per-stage alpha input CW | method | `NV097_SET_COMBINER_ALPHA_ICW` | nv2a_regs.h:898 |
| Per-stage alpha output CW | method | `NV097_SET_COMBINER_ALPHA_OCW` | nv2a_regs.h:1086 |
| Final combiner inputs A-D | method | `NV097_SET_COMBINER_SPECULAR_FOG_CW0` | nv2a_regs.h:899 |
| Final combiner inputs E-G + flags | method | `NV097_SET_COMBINER_SPECULAR_FOG_CW1` | nv2a_regs.h:900 |
| Combiner constant C0 (per stage) | method | `NV097_SET_COMBINER_FACTOR0` | nv2a_regs.h:1084 |
| Combiner constant C1 (per stage) | method | `NV097_SET_COMBINER_FACTOR1` | nv2a_regs.h:1085 |
| Per-stage texture mode (5 bits x4) | method | `NV097_SET_SHADER_STAGE_PROGRAM` | nv2a_regs.h:1302 |
| Dot-product source stage indices | method | `NV097_SET_SHADER_OTHER_STAGE_INPUT` | nv2a_regs.h:1304 |
| Dot RGB mapping (dotmap) | method | `NV097_SET_DOT_RGBMAPPING` | pgraph.c:4098 (handler) |
| Clip-plane compare mode | method | `NV097_SET_SHADER_CLIP_PLANE_MODE` | nv2a_regs.h:1158 |
| Shadow compare func | method | `NV097_SET_SHADOW_DEPTH_FUNC` | pgraph.c:4087 (handler) |
| Colour key colour (x4) | method | `NV097_SET_COLOR_KEY_COLOR` | pgraph.c:3074 (handler) |

### PGRAPH registers the compiler reads

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Combiner control (num stages + flags) | regfield | `NV_PGRAPH_COMBINECTL` | nv2a_regs.h:424 |
| RGB input CW base | regfield | `NV_PGRAPH_COMBINECOLORI0` | nv2a_regs.h:422 |
| RGB output CW base | regfield | `NV_PGRAPH_COMBINECOLORO0` | nv2a_regs.h:423 |
| Alpha input CW base | regfield | `NV_PGRAPH_COMBINEALPHAI0` | nv2a_regs.h:420 |
| Alpha output CW base | regfield | `NV_PGRAPH_COMBINEALPHAO0` | nv2a_regs.h:421 |
| Final combiner CW0 | regfield | `NV_PGRAPH_COMBINESPECFOG0` | nv2a_regs.h:425 |
| Final combiner CW1 | regfield | `NV_PGRAPH_COMBINESPECFOG1` | nv2a_regs.h:426 |
| Combiner factor 0 base | regfield | `NV_PGRAPH_COMBINEFACTOR0` | nv2a_regs.h:418 |
| Combiner factor 1 base | regfield | `NV_PGRAPH_COMBINEFACTOR1` | nv2a_regs.h:419 |
| Final combiner factor 0 | regfield | `NV_PGRAPH_SPECFOGFACTOR0` | nv2a_regs.h:526 |
| Final combiner factor 1 | regfield | `NV_PGRAPH_SPECFOGFACTOR1` | nv2a_regs.h:527 |
| Texture stage program | regfield | `NV_PGRAPH_SHADERPROG` | nv2a_regs.h:521 |
| dotmap + input_tex packing | regfield | `NV_PGRAPH_SHADERCTL` | nv2a_regs.h:520 |
| Clip-plane compare bits (4x4) | regfield | `NV_PGRAPH_SHADERCLIPMODE` | nv2a_regs.h:519 |
| Shadow depth compare func | regfield | `NV_PGRAPH_SHADOWCTL_SHADOW_ZFUNC` | nv2a_regs.h:524 |
| Bump matrix m00/m01/m10/m11 | regfield | `NV_PGRAPH_BUMPMAT00..11` | nv2a_regs.h:401-404 |
| Bump luminance scale/offset | regfield | `NV_PGRAPH_BUMPSCALE1` / `NV_PGRAPH_BUMPOFFSET1` | nv2a_regs.h:406 / 405 |
| Colour key colours | regfield | `NV_PGRAPH_COLORKEYCOLOR0..3` | nv2a_regs.h:414-417 |
| Alpha ref / func / test enable | regfield | `NV_PGRAPH_CONTROL_0_ALPHAREF` / `_ALPHAFUNC` / `_ALPHATESTENABLE` | nv2a_regs.h:428 / 429 / 430 |
| Window clip inclusive/exclusive | regfield | `NV_PGRAPH_SETUPRASTER_WINDOWCLIPTYPE` | nv2a_regs.h:518 |
| Z fixed/float select | regfield | `NV_PGRAPH_SETUPRASTER_Z_FORMAT` | nv2a_regs.h:517 |
| Per-texture ctl (alphakill/colorkey/enable) | regfield | `NV_PGRAPH_TEXCTL0_0_*` | nv2a_regs.h:544-550 |

### Combiner ISA enums (the vocabulary of the emitted GLSL)

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Per-stage texture addressing mode (19 values) | enum | `enum PS_TEXTUREMODES` | psh_regs.h:31 |
| Combiner input mapping (8 values) | enum | `enum PS_INPUTMAPPING` | psh_regs.h:55 |
| Combiner register file | enum | `enum PS_REGISTER` | psh_regs.h:67 |
| Unique-C0/C1, MUX MSB/LSB flags | enum | `enum PS_COMBINERCOUNTFLAGS` | psh_regs.h:91 |
| Output mapping / dot / blue-to-alpha / mux | enum | `enum PS_COMBINEROUTPUT` | psh_regs.h:103 |
| RGB vs BLUE vs ALPHA channel select | enum | `enum PS_CHANNEL` | psh_regs.h:126 |
| Final combiner clamp/complement flags | enum | `enum PS_FINALCOMBINERSETTING` | psh_regs.h:134 |
| Dot-product remap mode (8 values) | enum | `enum PS_DOTMAPPING` | psh_regs.h:143 |
| Colour key kill mode | enum | `enum PS_COLORKEYMODE` | psh_regs.h:155 |
| Alpha test function | enum | `enum PshAlphaFunc` | psh_regs.h:162 |
| Shadow depth compare function | enum | `enum PshShadowDepthFunc` | psh_regs.h:173 |
| Convolution kernel select | enum | `enum ConvolutionFilter` | psh_regs.h:184 |
| Depth surface format (D16/D24/F16/F24) | enum | `enum PshDepthFormat` | psh.h:30 |

### PshState — the pixel/combiner shader-state struct (`psh.h:37-77`)

Every field below is a *shader-state-field*: it is part of the shader cache key
(hashed at shaders.c:40, compared at shaders.c:69) and therefore selects GLSL text.

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Stage count + unique-C0/C1 + MUX bit | shader-state-field | `PshState.combiner_control` | psh.h:38 |
| Packed 4x5-bit texture modes | shader-state-field | `PshState.shader_stage_program` | psh.h:39 |
| dotmap[1..3] + input_tex[2..3] | shader-state-field | `PshState.other_stage_input` | psh.h:40 |
| Final combiner A-D | shader-state-field | `PshState.final_inputs_0` | psh.h:41 |
| Final combiner E-G + flags | shader-state-field | `PshState.final_inputs_1` | psh.h:42 |
| Per-stage RGB CWs | shader-state-field | `PshState.rgb_inputs[8]` / `.rgb_outputs[8]` | psh.h:44 |
| Per-stage alpha CWs | shader-state-field | `PshState.alpha_inputs[8]` / `.alpha_outputs[8]` | psh.h:45 |
| Point-sprite T3 override | shader-state-field | `PshState.point_sprite` | psh.h:47 |
| Non-swizzled (linear/rect) texture | shader-state-field | `PshState.rect_tex[4]` | psh.h:48 |
| Texture already signed-normalized | shader-state-field | `PshState.snorm_tex[4]` | psh.h:49 |
| Clip-plane per-channel compare sense | shader-state-field | `PshState.compare_mode[4][4]` | psh.h:50 |
| Discard on alpha==0 | shader-state-field | `PshState.alphakill[4]` | psh.h:51 |
| Colour key kill mode per stage | shader-state-field | `PshState.colorkey_mode[4]` | psh.h:52 |
| Convolution filter per stage | shader-state-field | `PshState.conv_tex[4]` | psh.h:53 |
| X8Y24 depth texture (VK usampler) | shader-state-field | `PshState.tex_x8y24[4]` | psh.h:54 |
| Texture dimensionality (2/3) | shader-state-field | `PshState.dim_tex[4]` | psh.h:55 |
| Cubemap enable per stage | shader-state-field | `PshState.tex_cubemap[4]` | psh.h:56 |
| 4-texel border logical size | shader-state-field | `PshState.border_logical_size[4][3]` | psh.h:58 |
| 4-texel border 1/real size | shader-state-field | `PshState.border_inv_real_size[4][3]` | psh.h:59 |
| Depth-format texture (shadow map) | shader-state-field | `PshState.shadow_map[4]` | psh.h:61 |
| Shadow compare operator | shader-state-field | `PshState.shadow_depth_func` | psh.h:62 |
| Alpha test enable | shader-state-field | `PshState.alpha_test` | psh.h:64 |
| Alpha test operator | shader-state-field | `PshState.alpha_func` | psh.h:65 |
| Window clip inclusive/exclusive | shader-state-field | `PshState.window_clip_exclusive` | psh.h:67 |
| Number of non-trivial window clip regions | shader-state-field | `PshState.window_clip_count` | psh.h:68 |
| Smooth vs flat varying qualifier | shader-state-field | `PshState.smooth_shading` | psh.h:70 |
| Discard vs clamp out-of-range Z | shader-state-field | `PshState.depth_clipping` | psh.h:71 |
| W-buffering (z_perspective) | shader-state-field | `PshState.z_perspective` | psh.h:72 |
| Emit `gl_FragDepth` at all | shader-state-field | `PshState.depth_needed` | psh.h:73 |
| Raw zeta surface format (dirty check only) | shader-state-field | `PshState.surface_zeta_format` | psh.h:75 |
| D16/D24/F16/F24 selection | shader-state-field | `PshState.depth_format` | psh.h:76 |

### PshUniform declarations (the uniform block the GLSL declares)

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Full PSH uniform list (X-macro) | uniform decl | `PSH_UNIFORM_DECL_X` | psh.h:81-95 |
| Generated enum/locs/values/info types | uniform decl | `DECL_UNIFORM_TYPES(PshUniform, ...)` | psh.h:97 |
| Info array definition | uniform decl | `DEF_UNIFORM_INFO_ARR(PshUniform, ...)` | psh.c:35 |
| GLSL codegen options (vulkan/gles/bindings) | struct | `GenPshGlslOptions` | psh.h:99-106 |

### VshState — vertex shader state struct (`vsh.h:50-78`)

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Fixed-function sub-state | shader-state-field | `FixedFunctionVshState` | vsh.h:30-43 |
| — normal renormalization | shader-state-field | `.normalization` | vsh.h:31 |
| — per-stage texture matrix enable | shader-state-field | `.texture_matrix_enable[4]` | vsh.h:32 |
| — per-stage per-channel texgen mode | shader-state-field | `.texgen[4][4]` | vsh.h:33 |
| — fog distance generation mode | shader-state-field | `.foggen` | vsh.h:34 |
| — skinning mode | shader-state-field | `.skinning` | vsh.h:35 |
| — lighting master enable | shader-state-field | `.lighting` | vsh.h:36 |
| — per-light type (off/infinite/local/spot) | shader-state-field | `.light[NV2A_MAX_LIGHTS]` | vsh.h:37 |
| — material colour sources | shader-state-field | `.emission_src`/`.ambient_src`/`.diffuse_src`/`.specular_src` | vsh.h:38-41 |
| — local viewer | shader-state-field | `.local_eye` | vsh.h:42 |
| Programmable sub-state (raw tokens) | shader-state-field | `ProgrammableVshState` | vsh.h:45-48 |
| Attribute compression / uniform / swizzle masks | shader-state-field | `.compressed_attrs`/`.uniform_attrs`/`.swizzle_attrs` | vsh.h:53-55 |
| Fog enable + mode | shader-state-field | `.fog_enable` / `.fog_mode` | vsh.h:57-58 |
| Specular enable / separate / ignore-alpha | shader-state-field | `.specular_enable`/`.separate_specular`/`.ignore_specular_alpha` | vsh.h:60-62 |
| Specular power (front/back) | shader-state-field | `.specular_power` / `.specular_power_back` | vsh.h:63-64 |
| Point params enable / size / coefficients | shader-state-field | `.point_params_enable`/`.point_size`/`.point_params[8]` | vsh.h:66-68 |
| FF vs programmable discriminator | shader-state-field | `.is_fixed_function` | vsh.h:73 |
| VSH uniform list | uniform decl | `VSH_UNIFORM_DECL_X` | vsh.h:82-97 |
| VSH codegen options | struct | `GenVshGlslOptions` | vsh.h:101-110 |

### GeomState — geometry shader state (`geom.h:28-34`)

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Rewritten primitive mode | shader-state-field | `GeomState.primitive_mode` | geom.h:29 |
| Front/back polygon fill mode | shader-state-field | `.polygon_front_mode` / `.polygon_back_mode` | geom.h:30-31 |
| Smooth shading (provoking vertex) | shader-state-field | `.smooth_shading` | geom.h:32 |
| W-buffering | shader-state-field | `.z_perspective` | geom.h:33 |

### Aggregate

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Full shader cache key | struct | `ShaderState { VshState vsh; GeomState geom; PshState psh; }` | shaders.h:27-31 |
| Inter-stage varying block (shared vsh/geom/psh) | codegen | `pgraph_glsl_get_vtx_header()` | common.c:28-68 |
| `#version` + GLES precision prologue | codegen | `pgraph_glsl_append_version()` | common.c:70-93 |

---

## Sites

### Dispatch / state capture

| concept | file:line | role | notes |
|---|---|---|---|
| `pgraph_glsl_get_shader_state` | glsl/shaders.c:72-86 | DISPATCH | `memset(&state, 0, sizeof(ShaderState))` at shaders.c:79 **before** the three setters — this is why every field the setters skip stays at 0/false. **[V]** |
| `pgraph_glsl_set_psh_state` | glsl/psh.c:62-262 | READ/WRITE | Reads PGRAPH regs, writes `PshState`. **[V]** |
| `pgraph_glsl_set_vsh_state` | glsl/vsh.c:102-159 | READ/WRITE | **[V]** |
| `pgraph_glsl_set_geom_state` | glsl/geom.c:27-46 | READ/WRITE | **[V]** |
| `pgraph_glsl_hash_shader_state` | glsl/shaders.c:24-42 | READ | `fast_hash` over the whole `PshState` (shaders.c:40) — any struct field, even one no generator reads, splits the shader cache. **[V]** |
| `pgraph_glsl_compare_shader_state` | glsl/shaders.c:44-70 | READ | `memcmp` of whole `PshState` (shaders.c:69). **[V]** |
| `pgraph_glsl_check_shader_state_dirty` | glsl/shaders.c:88-144 | READ | Dirty-reg whitelist at shaders.c:95-104; per-stage combiner regs at shaders.c:113-116; texture regs at shaders.c:131-133. A register **not** on these lists will not re-trigger shader regeneration. **[V]** |
| GL: module cache entry -> generator | gl/shaders.c:195-230 | DISPATCH | `pgraph_glsl_gen_psh` at gl/shaders.c:218; `gen_vsh` at :208; `gen_geom` at :213. **[V]** |
| GL: `gles` option decided by `#ifdef __ANDROID__` | gl/shaders.c:263-269 | DISPATCH | `const bool gles = true` on Android (gl/shaders.c:264), `false` otherwise (gl/shaders.c:267). Both are `CONFIG_DISPLAY_RENDERER_OPENGL`. **[V]** |
| GL: psh opts populated | gl/shaders.c:299-304 | DISPATCH | Only `gles`/`gles_version` set; `vulkan` stays false via the `memset` at gl/shaders.c:299. **[V]** |
| GL: geometry shader skipped when unsupported | gl/shaders.c:272-279 | DISPATCH | On Android, `need_geometry_shader` forced false if `!r->geometry_shaders_supported` — comment at gl/shaders.c:273-275 admits provoking-vertex and wireframe will be wrong. **[V]** |
| VK: module keys built | vk/shaders.c:738-771 | DISPATCH | `psh_key->psh.glsl_opts.vulkan = true` (vk/shaders.c:767), `ubo_binding = 1` (:768), `ubo_set = 1` (:769), `tex_binding = 0` (:770). `gles` never set for VK. **[V]** |
| VK: module compile | vk/shaders.c:935-966 | DISPATCH | `pgraph_glsl_gen_psh` at vk/shaders.c:950. **[V]** |
| VK: GLSL -> SPIR-V | vk/glsl.c:195-283 | DISPATCH | glslang; on failure `dump_glsl_failure` prints the numbered source (vk/glsl.c:36-58) and `pgraph_vk_create_shader_module_from_glsl` returns NULL (vk/glsl.c:468-472). **[V]** |
| VK: SPIR-V disk cache keyed on GLSL text hash | vk/glsl.c:449-462 | DISPATCH | `fast_hash(glsl, strlen(glsl))` at vk/glsl.c:450 — cache key is the *emitted text*, so any codegen change invalidates it automatically. **[V]** |
| GL: program-binary disk cache keyed on `ShaderState` bytes | gl/shaders.c:742 | WRITE | `WRITE_OR_ERR(&binding->state, sizeof(binding->state))`; validated on load only against xemu version (gl/shaders.c:527) and GL vendor (:536). A codegen change with an unchanged `xemu_version` will reuse stale binaries. **[V]** |

### EMIT-SHADER sites — pixel shader / register combiners (psh.c)

Each row names the emitted GLSL and the state that selects it.

| concept | file:line | role | notes |
|---|---|---|---|
| Fragment output + UBO block header | psh.c:873-890 | EMIT-SHADER | `opts.vulkan && opts.ubo_set > 0` -> `"layout(location = 0) out vec4 fragColor;\nlayout(set = %d, binding = %d, std140) uniform PshUniforms {\n"` (psh.c:875-879); `opts.vulkan && ubo_set==0` -> same without `set =` (psh.c:881-885); non-Vulkan -> only `"layout(location = 0) out vec4 fragColor;\n"` (psh.c:888-889). **[V]** |
| Uniform declarations | psh.c:892-903 | EMIT-SHADER | `const char *u = ps->opts.vulkan ? "" : "uniform "` (psh.c:892) — every uniform is emitted as `uniform T name;` on GL and bare `T name;` inside the block on VK. Scalar vs array chosen by `info->count == 1` (psh.c:896). **[V]** |
| `c0_N` / `c1_N` -> `consts[]` defines | psh.c:905-909 | EMIT-SHADER | `"#define c%d_%d consts[%d]\n"`, 18 entries (9 stages x 2). **[V]** |
| sign remap + dotmap helper library | psh.c:926-1023 | EMIT-SHADER | Unconditional preflight: `sign1`/`sign2`/`sign3`/`sign3_to_0_to_1` (psh.c:927-944), the 8 `dotmap_*` functions (psh.c:945-974), `gaussian3x3`/`convolution3x3` constants (psh.c:975-982), `remapCubeTo2D` (psh.c:983-1017), `remap2DToCube` (psh.c:1019-1022). **[V]** |
| Barycentric depth helpers | psh.c:1025-1036 | EMIT-SHADER | Emitted **only if** `state->depth_needed`: `kahan_det` + `area`. **[V]** |
| Window-clip block | psh.c:1041-1086 | EMIT-SHADER | Gated on `window_clip_count > 0` (psh.c:1041). Header text picks `"Exc"`/`"Inc"` from `window_clip_exclusive` (psh.c:1042-1044). `count == 1` emits an unrolled block (psh.c:1050-1063); `count > 1` emits `for (int i = 0; i < N; i++)` (psh.c:1065-1070). Inside, `window_clip_exclusive` selects `"    discard;\n"` (psh.c:1058, :1072) vs `"    clipContained = true;\n"` (psh.c:1060, :1074). Inclusive mode adds the trailing `if (!clipContained) { discard; }` (psh.c:1082-1084). **[V]** |
| Per-pixel Z reconstruction | psh.c:1088-1143 | EMIT-SHADER | Gated on `depth_needed` (psh.c:1088). `z_perspective` true -> W-buffered variant using `vtxPos*.w`, `bc0/bc1/bc2 /= vtxPos*.w`, `zslopeofs = depthFactor*triMZ*zvalue*zvalue`, and `zvalue = uintBitsToFloat(0x7F7FFFFFu)` for `zvalue <= 0` or NaN (psh.c:1090-1115). Otherwise the Z-buffered variant interpolating `vtxPos*.z` with `zvalue += depthFactor*triMZ` (psh.c:1117-1131). Then `depth_clipping` selects `if (zvalue < clipRange.z \|\| clipRange.w < zvalue) { discard; }` (psh.c:1136-1138) vs `zvalue = clamp(zvalue, clipRange.z, clipRange.w);` (psh.c:1141). **[V]** |
| Varying copies + `pFog` | psh.c:1146-1165 | EMIT-SHADER | `vec4 pFog = vec4(fogColor.rgb, clamp(vtxFog, 0.0, 1.0));` (psh.c:1150) — the whole pixel-side fog contract is this one line; fog *factor* is computed in the vertex shader. **[V]** |
| Point-sprite T3 override | psh.c:1154-1159 | EMIT-SHADER | `point_sprite` -> `vec4 pT3 = vec4(gl_PointCoord, 1.0, 1.0);` (psh.c:1156) else `vec4 pT3 = vtxT3;` (psh.c:1158). `assert(!ps->state->rect_tex[3])` guards the sprite path (psh.c:1155). **[V]** |
| Sampler type selection | psh.c:663-736 | EMIT-SHADER | Returns the GLSL sampler type string used at psh.c:1446. `tex_x8y24[i] && opts.vulkan` -> `"usampler2D"` (psh.c:679-681, :705-707) — Vulkan-only. `tex_cubemap[i]` -> `"samplerCube"` (psh.c:682-684, :722-724). `dim_tex[i]==3` -> `"sampler3D"` (psh.c:687, :699, :711). `shadow_map[i]` forces `sampler2D` for PROJECT3D/DOT_STR_3D (psh.c:708-710) and **aborts** for every other mode (psh.c:694-697, :717-720, :729-732). **[V]** |
| `PS_TEXTUREMODES_NONE` | psh.c:1185-1188 | EMIT-SHADER | `vec4 t%d = vec4(0.0, 0.0, 0.0, 1.0); /* PS_TEXTUREMODES_NONE */`. **[V]** |
| `PS_TEXTUREMODES_PROJECT2D` | psh.c:1189-1219 | EMIT-SHADER | 5-way branch: `shadow_map[i]` -> `psh_append_shadowmap(..., compare_z=false)` (psh.c:1191); `conv_tex[i]` in {GAUSSIAN,QUINCUNX} -> `apply_convolution_filter` (psh.c:1194-1196); `dim_tex==2 && tex_cubemap` -> `vec4 t%d = texture(texSamp%d, remap2DToCube(%s(pT%d.xyw)));` (psh.c:1200-1203); `dim_tex==2` plain -> `vec4 t%d = textureProj(texSamp%d, %s(pT%d.xyw));` (psh.c:1205-1208); `dim_tex==3` -> `textureProj(texSamp%d, vec4(pT%d.xy, 0.0, pT%d.w))` (psh.c:1211-1212). The `%s` is `norm%d` when `rect_tex[i]`, else empty (psh.c:1176). **[V]** |
| `PS_TEXTUREMODES_PROJECT3D` | psh.c:1220-1228 | EMIT-SHADER | `shadow_map[i]` -> shadowmap with `compare_z=true` (psh.c:1222) else `vec4 t%d = textureProj(texSamp%d, %s(pT%d.xyzw));` (psh.c:1225). **[V]** |
| `PS_TEXTUREMODES_CUBEMAP` | psh.c:1229-1238 | EMIT-SHADER | `!tex_cubemap[i]` first emits `pT%d.xy = remapCubeTo2D(pT%d.xyz);` (psh.c:1231-1233); then `vec4 t%d = texture(texSamp%d, pT%d.xy%s);` where `%s` is `"z"` for a real cubemap and `""` otherwise (psh.c:1235-1237). **[V]** |
| `PS_TEXTUREMODES_PASSTHRU` | psh.c:1239-1242 | EMIT-SHADER | `vec4 t%d = pT%d;`. **[V]** |
| `PS_TEXTUREMODES_CLIPPLANE` | psh.c:1243-1253 | EMIT-SHADER | Per channel x/y/z/w emits `if(pT%d.%c %s 0.0) { discard; };` where the operator is `">="` when `compare_mode[i][j]` else `"<"` (psh.c:1248-1250). **[V]** |
| **`PS_TEXTUREMODES_BUMPENVMAP`** | psh.c:1254-1279 | EMIT-SHADER | **The worked example.** `snorm_tex[ps->input_tex[i]]` true -> `vec2 dsdt%d = t%d.bg;` (psh.c:1259-1260); false -> `vec2 dsdt%d = vec2(sign3(t%d.b), sign3(t%d.g));` (psh.c:1263-1264). Then unconditionally `dsdt%d = bumpMat[%d] * dsdt%d;` (psh.c:1267). Sample: `dim_tex==2` -> `vec4 t%d = texture(texSamp%d, %s(pT%d.xy + dsdt%d));` (psh.c:1270-1271); `dim_tex==3` -> `texture(texSamp%d, vec3(pT%d.xy + dsdt%d, pT%d.z))` (psh.c:1274-1275). **[V]** |
| **`PS_TEXTUREMODES_BUMPENVMAP_LUM`** | psh.c:1280-1309 | EMIT-SHADER | `snorm_tex[ps->input_tex[i]]` true -> `vec3 dsdtl%d = vec3(t%d.bg, sign3_to_0_to_1(t%d.r));` (psh.c:1285-1286); false -> `vec3 dsdtl%d = vec3(sign3(t%d.b), sign3(t%d.g), t%d.r);` (psh.c:1289-1290). Note this is a **vec3**, and the luminance component (`.r`) is *also* remapped in the true branch (`sign3_to_0_to_1`) but left raw in the false branch — the two branches differ in **two** places, not one. Then `dsdtl%d.st = bumpMat[%d] * dsdtl%d.st;` (psh.c:1293) and finally `t%d = t%d * (bumpScale[%d] * dsdtl%d.p + bumpOffset[%d]);` (psh.c:1307-1308). **[V]** |
| `PS_TEXTUREMODES_BRDF` | psh.c:1310-1315 | EMIT-SHADER | Always `vec4 t%d = vec4(0.0); /* PS_TEXTUREMODES_BRDF */` + `NV2A_UNIMPLEMENTED`. **[V]** |
| `PS_TEXTUREMODES_DOT_ST` | psh.c:1316-1327 | EMIT-SHADER | `float dot%d = dot(pT%d.xyz, %s(t%d));` where `%s` is `dotmap_funcs[ps->dot_map[i]]` (psh.c:1319-1322), then `vec2 dotST%d = vec2(dot%d, dot%d)` and `vec4 t%d = texture(texSamp%d, %s(dotST%d));` (psh.c:1325-1326). **[V]** |
| `PS_TEXTUREMODES_DOT_ZW` | psh.c:1328-1335 | EMIT-SHADER | Computes `dot%d` then emits `vec4 t%d = vec4(0.0);`. Depth write is commented out at psh.c:1334. **[V]** |
| `PS_TEXTUREMODES_DOT_RFLCT_DIFF` | psh.c:1336-1354 | EMIT-SHADER | Uses **two** dotmaps: `dot_map[i]` for stage i and `dot_map[i+1]` for the neighbour (psh.c:1339-1343). `!tex_cubemap[i]` inserts `n_%d.xy = remapCubeTo2D(n_%d);` (psh.c:1348-1349) and the sample suffix flips between `""` and `".xy"` (psh.c:1353). **[V]** |
| `PS_TEXTUREMODES_DOT_RFLCT_SPEC` | psh.c:1355-1374 | EMIT-SHADER | Emits the reflection vector `rv_%d = 2.0*n_%d*dot(n_%d,e_%d)/dot(n_%d,n_%d) - e_%d;` (psh.c:1364-1365); cubemap-vs-2D suffix as above (psh.c:1367-1373). **[V]** |
| `PS_TEXTUREMODES_DOT_STR_3D` | psh.c:1375-1388 | EMIT-SHADER | Sample suffix `".xy"` when `dim_tex[i]==2`, else `""` (psh.c:1387). **[V]** |
| `PS_TEXTUREMODES_DOT_STR_CUBE` | psh.c:1389-1405 | EMIT-SHADER | `!tex_cubemap[i]` inserts `dotSTR%dCube.xy = remapCubeTo2D(dotSTR%dCube);` (psh.c:1398-1400). **[V]** |
| `PS_TEXTUREMODES_DPNDNT_AR` / `_GB` | psh.c:1406-1421 | EMIT-SHADER | `vec2 t%dAR = t%d.ar;` (psh.c:1409) / `vec2 t%dGB = t%d.gb;` (psh.c:1417), each followed by `texture(texSamp%d, %s(t%dAR\|GB))`. Both `assert(!rect_tex[i])` (psh.c:1408, :1416). **[V]** |
| `PS_TEXTUREMODES_DOTPRODUCT` | psh.c:1422-1428 | EMIT-SHADER | `float dot%d = ...` then `vec4 t%d = vec4(0.0);`. **[V]** |
| `PS_TEXTUREMODES_DOT_RFLCT_SPEC_CONST` | psh.c:1429-1434 | EMIT-SHADER | Always `vec4 t%d = vec4(0.0);` + `NV2A_UNIMPLEMENTED`. **[V]** |
| Sampler uniform declaration | psh.c:1441-1447 | EMIT-SHADER | `opts.vulkan` prepends `layout(binding = %d) ` with `tex_binding + i` (psh.c:1443-1444); then `uniform %s texSamp%d;` (psh.c:1446). **[V]** |
| Alpha kill | psh.c:1449-1453 | EMIT-SHADER | `alphakill[i]` -> `if (t%d.a == 0.0) { discard; };`. Only emitted when a sampler exists (`sampler_type != NULL`, psh.c:1441). **[V]** |
| Colour key comparator + kill | psh.c:1455-1487 | EMIT-SHADER | `colorkey_mode[i] != COLOR_KEY_NONE` emits `check_color_key` once (psh.c:1457-1460, body at psh.c:854-865) then `if (check_color_key(t%d, colorKey[%d], colorKeyMask[%d])) {` (psh.c:1463-1466). Mode selects `"  discard;\n"` (psh.c:1471), `"  t%d.a = 0.0;\n"` (psh.c:1475), or `"  t%d = vec4(0.0);\n"` (psh.c:1479). **[V]** |
| `norm%d()` rect-texture normalizers | psh.c:1489-1505 | EMIT-SHADER | `rect_tex[i]` emits three overloads dividing by `vec2(textureSize(texSamp%d, 0)) / texScale[%d]` (psh.c:1490-1504). **[V]** |
| Shadow map sampling | psh.c:747-800 | EMIT-SHADER | `shadow_depth_func == NEVER` -> `vec4 t%d = vec4(0.0);` (psh.c:750); `== ALWAYS` -> `vec4 t%d = vec4(1.0);` (psh.c:755). Otherwise the operator comes from `shadow_comparison_map[]` (psh.c:738-745, indexed at :762). `tex_x8y24[i] && opts.vulkan` switches the fetch to `uvec4 t%d_depth_raw` + `vec4 t%d_depth = vec4(float(t%d_depth_raw.x >> 8) / 16777215.0, 1.0, 0.0, 0.0);` (psh.c:764-776). `compare_z` selects the runtime max-depth ladder + `pT%d.z = clamp(pT%d.z / pT%d.w, 0.0, t%d_max_depth);` (psh.c:780-793) vs the bare `vec4 t%d = vec4(t%d_depth.x %s 0.0 ? 1.0 : 0.0);` (psh.c:795-798). **[V]** |
| Border adjustment | psh.c:804-820 | EMIT-SHADER | No-op when `border_logical_size[i][0] == 0.0f` (psh.c:807-809). Otherwise emits literal floats for logical size and inverse real size into `%s.xyz = (%s.xyz * t%dLogicalSize + vec3(4.0,4.0,4.0)) * vec3(%f,%f,%f);` (psh.c:814-819) — i.e. **numeric literals baked into the shader text**, so a change in the border-size computation at psh.c:180-208 produces a different shader string and a different cache entry. **[V]** |
| Convolution filter | psh.c:822-852 | EMIT-SHADER | 9-tap unrolled `textureProj(texSamp%d, convBase + vec3(vec2(%.1f,%.1f)*convTexelSize, 0.0)) * %s` (psh.c:846-849) with the fixed weights at psh.c:832-836. Note it always emits the **Gaussian** weights even when `conv_tex[i] == CONVOLUTION_FILTER_QUINCUNX` (dispatch at psh.c:1194-1196 treats both the same). **[V]** |
| Combiner input remapping | psh.c:398-462 | EMIT-SHADER | Channel suffix: `.rgb` / `.aaa` for RGB stages (psh.c:405, :408), `.b` / `.a` for alpha stages (psh.c:417, :420). Then the 8 `PS_INPUTMAPPING` cases each emit a distinct expression: `max(%s, 0.0)` (psh.c:431), `(1.0 - clamp(%s, 0.0, 1.0))` (:434), `(2.0 * max(%s, 0.0) - 1.0)` (:437), `(-2.0 * max(%s, 0.0) + 1.0)` (:440), `(max(%s, 0.0) - 0.5)` (:443), `(-max(%s, 0.0) + 0.5)` (:446), identity (:449-450), `-%s` (:453). **[V]** |
| Combiner register naming | psh.c:325-396 | EMIT-SHADER | `PS_REGISTER_DISCARD` -> `""` (dest) or `"vec4(0.0)"` (src) (psh.c:330, :332). `PS_COMBINERCOUNT_UNIQUE_C0`/`_C1` or final stage -> `c0_%d`/`c1_%d` per stage, else `c0_0`/`c1_0` (psh.c:336-353). `PS_REGISTER_V1R0_SUM` emits `clamp(vec4(%s.rgb + %s.rgb, 0.0), 0.0, 1.0)` when `final_input.clamp_sum` else the unclamped `vec4(%s.rgb + %s.rgb, 0.0)`, with each operand `(1.0 - v1)`/`v1` and `(1.0 - r0)`/`r0` selected by `inv_v1`/`inv_r0` (psh.c:377-387). **[V]** |
| Combiner output mapping (shift/bias) | psh.c:464-492 | EMIT-SHADER | 6 cases: identity, `(%s - 0.5)` (:473), `(%s * 2.0)` (:476), `((%s - 0.5) * 2.0)` (:479), `(%s * 4.0)` (:482), `(%s / 2.0)` (:485). **[V]** |
| Combiner stage body | psh.c:494-634 | EMIT-SHADER | AB/CD select `dot(%s, %s)` vs `(%s * %s)` from `output.ab_op`/`cd_op` (psh.c:523-540). Writes emit `ab.%s = clamp(%s(%s), -1.0, 1.0);` (psh.c:553-554), same for `cd` (:563) and `mux_sum` (:590). The `%s(` caster is `"vec3"` for a 3-char write mask, `""` otherwise (psh.c:515-518). Mux emits `((%s) ? %s(%s) : %s(%s))` where the condition is `"r0.a >= 0.5"` when `PS_COMBINERCOUNT_MUX_MSB` else `"(uint(r0.a * 255.0) & 1u) == 1u"` (psh.c:580-585). Blue-to-alpha flags emit `%s.a = ab.b;` / `%s.a = cd.b;` (psh.c:601-602, :610-611). **[V]** |
| Final combiner | psh.c:636-661 | EMIT-SHADER | `fragColor.rgb = %s + mix(vec3(%s), vec3(%s), vec3(%s));` (psh.c:647-649) and `fragColor.a = %s;` (psh.c:650). Enabled only when `final_inputs_0 \|\| final_inputs_1` (psh.c:1666, gate at :1521). **[V]** |
| Alpha test | psh.c:1527-1548 | EMIT-SHADER | Gated on `alpha_test && alpha_func != ALPHA_FUNC_ALWAYS` (psh.c:1527). `ALPHA_FUNC_NEVER` -> bare `discard;` (psh.c:1529). Otherwise the operator string (`<`,`==`,`<=`,`>`,`!=`,`>=`, psh.c:1533-1538) is substituted into `int fragAlpha = int(round(fragColor.a * 255.0));\nif (!(fragAlpha %s alphaRef)) discard;` (psh.c:1543-1546). **[V]** |
| `r0.a` initialization | psh.c:1550-1559 | EMIT-SHADER | If `r0` is referenced, `tex_modes[0] != PS_TEXTUREMODES_NONE` -> `r0.a = t0.a;` (psh.c:1554) else `r0.a = 1.0;` (psh.c:1556). This feeds the MUX condition emitted at psh.c:580-585. **[V]** |
| Depth write | psh.c:1561-1578 | EMIT-SHADER | Gated on `depth_needed`. `DEPTH_FORMAT_D16` -> `gl_FragDepth = floor(zvalue) / 65535.0;` (psh.c:1566); `DEPTH_FORMAT_D24` -> `gl_FragDepth = uintBitsToFloat(floatBitsToUint(floor(zvalue) / 16777216.0) + 1u);` (psh.c:1571); F16/F24 fall through to `gl_FragDepth = zvalue / clipRange.y;` (psh.c:1575). **[V]** |
| Final assembly | psh.c:1580-1594 | EMIT-SHADER | Order: version prologue, preflight, `void main() {`, clip, vars, code, `}` (psh.c:1581-1588). **[V]** |
| Combiner control word parsing | psh.c:1597-1627, 1638-1678 | READ | `num_stages = combiner_control & 0xFF` (psh.c:1638); `flags = combiner_control >> 8` (:1639); `tex_modes[i] = (shader_stage_program >> (i*5)) & 0x1F` (:1641); `dot_map[1..3]` from `other_stage_input` bits 0/4/8 (:1645-1647); `input_tex[2]`/`[3]` from bits 16/20 (:1651-1652), with `input_tex[0] = -1` and `input_tex[1] = 0` hardcoded (:1649-1650). **[V]** |

### EMIT-SHADER sites — vertex shader (vsh.c / vsh-ff.c / vsh-prog.c)

| concept | file:line | role | notes |
|---|---|---|---|
| VSH uniform block / `inlineValue` elision | vsh.c:163-180 | EMIT-SHADER | `inlineValue` is skipped entirely when `!state->uniform_attrs \|\| opts.use_push_constants_for_uniform_attrs` (vsh.c:168-171). **[V]** |
| Static VSH header (matrix defines, helpers) | vsh.c:182-233 | EMIT-SHADER | Includes `decompress_11_11_10` (vsh.c:204-209), `clampAwayZeroInf` (:212-219), `NaNToOne`/`NaNToValue` (:221-226), `roundScreenCoords` doing `trunc(pos*16.0)/16.0` (:231-233). **[V]** |
| `v_`-prefixed outputs when a geometry shader follows | vsh.c:238-255 | EMIT-SHADER | `opts.prefix_outputs` emits 14 `#define vtxX v_vtxX` lines. Set from `need_geometry_shader` at gl/shaders.c:293 and vk/shaders.c:756. **[V]** |
| Per-attribute input declarations | vsh.c:260-284 | EMIT-SHADER | Three-way: `uniform_attrs` bit -> `vec4 v%d = inlineValue[%d];` (vsh.c:269); `compressed_attrs` bit -> `layout(location = %d) in int v%d_cmp;` (:274-275); `swizzle_attrs` bit -> `layout(location = %d) in vec4 v%d_sw;` (:277); else plain `in vec4 v%d` (:280). **[V]** |
| Attribute decode in body | vsh.c:290-300 | EMIT-SHADER | `compressed_attrs` -> `vec4 v%d = decompress_11_11_10(v%d_cmp);` (vsh.c:292-293); `swizzle_attrs` -> `vec4 v%d = v%d_sw.bgra;` (:297). **[V]** |
| FF vs programmable body | vsh.c:302-314 | DISPATCH | `is_fixed_function` -> `pgraph_glsl_gen_vsh_ff` (vsh.c:303) else `pgraph_glsl_gen_vsh_prog` (:305-307) plus a point-size fallback when `!point_params_enable` (:308-313). **[V]** |
| **Fog factor** | vsh.c:316-399 | EMIT-SHADER | `!fog_enable` -> `oFog = vec4(1.0);` (vsh.c:318). Otherwise: programmable path first emits `float fogDistance = oFog.x;` (vsh.c:327). Then `fog_mode` selects: LINEAR/LINEAR_ABS -> `fogFactor = fogParam.x + fogDistance * fogParam.y;` then `fogFactor -= 1.0;` (vsh.c:345-346); EXP/EXP_ABS -> `fogFactor = fogParam.x + exp2(fogDistance * fogParam.y * 16.0);` then `-= 1.5` (vsh.c:358-359); EXP2/EXP2_ABS -> `fogFactor = fogParam.x + exp2(-fogDistance*fogDistance*fogParam.y*fogParam.y*32.0);` then `-= 1.5` (vsh.c:369-370). `_ABS` variants append `fogFactor = abs(fogFactor);` (vsh.c:380). Finally the exceptional-value clamp `if (isinf(fogDistance)) { oFog = vec4(%f); } else { oFog = clamp(NaNToValue(vec4(fogFactor), %f), -FLOAT_MAX, FLOAT_MAX); }` (vsh.c:390-397) — the two `%f` are `infinite_fogdistance_result` and `nan_fogfactor_result`, which are **1.0 for LINEAR/LINEAR_ABS and EXP, but 0.0 for EXP_ABS, EXP2 and EXP2_ABS** (set at vsh.c:343-344, :349-350; note EXP falls through into EXP_ABS at vsh.c:351 *after* setting them, so EXP_ABS alone keeps 0.0). **[V]** |
| Varying writes | vsh.c:401-415 | EMIT-SHADER | Unconditional block; `vtxFog = oFog.x;` (vsh.c:404); `vtxPos0/1/2 = vtxPos` and `triMZ = 0.0` (vsh.c:409-412) — these are the degenerate values used when **no geometry shader** runs. **[V]** |
| **Specular varyings** | vsh.c:417-434 | EMIT-SHADER | `specular_enable` -> `vtxD1 = clamp(NaNToOne(oD1), 0.0, 1.0); vtxB1 = clamp(NaNToOne(oB1), 0.0, 1.0);` (vsh.c:419-420), plus `vtxD1.w = 1.0; vtxB1.w = 1.0;` when `ignore_specular_alpha` (vsh.c:424-427). Else `vtxD1 = vec4(0.0, 0.0, 0.0, 1.0); vtxB1 = vec4(0.0,0.0,0.0,1.0);` (vsh.c:431-432). **[V]** |
| Clip-space Z convention | vsh.c:436-444 | EMIT-SHADER | `opts.vulkan` -> `gl_Position = oPos;` (vsh.c:438); GL -> `gl_Position = vec4(oPos.x, oPos.y, 2.0*oPos.z - oPos.w, oPos.w);` (vsh.c:442). **The single most important VK/GL text divergence in the vertex shader.** **[V]** |
| Push-constant `inlineValue` block | vsh.c:453-469 | EMIT-SHADER | Vulkan-only; `opts.vertex_push_offset > 0` adds `layout(offset = %d)` (vsh.c:456-461). **[V]** |
| FF: skinning | vsh-ff.c:26-65, 147-176 | EMIT-SHADER | 7 skinning modes map to (mix,count) pairs (vsh-ff.c:149-167). `count==0` -> `%s %s = (%s * %s0).%s;` (vsh-ff.c:32-33). `mix` true -> the weight-sum-unity loop with `weight_n` (vsh-ff.c:38-54); false -> per-weight accumulation (vsh-ff.c:58-61). **[V]** |
| FF: normal renormalization | vsh-ff.c:178-180 | EMIT-SHADER | `normalization` -> `tNormal = normalize(tNormal);`. **[V]** |
| FF: texgen (4 stages x 4 channels) | vsh-ff.c:182-244 | EMIT-SHADER | Per channel: DISABLE -> `oT%d.%c = texture%d.%c;` (vsh-ff.c:193); EYE_LINEAR -> `dot(texPlane%c%d, tPosition)` (:197); OBJECT_LINEAR -> `dot(texPlane%c%d, position)` (:201); SPHERE_MAP -> the `u`/`r`/`invM` block ending `oT%d.%c = r.%c * invM + 0.5;` (:206-222, asserts `j < 2` at :205); REFLECTION_MAP -> `oT%d.%c = r.%c;` (:226-232, asserts `j < 3` at :225); NORMAL_MAP -> `oT%d.%c = tNormal.%c;` (:236, asserts `j < 3` at :235). **[V]** |
| FF: texture matrix | vsh-ff.c:246-252 | EMIT-SHADER | `texture_matrix_enable[i]` -> `oT%d = oT%d * texMat%d;`. **[V]** |
| FF: lighting off | vsh-ff.c:254-258 | EMIT-SHADER | `oD0 = diffuse; oD1 = specular; oB0 = backDiffuse; oB1 = backSpecular;`. **[V]** |
| FF: material colour sources | vsh-ff.c:261-286 | EMIT-SHADER | `diffuse_src` picks the alpha source string `"diffuse.a"` / `"specular.a"` / `"material_alpha"` (vsh-ff.c:261-269). `ambient_src` picks `oD0 = vec4(sceneAmbientColor, %s);` / `vec4(diffuse.rgb, %s)` / `vec4(specular.rgb, %s)` (vsh-ff.c:271-277). `emission_src` picks the `oD0.rgb +=` operand (vsh-ff.c:280-286). **[V]** |
| FF: local eye | vsh-ff.c:290-294 | EMIT-SHADER | `local_eye` -> `vec3 VPeye = normalize(eyePosition.xyz / eyePosition.w - tPosition.xyz / tPosition.w);`. **[V]** |
| FF: per-light code | vsh-ff.c:296-417 | EMIT-SHADER | `light[i] == LIGHT_OFF` skips the light entirely (vsh-ff.c:297-299) — light count changes the shader text, not a uniform. LOCAL/SPOT emit the range/attenuation preamble, with the half-vector operand `"VPeye"` vs `"vec3(0.0, 0.0, 0.0)"` chosen by `local_eye` (vsh-ff.c:306-320). INFINITE emits `attenuation = 1.0` plus `nDotHV` from either `normalize(lightDirection + VPeye)` or `lightInfiniteHalfVector[%d]` again by `local_eye` (vsh-ff.c:328-343). **SPOT** emits the `spotDir`/`cosHalfPhi`/`cosHalfTheta`/`rho` block (vsh-ff.c:350-363). Specular exponent is always `pf = pow(nDotHV, specularPower);` (vsh-ff.c:375). `diffuse_src` selects the `oD0.xyz +=` form (vsh-ff.c:385-398) and `specular_src` the `oD1.xyz +=` form (vsh-ff.c:400-413). **[V]** |
| FF: specular combine | vsh-ff.c:424-446 | EMIT-SHADER | `!specular_enable` -> `oD1 = vec4(0.0,0.0,0.0,1.0); oB1 = vec4(0.0,0.0,0.0,1.0);` (vsh-ff.c:425-426). Else `!separate_specular` folds specular into diffuse: `oD0.xyz += oD1.xyz; oB0.xyz += oB1.xyz;` (only when lighting is on, vsh-ff.c:429-434) then `oD1 = specular; oB1 = backSpecular;` (:435-438). `ignore_specular_alpha` -> `oD1.a = 1.0; oB1.a = 1.0;` (:441-444). **[V]** |
| **FF: foggen (fog distance)** | vsh-ff.c:448-473 | EMIT-SHADER | Gated on `state->fog_enable` (vsh-ff.c:448). SPEC_ALPHA -> `float fogDistance = clamp(specular.a, 0.0, 1.0);` (:453); RADIAL -> `length(tPosition.xyz)` (:456); PLANAR/ABS_PLANAR -> `dot(fogPlane.xyz, tPosition.xyz) + fogPlane.w` (:460) with `fogDistance = abs(fogDistance);` appended for ABS_PLANAR (:462); FOG_X -> `fogCoord` (:466). **[V]** |
| FF: position transform | vsh-ff.c:475-490 | EMIT-SHADER | `skinning == SKINNING_OFF` first emits `tPosition = position;` (vsh-ff.c:477). Then the fixed block ending `oPos.xy = (2.0*oPos.xy - surfaceSize) / surfaceSize; oPos.xy *= oPos.w;` (vsh-ff.c:480-490). **[V]** |
| FF: point size | vsh-ff.c:492-506 | EMIT-SHADER | `point_params_enable` -> the distance-attenuated `oPts.x` expression with `pointParams[0..7]` and a `63.875` clamp (vsh-ff.c:493-501); else the literal `oPts.x = %f * float(%d);` with `MAX(1.f, point_size)` and `surface_scale_factor` baked in (vsh-ff.c:503-505). **[V]** |
| Programmable VSH opcode library | vsh-prog.c:523-724 | EMIT-SHADER | Static header defining R0-R11, `#define R12 oPos` (vsh-prog.c:539) and the macro/function pairs for MOV, MUL, ADD, MAD, DP3, DPH, DP4, DST, MIN, MAX, SLT, ARL, SGE, RCP, RCC, RSQ, EXP, LOG, LIT (vsh-prog.c:564-724). `_MUL` implements NV2A's "anything * 0 == 0" via per-component sign checks (vsh-prog.c:571-583). `_ARL` applies a `+0.001` rounding bias (vsh-prog.c:654). `_RSQ` maps 0 -> `INFINITY` and inf -> 0 (vsh-prog.c:679-680). `_LIT` clamps `s.w` to +/-(128 - 1/256) (vsh-prog.c:713). **[V]** |
| Programmable VSH token emission | vsh-prog.c:726-772 | EMIT-SHADER | Emits `/* Slot %d: 0x%08X ... */` plus the decoded instruction per token (vsh-prog.c:739-743). The raw token bytes are in the shader-state hash (`program_data` at vsh.h:46, hashed at shaders.c:33-36), so the text is a pure function of the tokens. Epilogue at vsh-prog.c:753-771. **[V]** |
| Programmable VSH: MAC/ILU pairing | vsh-prog.c:377-427 | EMIT-SHADER | Emits `ARL(_temp_addr%s)` + `A0 = _temp_addr;` or `%s(_temp_vec%s%s)` + `R%d = _temp_vec;` when a temp is needed (vsh-prog.c:404-419), else direct `ARL(A0%s)` / `%s(R%d%s%s)` (:424-426). **[V]** |

### EMIT-SHADER sites — geometry shader (geom.c)

| concept | file:line | role | notes |
|---|---|---|---|
| Need-geom decision | geom.c:48-60 | DISPATCH | True only for `PRIM_TYPE_LINES` / `PRIM_TYPE_TRIANGLES` (geom.c:54-56). **[V]** |
| Layout + body selection | geom.c:75-115 | EMIT-SHADER | POINTS -> returns NULL (geom.c:76). LINES -> `layout(lines) in;` / `layout(line_strip, max_vertices = 2) out;` / `emit_line(0, 1, 0.0);` (geom.c:79-81). TRIANGLES x `polygon_front_mode`: FILL -> `triangle_strip, max_vertices = 3` + 3 `emit_vertex` (geom.c:87-92); LINE -> `line_strip, max_vertices = 6` + 3 `emit_line` (geom.c:95-99); POINT -> `points, max_vertices = 3` + 3 collapsed `emit_vertex` (geom.c:102-109). **[V]** |
| **Provoking vertex** | geom.c:73, 143-164 | EMIT-SHADER | `const char *provoking_index = state->smooth_shading ? "index" : "0";` (geom.c:73), substituted into `vtxD0/vtxD1/vtxB0/vtxB1 = v_vtxX[%s];` (geom.c:145-148, args at :161-164). Flat shading therefore hard-wires vertex 0 as provoking. **[V]** |
| `gl_PointSize` passthrough | geom.c:139-142 | EMIT-SHADER | Emitted **only when `!opts.gles`** (geom.c:139) — GLES geometry shaders omit `gl_PointSize`. **[V]** |
| `calc_triz` | geom.c:166-218 | EMIT-SHADER | `need_triz`; `z_perspective` selects the W-based variant (geom.c:187-200) vs the Z-based variant (geom.c:204-216). Both use `kahan_det` (geom.c:177-182). **[V]** |
| `emit_line` | geom.c:220-233 | EMIT-SHADER | Synthesizes a third vertex rotated 90 degrees so the fragment shader's triangle interpolation works for lines. **[V]** |

### EMIT-SHADER sites — shared (common.c)

| concept | file:line | role | notes |
|---|---|---|---|
| Varying block | common.c:28-68 | EMIT-SHADER | 14 varyings. `smooth` selects `""` vs `"flat "` for `vtxD0/D1/B0/B1` only (common.c:33, table at :42-45); `vtxFog`, `vtxT0..3`, `vtxPointSize` are always smooth; `vtxPos0/1/2` and `triMZ` are always `flat` (common.c:51-54). `location` adds `layout(location = %d)` (common.c:59-61); `prefix` adds `v_` (:37); `array` adds `[]` (:38). **[V]** |
| Version + precision prologue | common.c:70-93 | EMIT-SHADER | `vulkan` -> `#version 450` (common.c:74); `gles` -> `#version %d es` with `gles_version ? gles_version : 300` plus six `precision highp` lines including `usampler2D` (common.c:78-89); otherwise `#version 400` (common.c:92). **[V]** |

### Uniform-value plumbing (READ sites; no GLSL text)

| concept | file:line | role | notes |
|---|---|---|---|
| PSH uniform values | psh.c:1683-1852 | READ | `consts` from `NV_PGRAPH_COMBINEFACTOR0/1` and `NV_PGRAPH_SPECFOGFACTOR0/1` (psh.c:1687-1707); `alphaRef` (:1708-1712); `colorKey` (:1713-1718); `colorKeyMask` via `get_colorkey_mask` (:1719-1724, mask table at psh.c:40-52); `bumpMat`/`bumpScale`/`bumpOffset` for stages 1..3 only (:1726-1750); `fogColor` (:1756-1766); `clipRange` (:1768-1770); `depthOffset`/`depthFactor` gated on polygon-offset enable (:1772-1818); `surfaceScale` (:1820-1826); `clipRegion` (:1832-1851). **[V]** |
| VSH uniform values | vsh.c:499-601 | READ | `fogParam` from `NV_PGRAPH_FOGPARAM0/1` (vsh.c:513-518); light arrays and `specularPower` only when `is_fixed_function` (vsh.c:545-600). **[V]** |
| GL uniform upload | gl/shaders.c:804-884 | WRITE | Type-dispatched `glUniform*v` (gl/shaders.c:819-849). `texScale[i]` overridden from the texture binding only when `r->texture_binding[i] != NULL` (gl/shaders.c:876-881). **[V]** |
| VK uniform upload | vk/shaders.c:1183-1236 | WRITE | `texScale[i]` overridden unconditionally, and forced to `1.0` for non-linear formats (vk/shaders.c:1197-1205). **[V]** |

---

## State-to-shader-text map

The headline table. "GLSL text it selects" quotes the format string as it appears in the source.

| pgraph state | struct field it travels in | where set (file:line) | where read (file:line) | GLSL text it selects |
|---|---|---|---|---|
| Texture colour format == `SZ_R6G5B5` (and renderer == OpenGL) | `PshState.snorm_tex[4]` | psh.c:219-222 | psh.c:1257, psh.c:1283 | BUMPENVMAP: `vec2 dsdt%d = t%d.bg;` (psh.c:1259) **vs** `vec2 dsdt%d = vec2(sign3(t%d.b), sign3(t%d.g));` (psh.c:1263). BUMPENVMAP_LUM: `vec3 dsdtl%d = vec3(t%d.bg, sign3_to_0_to_1(t%d.r));` (psh.c:1285) **vs** `vec3 dsdtl%d = vec3(sign3(t%d.b), sign3(t%d.g), t%d.r);` (psh.c:1289). Indexed by `ps->input_tex[i]` (the *source* stage), not by `i`. |
| `kelvin_color_format_info_map[fmt].linear` | `PshState.rect_tex[4]` | psh.c:160-161 | psh.c:760, 827, 1176, 1489 | Substitutes `norm%d` vs `""` into every `textureProj`/`texture` call, and emits the three `norm%d()` overloads `return coord / (vec2(textureSize(texSamp%d, 0)) / texScale[%d]);` (psh.c:1490-1504). Also asserted absent for point sprites (psh.c:1155) and DPNDNT modes (psh.c:1408, :1416). |
| `kelvin_color_format_info_map[fmt].depth` | `PshState.shadow_map[4]` | psh.c:224 | psh.c:694, 708, 717, 729, 1190, 1221 | Routes PROJECT2D/PROJECT3D to `psh_append_shadowmap` (psh.c:1191, :1222); forces `sampler2D` for PROJECT3D/DOT_STR_3D (psh.c:709); **aborts** for BUMPENVMAP/DOT_ST/CUBEMAP/DOT_*/DPNDNT_* (psh.c:696, :719, :731). |
| Colour format `LU_IMAGE_DEPTH_X8_Y24_{FIXED,FLOAT}` | `PshState.tex_x8y24[4]` | psh.c:162-166 | psh.c:679, 705, 764 | Vulkan only: `"usampler2D"` instead of `sampler2D` (psh.c:680, :706), and `uvec4 t%d_depth_raw` + `vec4 t%d_depth = vec4(float(t%d_depth_raw.x >> 8) / 16777215.0, 1.0, 0.0, 0.0);` (psh.c:766-776). |
| `NV_PGRAPH_TEXFMT0_DIMENSIONALITY` | `PshState.dim_tex[4]` | psh.c:157 | psh.c:669, 824, 1198, 1210, 1269, 1272, 1296, 1299, 1387 | `sampler2D` vs `sampler3D` (psh.c:687, :698-699, :711); `textureProj(..., pT%d.xyw)` vs `textureProj(..., vec4(pT%d.xy, 0.0, pT%d.w))` (psh.c:1207 vs :1211); bump sample `%s(pT%d.xy + dsdt%d)` vs `vec3(pT%d.xy + dsdt%d, pT%d.z)` (psh.c:1270 vs :1274); DOT_STR_3D suffix `".xy"` vs `""` (psh.c:1387). Any other value hits `assert(!"Unhandled texture dimensions")`. |
| `NV_PGRAPH_TEXFMT0_CUBEMAPENABLE` | `PshState.tex_cubemap[4]` | psh.c:170-171 | psh.c:682, 722, 1199, 1230, 1237, 1347, 1353, 1367, 1373, 1397, 1404 | `samplerCube` vs `sampler2D` (psh.c:683, :723); `texture(texSamp%d, remap2DToCube(...))` vs `textureProj(...)` (psh.c:1202 vs :1207); insertion of `X.xy = remapCubeTo2D(X);` (psh.c:1232, :1349, :1369, :1399); sample-argument suffix `""` vs `".xy"` / `"z"` vs `""` (psh.c:1237, :1353, :1373, :1404). |
| `NV_PGRAPH_TEXFMT0_BORDER_SOURCE` + BASE_SIZE_U/V/P | `PshState.border_logical_size[4][3]`, `.border_inv_real_size[4][3]` | psh.c:168-208 | psh.c:807, 816-819, 1240 | Emits literal floats into `vec3 t%dLogicalSize = vec3(%f, %f, %f);` and `%s.xyz = (%s.xyz * t%dLogicalSize + vec3(4.0, 4.0, 4.0)) * vec3(%f, %f, %f);` (psh.c:816-819). Zero logical size emits nothing (psh.c:807-809). |
| `NV_PGRAPH_TEXFILTER0_MIN == CONVOLUTION_2D_LOD0` + kernel | `PshState.conv_tex[4]` | psh.c:226-240 | psh.c:1194-1196 | Replaces the single `textureProj` with the 9-tap unrolled sum at psh.c:838-851. **Both** QUINCUNX and GAUSSIAN produce identical text (psh.c:1194-1195). |
| `NV_PGRAPH_TEXCTL0_0_ALPHAKILLEN` | `PshState.alphakill[4]` | psh.c:153 | psh.c:1450 | `if (t%d.a == 0.0) { discard; };` (psh.c:1451). |
| `NV_PGRAPH_TEXCTL0_0_COLORKEYMODE` | `PshState.colorkey_mode[4]` | psh.c:154 | psh.c:1455-1487 | `check_color_key` definition (psh.c:857-863) + `if (check_color_key(t%d, colorKey[%d], colorKeyMask[%d])) {` (psh.c:1465) with body `discard;` / `t%d.a = 0.0;` / `t%d = vec4(0.0);` (psh.c:1471, :1475, :1479). |
| `NV_PGRAPH_SHADERCLIPMODE` bits (4x4) | `PshState.compare_mode[4][4]` | psh.c:142-143 | psh.c:1250 | `if(pT%d.%c >= 0.0) { discard; };` vs `if(pT%d.%c < 0.0) { discard; };` (psh.c:1248-1250). |
| `NV_PGRAPH_SHADOWCTL_SHADOW_ZFUNC` | `PshState.shadow_depth_func` | psh.c:103-105 | psh.c:749, 754, 762 | `vec4 t%d = vec4(0.0);` (NEVER, psh.c:750); `vec4 t%d = vec4(1.0);` (ALWAYS, psh.c:755); otherwise one of `<`, `==`, `<=`, `>`, `!=`, `>=` from `shadow_comparison_map` (psh.c:739-744) into `vec4 t%d = vec4(t%d_depth.x %s pT%d.z ? 1.0 : 0.0);` (psh.c:790) or `... %s 0.0 ...` (psh.c:797). |
| `NV_PGRAPH_SETUPRASTER_POINTSMOOTHENABLE` | `PshState.point_sprite` | psh.c:100-101 | psh.c:1154 | `vec4 pT3 = vec4(gl_PointCoord, 1.0, 1.0);` vs `vec4 pT3 = vtxT3;` (psh.c:1156 vs :1158). |
| `NV_PGRAPH_CONTROL_0_ALPHATESTENABLE` / `_ALPHAFUNC` | `PshState.alpha_test`, `.alpha_func` | psh.c:95-98 | psh.c:1527-1546 | Nothing / `discard;` (NEVER) / `int fragAlpha = int(round(fragColor.a * 255.0));\nif (!(fragAlpha %s alphaRef)) discard;` with the operator from psh.c:1533-1538. |
| `NV_PGRAPH_SETUPRASTER_WINDOWCLIPTYPE` | `PshState.window_clip_exclusive` | psh.c:64-65 | psh.c:1043, 1045, 1057, 1071, 1081 | `"Exc"`/`"Inc"` in the comment (psh.c:1043); `discard;` inside the region test vs `clipContained = true;` + trailing `if (!clipContained) { discard; }` (psh.c:1058/1060, :1072/1074, :1082-1084). |
| Non-trivial `NV_PGRAPH_WINDOWCLIPX0/Y0` region count | `PshState.window_clip_count` | psh.c:69-87 (**skipped for OpenGL**) | psh.c:1039, 1041, 1050, 1070 | 0 -> no clip code at all; 1 -> unrolled `clipRegion[0]` block (psh.c:1051-1063); N>1 -> `for (int i = 0; i < %d; i++)` loop (psh.c:1066-1070). |
| Depth test/write enable OR depth clipping | `PshState.depth_needed` | psh.c:120-126 (**skipped for OpenGL**) | psh.c:1025, 1088, 1561 | Emits/omits `kahan_det`+`area` (psh.c:1027-1035), the whole barycentric Z reconstruction (psh.c:1090-1142), and the `gl_FragDepth = ...` write (psh.c:1564-1576). |
| `NV_PGRAPH_ZCOMPRESSOCCLUDE_ZCLAMP_EN` | `PshState.depth_clipping` | psh.c:113-116 | psh.c:1134 | `if (zvalue < clipRange.z \|\| clipRange.w < zvalue) { discard; }` vs `zvalue = clamp(zvalue, clipRange.z, clipRange.w);` (psh.c:1136-1141). |
| `NV_PGRAPH_CONTROL_0_Z_PERSPECTIVE_ENABLE` | `PshState.z_perspective`, `VshState.z_perspective`, `GeomState.z_perspective` | psh.c:106-107, vsh.c:128-129, geom.c:44-45 | psh.c:1089, geom.c:184 | psh: W-buffered Z block (psh.c:1090-1115) vs Z-buffered block (psh.c:1117-1131). geom: `calc_triz` W-variant (geom.c:187-200) vs Z-variant (geom.c:204-216). |
| `pg->surface_shape.zeta_format` + `NV_PGRAPH_SETUPRASTER_Z_FORMAT` | `PshState.depth_format` | psh.c:243-261 | psh.c:1562 | `gl_FragDepth = floor(zvalue) / 65535.0;` (D16, psh.c:1566) / `gl_FragDepth = uintBitsToFloat(floatBitsToUint(floor(zvalue) / 16777216.0) + 1u);` (D24, psh.c:1571) / `gl_FragDepth = zvalue / clipRange.y;` (F16, F24, psh.c:1575). |
| `NV_PGRAPH_CONTROL_3_SHADEMODE` | `PshState.smooth_shading`, `VshState.smooth_shading`, `GeomState.smooth_shading` | psh.c:109-111, vsh.c:140-142, geom.c:40-42 | psh.c:871, vsh.c:235, geom.c:73/130/132 | Varying qualifier `""` vs `"flat "` on `vtxD0/D1/B0/B1` (common.c:33, :42-45); geometry-shader provoking index `"index"` vs `"0"` (geom.c:73). |
| `NV_PGRAPH_COMBINECTL & 0xFF` | `PshState.combiner_control` | psh.c:89 | psh.c:1638, 1653, 1509 | Number of `// Stage %d` blocks emitted (psh.c:1509-1519). |
| `NV_PGRAPH_COMBINECTL >> 8` (MUX_MSB, UNIQUE_C0/C1) | `PshState.combiner_control` | psh.c:89 | psh.c:336, 346, 581, 1639 | `c0_%d`/`c1_%d` vs `c0_0`/`c1_0` (psh.c:337-352); mux condition `"r0.a >= 0.5"` vs `"(uint(r0.a * 255.0) & 1u) == 1u"` (psh.c:581-583). |
| `NV_PGRAPH_SHADERPROG` (4x5 bits) | `PshState.shader_stage_program` | psh.c:90 | psh.c:1641, 1184, 1553 | Selects one of 19 `PS_TEXTUREMODES` bodies (psh.c:1184-1439) per stage, and `r0.a = t0.a;` vs `r0.a = 1.0;` (psh.c:1553-1557). |
| `NV_PGRAPH_SHADERCTL` low 12 bits (dotmap) | `PshState.other_stage_input` | psh.c:91 | psh.c:1179, 1645-1647 | Selects one of 8 `dotmap_*` function names substituted into `dot(pT%d.xyz, %s(t%d))` (psh.c:1320, :1331, :1339, :1358, :1379, :1392, :1425). |
| `NV_PGRAPH_SHADERCTL` bits 16-23 (input_tex) | `PshState.other_stage_input` | psh.c:91 | psh.c:1651-1652, 1257, 1283, 1322, 1332, 1340, 1359, 1381, 1393, 1409, 1417, 1426 | Chooses **which `t%d` register** the dependent/dot/bump modes sample from, and (critically) which `snorm_tex[]` slot gates the bump sign remap. |
| `NV_PGRAPH_COMBINESPECFOG0/1` | `PshState.final_inputs_0/1` | psh.c:92-93 | psh.c:1666-1678, 1521 | Presence of the whole `// Final Combiner` block (psh.c:1523-1524); `clamp_sum`/`inv_v1`/`inv_r0` flags select the `PS_REGISTER_V1R0_SUM` expression (psh.c:377-387). |
| Per-stage combiner CWs | `PshState.rgb_inputs/outputs`, `.alpha_inputs/outputs` | psh.c:129-138 | psh.c:1654-1662, 1512-1513 | The entire per-stage arithmetic text (psh.c:494-634). |
| `NV_PGRAPH_CSV0_D_MODE` | `VshState.is_fixed_function` | vsh.c:104-108, :153 | vsh.c:302 | Whole-body swap: `pgraph_glsl_gen_vsh_ff` (vsh-ff.c:67-507) vs `pgraph_glsl_gen_vsh_prog` (vsh-prog.c:726-772). |
| `NV_PGRAPH_CONTROL_3_FOGENABLE` | `VshState.fog_enable` | vsh.c:144-145 | vsh.c:316, vsh-ff.c:448 | `oFog = vec4(1.0);` (vsh.c:318) vs the full fog-factor block (vsh.c:320-398); and presence/absence of the `fogDistance` computation (vsh-ff.c:448-473). |
| `NV_PGRAPH_CONTROL_3_FOG_MODE` | `VshState.fog_mode` | vsh.c:148-150 | vsh.c:335, 376 | Three distinct `fogFactor` formulas (vsh.c:345-346, :358-359, :369-370), the optional `fogFactor = abs(fogFactor);` (vsh.c:380), and the two `%f` literals for inf/NaN fog distance (vsh.c:390-397). |
| `NV_PGRAPH_CSV0_D_FOGGENMODE` | `VshState.fixed_function.foggen` | vsh.c:77-80 | vsh-ff.c:450, 461 | Five `float fogDistance = ...` variants (vsh-ff.c:453, :456, :460, :466) plus the ABS_PLANAR `abs()` (vsh-ff.c:462). |
| `NV_PGRAPH_CSV0_C_SPECULAR_ENABLE` | `VshState.specular_enable` | vsh.c:118-119 | vsh.c:417, vsh-ff.c:424 | `vtxD1 = clamp(NaNToOne(oD1), 0.0, 1.0);` (vsh.c:419) vs `vtxD1 = vec4(0.0, 0.0, 0.0, 1.0);` (vsh.c:431); `oD1 = vec4(0.0,0.0,0.0,1.0);` (vsh-ff.c:425). |
| `NV_PGRAPH_CSV0_C_SEPARATE_SPECULAR` | `VshState.separate_specular` | vsh.c:120-121 | vsh-ff.c:428 | Presence of `oD0.xyz += oD1.xyz; oB0.xyz += oB1.xyz;` + `oD1 = specular;` (vsh-ff.c:430-438). |
| `NV_PGRAPH_CSV0_C_ALPHA_FROM_MATERIAL_SPECULAR` (inverted) | `VshState.ignore_specular_alpha` | vsh.c:122-124 | vsh.c:423, vsh-ff.c:440 | `vtxD1.w = 1.0; vtxB1.w = 1.0;` (vsh.c:425-426) and `oD1.a = 1.0; oB1.a = 1.0;` (vsh-ff.c:442-443). |
| `NV_PGRAPH_CSV0_C_LIGHTING` | `VshState.fixed_function.lighting` | vsh.c:67-68 | vsh-ff.c:254, 429 | Passthrough `oD0 = diffuse; ...` (vsh-ff.c:255-258) vs the full lighting accumulation (vsh-ff.c:260-421). |
| `NV_PGRAPH_CSV0_D_LIGHT0 << 2i` | `VshState.fixed_function.light[i]` | vsh.c:69-75 | vsh-ff.c:297, 303, 323 | Per light: nothing (OFF, vsh-ff.c:297-299), the INFINITE block (vsh-ff.c:328-343), the LOCAL preamble alone (vsh-ff.c:306-320), or LOCAL preamble + the SPOT `rho`/`cosHalfPhi`/`cosHalfTheta` block (vsh-ff.c:350-363). |
| `NV_PGRAPH_CSV0_C_LOCALEYE` | `VshState.fixed_function.local_eye` | vsh.c:37-38 | vsh-ff.c:290, 319, 334 | `vec3 VPeye = normalize(...)` declaration (vsh-ff.c:292); half-vector operand `"VPeye"` vs `"vec3(0.0, 0.0, 0.0)"` (vsh-ff.c:319); infinite-light `nDotHV` from `normalize(lightDirection + VPeye)` vs `lightInfiniteHalfVector[%d]` (vsh-ff.c:336 vs :340). |
| `NV_PGRAPH_CSV0_C_EMISSION/AMBIENT/DIFFUSE/SPECULAR` | `.emission_src`/`.ambient_src`/`.diffuse_src`/`.specular_src` | vsh.c:40-47 | vsh-ff.c:265, 271, 280, 385, 400 | Alpha source token (`"diffuse.a"`/`"specular.a"`/`"material_alpha"`, vsh-ff.c:261-269); `oD0 = vec4(...)` initializer (vsh-ff.c:272-276); `oD0.rgb +=` operand (vsh-ff.c:281-285); per-light `oD0.xyz +=` form (vsh-ff.c:387-397); per-light `oD1.xyz +=` form (vsh-ff.c:402-412). |
| `NV_PGRAPH_CSV0_D_SKIN` | `VshState.fixed_function.skinning` | vsh.c:33-34 | vsh-ff.c:149, 168, 476 | 7 different `append_skinning_code` expansions (vsh-ff.c:31-64) plus the `tPosition = position;` shortcut when OFF (vsh-ff.c:477). |
| `NV_PGRAPH_CSV0_C_NORMALIZATION_ENABLE` | `.normalization` | vsh.c:35-36 | vsh-ff.c:178 | `tNormal = normalize(tNormal);` (vsh-ff.c:179). |
| `NV_PGRAPH_CSV1_A/B` texgen fields | `.texgen[4][4]` | vsh.c:53-65 | vsh-ff.c:191 | Six per-channel `oT%d.%c = ...` forms (vsh-ff.c:193, :197, :201, :220, :230, :236). |
| `pg->texture_matrix_enable[i]` | `.texture_matrix_enable[4]` | vsh.c:49-51 | vsh-ff.c:247 | `oT%d = oT%d * texMat%d;` (vsh-ff.c:249). |
| `NV_PGRAPH_CSV0_D_POINTPARAMSENABLE` / `NV_PGRAPH_POINTSIZE` | `.point_params_enable`, `.point_size` | vsh.c:131-138 | vsh.c:308, vsh-ff.c:492 | Attenuated `oPts.x` expression (vsh-ff.c:493-501) vs literal `oPts.x = %f * float(%d);` (vsh-ff.c:503-505, vsh.c:309-312). |
| `pg->compressed_attrs` / `uniform_attrs` / `swizzle_attrs` | `VshState.*_attrs` | vsh.c:114-116 | vsh.c:261-263, 291, 296 | Attribute declaration form and the `decompress_11_11_10` / `.bgra` decode lines (vsh.c:269-297). |
| `pg->program_data[]` tokens | `ProgrammableVshState.program_data` | vsh.c:86-99 | vsh-prog.c:736-750 | The entire translated instruction stream (vsh-prog.c:739-743). |
| `pg->primitive_mode` (rewritten) | `GeomState.primitive_mode` | geom.c:36-38 | geom.c:53, 75 | Whether a geometry shader exists at all (geom.c:54-58) and which `layout(...)`/body pair is emitted (geom.c:77-110). |
| `NV_PGRAPH_SETUPRASTER_FRONTFACEMODE` | `GeomState.polygon_front_mode` | geom.c:29-31 | geom.c:66, 86, 93, 101 | FILL/LINE/POINT geometry-shader bodies (geom.c:87-109). |
| `opts.vulkan` | `GenPshGlslOptions.vulkan` / `GenVshGlslOptions.vulkan` | gl/shaders.c:299 (false), vk/shaders.c:767 / :755 (true) | psh.c:679, 705, 764, 873, 892, 911, 1442; vsh.c:164, 235, 436, 453; common.c:73 | `#version 450` vs `#version 400`/`es` (common.c:74/92); `usampler2D` for X8Y24 (psh.c:680); UBO block vs loose `uniform` (psh.c:873-913, vsh.c:453-488); `layout(binding = %d)` on samplers (psh.c:1443); `gl_Position = oPos;` vs the `2.0*oPos.z - oPos.w` rewrite (vsh.c:438 vs :442). |
| `opts.gles` (== `__ANDROID__`) | `GenPshGlslOptions.gles` / `GenGeomGlslOptions.gles` | gl/shaders.c:264/267, :284-285, :294-295, :302-303 | common.c:78, geom.c:139 | `#version %d es` + six `precision highp` lines (common.c:80-88); suppression of `gl_PointSize = gl_in[index].gl_PointSize;` in the geometry shader (geom.c:139-142). |

---

## Coupling points (must-agree, unenforced)

### 1. `snorm_tex` is set only for the OpenGL renderer, but Vulkan uploads the same texture as SNORM — **the comment at psh.c:223 is wrong, and the underlying bug is real**

Verified chain:

- psh.c:219 guards the assignment with `if (g_config.display.renderer == CONFIG_DISPLAY_RENDERER_OPENGL) {`. **[V]**
- The renderer enum has exactly three values: `CONFIG_DISPLAY_RENDERER_NULL`, `_OPENGL`, `_VULKAN` (include/xemu-config.h:7-12). **There is no separate GLES renderer value.** **[V]**
- The GL backend registers itself as `.type = CONFIG_DISPLAY_RENDERER_OPENGL` (gl/renderer.c:316); the VK backend as `_VULKAN` (vk/renderer.c:1679). **[V]**
- Desktop GL vs GLES is a **compile-time** distinction inside the GL backend: `#ifdef __ANDROID__ const bool gles = true; #else const bool gles = false;` (gl/shaders.c:263-268). **[V]**

Therefore, on the claim in the task:

- **"snorm_tex is left at default (false) for ... desktop GL" — FALSE.** Desktop GL runs under `CONFIG_DISPLAY_RENDERER_OPENGL`, so the assignment at psh.c:220-221 **does** execute. **[V]**
- **"snorm_tex is left at default (false) for VK" — TRUE.** Vulkan is `CONFIG_DISPLAY_RENDERER_VULKAN`, the guard fails, and `ShaderState` was zeroed at shaders.c:79, so `snorm_tex[i]` stays `false`. **[V]**
- **"while being set for OpenGL ES" — TRUE but for the wrong reason, and the stated rationale is factually wrong.** The rationale at psh.c:216-218 says *"GLES uploads as unsigned RGBA8, so detect signed via color format."* But `SZ_R6G5B5` is **not** in the Android RGBA8-conversion list (`android_texture_needs_rgba8_upload`, gl/texture.c:81-115 — the list contains 30 formats, none of which is `SZ_R6G5B5`), so on Android it takes the normal path and is uploaded as `GL_RGB8_SNORM, GL_RGB, GL_BYTE` (gl/constants.h:277-278) exactly like desktop GL. **[V]**

The important consequence:

- **Vulkan uploads `SZ_R6G5B5` as `VK_FORMAT_R8G8B8_SNORM` (vk/constants.h:246-248), the same signed data as GL** — the comment there even says `// Converted`. **[V]**
- The CPU-side conversion at texture.c:380-396 writes **signed** bytes (`int8_t *pixel` at texture.c:387, with G/B mapped to `-0x80..0x7F` at texture.c:393-394). **[V]**
- So under Vulkan, `t%d.b`/`t%d.g` already carry values in `[-1, 1]`, yet psh.c:1257/:1283 take the `false` branch and apply `sign3()` (psh.c:936-940) a second time. **[I — the double-remap is a direct consequence of the verified lines; I did not run it.]**
- The mirror-image hazard exists for GL: `snorm_tex` is keyed **only** on `SZ_R6G5B5` (psh.c:221), but `kelvin_color_format_gl_map` may contain other SNORM entries in future. Today `GL_RGB8_SNORM` appears exactly once in the GL backend (gl/constants.h:278), so the set is currently complete. **[V]**

**Unenforced invariant:** "a texture whose *upload* format is signed-normalized must have `snorm_tex[i] == true`". Nothing links gl/constants.h:277-278 or vk/constants.h:246-248 to psh.c:221. A future format added to either table as SNORM will silently produce double-remapped bump vectors.

### 2. `window_clip_count` and `depth_needed` are never computed for the OpenGL renderer

- psh.c:69 `if (g_config.display.renderer != CONFIG_DISPLAY_RENDERER_OPENGL) { ... state->window_clip_count = count; }` (psh.c:69-87). **[V]**
- psh.c:120 `if (g_config.display.renderer != CONFIG_DISPLAY_RENDERER_OPENGL) { ... state->depth_needed = ...; }` (psh.c:120-126). **[V]**
- Both stay `0`/`false` on GL because of the `memset` at shaders.c:79. **[V]**
- Consequence on GL: the entire window-clip block (psh.c:1041-1086), the barycentric depth reconstruction (psh.c:1088-1143), the `kahan_det`/`area` helpers (psh.c:1025-1036) and the `gl_FragDepth` write (psh.c:1561-1578) are all omitted from the fragment shader. **[V]**
- GL substitutes `glScissor` for window clipping (gl/draw.c:128, gl/draw.c:350). **[V]** GL relies on the fixed-function depth pipeline for Z (comment at psh.c:118-119). **[V]**
- **Unenforced:** `window_clip_exclusive` is still assigned unconditionally at psh.c:64-65 and is still part of the hash (shaders.c:40) and `memcmp` (shaders.c:69). On GL it therefore splits the shader cache without changing a single character of emitted GLSL. **[V]**
- **Unenforced:** `depth_clipping` (psh.c:113-116) and `depth_format` (psh.c:243-261) are also always computed but only read under `depth_needed` (psh.c:1134, :1562). Same dead-cache-key effect on GL. **[V]**
- **This is a renderer-behaviour fork, not just an optimization:** whether the emulator honours `NV_PGRAPH_WINDOWCLIPX0/Y0` per-pixel (VK) or per-scissor-rect (GL) is decided by a config value read inside the *shader state setter*. **[I]**

### 3. `g_config` is read from inside the shader-state hash input

`pgraph_glsl_set_psh_state` reads `g_config.display.renderer` three times (psh.c:69, :120, :219). The resulting `PshState` is hashed (shaders.c:40) and persisted to disk as part of the GL program-binary cache (gl/shaders.c:742) and used as the SPIR-V module key on VK. Changing the renderer at runtime changes the shader text for the *same* PGRAPH register state. **[V]** The GL disk cache only validates `xemu_version` (gl/shaders.c:527) and GL vendor (gl/shaders.c:536) — **not** the renderer — but since the GL cache is only read by the GL backend, this is benign today. **[I]**

### 4. `specular_power` / `specular_power_back` are in the shader-state key but never reach the GLSL

- Set at vsh.c:125 and vsh.c:126. **[V]**
- Grepping the whole `glsl/` directory finds no read of `state->specular_power` or `state->specular_power_back` in any generator — only the *uniform* path uses `pg->specular_power` (vsh.c:598). **[V]**
- Since both are `float` fields inside `VshState` before the union (vsh.h:63-64) and `common_size = offsetof(VshState, fixed_function)` (shaders.c:26, :47), they **are** hashed and memcmp'd. **[V]**
- Effect: every distinct specular power spawns a fresh shader-cache entry and a fresh shader compile, even though the generated text is byte-identical. **[I]**
- `specular_power_back` additionally has no consumer anywhere in the GLSL path at all — the `pf = pow(nDotHV, specularPower);` at vsh-ff.c:375 uses only the front value, and vsh-ff.c:419-421 admits `/* TODO: Implement two-sided lighting */`. **[V]**

### 5. `texScale[1..3]` can be read uninitialized on the GL path

- psh.c:1751-1753 sets **only** `values->texScale[0] = 1.0;`, inside a loop over `i` (psh.c:1726) — indices 1..3 are never written by the shared code. **[V]**
- `PshUniformValues psh_values;` is a plain uninitialized stack struct at gl/shaders.c:873 and vk/shaders.c:1190. **[V]**
- VK unconditionally overwrites all four (vk/shaders.c:1193-1206, with `assert(r->texture_bindings[i] != NULL)` at :1194). **[V]**
- GL overwrites only when `r->texture_binding[i] != NULL` (gl/shaders.c:876-881). **[V]**
- So on GL, if a stage has no texture binding but the shader declared `texScale` (i.e. some other stage was `rect_tex`), `texScale[i]` is garbage. It reaches the shader through `norm%d()` (psh.c:1492). **[I — the uninitialized read is verified from the lines; whether the divisor is actually consumed depends on which stage is rect.]**
- The two backends also disagree on semantics: VK forces `scale = 1.0` for non-linear formats (vk/shaders.c:1197-1203), GL does not. **[V]**

### 6. `assert` vs graceful degradation across backends

- `#ifdef NDEBUG #error building with NDEBUG is not supported` (include/qemu/osdep.h:311-312) — **every `assert()` in this code is live and aborts the process.** **[V]**
- GL tolerates a failed shader link: sets `binding->gl_program = 0`, marks initialized, returns (gl/shaders.c:318-323), and `pgraph_gl_bind_shaders` skips the draw (gl/shaders.c:918-922). **[V]**
- VK returns NULL from `pgraph_vk_create_shader_module_from_glsl` on compile failure (vk/glsl.c:468-472) and the binding is abandoned (vk/shaders.c:786-792). **[V]**
- But both share the same generator, which aborts on unsupported combinations *before* either safety net is reached (e.g. psh.c:696, :719, :731, :1214, :1277, :1304, :1437). **[V]**
- GL clears GL errors instead of asserting on Android (gl/shaders.c:408-414, :856-858) — a compile-time-only divergence in error strictness. **[V]**

### 7. Geometry shader may be silently dropped on GLES, changing flat-shading semantics

gl/shaders.c:276-278 forces `need_geometry_shader = false` when `!r->geometry_shaders_supported`. That flips `opts.prefix_outputs` at gl/shaders.c:293, so the vertex shader emits unprefixed varyings (vsh.c:238) and the fragment shader receives `vtxPos0 = vtxPos1 = vtxPos2 = vtxPos` with `triMZ = 0.0` (vsh.c:409-412) instead of real triangle corners from `calc_triz` (geom.c:199). The in-source comment (gl/shaders.c:273-275) acknowledges the provoking-vertex and wireframe consequences but not the `triMZ`/`vtxPos*` degradation. **[V]** Since `depth_needed` is false on GL anyway (see #2), `triMZ` is currently unused there — but the same code path is what VK would take if it ever ran without geometry shaders. **[I]**

### 8. `pgraph_glsl_check_shader_state_dirty` whitelist must stay in sync with the setters

shaders.c:95-104 lists 16 registers; shaders.c:113-116 adds the per-stage combiner CWs; shaders.c:131-133 adds `TEXCTL0_0`, `TEXFILTER0`, `TEXFMT0`. **[V]** Notably absent: `NV_PGRAPH_WINDOWCLIPX0/Y0` (read at psh.c:74-75) and `NV_PGRAPH_SHADOWZSLOPETHRESHOLD`. **[V]** A window-clip region change alone therefore will not mark the shader dirty; the VK path would keep an out-of-date `window_clip_count`. **[I — the register is read but not on the dirty list; I did not confirm another path forces regeneration.]**

### 9. `apply_convolution_filter` ignores the kernel selection

`state->conv_tex[i]` distinguishes `CONVOLUTION_FILTER_QUINCUNX` from `_GAUSSIAN` (psh_regs.h:184-188, set at psh.c:228-240), but psh.c:1194-1195 dispatches both to the same function, which emits only Gaussian weights (psh.c:832-836). The two states produce identical shader text but distinct cache entries. **[V]**

---

## Stubs and gaps

| symbol | file:line | kind | what behaviour it gates | does it ABORT the emulator? |
|---|---|---|---|---|
| Border source with linear/cubemap texture | psh.c:210-212 | NV2A_UNIMPLEMENTED | 4-texel hardware border on linear or cubemap textures; border adjustment silently omitted | **No** — `NV2A_UNIMPLEMENTED` expands to `do {} while (0)` unless `DEBUG_NV2A_FEATURES` (debug.h:66-67) **[V]** |
| Convolution kernel not QUINCUNX/GAUSSIAN | psh.c:235-236 | assert | Any other convolution kernel value | **Yes** **[V]** |
| Unknown zeta surface format | psh.c:257-260 | assert(false) + fprintf | `depth_format` selection | **Yes** **[V]** |
| Unknown combiner register | psh.c:392-394 | assert(false) | `get_var` fallthrough | **Yes** **[V]** |
| Unknown RGB/alpha channel select | psh.c:411, :423 | assert(false) | `get_input_var` channel suffix | **Yes** **[V]** |
| Unknown input mapping | psh.c:455-457 | assert(false) | 8-case `PS_INPUTMAPPING` switch | **Yes** **[V]** |
| Unknown output mapping | psh.c:487-489 | assert(false) | 6-case `PS_COMBINEROUTPUT` shift/bias switch | **Yes** **[V]** |
| `get_sampler_type` cleanup | psh.c:671 | FIXME | — | No **[V]** |
| Unhandled texture dimensionality (sampler type) | psh.c:688, :700 | assert | PROJECT2D / BUMPENVMAP / DOT_ST with `dim_tex` not 2 or 3 | **Yes** **[V]** |
| Shadow map in BUMPENVMAP / BUMPENVMAP_LUM / DOT_ST | psh.c:694-697 | assert + fprintf | Depth-format texture in a bump/dot mode | **Yes** **[V]** |
| Shadow map in CUBEMAP / DOT_RFLCT_* / DOT_STR_CUBE | psh.c:717-720 | assert + fprintf | Depth-format texture in a cubemap/reflect mode | **Yes** **[V]** |
| Shadow map in DPNDNT_AR / DPNDNT_GB | psh.c:729-732 | assert + fprintf | Depth-format texture in a dependent-read mode | **Yes** **[V]** |
| Cubemap dimensionality must be 2 | psh.c:721, :733 | assert | `dim_tex != 2` in cubemap/dependent modes | **Yes** **[V]** |
| Convolution requires 2D | psh.c:824 | assert | `dim_tex[tex] != 2` with a convolution filter | **Yes** **[V]** |
| `dotmap_hilo_hemisphere_d3d` | psh.c:966-968 | FIXME | Returns `col.rgb` unchanged — hemisphere HILO remap is a **stub** | No (silently wrong output) **[V]** |
| `dotmap_hilo_hemisphere_gl` | psh.c:969-971 | FIXME | Same stub | No **[V]** |
| `dotmap_hilo_hemisphere` | psh.c:972-974 | FIXME | Same stub | No **[V]** |
| Point sprite with rect T3 | psh.c:1155 | assert | `point_sprite && rect_tex[3]` | **Yes** **[V]** |
| dot_map index bound | psh.c:1178, :1341 | assert | `dot_map[i] >= 8` | **Yes** **[V]** |
| Dot mapping modes 4-7 (HILO family) | psh.c:1180-1182 | NV2A_UNIMPLEMENTED | HILO_1, HILO_HEMISPHERE_{D3D,GL,plain}; shader still emits the stub functions above | **No** **[V]** |
| Unhandled dimensionality in PROJECT2D body | psh.c:1213-1214 | assert | `dim_tex[i]` not 2 or 3 | **Yes** **[V]** |
| Border texture on PASSTHRU | psh.c:1240 | assert | `border_logical_size[i][0] != 0.0f` with PASSTHRU | **Yes** **[V]** |
| BUMPENVMAP stage index | psh.c:1255, :1281 | assert | `i < 1` | **Yes** **[V]** |
| "May not always want signed textures in this case" | psh.c:1258, :1284 | FIXME | The `snorm_tex` true branch | No **[V]** |
| "loss of accuracy due to filtering/interpolation" | psh.c:1262, :1288 | FIXME | The `sign3()` false branch | No **[V]** |
| BUMPENVMAP 3D r/z coordinate | psh.c:1273, :1300 | FIXME | Whether hardware passes `pT%d.z` or 0 | No **[V]** |
| Unhandled dimensionality in BUMPENVMAP / _LUM | psh.c:1277, :1304 | assert | `dim_tex[i]` not 2 or 3 | **Yes** **[V]** |
| `PS_TEXTUREMODES_BRDF` | psh.c:1310-1315 | NV2A_UNIMPLEMENTED | Always emits `vec4 t%d = vec4(0.0);` | **No** — silently black **[V]** |
| DOT_ZW depth write | psh.c:1334 | FIXME (commented-out code) | `gl_FragDepth = t%d.x;` is disabled; DOT_ZW produces `vec4(0.0)` | No **[V]** |
| Dot-mode stage-index constraints | psh.c:1317, :1329, :1337, :1356, :1376, :1390, :1407, :1415, :1423, :1430 | assert | DOT_ST/DOT_ZW `i>=2`; DOT_RFLCT_DIFF `i==2`; DOT_RFLCT_SPEC/DOT_STR_3D/DOT_STR_CUBE/SPEC_CONST `i==3`; DPNDNT `i>=1`; DOTPRODUCT `i==1\|\|2` | **Yes** **[V]** |
| DPNDNT modes reject rect textures | psh.c:1408, :1416 | assert | `rect_tex[i]` with DPNDNT_AR/GB | **Yes** **[V]** |
| `PS_TEXTUREMODES_DOT_RFLCT_SPEC_CONST` | psh.c:1429-1434 | NV2A_UNIMPLEMENTED | Always `vec4 t%d = vec4(0.0);` | **No** — silently black **[V]** |
| Unknown texture mode | psh.c:1435-1438 | assert(false) + fprintf | `tex_modes[i]` outside 0..0x12 | **Yes** **[V]** |
| Unhandled colour key mode | psh.c:1482-1483 | assert | `colorkey_mode` outside 0..3 | **Yes** **[V]** |
| Unhandled alpha func | psh.c:1539-1541 | assert(false) | `alpha_func` outside the 8 enum values | **Yes** **[V]** |
| Colour keying for alpha-only / no-alpha formats | psh.c:37-39 | TODO (links xemu issue #2260) | `get_colorkey_mask` returns `0xFFFFFFFF` for everything except X1R5G5B5/X8R8G8B8 | No **[V]** |
| `ZOFFSETFACTOR` under w-buffering | psh.c:1808-1813 | FIXME + NV2A_UNIMPLEMENTED | Per-pixel vs constant polygon slope | **No** **[V]** |
| `surface_scale_factor` in VshState | vsh.c:112 | FIXME | Baked into `oPts.x` literals (vsh-ff.c:501, :505; vsh.c:312) | No **[V]** |
| Fog mode source register | vsh.c:147 | FIXME | Whether `CSV0_D` should supply fog mode | No **[V]** |
| Fog when disabled | vsh.c:317 | FIXME | Whether hardware still computes/passes fog | No **[V]** |
| foggen in programmable mode | vsh.c:321-326 | FIXME | RollerCoaster Tycoon uses `oFog.x` directly | No **[V]** |
| Fog computed per vertex not per pixel | vsh.c:330 | FIXME | Interpolation accuracy | No **[V]** |
| Unknown fog mode | vsh.c:372-374 | assert(false) | `fog_mode` outside the 6 values | **Yes** **[V]** |
| Uniform attr cannot also be compressed/swizzled | vsh.c:265-266 | assert | Attribute mask conflict | **Yes** **[V]** |
| Neither vertex program nor fixed function | vsh.c:110 | assert | `CSV0_D_MODE` == 1 or 3 | **Yes** **[V]** |
| Unknown skinning mode | vsh-ff.c:164-166 | assert(false) | `skinning` outside the 7 values | **Yes** **[V]** |
| TexGen View Model | vsh-ff.c:188 | TODO | Mode not implemented | (falls to `assert(false)` at vsh-ff.c:240 if selected) **[I]** |
| SPHERE_MAP restricted to S,T | vsh-ff.c:205 | assert | `j >= 2` | **Yes** **[V]** |
| REFLECTION_MAP / NORMAL_MAP restricted to S,T,R | vsh-ff.c:225, :235 | assert | `j >= 3` | **Yes** **[V]** |
| Unknown texgen mode | vsh-ff.c:239-241 | assert(false) | `texgen[i][j]` outside the 6 values | **Yes** **[V]** |
| Two-sided lighting | vsh-ff.c:260, :419-421 | FIXME / TODO | `oB0 = backDiffuse; oB1 = backSpecular;` — back colours are never lit | No (silently wrong) **[V]** |
| Local light range inclusivity | vsh-ff.c:310 | FIXME | `d <= lightLocalRange(i)` | No **[V]** |
| **Spotlight falloff** | vsh-ff.c:361 | FIXME | `attenuation *= spotDirDotVP + spotDir.w;` — `lightSpotFalloff(i)` (defined at vsh-ff.c:134-135) is **never used** | No (silently wrong falloff curve) **[V]** |
| Unknown light type | vsh-ff.c:365-367 | assert(false) | `light[i]` outside the 4 values | **Yes** **[V]** |
| foggen SPEC_ALPHA clamp | vsh-ff.c:452 | FIXME | `clamp(specular.a, 0.0, 1.0)` | No **[V]** |
| Invalid foggen mode | vsh-ff.c:468-470 | assert | `foggen` outside the 5 values | **Yes** **[V]** |
| `convert_c_register` correctness | vsh-prog.c:256, :326 | FIXME | Constant-register indexing in programmable VSH | No **[V]** |
| Unknown VSH parameter type | vsh-prog.c:334 | assert(false) | Token decode | **Yes** **[V]** |
| Writeable const registers | vsh-prog.c:383 | assert(!"TODO: ...") | `mov c[a0], ...` style writes | **Yes** **[V]** |
| Temp var on non-MAC instruction | vsh-prog.c:401 | assert | MAC/ILU pairing invariant | **Yes** **[V]** |
| Program without FINAL token | vsh-prog.c:751 | assert | Malformed / truncated vertex program | **Yes** **[V]** |
| Two-sided polygon mode | geom.c:50-51, :64-65 | FIXME + assert | `polygon_front_mode != polygon_back_mode` | **Yes** **[V]** |
| Unknown polygon mode | geom.c:101 | assert | `polygon_mode` outside FILL/LINE/POINT | **Yes** **[V]** |
| Unknown primitive mode | geom.c:112-114 | assert(false) | `primitive_mode` outside POINTS/LINES/TRIANGLES | **Yes** **[V]** |
| Unknown zeta format in `clipRange` | common.c:105-106 | assert(0) | `pgraph_glsl_set_clip_range_uniform_value` | **Yes** **[V]** |
| Invalid GL primitive mode | gl/shaders.c:42-44 | assert | `get_gl_primitive_mode` | **Yes** **[V]** |
| Invalid shader module kind | gl/shaders.c:222, vk/shaders.c:954 | assert | Cache key corruption | **Yes** **[V]** |
| VK texture binding must exist | vk/shaders.c:1194 | assert | `r->texture_bindings[i] == NULL` during uniform update | **Yes** **[V]** |
| Shader module cache size not configurable | gl/shaders.c:653, :669 | FIXME | Fixed 50*1024 entries | No **[V]** |
| No dirty tracking on uniforms (GL) | gl/shaders.c:861-862 | FIXME | Every draw re-uploads all uniforms | No **[V]** |
| `program_data_dirty` reset | shaders.c:74 | fixme | `pg->program_data_dirty = false; /* fixme */` at the top of the state getter | No **[V]** |

**Additional abort risk (INFERRED):** if a texture stage has a non-NONE, non-PASSTHRU `PS_TEXTUREMODES` but `NV_PGRAPH_TEXCTL0_0_ENABLE` is clear, psh.c:149-151 `continue`s before setting `dim_tex[i]`, leaving it `0` (from the memset at shaders.c:79). `get_sampler_type` is then called unconditionally at psh.c:1173 and reaches `assert(!"Unhandled texture dimensions")` at psh.c:688. `pgraph_is_texture_stage_active` (pgraph.h:409-414) only excludes modes 0 and 4, so this state is reachable from the guest. **[I — I traced the control flow but did not observe it firing.]**

---

## Suites plausibly exercised

Grounded in `docs/testing/nv2a_index.json` (`provenance.tests_commit` = `33e7c6b0ebf4d6e1b67d0ca475adc336fb5fbaf8`, `provenance.tests_root` = `/home/user/nxdk_pgraph_tests`), which records each suite's source files and the NV097 symbols it references.

| suite (results_name) | index entry | code sites above | confidence |
|---|---|---|---|
| **Bump_map** | `suites["Bump map"]`, sources `src/tests/bump_map_tests.cpp`; symbols include `NV097_SET_DOT_RGBMAPPING` | psh.c:1254-1279 (BUMPENVMAP body); psh.c:1179-1182 + psh.c:915-924 + psh.c:945-974 (dotmap selection and the eight `dotmap_*` bodies); psh.c:1267 (`bumpMat[%d]`); psh.c:1729-1739 (bumpMat uniform); psh.c:691-701 (sampler type). Also touches the HILO stubs at psh.c:957-974 whenever `dot_map > 3`. | **High** — the suite's symbol list names `NV097_SET_DOT_RGBMAPPING`, which is exactly the register decoded at psh.c:1645-1647 into `dotmap_funcs[]`. |
| **Bump_env_lum** (not in the task list but the one that matters most here) | `suites["Bump env lum"]`; symbols include **`NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R6G5B5`** | psh.c:219-222 (`snorm_tex` set), psh.c:1283-1291 (LUM sign branch), psh.c:1293 + :1307-1308 (`bumpMat`/`bumpScale`/`bumpOffset`), psh.c:1740-1749 (uniforms) | **High** — this is the **only** bump suite whose symbol list contains `SZ_R6G5B5`, i.e. the one that will actually exercise the `snorm_tex` branch and therefore the GL-vs-VK divergence in Coupling Point 1. The task's brief attributed this to `Bump_map`; per the index, `Bump_map`'s symbol list does **not** include `SZ_R6G5B5`. |
| **Fog_gen** | `suites["Fog gen"]`; symbols cover all five `NV097_SET_FOG_GEN_MODE_V_*` plus all six `NV097_SET_FOG_MODE_V_*` and `NV097_SET_SPECULAR_ENABLE` | vsh-ff.c:448-473 (the five `float fogDistance = ...` variants); vsh.c:335-384 (the three `fogFactor` formulas + `abs()`); vsh.c:144-151 (state capture); psh.c:1150 (`pFog`) | **High** |
| **Fog_param** | `suites["Fog param"]`; symbols `NV097_SET_FOG_PARAMS`, all `FOG_MODE_V_*`, `FOG_GEN_MODE_V_FOG_X` | vsh.c:513-518 (`fogParam` uniform from `NV_PGRAPH_FOGPARAM0/1`); vsh.c:345-370 (the formulas that consume `fogParam.x/.y`); vsh-ff.c:466 (`fogCoord`) | **High** |
| **Fog_exceptional_value** | `suites["Fog exceptional value"]`; same fog symbol set plus `NV097_SET_LIGHT_CONTROL_V_SEPARATE_SPECULAR` and `NV097_SET_SPECULAR_ENABLE` | vsh.c:386-398 — specifically the `isinf(fogDistance)` branch and `NaNToValue(...)` with the two per-mode literals `infinite_fogdistance_result` / `nan_fogfactor_result` (vsh.c:332-333, :343-344, :349-350). Also `NaNToValue` itself at vsh.c:224-226 and the `clamp(vtxFog, 0.0, 1.0)` at psh.c:1150 | **High** — this suite is the direct test of the exceptional-value literals, and the EXP/EXP_ABS fallthrough at vsh.c:351 is the subtle bit it would catch. |
| **Specular** | `suites["Specular"]`; symbols `NV097_SET_SPECULAR_ENABLE`, `NV097_SET_SPECULAR_PARAMS`, `NV097_SET_LIGHT_CONTROL_V_{ALPHA_FROM_MATERIAL_SPECULAR,LOCALEYE,SEPARATE_SPECULAR}` | vsh-ff.c:424-446 (specular combine, `separate_specular`, `ignore_specular_alpha`); vsh.c:417-434 (varying writes); vsh-ff.c:400-413 (`specular_src`); vsh-ff.c:375 (`pow(nDotHV, specularPower)`); vsh.c:597-599 (uniform); vsh-ff.c:290-294 + :319 + :334-343 (`local_eye`) | **High** |
| **Specular_back** (not in task list; adjacent) | `suites["Specular back"]` | Would exercise `specular_power_back` (vsh.c:126) — which **no generator reads** (Coupling Point 4) and `oB1 = backSpecular;` (vsh-ff.c:421), the un-lit passthrough | **Medium** — inferred from the field being dead; I did not read the test source. |
| **Lighting_spotlight** | `suites["Lighting spotlight"]`; symbols include `NV097_SET_LIGHT_ENABLE_MASK_LIGHT0_SPOT`, `NV097_SET_LIGHT_SPOT_DIRECTION`, **`NV097_SET_LIGHT_SPOT_FALLOFF`**, `NV097_SET_LIGHT_LOCAL_{ATTENUATION,POSITION,RANGE}` | vsh-ff.c:348-363 (the SPOT block) and vsh-ff.c:306-320 (the LOCAL preamble it shares); vsh.c:589-595 (`lightLocalAttenuation` uniform); vsh-ff.c:139-140 (`lightLocalRange` define) | **High** — and this suite is the one that should surface the `/* FIXME: lightSpotFalloff */` at vsh-ff.c:361: the test sets `SET_LIGHT_SPOT_FALLOFF`, but the generated GLSL never reads the `lightSpotFalloff(i)` define declared at vsh-ff.c:134-135. |
| **Attrib_carryover** | `suites["Attrib carryover"]` — `symbols: []` (empty) | vsh.c:260-300 (attribute declaration / decode, `uniform_attrs` / `swizzle_attrs` / `compressed_attrs`); vsh.c:531-534 (`inlineValue` uniform via `pgraph_get_inline_values`); vsh.c:168-171 (`inlineValue` elision); shaders.c:121-123 (dirty check on the three attr masks) | **Medium** — the index records no symbols for this suite, so the mapping is inferred from the suite name and the attribute machinery. |
| **Blend_tests** | `suites["Blend tests"]`; symbols are overwhelmingly `NV097_SET_BLEND_*` plus `NV097_SET_ALPHA_TEST_ENABLE` and `NV097_SET_COLOR_MASK_ALPHA_WRITE_ENABLE` | Mostly **outside** shader codegen — blending is fixed-function. The only shader-side contact is the alpha-test emission at psh.c:1527-1548 and the final-combiner alpha write `fragColor.a = %s;` at psh.c:650 | **Low for shader codegen** — I found no blend-related emission in any file under `glsl/`. Listing it here mainly to record that a combiner change is *unlikely* to move this suite. |
| **Texture_shadow_comparator** | `suites["Texture shadow comparator"]`; symbols include all eight `NV097_SET_SHADOW_COMPARE_FUNC_*`, `NV097_SET_SURFACE_FORMAT_ZETA_{Z16,Z24S8}`, and `LU_IMAGE_DEPTH_{X8_Y24_FIXED,Y16_FIXED,Y16_FLOAT}` | psh.c:747-800 (`psh_append_shadowmap`, incl. NEVER/ALWAYS shortcuts at :749-757 and the operator table at :738-745); psh.c:224 (`shadow_map` from `f.depth`); psh.c:162-166 + :679/:705/:764 (`tex_x8y24`, **Vulkan-only `usampler2D` path**); psh.c:1190-1191 and :1221-1222 (dispatch); psh.c:243-261 + :1561-1578 (`depth_format`) | **High** — and note the VK/GL asymmetry: the `X8_Y24` 24-bit extraction at psh.c:766-776 exists **only** under `opts.vulkan`, so this suite can pass on VK and behave differently on GL for the `LU_IMAGE_DEPTH_X8_Y24_*` cases. **[I]** |
| **Texture_signed_component_tests** | `suites["Texture signed component tests"]`; symbols `NV097_SET_TEXTURE_FORMAT_COLOR_SZ_A8R8G8B8`, `NV097_SET_BLEND_EQUATION_V_FUNC_{ADD,ADD_SIGNED,REVERSE_SUBTRACT_SIGNED}` | psh.c:927-940 (`sign1`/`sign2`/`sign3`); psh.c:398-462 (the signed `PS_INPUTMAPPING` forms, especially `SIGNED_IDENTITY` at :448-450 and `SIGNED_NEGATE` at :453); psh.c:553/:563/:590 (the `clamp(..., -1.0, 1.0)` that preserves sign) | **Medium** — the suite's recorded symbols name only `SZ_A8R8G8B8` and signed *blend* equations, not a signed texture format, so its overlap with `snorm_tex` (psh.c:219-222) is not established by the index. The signed-input-mapping and `sign*()` codegen is the plausible shader-side contact. |

**Suites the index shows are more directly on this code path than several of the ones listed in the brief** (offered because the brief asked which suites a change here would disturb):

- `Pixel shader` — `suites["Pixel shader"]` symbols include `NV097_SET_SHADER_STAGE_PROGRAM` and `NV097_SET_SHADER_CLIP_PLANE_MODE`, i.e. psh.c:1641 (mode unpacking) and psh.c:1243-1253 (the CLIPPLANE `discard` emission). **High confidence.**
- `Combiner` — `suites["Combiner"]` symbols include `NV097_SET_COMBINER_`, i.e. the whole of psh.c:494-661. **High confidence.**
- `Color key` — `suites["Color key"]` symbols `NV097_SET_COLOR_KEY_COLOR` and `NV097_SET_TEXTURE_CONTROL0_COLOR_KEY_MODE`, i.e. psh.c:854-865 + :1455-1487 + :1713-1724. **High confidence.**
- `Alpha func` — `suites["Alpha func"]` names all eight `NV097_SET_ALPHA_FUNC_V_*`, i.e. psh.c:1527-1548 exhaustively. **High confidence.**
- `Window clip` — would exercise psh.c:1041-1086 on VK and `glScissor` (gl/draw.c:128, :350) on GL — the clearest observable consequence of Coupling Point 2. **Medium** (inferred from the suite name; the index entry's symbols were not inspected).
- `Texture border` / `Texture border color` — psh.c:168-208 + :804-820; `suites["Texture border color"]` also names `SZ_R6G5B5`. **Medium.**
- `Texture cubemap` and `Texture 2D as cubemap` — both name `NV097_SET_DOT_RGBMAPPING`; psh.c:983-1022 (`remapCubeTo2D`/`remap2DToCube`) and psh.c:1229-1238, :1336-1405. **High.**
- `Point sprite` — psh.c:1154-1159 and the `assert` at psh.c:1155. **Medium.**

---

## Uncertainties

1. **I did not build or run anything.** Every "aborts the emulator" claim rests on osdep.h:311-312 (`#error building with NDEBUG is not supported`) making `assert()` live. I did not confirm the actual compiler flags in a real build of this tree — there is no `build/` directory present.

2. **I did not read the nxdk_pgraph_tests sources.** `docs/testing/nv2a_index.json` says they live at `/home/user/nxdk_pgraph_tests`, which is outside the repo. All suite mappings derive from that index's `symbols` lists, which are themselves generated. A suite may exercise a code path without referencing a distinctive NV097 symbol (`Attrib carryover` has an empty symbol list, which proves the index can be blind).

3. **The `Texture_signed_component_tests` mapping is weak.** Its recorded symbols mention only `SZ_A8R8G8B8` and signed blend equations. I could not establish that it drives `snorm_tex` or the `sign3()` branches. Someone should read `src/tests/texture_signed_component_tests.cpp` before treating it as coverage for Coupling Point 1.

4. **Whether the Vulkan double-remap actually produces visibly wrong output** — I verified that VK uploads `SZ_R6G5B5` as `VK_FORMAT_R8G8B8_SNORM` (vk/constants.h:246-248), that the CPU conversion writes signed bytes (texture.c:387-394), and that psh.c:219 excludes VK. I did **not** verify that no other VK-side code compensates (e.g. a component swizzle in the image view, or a different sampler configuration). The `vk/constants.h:246-248` entry has no swizzle field, unlike its neighbours, which suggests no compensation — but that is inference.

5. **Whether desktop GL is ever built with `gles = true`.** I only found the `#ifdef __ANDROID__` at gl/shaders.c:263-268. I did not audit whether any build configuration defines `__ANDROID__` on a desktop target, or whether `r->gles_version` (gl/shaders.c:265) can be zero (which would make `pgraph_glsl_append_version` fall back to `300`, common.c:79).

6. **`pgraph_glsl_check_shader_state_dirty` completeness.** I verified `NV_PGRAPH_WINDOWCLIPX0/Y0` are read at psh.c:74-75 but absent from the whitelist at shaders.c:95-104. I did **not** trace whether some other mechanism (a `program_data_dirty` set, a surface change, a `pgraph_reg_w` side effect) forces regeneration when window clip regions change. Treat #8 in Coupling Points as a lead, not a confirmed bug.

7. **The `texScale[1..3]` uninitialized read (Coupling Point 5).** I verified the write at psh.c:1752 covers only index 0 and that gl/shaders.c:876 is conditional. I did **not** determine how often `r->texture_binding[i]` is actually NULL while a `norm%d()` function referencing `texScale[i]` was emitted — that requires the rect/enable states to disagree, which may be unreachable in practice.

8. **`get_colorkey_mask` correctness.** psh.c:40-52 returns `0x00FFFFFF` for four X-format variants and `0xFFFFFFFF` otherwise; the TODO at psh.c:37-39 says the alpha-only / no-alpha cases are unresolved. I did not evaluate which formats are actually affected.

9. **`PS_COMBINEROUTPUT` flag decoding.** psh.c:1619-1626 assigns `out->ab_op = flags & 2` and `out->cd_op = flags & 1`, then psh.c:523 compares `output.ab_op == PS_COMBINEROUTPUT_AB_DOT_PRODUCT` (`0x02`) and psh.c:534 compares `output.cd_op == PS_COMBINEROUTPUT_CD_DOT_PRODUCT` (`0x01`). These line up. But `out->muxsum_op = flags & 4` (psh.c:1623) is compared against `PS_COMBINEROUTPUT_AB_CD_SUM` (`0x00`) at psh.c:576 — an equality against zero, which reads correctly but is fragile. `out->ab_alphablue`/`cd_alphablue` (psh.c:1625-1626) are assigned but **never read**; the blue-to-alpha decision uses `output.flags & PS_COMBINEROUTPUT_{AB,CD}_BLUE_TO_ALPHA` directly (psh.c:600, :609). I did not determine whether the unused fields are dead code or a latent inconsistency.

10. **`input_tex[0] = -1`** (psh.c:1649). Stage 0 can never be a bump/dependent target (asserted at psh.c:1255, :1281, :1407, :1415), so `snorm_tex[-1]` should be unreachable — but nothing in the type system prevents it, and an out-of-range `other_stage_input` field could in principle produce `input_tex[2]`/`[3]` values up to 15 (masked `& 0xF` at psh.c:1651-1652) indexing 4-element arrays. **I could not find a bounds check**; `state->snorm_tex[ps->input_tex[i]]` at psh.c:1257/:1283 and `ps->input_tex[i]` used as a `t%d` register number at psh.c:1322 etc. would both be out of range. Whether the guest can actually program such a value is unverified.

11. **`NV_PGRAPH_SHADERCTL` field layout.** psh.c:1645-1652 unpacks dotmap from bits 0/4/8 and input_tex from bits 16/20, but `nv2a_regs.h:520` defines no sub-fields for `NV_PGRAPH_SHADERCTL` at all. The method handlers write masks `0xFFF` (pgraph.c:4100) and `0xFFFF000` (pgraph.c:4106) — note `0xFFFF000` covers bits 12..27, so bits 12-15 are writable but never read by the unpacker. I did not determine what, if anything, lives there.

12. **Line-ending / offset drift.** All cited line numbers were re-verified with `grep -n` or `sed -n 'Np'` against the working tree at commit `5b4f577` (`git log --oneline -1`). If the tree moves, re-verify.
