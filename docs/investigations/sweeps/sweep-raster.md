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

# NV2A raster / draw-state inventory sweep (hakuX)

Repo: `/home/user/hakuX` @ `5b4f577`. Read-only sweep. No files under the repo were modified.

Legend: **[V]** = verified by reading the cited line(s). **[I]** = inferred (reasoning stated).
Everything without a `file:line` is in Uncertainties.

---

## Concepts owned

### Fog

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| fog enable (method) | method | `NV097_SET_FOG_ENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:923 |
| fog enable (raster state) | regfield | `NV_PGRAPH_CONTROL_3_FOGENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:482 |
| fog enable (xform state) | regfield | `NV_PGRAPH_CSV0_D_FOGENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:294 |
| fog mode (method) | method | `NV097_SET_FOG_MODE` + `_V_LINEAR/EXP/EXP2/EXP_ABS/EXP2_ABS/LINEAR_ABS` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:910-916 |
| fog mode (raster state) | regfield | `NV_PGRAPH_CONTROL_3_FOG_MODE` (+ 6 enum values) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:483-489 |
| fog mode (xform state) | regfield | `NV_PGRAPH_CSV0_D_FOG_MODE` (LINEAR/EXP) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:298-300 |
| fog gen mode (method) | method | `NV097_SET_FOG_GEN_MODE` + 5 `_V_` values | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:917-922 |
| fog gen mode (state) | regfield | `NV_PGRAPH_CSV0_D_FOGGENMODE` + 5 values | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:301-306 |
| fog color | method/reg | `NV097_SET_FOG_COLOR` / `NV_PGRAPH_FOGCOLOR{_RED,_GREEN,_BLUE,_ALPHA}` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:924-928, 491-495 |
| fog params | method/reg | `NV097_SET_FOG_PARAMS` / `NV_PGRAPH_FOGPARAM0`,`FOGPARAM1` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1067, 496-497 |
| fog plane | method | `NV097_SET_FOG_PLANE` → `NV_IGRAPH_XF_XFCTX_FOG` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1075, 1343 |
| fog coord (per-vertex) | method | `NV097_SET_FOG_COORD`, `NV2A_VERTEX_ATTR_FOG` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1131, 1474 |
| combiner fog inputs | reg | `NV_PGRAPH_COMBINESPECFOG0/1` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:425-426 |
| specular-fog factor | method/reg | `NV097_SET_SPECULAR_FOG_FACTOR` / `NV_PGRAPH_SPECFOGFACTOR0/1` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1288, 526-527 |
| fog mode enum (internal) | enum-value | `enum VshFogMode` (incl. `FOG_MODE_ERROR2`, `FOG_MODE_ERROR6`) | /home/user/hakuX/hw/xbox/nv2a/pgraph/vsh_regs.h:42-51 |
| foggen enum (internal) | enum-value | `enum VshFoggen` | /home/user/hakuX/hw/xbox/nv2a/pgraph/vsh_regs.h:53-59 |

### Blend

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| blend enable | method/regbit | `NV097_SET_BLEND_ENABLE` / `NV_PGRAPH_BLEND_EN` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:935, 361 |
| src factor | method/regfield | `NV097_SET_BLEND_FUNC_SFACTOR` (15 values) / `NV_PGRAPH_BLEND_SFACTOR` (15 values) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:958-973, 362-377 |
| dst factor | method/regfield | `NV097_SET_BLEND_FUNC_DFACTOR` / `NV_PGRAPH_BLEND_DFACTOR` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:974-989, 378-393 |
| blend equation | method/regfield | `NV097_SET_BLEND_EQUATION` (7 values incl. `_SIGNED`) / `NV_PGRAPH_BLEND_EQN` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:991-998, 360 |
| blend color | method/reg | `NV097_SET_BLEND_COLOR` / `NV_PGRAPH_BLENDCOLOR` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:990, 396 |
| logic op | method/regfield | `NV097_SET_LOGIC_OP_ENABLE`,`NV097_SET_LOGIC_OP` / `NV_PGRAPH_BLEND_LOGICOP_ENABLE`,`NV_PGRAPH_BLEND_LOGICOP` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1147-1148, 394-395 |
| colour write mask | regbits | `NV_PGRAPH_CONTROL_0_{RED,GREEN,BLUE,ALPHA}_WRITE_ENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:445-448 |
| dither | regbit | `NV_PGRAPH_CONTROL_0_DITHERENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:441 |

### Depth / stencil

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| depth test enable | method/regbit | `NV097_SET_DEPTH_TEST_ENABLE` / `NV_PGRAPH_CONTROL_0_ZENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:937, 431 |
| depth func | method/regfield | `NV097_SET_DEPTH_FUNC` / `NV_PGRAPH_CONTROL_0_ZFUNC` (8 values) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:999, 432-440 |
| depth write | method/regbit | `NV097_SET_DEPTH_MASK` / `NV_PGRAPH_CONTROL_0_ZWRITEENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1005, 443 |
| stencil write enable | method/regbit | `NV097_SET_CONTROL0_STENCIL_WRITE_ENABLE` / `NV_PGRAPH_CONTROL_0_STENCIL_WRITE_ENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:902, 444 |
| stencil test enable | method/regbit | `NV097_SET_STENCIL_TEST_ENABLE` / `NV_PGRAPH_CONTROL_1_STENCIL_TEST_ENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:952, 450 |
| stencil func/ref/masks | method/regfields | `NV097_SET_STENCIL_FUNC{,_REF,_MASK}`, `NV097_SET_STENCIL_MASK` / `NV_PGRAPH_CONTROL_1_STENCIL_{FUNC,REF,MASK_READ,MASK_WRITE}` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1006-1009, 451-462 |
| stencil ops | method/regfields | `NV097_SET_STENCIL_OP_{FAIL,ZFAIL,ZPASS}` (8 `_V_` values) / `NV_PGRAPH_CONTROL_2_STENCIL_OP_*` (8 values) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1010-1020, 464-474 |
| z perspective (w-buffer) | regbit | `NV_PGRAPH_CONTROL_0_Z_PERSPECTIVE_ENABLE` (`NV097_SET_CONTROL0_Z_PERSPECTIVE_ENABLE`) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:442 |
| z float format | regbit | `NV_PGRAPH_SETUPRASTER_Z_FORMAT` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:517 |
| polygon offset factor/bias | method/reg | `NV097_SET_POLYGON_OFFSET_SCALE_FACTOR`,`_BIAS` / `NV_PGRAPH_ZOFFSETFACTOR`,`NV_PGRAPH_ZOFFSETBIAS` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1024-1025 |
| polygon offset enables | method/regbits | `NV097_SET_POLY_OFFSET_{POINT,LINE,FILL}_ENABLE` / `NV_PGRAPH_SETUPRASTER_POFFSET{POINT,LINE,FILL}ENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:953-955, 505-507 |
| shadow depth func | method/regfield | `NV097_SET_SHADOW_DEPTH_FUNC` (8 values) / `NV_PGRAPH_SHADOWCTL_SHADOW_ZFUNC` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1293-1301, 524 |
| z/stencil clear value | method/reg | `NV097_SET_ZSTENCIL_CLEAR_VALUE` / `NV_PGRAPH_ZSTENCILCLEARVALUE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1276, 642 |
| clear-surface z/stencil bits | enum-value | `NV097_CLEAR_SURFACE_Z`, `_STENCIL` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1279-1280 |

### Clip / viewport / window clip

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| z clip min/max | method/reg | `NV097_SET_CLIP_MIN`,`_MAX` / `NV_PGRAPH_ZCLIPMIN`,`NV_PGRAPH_ZCLIPMAX` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1031-1032, 643, 649 |
| z clamp vs cull | method/regbit | `NV097_SET_ZMIN_MAX_CONTROL_ZCLAMP_EN{_CULL,_CLAMP}` / `NV_PGRAPH_ZCOMPRESSOCCLUDE_ZCLAMP_EN{_CULL,_CLAMP}` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1270-1273, 638-641 |
| window clip type (incl/excl) | method/regbit | `NV097_SET_WINDOW_CLIP_TYPE` / `NV_PGRAPH_SETUPRASTER_WINDOWCLIPTYPE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:929, 518 |
| window clip rects (8) | method/reg | `NV097_SET_WINDOW_CLIP_HORIZONTAL/_VERTICAL` / `NV_PGRAPH_WINDOWCLIPX0..X7`, `Y0..Y7` (+ `_XMIN/_XMAX/_YMIN/_YMAX`) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:930-933, 618-637 |
| surface clip | method | `NV097_SET_SURFACE_CLIP_HORIZONTAL/_VERTICAL` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:863-868 |
| viewport offset/scale | method | `NV097_SET_VIEWPORT_OFFSET`, `NV097_SET_VIEWPORT_SCALE` → `NV_IGRAPH_XF_XFCTX_VPOFF`/`VPSCL` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1081, 1089, 1344 |
| shader (texture) clip planes | method/reg | `NV097_SET_SHADER_CLIP_PLANE_MODE` / `NV_PGRAPH_SHADERCLIPMODE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1158, 519 |
| clear rect | reg | `NV_PGRAPH_CLEARRECTX/Y` (`NV097_SET_CLEAR_RECT_HORIZONTAL/_VERTICAL`) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:407-412, 1281-1282 |

### Line / point / polygon rasterisation

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| point size | method/reg | `NV097_SET_POINT_SIZE` (`_V_MAX` 0x1FF) / `NV_PGRAPH_POINTSIZE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1060-1061, 498 |
| point params enable | method/regbits | `NV097_SET_POINT_PARAMS_ENABLE` / `NV_PGRAPH_CONTROL_3_POINTPARAMSENABLE`, `NV_PGRAPH_CSV0_D_POINTPARAMSENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:940, 490, 308 |
| point params (8 floats) | method | `NV097_SET_POINT_PARAMS` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1082 |
| point smooth | method/regbit | `NV097_SET_POINT_SMOOTH_ENABLE` / `NV_PGRAPH_SETUPRASTER_POINTSMOOTHENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:941, 508 |
| line smooth | method/regbit | `NV097_SET_LINE_SMOOTH_ENABLE` / `NV_PGRAPH_SETUPRASTER_LINESMOOTHENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:942, 509 |
| poly smooth | method/regbit | `NV097_SET_POLY_SMOOTH_ENABLE` / `NV_PGRAPH_SETUPRASTER_POLYSMOOTHENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:943, 510 |
| front/back polygon mode | method/regfield | `NV097_SET_FRONT_POLYGON_MODE`,`NV097_SET_BACK_POLYGON_MODE` / `NV_PGRAPH_SETUPRASTER_FRONTFACEMODE`,`_BACKFACEMODE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1026-1030, 500-504 |
| cull enable / cull face | method/regfields | `NV097_SET_CULL_FACE_ENABLE`,`NV097_SET_CULL_FACE` / `NV_PGRAPH_SETUPRASTER_CULLENABLE`,`_CULLCTRL` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:936, 1033-1036, 511-516 |
| front face winding | method/regbit | `NV097_SET_FRONT_FACE` (CW/CCW) / `NV_PGRAPH_SETUPRASTER_FRONTFACE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1037-1039, 515 |
| shade mode | method/regbit | `NV097_SET_SHADE_MODE` (FLAT/SMOOTH) / `NV_PGRAPH_CONTROL_3_SHADEMODE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1021-1023, 479-481 |
| provoking vertex | method/regbit | `NV097_SET_PROVOKING_VERTEX` (LAST/FIRST) / `NV_PGRAPH_CONTROL_3_PROVOKING_VERTEX` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1077-1079, 476-478 |
| anti-aliasing control | method/regbit | `NV097_SET_ANTI_ALIASING_CONTROL_ENABLE` / `NV_PGRAPH_ANTIALIASING_ENABLE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1274-1275, 357-358 |
| polygon mode enum (internal) | enum-value | `enum ShaderPolygonMode` (FILL/POINT/LINE) | /home/user/hakuX/hw/xbox/nv2a/pgraph/vsh_regs.h:199-203 |
| **line width** | — | **no NV2A register or method defined** | see "State distinctions" |
| **line/polygon stipple** | — | **no NV2A register or method defined** | see "State distinctions" |

### Vertex attributes

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| attribute slots | enum-value | `NV2A_VERTEX_ATTR_POSITION..RESERVED3` (16) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1469-1484 |
| array format | method/fields | `NV097_SET_VERTEX_DATA_ARRAY_FORMAT` + `_TYPE`/`_SIZE`/`_STRIDE` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1137-1146 |
| array type values | enum-value | `_TYPE_UB_D3D`(0), `_S1`(1), `_F`(2), `_UB_OGL`(4), `_S32K`(5), `_CMP`(6) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1139-1144 |
| array offset / DMA select | method | `NV097_SET_VERTEX_DATA_ARRAY_OFFSET` (bit31 = dma_select) | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:3562-3569 |
| immediate vertex data | method | `NV097_SET_VERTEX_DATA{2F_M,4F_M,2S,4UB,4S_M}` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1178-1182 |
| inline value carryover | state-bit | `VertexAttribute::inline_value`, `pgraph_update_inline_value()` | /home/user/hakuX/hw/xbox/nv2a/pgraph/vertex.c:24-81 |
| inline buffer | state-bit | `inline_buffer_populated`, `pgraph_allocate_inline_buffer_vertices()` | /home/user/hakuX/hw/xbox/nv2a/pgraph/vertex.c:101-115 |
| swizzle / compressed / uniform attr masks | state-bit | `pg->swizzle_attrs`, `pg->compressed_attrs`, `pg->uniform_attrs` | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/vertex.c:101-103, /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/vertex.c:177-179 |

### Primitive type / assembly

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| begin/end op | method/enum | `NV097_SET_BEGIN_END` + `_OP_END..._OP_POLYGON` (11 values) | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1159-1170 |
| primitive mode (internal) | enum-value | `enum ShaderPrimitiveMode` `PRIM_TYPE_INVALID..PRIM_TYPE_POLYGON` | /home/user/hakuX/hw/xbox/nv2a/pgraph/vsh_regs.h:185-197 |
| draw arrays | method/fields | `NV097_DRAW_ARRAYS` + `_COUNT`/`_START_INDEX` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1173-1175 |
| element arrays | method | `NV097_ARRAY_ELEMENT16`, `NV097_ARRAY_ELEMENT32` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1171-1172 |
| inline array | method | `NV097_INLINE_ARRAY` | /home/user/hakuX/hw/xbox/nv2a/nv2a_regs.h:1176 |
| CPU prim rewrite | state | `PrimAssemblyState`, `pgraph_prim_rewrite_get_output_mode()` | /home/user/hakuX/hw/xbox/nv2a/pgraph/prim_rewrite.h:39-52 |

---

## Sites

### Fog

| concept | file:line | role | notes |
|---|---|---|---|
| `NV097_SET_FOG_MODE` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2169-2192 | TRANSLATE | 6 method values → `NV_PGRAPH_CONTROL_3_FOG_MODE`; `default: assert(false)` [V] |
| `NV097_SET_FOG_GEN_MODE` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2194-2213 | TRANSLATE | `_V_FOG_X`(6) → `FOGGENMODE_FOG_X`(4); `default: assert(false)` [V] |
| `NV097_SET_FOG_ENABLE` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2215-2224 | WRITE | only `CONTROL_3_FOGENABLE`; CSV0_D write is commented out (FIXME) [V] |
| `NV097_SET_FOG_ENABLE` (fast path) | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:484-485 | TABLE-ENTRY | `MF_MASKED(NV_PGRAPH_CONTROL_3, 25)`; mask_lut[25] = `CONTROL_3_FOGENABLE` at pgraph.c:307 [V] |
| `NV097_SET_FOG_COLOR` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2226-2237 | TRANSLATE | ABGR param → ARGB register [V] |
| `NV097_SET_FOG_PARAMS` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2860-2872 | WRITE | slots 0,1 → `FOGPARAM0/1`; slot 2 dropped with FIXME [V] |
| `NV097_SET_FOG_PLANE` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2892-2898 | WRITE | → vsh constant `NV_IGRAPH_XF_XFCTX_FOG` [V] |
| `NV097_SET_FOG_COORD` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:3261-3269 | WRITE | replicates scalar into all 4 components of attr 5 [V] |
| foggen state read | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:77-80 | READ | **only read when `CONTROL_3_FOGENABLE` set** [V] |
| fog mode state read | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:144-151 | READ | `/*FIXME: Use CSV0_D? */` [V] |
| foggen → fogDistance | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh-ff.c:448-470 | EMIT-SHADER | 5 modes; `default: assert(!"Invalid foggen mode")` [V] |
| programmable-vsh fogDistance | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:320-327 | EMIT-SHADER | foggen ignored, `fogDistance = oFog.x` [V] |
| fog factor formulas | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:335-374 | EMIT-SHADER | LINEAR / EXP / EXP2 variants [V] |
| fog _ABS handling | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:376-383 | EMIT-SHADER | `fogFactor = abs(fogFactor)` for the 3 `_ABS` modes [V] |
| fog inf/NaN handling | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:385-397 | EMIT-SHADER | `infinite_fogdistance_result` / `nan_fogfactor_result` [V] |
| fog disabled | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:316-318 | EMIT-SHADER | `oFog = vec4(1.0)` with `/* FIXME: Is the fog still calculated ... */` [V] |
| `pFog` combiner register | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1150 | EMIT-SHADER | `vec4(fogColor.rgb, clamp(vtxFog,0,1))` — alpha comes from fog factor, not `FOGCOLOR_ALPHA` [V] |
| fogColor uniform | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1756-1766 | READ | all 4 channels uploaded incl. alpha [V] |
| `PS_REGISTER_FOG` | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:355-356 | EMIT-SHADER | combiner input mapping [V] |
| SPECFOGFACTOR | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1692-1693 | READ | final-combiner constant [V] |

### Blend

| concept | file:line | role | notes |
|---|---|---|---|
| SFACTOR method | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2365-2404 | TRANSLATE | `default: return; /* discard */` [V] |
| DFACTOR method | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2406-2445 | TRANSLATE | discard on unknown [V] |
| EQUATION method | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2452-2475 | TRANSLATE | 7 values → 0..6 [V] |
| fast-path blend xlat | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:229-243 | TRANSLATE | `XLAT_BLEND_FACTOR`, `XLAT_BLEND_EQN`; agrees with slow path [V] |
| fast-path table entries | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:557-563 | TABLE-ENTRY | 0x0344/0x0348/0x0350 [V] |
| blend factor → Vk | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/constants.h:55-72 | TRANSLATE | index 11 = `0` (unreachable via methods) [V] |
| blend equation → Vk | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/constants.h:74-82 | TRANSLATE | 7 entries; **[5]=REVERSE_SUBTRACT, [6]=ADD — same as [1],[2]** [V] |
| blend factor → GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/constants.h:110-127 | TRANSLATE | same shape [V] |
| blend equation → GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/constants.h:129-137 | TRANSLATE | **[5]=`GL_FUNC_REVERSE_SUBTRACT`, [6]=`GL_FUNC_ADD`** [V] |
| logicop map | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/constants.h:84-102, /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/constants.h:139-157 | — | entire table commented out `/* FIXME ... */` in both backends [V] |
| VK static blend state | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1472-1533 | TRANSLATE | src/dstAlpha = src/dstColor; `logicOpEnable = VK_FALSE` hardcoded (line 1526) [V] |
| VK dynamic blend (EDS3) | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:3275-3317 | TRANSLATE | second copy of the same mapping [V] |
| VK reorder-replay blend | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:4584-4620 | TRANSLATE | third copy [V] |
| GL blend | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:187-210 | TRANSLATE | `glBlendFunc` (not Separate), `glBlendEquation`, `glBlendColor` [V] |
| blend colour → float | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1523, /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:205-208 | TRANSLATE | `pgraph_argb_pack32_to_rgba_float` [V] |
| colour write mask VK | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1478-1490 | TRANSLATE | [V] |
| colour write mask GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:182 | WRITE | `glColorMask` [V] |
| dither GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:292-299 | READ/WRITE | `glEnable/glDisable(GL_DITHER)`, `/* FIXME: GL implementation dependent */` [V] |
| dither VK | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1576-1578 | — | `// FIXME: Dither` — commented out [V] |

### Depth / stencil

| concept | file:line | role | notes |
|---|---|---|---|
| `SET_CONTROL0` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2124-2144 | WRITE | stencil-write-enable, Z_FORMAT, Z_PERSPECTIVE [V] |
| `SET_DEPTH_FUNC` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2477-2483 | TRANSLATE | silently ignores out-of-range values [V] |
| `SET_STENCIL_OP_*` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2562-2581 via `kelvin_map_stencil_op` (pgraph.c:2535-2560) | TRANSLATE | `default: assert(false)` [V] |
| fast-path depth/stencil xlat | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:246-257 | TRANSLATE | `XLAT_DEPTH_FUNC`, `XLAT_STENCIL_OP` [V] |
| depth func → Vk | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/constants.h:112-121 | TRANSLATE | [V] |
| stencil func/op → Vk | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/constants.h:123-144 | TRANSLATE | op index 0 = `0` (unused; HW ops are 1..8) [V] |
| depth/stencil → GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/constants.h:159-194 | TRANSLATE | [V] |
| VK static depth/stencil | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1420-1470 | TRANSLATE | used only when extended dynamic state is NOT available [V] |
| VK dynamic depth/stencil | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:3173-3272 | TRANSLATE | second copy; applies `STENCIL_WRITE_ENABLE` gate at 3198, 3226 [V] |
| VK reorder-replay depth/stencil | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:4507-4582 | TRANSLATE | third copy; gate at 4541 [V] |
| GL depth/stencil | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:237-289 | TRANSLATE | `glDepthFunc`, `glStencilFunc`, `glStencilOp`; `glStencilMask` at 184 [V] |
| depth clamp GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:249-251 | WRITE | `glEnable(GL_DEPTH_CLAMP)` unconditional (skipped on Android) [V] |
| depth clamp VK | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1389-1391 | WRITE | `depthClampEnable` = device support, not NV2A state [V] |
| z clamp/cull → shader | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:113-116, 1134-1142 | READ / EMIT-SHADER | `depth_clipping` ⇒ `discard` when outside `clipRange.zw`, else `clamp` [V] |
| depth output (frag) | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1561-1578 | EMIT-SHADER | `gl_FragDepth` per `depth_format`; **gated on `depth_needed`** [V] |
| `depth_needed` gate | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:118-126 | READ | **only computed when renderer != OpenGL** [V] |
| polygon offset uniforms | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1772-1818 | READ | `polygon_offset_enabled` from FRONTFACEMODE + POFFSET*ENABLE; `NV2A_UNIMPLEMENTED` at 1813 [V] |
| polygon offset math | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1106-1131 | EMIT-SHADER | `depthOffset` + `depthFactor*triMZ`; gated on `depth_needed` [V] |
| `triMZ` (depth slope) | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/geom.c:157, /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:412 | EMIT-SHADER | geom shader computes; VS path sets 0.0 [V] |
| GL polygon offset | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:230-235 | WRITE | all three `glDisable(GL_POLYGON_OFFSET_*)` [V] |
| VK depth bias | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1398 | WRITE | `.depthBiasEnable = VK_FALSE` hardcoded [V] |
| clear depth/stencil value | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:4261-4292 | TRANSLATE | Z16/Z24S8, fixed vs float; `/* FIXME: Remove bit for stencil clear? */` [V] |
| depth format selection | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:243-261 | TRANSLATE | `Z_FORMAT` × zeta format → D16/D24/F16/F24 [V] |
| `zeta_write_enabled` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.h:439-444 | READ | ZWRITEENABLE \| STENCIL_WRITE_ENABLE [V] |

### Clip / viewport / window clip

| concept | file:line | role | notes |
|---|---|---|---|
| `SET_WINDOW_CLIP_TYPE` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2239-2243 | WRITE | → `SETUPRASTER_WINDOWCLIPTYPE` [V] |
| `SET_WINDOW_CLIP_TYPE` (fast) | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:485-486 | TABLE-ENTRY | `MF_MASKED(NV_PGRAPH_SETUPRASTER, 4)`, mask_lut[4] at pgraph.c:286 [V] |
| `SET_WINDOW_CLIP_HORIZONTAL/VERTICAL` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2245-2258 | WRITE | writes slot..7 with same value (HW propagation emulation) [V] |
| window clip count | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:67-87 | READ | **skipped entirely for the OpenGL renderer** (line 68) [V] |
| window clip type read | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:64-65 | READ | read for both renderers [V] |
| window clip shader | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1039-1085 | EMIT-SHADER | **inclusive AND exclusive both implemented**; 1-region and N-region variants [V] |
| clipRegion uniform | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1832-1851 | READ | 8 rects, AA + scale applied [V] |
| `SET_CLIP_MIN/MAX` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2648-2656 | WRITE | → `ZCLIPMIN`/`ZCLIPMAX` [V] |
| clipRange uniform | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/common.c:95-116 | TRANSLATE | `[0]=0,[1]=zmax,[2]=zclipmin,[3]=zclipmax` [V] |
| `SET_ZMIN_MAX_CONTROL` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:3992-4010 | TRANSLATE | CULL/CLAMP → `ZCOMPRESSOCCLUDE_ZCLAMP_EN`; `assert(!"Invalid zclamp value")` [V] |
| surface clip scissor GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:336-350 | WRITE | `/* FIXME: Consider moving to PSH w/ window clip */` at 337 [V] |
| surface clip scissor VK | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:3115-3135 | WRITE | identical code + identical FIXME at 3116 [V] |
| clear-rect scissor GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:126-128 | WRITE | `/* FIXME: Respect window clip?!?! */` [V] |
| clear-rect VK | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:5233-5252, 5294-5320 | WRITE | inline `vkCmdClearAttachments` path + pipeline path; no window clip [V] |
| viewport GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:330-334 | WRITE | `glViewport(0,0,surface_w,surface_h)` — NV2A viewport is applied in VS [V] |
| viewport VK | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:3101-3113 | WRITE | `minDepth 0, maxDepth 1` [V] |
| viewport offset in VS | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh-ff.c:481-489 | EMIT-SHADER | `c[VPOFF].xy` then NDC remap by `surfaceSize` [V] |
| programmable VS position | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh-prog.c:757-770 | EMIT-SHADER | [V] |
| depth range remap | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:435-443 | EMIT-SHADER | GL uses `2z-w`, VK uses `z` [V] |
| shader clip planes | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:140-144 | READ | `SHADERCLIPMODE` → per-texture `compare_mode[i][j]` (shadow compare), not geometric clip planes [V] |

### Line / point / polygon

| concept | file:line | role | notes |
|---|---|---|---|
| `SET_POINT_SIZE` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2799-2806 | WRITE | values > 0x1FF are dropped [V] |
| point size in VS | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:131-138, 308-314, 412-414 | READ/EMIT-SHADER | `POINTSIZE/8.0`, `gl_PointSize = oPts.x` [V] |
| point params | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh-ff.c:492-506 | EMIT-SHADER | distance attenuation formula [V] |
| point sprite | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:99-101, 1154-1156 | READ/EMIT-SHADER | derived from **`POINTSMOOTHENABLE`**; replaces `pT3` with `gl_PointCoord` [V] |
| GL program point size | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:302-305 | WRITE | `glEnable(GL_PROGRAM_POINT_SIZE)` [V] |
| VK point size | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1579 | — | `// FIXME: point size` [V] |
| GL line/poly smooth | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:308-328 | READ/WRITE | `GL_LINE_SMOOTH`, `GL_POLYGON_SMOOTH`, gated on `ANTIALIASING_ENABLE`; entire block `#ifndef __ANDROID__` [V] |
| VK line/poly smooth | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1580-1591 | — | fully commented out (`FIXME: VK_EXT_line_rasterization`) [V] |
| GL line width | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:310-322 | WRITE | `glLineWidth(min(device_max, surface_scale_factor))` — **no NV2A input** [V] |
| VK line width | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1398 (static 1.0), 3028-3041, 3137-3141, 4272-4275, 4406-4409, 4478-4480 | WRITE | dynamic width = `surface_scale_factor` only [V] |
| cull face VK | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1400-1412 (static), 3146-3168 (dynamic), 4484-4497 (replay) | TRANSLATE | three copies [V] |
| cull face GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:212-228 | TRANSLATE | `glCullFace`, `glFrontFace` (winding reversed: comment at 225) [V] |
| polygon mode VK | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1379-1385 | TRANSLATE | falls back to FILL when `fillModeNonSolid` unsupported [V] |
| polygon mode map | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/constants.h:146-150 | TRANSLATE | FILL/POINT/LINE [V] |
| polygon mode GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/geom.c:81-112 | EMIT-SHADER | wireframe/points synthesised in the geometry shader, not `glPolygonMode` [V] |
| shade mode | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2583-2599 | TRANSLATE | unknown values discarded [V] |
| flat-shade interpolation | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/common.c:54-55, /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/geom.c:73, 149-164 | EMIT-SHADER | provoking index hardcoded to `0` for flat; `vtxFog`/`vtxT*` always use `index` [V] |
| provoking vertex GL | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:253-256 | WRITE | `glProvokingVertex(GL_FIRST_VERTEX_CONVENTION)` [V] |
| anti-aliasing control | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:4012-4017 | WRITE | `// FIXME: Handle the remaining bits` [V] |

### Vertex attributes

| concept | file:line | role | notes |
|---|---|---|---|
| `SET_VERTEX_DATA_ARRAY_FORMAT` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:3513-3560 | WRITE | sets `size`; `assert(count==4)` for UB_D3D; `assert(count==1)` for CMP [V] |
| `SET_VERTEX_DATA_ARRAY_OFFSET` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:3562-3569 | WRITE | + fast-path `MF_VTX_OFF` at pgraph.c:493-509, applied at 663-670 [V] |
| inline value decode | /home/user/hakuX/hw/xbox/nv2a/pgraph/vertex.c:24-81 | TRANSLATE | **UB_D3D and UB_OGL share one branch** (lines 33-38) [V] |
| GL attrib binding | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/vertex.c:82-228 | TRANSLATE | UB_D3D → `GL_BGRA` count (non-Android) or `d3d_swizzle` (Android) at 121-131 [V] |
| VK attrib binding | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/vertex.c:128-340 | TRANSLATE | UB_D3D sets `d3d_swizzle` and reuses `ub_to_count` (lines 205-211) [V] |
| stride-0 carryover | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/vertex.c:195-203, /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/vertex.c:269-281 | READ | `pgraph_update_inline_value(attr, last_entry)` [V] |
| provoking-element carryover | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/vertex.c:222-223, /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/vertex.c:283-284 | READ | `last_entry += stride * provoking_element_index` [V] |
| inline buffer carryover | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:566-568, /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/vertex.c:378-380 | WRITE | copies the last inline-buffer vertex into `inline_value` [V] |
| CMP unpack | /home/user/hakuX/hw/xbox/nv2a/pgraph/vertex.c:56-75 | TRANSLATE | 11/11/10 signed unpack [V] |
| VK vertex-attr cache | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/vertex.c:140-166 | READ | keyed on `pg->vertex_attr_gen` [V] |

### Primitive type

| concept | file:line | role | notes |
|---|---|---|---|
| `SET_BEGIN_END` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:3610-3632 | DISPATCH | `assert(parameter <= OP_POLYGON)`; Begin-without-End is dropped [V] |
| output mode selection | /home/user/hakuX/hw/xbox/nv2a/pgraph/prim_rewrite.c:47-71 | TRANSLATE | 11 NV2A modes → POINTS/LINES/TRIANGLES [V] |
| rewrite dispatch | /home/user/hakuX/hw/xbox/nv2a/pgraph/prim_rewrite.c:389-436 | DISPATCH | per-primitive rewrite [V] |
| `needs_rewrite` | /home/user/hakuX/hw/xbox/nv2a/pgraph/prim_rewrite.c:73-83 | READ | LINES/TRIANGLES rewritten only when `last_provoking && flat_shading` [V] |
| quads flat-shade diagonal | /home/user/hakuX/hw/xbox/nv2a/pgraph/prim_rewrite.c:270-291 | TRANSLATE | flat: v1-v3 diagonal; smooth: v0-v2 (comment admits depth-slope difference) [V] |
| quad-strip flat diagonal | /home/user/hakuX/hw/xbox/nv2a/pgraph/prim_rewrite.c:309-335 | TRANSLATE | same trade-off [V] |
| VK topology | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:346-362 | TRANSLATE | only 3 topologies; `assert(!"Invalid primitive_mode")` [V] |
| GL topology | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/shaders.c:36, 329-330, 447-448 | TRANSLATE | `get_gl_primitive_mode` [V] |
| geometry shader need | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/geom.c:48-59 | DISPATCH | LINES/TRIANGLES only [V] |
| GL draw dispatch | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:429-616 | DISPATCH | 4 source paths [V] |
| VK draw dispatch | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:5636+ | DISPATCH | mirrors GL, plus queueing/reorder paths [V] |

---

## State distinctions we may not implement

Search method used for every "no reader" claim below: `grep -rn <symbol> /home/user/hakuX/hw/xbox/` (whole `hw/xbox` tree, all file types), then manual inspection of every hit. Claims are about *this* search; a reader reached by a different spelling (e.g. a literal bit index) would not be found.

### Window clip — the specific case asked about

**The premise "inclusive vs exclusive is implemented as exclusive in both cases" does NOT match what is in this tree.** What I actually found:

1. **Vulkan: inclusive and exclusive ARE distinguished.** `psh.c:1045-1085` emits genuinely different code — exclusive discards fragments *inside* any region; inclusive accumulates `clipContained` and discards fragments *outside* all regions. The comment string at 1042-1044 even prints "Exc"/"Inc". Confidence: **high [V]**, read the whole generator block.

2. **OpenGL: window clip is not implemented at all** — neither inclusive nor exclusive.
   - `psh.c:67-87`: the region count loop is wrapped in `if (g_config.display.renderer != CONFIG_DISPLAY_RENDERER_OPENGL)`, so `state->window_clip_count` is never assigned on GL.
   - `shaders.c:79`: `memset(&state, 0, sizeof(ShaderState))` ⇒ it stays `0`.
   - `psh.c:1041`: `if (wc_count > 0)` ⇒ no clip code is emitted for GL at all.
   - `gl/draw.c:336-350`: the only scissor set during a draw is the **surface** clip, with `/* FIXME: Consider moving to PSH w/ window clip */` at 337.
   - `gl/draw.c:126`: the clear path carries `/* FIXME: Respect window clip?!?! */`.
   - Searched: `grep -rn "WINDOWCLIP\|window_clip\|WINDOW_CLIP" hw/xbox/nv2a/` — the complete set of readers is `glsl/psh.c` (lines 64-86, 1039-1085, 1833-1850). Nothing in `gl/`.
   Confidence: **high [V]**.

3. **Window clip is not applied to `NV097_CLEAR_SURFACE` in either backend.** GL: `gl/draw.c:126-128`. VK: the inline clear (`vk/draw.c:5233-5252`) and the pipeline clear (`vk/draw.c:5294-5345`) both use only the clear rect, and the clear pipeline's fragment shader is `solid_frag_glsl` (`vk/draw.c:527-533`) which contains no clip code. Confidence: **high [V]**.

4. **Dirty-tracking gap: changing only the window-clip *rectangles* may not regenerate the shader.** `NV_PGRAPH_WINDOWCLIPX0..7`/`Y0..7` are absent from the shader-state register list in `glsl/shaders.c:95-103` and from the `REG_CAT_SHADER` set in `pgraph.c:109-116`. Consequences, in order:
   - `pgraph_reg_w` (`pgraph.h:333-354`) bumps `shader_state_gen` only for `REG_CAT_SHADER` registers, so a window-clip-rect write does not bump it.
   - `vk/draw.c:1210-1214` calls `pgraph_vk_bind_shaders` only when `program_data_dirty || !shader_binding || shader_state_gen changed || primitive_mode changed`.
   - Even if reached, `pgraph_glsl_check_shader_state_dirty` (`glsl/shaders.c:88-144`) does not test those registers, and `pgraph_vk_bind_shaders` (`vk/shaders.c:1250-1263`) reuses `cached_shader_state` when `shader_state_gen` is unchanged.
   ⇒ a test that establishes clip rects *after* its last shader-state-affecting register write can be rendered with a stale `window_clip_count`. Note `SET_WINDOW_CLIP_TYPE` writes `SETUPRASTER`, which *is* tracked, so toggling incl/excl does force a regen. `pg->surface_shape.clip_width/clip_height` (used at `psh.c:70-72` to decide whether a region is "trivial") is likewise not in the dirty check. Confidence: **medium-high [V] on the code; [I] on whether real test sequences hit it.**

### Fog

- **`NV_PGRAPH_CSV0_D_FOGENABLE`** (nv2a_regs.h:294) — **no writer, no reader.** The only write site is commented out inside a FIXME block at `pgraph.c:2216-2220`. Searched `grep -rn "CSV0_D_FOGENABLE" hw/xbox/nv2a/` → only the definition and that comment. [V]
- **`NV_PGRAPH_CSV0_D_FOG_MODE`** + `_LINEAR`/`_EXP` (nv2a_regs.h:298-300) — **no writer, no reader.** `pgraph.c:2171` says `/* FIXME: There is also NV_PGRAPH_CSV0_D_FOG_MODE */`. Fog mode is taken exclusively from `CONTROL_3` (`glsl/vsh.c:147-150`). If hardware has two independent fog-mode fields, tests that set them differently collapse. [V] for the absence; [I] for the hardware consequence.
- **Fog gen mode is ignored entirely for programmable vertex shaders.** `glsl/vsh.c:320-327` uses `oFog.x` regardless of `FOGGENMODE`; the FOGGEN switch exists only in `vsh-ff.c:448-470`. Also `glsl/vsh.c:77-80` only samples FOGGENMODE at all when `FOGENABLE` is set. So `Fog_gen` variants differing only in gen mode render identically under a programmable VSH. [V]
- **`FOG_MODE_EXP2` vs `FOG_MODE_EXP2_ABS` differ only by `abs(fogFactor)`.** `glsl/vsh.c:361-371` puts both in one `case` block and neither sets `infinite_fogdistance_result`/`nan_fogfactor_result` (both stay 0.0f, initialised at 332-333), unlike LINEAR/LINEAR_ABS/EXP which set 1.0f. So for infinite fog distance, EXP2 and EXP2_ABS both give `oFog = 0`, while EXP gives 1 and EXP_ABS gives 0. Whether that asymmetry is intentional I cannot tell. [V] for the code; **uncertain** for correctness.
- **The `_ABS` fog modes take `abs()` of the fog *factor*, not the fog *distance*** (`glsl/vsh.c:376-383`). I could not verify which the hardware does. Listed as an uncertainty, not a defect.
- **`FOG_MODE_ERROR2` (2) and `FOG_MODE_ERROR6` (6)** (`vsh_regs.h:45,49`) are reachable register encodings of the 3-bit `CONTROL_3_FOG_MODE` field but have no method that produces them and hit `default: assert(false)` at `glsl/vsh.c:372-374`. [V]
- **`NV_PGRAPH_FOGCOLOR_ALPHA` is uploaded but never consumed.** `psh.c:1763-1765` fills `fogColor[0][3]`; `psh.c:1150` builds `pFog` from `fogColor.rgb` only. This is very likely correct (the fog register's alpha is the fog factor on NV2A) — flagged only so it is not mistaken for a missing feature. [V]
- **Fog is smooth-interpolated even under flat shading.** `glsl/geom.c:149-158`: `vtxD0/D1/B0/B1` use `provoking_index`, but `vtxFog` uses `index`. Confirmed by `common.c:54-55` which declares `vtxFog` with the `smooth_s` qualifier while `triMZ` uses `flat_s`. So `Fog_*` + flat shading may differ from hardware. [V] for the code; [I] for the hardware expectation.
- **`NV097_SET_FOG_PARAMS` slot 2 is dropped** — `pgraph.c:2865-2867` `/* FIXME: No idea where slot = 2 is */`. It still lands in `ltctxa[FOG_K][2]`, so a vertex program could read it, but it never reaches `FOGPARAM*`. [V]

### Blend

- **`NV097_SET_BLEND_EQUATION_V_FUNC_ADD_SIGNED` (0xF006) collapses onto `FUNC_ADD`, and `_FUNC_REVERSE_SUBTRACT_SIGNED` (0xF005) onto `FUNC_REVERSE_SUBTRACT`, in BOTH backends.** Definitions at nv2a_regs.h:997-998; translation to distinct register values 5 and 6 at `pgraph.c:2470-2473`; then `vk/constants.h:74-82` entries `[5]=VK_BLEND_OP_REVERSE_SUBTRACT`, `[6]=VK_BLEND_OP_ADD` (identical to `[1]` and `[2]`), and `gl/constants.h:129-137` `[5]=GL_FUNC_REVERSE_SUBTRACT`, `[6]=GL_FUNC_ADD`. This is a textbook one-bit-difference-renders-identically case. Confidence: **high [V]**.
- **Logic op is entirely unimplemented in both backends.** `NV_PGRAPH_BLEND_LOGICOP_ENABLE`/`_LOGICOP` (nv2a_regs.h:394-395) are written (`pgraph.c:3573-3582`, plus fast-path entries at `pgraph.c:543-546`) but the only consumers are: the mapping table commented out at `vk/constants.h:84-102` and `gl/constants.h:139-157`; `vk/draw.c:1526` hardcodes `logicOpEnable = VK_FALSE`; `vk/draw.c:1134-1135` and `pgraph.c:71-72` explicitly mark those bits "dynamic" so they never even force a pipeline rebuild. No `glLogicOp`/`GL_COLOR_LOGIC_OP` anywhere (searched `grep -n "glLogicOp\|GL_COLOR_LOGIC_OP" hw/xbox/nv2a/pgraph/**`). Confidence: **high [V]**.
- **Separate alpha blend factors are not modelled** — `srcAlphaBlendFactor = srcColorBlendFactor` (`vk/draw.c:1489-1494`, `vk/draw.c:3296-3299`, `vk/draw.c:4598-4603`); GL uses `glBlendFunc`, not `glBlendFuncSeparate` (`gl/draw.c:196-197`). This matches the single `SFACTOR`/`DFACTOR` register pair, so it is very likely correct, not a gap. [V]
- **Blend-factor slot 11 maps to `0`** in both tables (`vk/constants.h:66`, `gl/constants.h:121`). Unreachable through `SET_BLEND_FUNC_*` (both the slow path at `pgraph.c:2365-2404` and the fast path at `pgraph.c:229-234` reject the gap), so this is inert rather than a bug. [V]
- **`NV_PGRAPH_CONTROL_0_DITHERENABLE`:** honoured in GL (`gl/draw.c:292-299`, with a caveat that GL dithering is implementation-defined) but **not in VK** (`vk/draw.c:1576-1578`, commented out; also masked out of the pipeline key at `vk/draw.c:1136-1137`). Dither on/off pairs render identically under Vulkan. Confidence: **high [V]**.

### Depth / stencil

- **`NV_PGRAPH_CONTROL_0_STENCIL_WRITE_ENABLE` is honoured in exactly one of three code paths.**
  - Honoured: VK dynamic-state path (`vk/draw.c:3196-3202`, `3226-3228`) and VK reorder replay (`vk/draw.c:4541-4542`) — both only when `r->extended_dynamic_state_supported`.
  - **Not** honoured: VK static-pipeline path — `vk/draw.c:1443-1444`, `1466` sets `depth_stencil.front.writeMask = mask_write` with no gate.
  - **Not** honoured: GL — `gl/draw.c:184-185` is `glStencilMask(GET_MASK(CONTROL_1, STENCIL_MASK_WRITE))` with no reference to `STENCIL_WRITE_ENABLE`. Searched `grep -rn "STENCIL_WRITE_ENABLE" hw/xbox/nv2a/pgraph/gl/` → zero hits.
  Confidence: **high [V]**.
- **`ZMIN_MAX_CONTROL` CULL vs CLAMP is implemented only for non-OpenGL renderers.** The distinction lives at `psh.c:1134-1142` (`discard` vs `clamp`), inside `if (ps->state->depth_needed)` (`psh.c:1088`), and `depth_needed` is only ever assigned inside `if (g_config.display.renderer != CONFIG_DISPLAY_RENDERER_OPENGL)` at `psh.c:118-126` (zeroed by the `memset` at `shaders.c:79`). GL instead calls `glEnable(GL_DEPTH_CLAMP)` unconditionally at `gl/draw.c:249-251`. So under GL, ZCLAMP_EN=CULL and =CLAMP render identically (both clamp), and `NV097_SET_CLIP_MIN/MAX` are not enforced at all. Confidence: **high [V]**.
- **Polygon offset is implemented only for non-OpenGL renderers.** `psh.c:1106-1131` (the `depthOffset`/`depthFactor*triMZ` application) sits inside the same `depth_needed` gate; `gl/draw.c:230-235` disables all three GL polygon-offset modes with the comment "Polygon offset is handled in geometry and fragment shaders explicitly". Under GL that shader code is not generated ⇒ `NV097_SET_POLYGON_OFFSET_SCALE_FACTOR`, `_BIAS`, and all three `POLY_OFFSET_*_ENABLE` bits have no effect. Confidence: **high [V] on the code paths**; I did not run the emulator to confirm.
- **VK never uses hardware depth bias** — `.depthBiasEnable = VK_FALSE` at `vk/draw.c:1398`, `VK_DYNAMIC_STATE_DEPTH_BIAS` is not in the dynamic-state list (`vk/draw.c:1536-1560`). Offset is entirely fragment-shader-side. [V]
- **`polygon_offset_enabled` consults only `FRONTFACEMODE`.** `psh.c:1774-1785` reads `NV_PGRAPH_SETUPRASTER_FRONTFACEMODE`; `NV_PGRAPH_SETUPRASTER_BACKFACEMODE` (nv2a_regs.h:504) is never consulted there. Searched `grep -rn "BACKFACEMODE" hw/xbox/nv2a/` → definition, the `mask_lut` entry at `pgraph.c:292`, the `SET_BACK_POLYGON_MODE` writer at `pgraph.c:2641-2646`/`pgraph.c:576-577`, and one reader at `glsl/geom.c:31-33` which only uses it in the two `assert(front == back)` checks. So a draw where front and back polygon modes differ in their offset-enable relevance collapses. [V]
- **`polygon_offset_enabled` requires `pg->primitive_mode >= PRIM_TYPE_TRIANGLES`** (`psh.c:1773`). Given `PRIM_TYPE_POINTS`=1, `LINES`=2, `LINE_LOOP`=3, `LINE_STRIP`=4, `TRIANGLES`=5 (`vsh_regs.h:186-191`), `POFFSETPOINTENABLE`/`POFFSETLINEENABLE` can never take effect for real point/line primitives — only for triangle-class primitives whose *polygon mode* is POINT/LINE. That is plausibly correct HW behaviour; flagged for awareness, not asserted as a defect. [V] on the code.
- **`ZOFFSETFACTOR` is knowingly wrong under w-buffering** — `NV2A_UNIMPLEMENTED("NV_PGRAPH_ZOFFSETFACTOR only partially implemented for w-buffering")` at `psh.c:1813`, guarded by `Z_PERSPECTIVE_ENABLE`. Note `NV2A_UNIMPLEMENTED` compiles to a no-op unless `DEBUG_NV2A_FEATURES` is set (`hw/xbox/nv2a/debug.h:59-68`), so this is silent in normal builds. [V]
- **`NV_PGRAPH_SHADOWCTL_SHADOW_ZFUNC`**: written at `pgraph.c:4087-4091`, read at `psh.c:103-105`. Implemented. Not a gap.
- **`NV097_SET_ANTI_ALIASING_CONTROL` non-enable bits are dropped** — `pgraph.c:4012-4017` `// FIXME: Handle the remaining bits (observed values 0xFFFF0000, 0xFFFF0001)`. [V]

### Line / point

- **There is no line-width register or method anywhere in the NV2A model.** Searched `grep -rn "LINE_WIDTH\|line_width\|LINEWIDTH" hw/xbox/nv2a/` — every hit is a *host* API concept (`GL_ALIASED_LINE_WIDTH_RANGE` at `gl/renderer.c:158-165`, `VK_DYNAMIC_STATE_LINE_WIDTH` at `vk/draw.c:1567`). The width actually used is `pg->surface_scale_factor` (`gl/draw.c:312-322`, `vk/draw.c:3138-3140`, `vk/draw.c:4274-4275`, `vk/draw.c:4408-4409`) — i.e. it tracks the *upscale factor*, not any guest state. **If `Line_width` varies line width via a guest register, that register is not modelled at all in `nv2a_regs.h`.** Confidence: **high [V]** for the absence in this tree.
- **There is no stipple state anywhere.** Searched `grep -rni "stipple" hw/xbox/` → zero hits. `Stipple_tests` cannot be exercising anything modelled here. Confidence: **high [V]**.
- **`LINESMOOTHENABLE` / `POLYSMOOTHENABLE` are ignored by Vulkan.** Read by GL at `gl/draw.c:308-328`; in VK the equivalent block is commented out (`vk/draw.c:1580-1591`) and both bits are explicitly stripped from the pipeline key (`vk/draw.c:1152-1154`) and marked "dynamic" (`pgraph.c:61-63`). Also: GL's smooth block is inside `#ifndef __ANDROID__` (`gl/draw.c:307-329`), so smoothing is off on Android GLES too. Confidence: **high [V]**.
- **`POINTSMOOTHENABLE` is re-purposed as "point sprite enable".** `psh.c:99-101` assigns it to `state->point_sprite`; `psh.c:1154-1156` then replaces texture coordinate 3 with `gl_PointCoord`. Searched `grep -rn "POINTSMOOTHENABLE" hw/xbox/nv2a/` — the only other hits are the writer (`pgraph.c:2305-2309`) and the `mask_lut` entry (`pgraph.c:293`). So there is **no** point-*antialiasing* implementation, and enabling point smoothing silently changes texture-coordinate generation. Whether that conflation matches hardware I cannot confirm — but "point smooth on/off" is definitely not a pure rasterisation difference here. Confidence: **high [V] on the code**, **uncertain on hardware semantics**.
- **`NV097_SET_POINT_SIZE` values above `0x1FF` are silently dropped** (`pgraph.c:2801-2803`) rather than clamped. [V]

### Primitive assembly / shading

- **Two-sided polygon mode is not supported and asserts.** `glsl/geom.c:50-51` and `glsl/geom.c:64-65`: `/* FIXME: Missing support for 2-sided-poly mode */ assert(state->polygon_front_mode == state->polygon_back_mode);`. So any test setting `NV097_SET_FRONT_POLYGON_MODE != NV097_SET_BACK_POLYGON_MODE` aborts in an assert-enabled build. `BACKFACEMODE` is stored and hashed into the shader key (`geom.c:31-33`) but never used to generate anything. Confidence: **high [V]**.
- **Quad / quad-strip flat shading uses a different diagonal from hardware, by design.** `prim_rewrite.c:279-286` and `prim_rewrite.c:322-329` both carry: "This gives correct flat shading color but slightly different depth slope vs hardware." So flat-shaded quads have a wrong `triMZ` ⇒ wrong polygon-offset slope and wrong `Depth_buffer`-style interpolation. Confidence: **high [V]**.
- **`PROVOKING_VERTEX` FIRST vs LAST is ignored for QUADS, QUAD_STRIP and POLYGON.** `rewrite_quads` (`prim_rewrite.c:270-291`) and `rewrite_quad_strip` (`prim_rewrite.c:309-335`) take `flat_shading` but not `last_provoking`, and always use `v3` as the flat-colour source; `rewrite_polygon` (`prim_rewrite.c:357-372`) takes neither and always fans from index 0. The dispatcher at `prim_rewrite.c:412-432` confirms `mode->last_provoking` is not forwarded for those three cases. So under flat shading, PROVOKING_VERTEX=FIRST and =LAST render identically for quads and polygons. Confidence: **high [V]**.
- **QUADS/QUAD_STRIP with `POLY_MODE_POINT` are tessellated to triangles first.** `pgraph_prim_rewrite_get_output_mode` (`prim_rewrite.c:63-67`) only special-cases `POLY_MODE_LINE`; POINT falls to TRIANGLES, and `geom.c:100-109` then emits three points per triangle ⇒ 6 points per quad with a duplicated diagonal pair, instead of 4. Confidence: **high [V] on the code path**; [I] on the hardware expectation.
- **`PRIM_TYPE_POLYGON` with `POLY_MODE_POINT` asserts** — `prim_rewrite.c:447` and `prim_rewrite.c:485`. [V]
- **Flat-shaded `vtxT0..vtxT3` are smooth-interpolated** — `geom.c:153-156` uses `index`, not `provoking_index`; `common.c` declares them smooth. Only the four colour varyings use the provoking index. [V] on the code.

### Vertex attributes

- **`UB_D3D` and `UB_OGL` produce identical results in `pgraph_update_inline_value`.** `vertex.c:33-38` shares one `case` label pair, dividing `data[i]` by 255 in memory order — no BGRA→RGBA reorder. The array path *does* distinguish them (`gl/vertex.c:121-131` → `GL_BGRA`; `vk/vertex.c:205-211` → `d3d_swizzle`), so a **UB_D3D attribute whose value is carried over (stride 0, or the trailing value used for the next draw's `inline_value`) will have swapped R/B relative to the same attribute read as a real array.** This is directly on the `Attrib_carryover` path. Confidence: **high [V] on the asymmetry**; [I] that it produces a visible difference.
- **`SET_VERTEX_DATA_ARRAY_FORMAT_TYPE` values 3, 7..15 are undefined** in `nv2a_regs.h:1139-1144` and hit `assert(false)` at `pgraph.c:3552-3555`, `gl/vertex.c:154-157`, `vk/vertex.c:233-236`. [V]
- **`NV_IGRAPH_XF_XFCTX_VPSCL`** (nv2a_regs.h:1344) is written by `SET_VIEWPORT_SCALE` (`pgraph.c:3080-3086`) but no generated shader references it by name (searched `grep -rn "VPSCL" hw/xbox/nv2a/` → writer + definition only). It is still uploaded into the generic `c[]` constant array, so a vertex program can read it; the fixed-function path folds viewport scale into the composite matrix instead (`vsh-ff.c:481-489` uses only `VPOFF`). Not a gap, but worth knowing. [V]

---

## Coupling points (must-agree, unenforced)

1. **Blend / depth / stencil translated in FIVE places, with no shared helper.**
   - VK static pipeline: `/home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1420-1533`
   - VK dynamic state: `/home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:3146-3317`
   - VK reorder-window replay: `/home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:4484-4620`
   - VK async-compile copy: `/home/user/hakuX/hw/xbox/nv2a/pgraph/vk/compile_worker.c:139` (copies `has_dynamic_line_width` and the pre-built structs)
   - GL: `/home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:186-289`
   Already divergent: the `STENCIL_WRITE_ENABLE` gate exists at `vk/draw.c:3198`, `3226`, `4541` but not at `vk/draw.c:1466` and not in GL at all. [V]

2. **Method decode duplicated between the fast-path table and the `DEF_METHOD` handlers.** `method_fast[]` (`pgraph.c:343-582`) plus `fast_xlat` (`pgraph.c:228-273`) must agree with the handlers in `pgraph.c:2124-4110`. I checked blend factor/equation, depth func, stencil op, shade mode, polygon mode, cull face and front face; they agree today. Nothing enforces it — there is no shared table and no cross-check. The two also differ in *error* handling: e.g. `SET_CULL_FACE` slow path `assert(false)` (`pgraph.c:2670-2672`) vs fast path returning `UINT32_MAX` and falling through to the slow path (`pgraph.c:1561`, `pgraph.c:746`). [V]

3. **`pgraph_reg_w` and `pgraph_reg_w_atomic` must implement identical dirty/generation logic.** `pgraph.h:333-354` vs `pgraph.h:363-391`. They currently match line-for-line; the lockless PFIFO path uses the atomic one (`pgraph.c:746`, `756`, `784`). [V]

4. **`pgraph_reg_dynamic_mask_table` must agree with what each backend actually sets dynamically.** Built in `pgraph_init_reg_dynamic_masks` (`pgraph.c:50-106`) from `eds1`/`eds3` capability flags; consumed implicitly by `pgraph_reg_w`. If a bit is marked dynamic but the backend bakes it into the pipeline, changes are silently lost. Two entries worth auditing: `POFFSET*ENABLE` and `LINESMOOTH/POLYSMOOTHENABLE` are marked dynamic unconditionally (`pgraph.c:59-63`) even though on GL they are read at draw time from `SETUPRASTER` (fine) and on VK they feed *uniforms* (`psh.c:1774-1817`) rather than pipeline state. I traced the uniform path: `begin_pre_draw` bails out of the super-fast path whenever `pg->any_reg_gen != r->last_any_reg_gen` (`vk/draw.c:2761-2763`) and then calls `pgraph_vk_update_shader_uniforms` (`vk/draw.c:2932`), so uniforms do get refreshed. **No bug found here** — recording it because the invariant is unenforced. [V]

5. **`init_pipeline_key`'s masked-out register bits must match the dynamic-state list.** `vk/draw.c:1090-1167` strips bits from `key->regs[]`; `vk/draw.c:1536-1568` builds `dynamic_states[]`. `key->regs` index ordering is positional (`regs[0]=BLEND`, `[1]=CONTROL_0`, `[2]=CONTROL_2`, `[3]=CONTROL_3`, `[4]=SETUPRASTER`, `[5]=CONTROL_1` under `OPT_DYNAMIC_STATES`, a *different* order and length in the `#else` branch at `vk/draw.c:1109-1116`). Two positional lists that must stay in lockstep; only `assert(ARRAY_SIZE(regs) == ARRAY_SIZE(key->regs))` (`vk/draw.c:1119`) is checked, not the ordering. [V]

6. **GL and VK share `prim_rewrite.c` and the GLSL generators but not the fixed-function state.** Shared: `PrimAssemblyState` construction is duplicated verbatim at `gl/draw.c:438-450`, `vk/draw.c:5663-5675`, `vk/draw.c:3618-3630`, `vk/draw.c:3919-3932`, `vk/draw.c:4225-4237`, `vk/draw.c:4347-4358` — six copies of the same four-field initialiser. [V]

7. **`psh.c` branches on `g_config.display.renderer` in two places** (`psh.c:68`, `psh.c:120`) rather than on a backend capability passed in. Anything that changes the renderer at runtime (`pgraph.c:4337` compares `g_config.display.renderer != pg->renderer->type`) must invalidate every cached shader; the shader-state hash does not include the renderer. [V] — **this is a real hazard**: `ShaderState` (`glsl/shaders.h:28-32`) has no renderer field, so a GL-generated `PshState` and a VK-generated one for the same registers hash identically despite differing in `window_clip_count`/`depth_needed`.

8. **GLES fallbacks silently change behaviour.** `gl/shaders.c:271-278`: when geometry shaders are unavailable, `need_geometry_shader` is forced false, with the comment "flat shading provoking vertex may be wrong, wireframe mode won't work". `gl/draw.c:253-256`: `glProvokingVertex` is skipped on Android. `gl/draw.c:249-251`: `GL_DEPTH_CLAMP` skipped on Android. [V]

---

## Stubs and gaps

| symbol | file:line | kind | what behaviour it gates | ABORTS? |
|---|---|---|---|---|
| 2-sided polygon mode | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/geom.c:50-51 | FIXME + assert | front≠back polygon mode | **Yes** (assert), in assert-enabled builds |
| 2-sided polygon mode | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/geom.c:64-65 | FIXME + assert | same, in the generator | **Yes** |
| POLYGON + POLY_MODE_POINT | /home/user/hakuX/hw/xbox/nv2a/pgraph/prim_rewrite.c:447, 485 | assert | polygon primitive rendered as points | **Yes** |
| unexpected primitive mode | /home/user/hakuX/hw/xbox/nv2a/pgraph/prim_rewrite.c:69, 434 | assert | out-of-range `SET_BEGIN_END` op | **Yes** (but `pgraph.c:3627` already asserts the range) |
| `get_primitive_topology` default | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:360 | assert | non-POINT/LINE/TRIANGLE topology reaching VK | **Yes** |
| `SET_FOG_MODE` default | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2186-2188 | assert | unknown fog mode value | **Yes**; with NDEBUG, `mode` is used uninitialised at 2190 |
| `SET_FOG_GEN_MODE` default | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2209-2211 | assert | unknown foggen value | **Yes**; same uninitialised-`mode` hazard at 2212 |
| `SET_CULL_FACE` default | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2670-2672 | assert | unknown cull-face value | **Yes**; same hazard for `face` at 2674 |
| `kelvin_map_stencil_op` default | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2556 | assert | unknown stencil op | **Yes**; `op` uninitialised under NDEBUG |
| `kelvin_map_polygon_mode` default | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2628 | assert | unknown polygon mode | **Yes**; same hazard |
| `SET_ZMIN_MAX_CONTROL` default | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:4004-4007 | FIXME + assert | should raise `NV_PGRAPH_NSOURCE_DATA_ERROR_PENDING` | **Yes** |
| `NV_PGRAPH_CSV0_D_FOG_MODE` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2171 | FIXME | second fog-mode field never written or read | No |
| `NV_PGRAPH_CSV0_D_FOGENABLE` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2216-2220 | FIXME (commented-out code) | second fog-enable bit | No |
| fog when disabled | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:316-318 | FIXME | `oFog = 1.0` when FOGENABLE=0 | No |
| foggen for programmable VSH | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:320-326 | FIXME | foggen ignored, `oFog.x` used raw | No |
| `SET_FOG_PARAMS` slot 2 | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2865-2867 | FIXME | third fog param dropped | No |
| window clip in GL clear | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:126 | FIXME | clears ignore window clip | No |
| window clip vs surface clip | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:337 | FIXME | GL never applies window clip | No |
| window clip vs surface clip | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:3116 | FIXME | (VK does apply it in the PSH; scissor is surface clip only) | No |
| clear rect degenerate cases | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:5300-5301 | FIXME ×2 | min≥max, min≥surface size | No |
| dither (VK) | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1576-1578 | FIXME | `DITHERENABLE` ignored | No |
| point size (VK pipeline) | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1579 | FIXME | (size still reaches `gl_PointSize` via the VS) | No |
| edge antialiasing (VK) | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1580-1591 | FIXME | `LINESMOOTH`/`POLYSMOOTH` ignored | No |
| logic op table | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/constants.h:84-102, /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/constants.h:139-157 | FIXME (commented-out) | logic op unimplemented | No |
| `ZOFFSETFACTOR` w-buffer | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1799-1817 | NV2A_UNIMPLEMENTED | per-pixel vs constant slope under w-buffering | No (macro is a no-op unless `DEBUG_NV2A_FEATURES`) |
| spotlight falloff | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh-ff.c:361 | FIXME | `lightSpotFalloff` exponent ignored | No |
| anti-aliasing control bits | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:4016 | FIXME | non-enable bits of `SET_ANTI_ALIASING_CONTROL` | No |
| clear-rect origin | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:96 | FIXME | "Needs confirmation" on clear-rect decode | No |
| nop-draw exception check | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:391-398 | FIXME | PGRAPH 0x880 bit 11 colour/zeta limit exception (xemu#635) | No |
| GL dither correctness | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:294 | FIXME | GL dithering is implementation-defined | No |
| inline-array offset rounding | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/vertex.c:243, /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:5954 | FIXME | "Double check" on attribute packing | No |
| occlusion-query overflow | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1788 | FIXME | query buffer too small | No |
| skip-occlusion-queries option | /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:30, 3054-3073 | option (default `false`) | when on, zpass counts are never updated | No |
| GLES occlusion queries | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/reports.c:45-52 | conditional | GLES only reports boolean "any samples passed" → count becomes 0/1 | No |
| GLES geometry shaders | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/shaders.c:271-278 | conditional | flat shading + wireframe silently wrong on GLES | No |

---

## Suites plausibly exercised

| suite | primary code sites | confidence | note |
|---|---|---|---|
| `Fog_gen` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2194-2213; /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:77-80; /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh-ff.c:448-470 | high | **fixed-function only** — programmable VSH ignores foggen (`vsh.c:320-327`) |
| `Fog_param` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2860-2872; /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:335-374 | high | `FOGPARAM0/1` → `fogParam.xy`; slot 2 dropped |
| `Fog_exceptional_value` | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:332-333, 385-397; `NaNToValue` helper | high | asymmetric inf/NaN results across modes — see "State distinctions/Fog" |
| `Blend_tests` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2365-2475; /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/constants.h:55-82; /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/constants.h:110-137; /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:187-210; /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1472-1533 | high | `*_SIGNED` equations collapse onto unsigned |
| `Blend_surface` | same + /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/constants.h:340-357 (`kelvin_surface_color_format_gl_map`, FIXME at 350) | medium | surface-format side is out of my scope; `LE_B8`/`LE_G8B8` carry `// FIXME: Map channel color` |
| `Depth_buffer` | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1088-1142, 1561-1578; /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:4261-4292 | high | fragment-shader depth is **VK-only** (`psh.c:118-126`) |
| `Depth_buffer_fixed_function` | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:243-261; /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh-ff.c:481-489 | high | `Z_FORMAT` × zeta format → D16/D24/F16/F24 |
| `W_param` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2138-2142; /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/geom.c:44-45, 180-195; /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1089-1116 | high | `Z_PERSPECTIVE_ENABLE` picks the `calc_triz` variant |
| `W_buffering` | same, plus /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:1799-1817 | high | known-incomplete `ZOFFSETFACTOR` under w-buffering |
| `Window_clip` | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:64-87, 1039-1085, 1832-1851 | high | **VK only**; GL renders as if unclipped. Clear path ignores it in both. |
| `ZMinMaxControl` | /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:3992-4010; /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:113-116, 1134-1142; /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/common.c:95-116 | high | **VK only**; GL is unconditionally `GL_DEPTH_CLAMP` |
| `ZPass_pixel_count` | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:352-371 + /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/reports.c:25-62; /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:1782-1816, 3054-3073 | high | GL divides by `scale_factor²` (`reports.c:53`); GLES degrades to boolean; VK has a skip option |
| `Line_width` | /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:310-322; /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/draw.c:3028-3041, 3137-3141 | **high that nothing guest-controlled feeds it** | no line-width register exists in `nv2a_regs.h`; width is always `surface_scale_factor` |
| `Stipple_tests` | — | high | no stipple state exists anywhere in `hw/xbox` |
| `Attrib_carryover` | /home/user/hakuX/hw/xbox/nv2a/pgraph/vertex.c:24-81; /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/vertex.c:186-223; /home/user/hakuX/hw/xbox/nv2a/pgraph/vk/vertex.c:255-284; /home/user/hakuX/hw/xbox/nv2a/pgraph/gl/draw.c:566-568 | high | UB_D3D channel-order asymmetry described above |
| `Specular` | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/psh.c:92-93, 1692-1693; /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh.c:416-433; `NV_PGRAPH_CSV0_C_SPECULAR_ENABLE` writer at /home/user/hakuX/hw/xbox/nv2a/pgraph/pgraph.c:2711-2714 (fast-path entry at pgraph.c:532-533) | medium | mostly a lighting/combiner concern, only partly in this sweep's scope |
| `Lighting_spotlight` | /home/user/hakuX/hw/xbox/nv2a/pgraph/glsl/vsh-ff.c:304, 348-362 | medium | `/* FIXME: lightSpotFalloff */` at 361 — falloff exponent ignored |

---

## Uncertainties

1. **I did not build or run anything.** Every claim is static reading of the tree at `5b4f577`. Nothing here has been confirmed against rendered output or against real hardware.

2. **Which renderer the failing suites actually run under.** The GL-vs-VK split is the single biggest factor in this report (window clip, ZMinMaxControl, polygon offset, fragment-shader depth, dither are all VK-only or GL-only). `psh.c:68` and `psh.c:120` key off `g_config.display.renderer`; the default is chosen at `pgraph.c:1085-1100`, which I did not fully trace. If the tests run under Vulkan, most of my "GL doesn't implement this" findings are irrelevant to them.

3. **The premise in my brief about window clip contradicts the code.** I found inclusive and exclusive *both* implemented for Vulkan (`psh.c:1045-1085`). Possible explanations I could not distinguish: the earlier observation was made on the GL renderer (where neither is implemented — consistent with "renders identically"); or on an older revision. `git log` for `glsl/psh.c` in this checkout shows only two commits, so the history here is too shallow to check.

4. **`_ABS` fog semantics.** `vsh.c:376-383` applies `abs()` to the fog *factor*. I do not know whether NV2A applies it to the fog distance/coordinate instead. This would change `Fog_param`/`Fog_gen` results for negative distances but I have no reference.

5. **EXP2 vs EXP inf/NaN asymmetry.** `vsh.c:343-344` (LINEAR) and `349-350` (EXP) set the inf/NaN results to 1.0; EXP2/EXP2_ABS and EXP_ABS leave them at 0.0. I cannot tell whether this is a deliberate hardware match or an oversight.

6. **`POINTSMOOTHENABLE` as point-sprite enable.** I could not confirm from this tree whether NV2A really overloads `NV097_SET_POINT_SMOOTH_ENABLE` for D3D point sprites. If it does not, `psh.c:99-101` is a mis-mapping; if it does, point antialiasing is simply not modelled. Either way point-smooth on/off is not a rasterisation-only difference here.

7. **`NV097_SET_WINDOW_CLIP_TYPE` value encoding.** `nv2a_regs.h:929` defines the method but no `_V_` constants. `psh.c:64-65` treats non-zero as exclusive. I did not find documentation of which value means inclusive.

8. **Whether the window-clip dirty-tracking gap (item 4 under Window clip) is actually reachable** by the nxdk test sequences. It depends on whether a test writes clip rects without touching any `REG_CAT_SHADER` register afterwards. I could not check the test source — nxdk_pgraph_tests is not in this repo (searched `ls hw/xbox/nv2a/` and the repo root; no test suite present).

9. **VK non-extended-dynamic-state path coverage.** Several findings (the missing `STENCIL_WRITE_ENABLE` gate at `vk/draw.c:1466`; static blend/depth-stencil at `1420-1533`) only apply when `r->extended_dynamic_state_supported` / `eds3_blend_supported` are false. I did not determine how commonly that happens.

10. **`OPT_DYNAMIC_STATES`, `OPT_DYNAMIC_BLEND`, `OPT_ASYNC_COMPILE`, `OPT_SYNC_RANGE_SKIP`, `OPT_VALIDATE_GEN_COUNTERS` default values.** I read the code under all branches but did not locate where these macros are defined, so I cannot say which VK path is the live one in a default build.

11. **Whether `NDEBUG` is set in release builds.** `grep -rn NDEBUG configure meson.build` found nothing, and there is no `b_ndebug` setting in `meson.build`/`meson_options.txt`, so asserts are presumably live. If a build *did* define `NDEBUG`, six `default:` cases in `pgraph.c` would fall through to using an uninitialised variable (listed in Stubs and gaps). I did not check `meson_options.txt` exhaustively.

12. **Surface-format interactions** (relevant to `Blend_surface`, `Depth_buffer`) live in `gl/surface.c` / `vk/surface.c`, which were outside this sweep's scope and which I only sampled.

13. **I did not read all 6032 lines of `vk/draw.c`.** I read the pipeline creation, dynamic-state, draw-dispatch, reorder-window, clear-surface and vertex-buffer sections in full (roughly lines 316-560, 1033-1720, 2670-3360, 4456-4700, 5140-5450, 5480-5800). The command-buffer / submission / memory-sync machinery (roughly 1780-2660, 3355-4450, 4700-5140, 5800-6032) I only skimmed for register reads via grep. A register read hidden in those ranges would have shown up in my `grep -n NV_PGRAPH_` sweeps, but a *behavioural* subtlety there would not have.

14. **`geom.c`'s `provoking_index` only covers colour varyings.** I state that `vtxFog`/`vtxT*` are smooth-interpolated under flat shading based on `geom.c:149-158` plus the qualifier table at `common.c:50-58`; I read enough of `pgraph_glsl_get_vtx_header` to believe the qualifiers apply, but did not read the whole function.
