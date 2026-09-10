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

# NV2A Texture Pipeline — Read-Only Inventory Sweep

Repo root: `/home/user/hakuX`. All `path:line` citations below are **relative to
`/home/user/hakuX/`** unless written out in full. Nothing in the repo was
modified.

Every row is VERIFIED (read directly in the source) unless explicitly tagged
**INFERRED**. Things I could not settle are in **Uncertainties**, not guessed at.

Two global facts that the rest of the report depends on:

- `assert()` is **live** in every build: `include/qemu/osdep.h:311-312` contains
  `#ifdef NDEBUG` / `#error building with NDEBUG is not supported`. So every
  `assert` in this sweep aborts the process.
- `NV2A_UNIMPLEMENTED(...)` is a **no-op by default**: `hw/xbox/nv2a/debug.h:48-50`
  defaults `DEBUG_NV2A_FEATURES` to `0`, and `hw/xbox/nv2a/debug.h:66-67` then
  defines both `NV2A_UNCONFIRMED` and `NV2A_UNIMPLEMENTED` as `do {} while (0)`.
  It only prints to stderr when `DEBUG_NV2A_FEATURES` is set
  (`hw/xbox/nv2a/debug.h:60-62`). It never aborts.

---

## Concepts owned

### A. Texture color formats (42 defined values)

Canonical enum symbol is `NV097_SET_TEXTURE_FORMAT_COLOR_*`, all defined in
`hw/xbox/nv2a/nv2a_regs.h`. The three per-format tables that must carry a row for
each are:

- `kelvin_color_format_info_map[66]` — `hw/xbox/nv2a/pgraph/texture.c:26`
  (declared `hw/xbox/nv2a/pgraph/texture.h:53`, type `BasicColorFormatInfo`
  at `texture.h:47-51`: `{bytes_per_pixel, linear, depth}`)
- `kelvin_color_format_vk_map[66]` — `hw/xbox/nv2a/pgraph/vk/constants.h:157`
  (type `VkColorFormatInfo` at `vk/constants.h:152-155`: `{vk_format, component_map}`)
- `kelvin_color_format_gl_map[66]` — `hw/xbox/nv2a/pgraph/gl/constants.h:211`
  (type `ColorFormatInfo` at `gl/constants.h:201-209`)

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| 0x00 SZ_Y8 | format-enum | `NV097_SET_TEXTURE_FORMAT_COLOR_SZ_Y8` | nv2a_regs.h:1192 |
| 0x01 SZ_AY8 | format-enum | `..._SZ_AY8` | nv2a_regs.h:1193 |
| 0x02 SZ_A1R5G5B5 | format-enum | `..._SZ_A1R5G5B5` | nv2a_regs.h:1194 |
| 0x03 SZ_X1R5G5B5 | format-enum | `..._SZ_X1R5G5B5` | nv2a_regs.h:1195 |
| 0x04 SZ_A4R4G4B4 | format-enum | `..._SZ_A4R4G4B4` | nv2a_regs.h:1196 |
| 0x05 SZ_R5G6B5 | format-enum | `..._SZ_R5G6B5` | nv2a_regs.h:1197 |
| 0x06 SZ_A8R8G8B8 | format-enum | `..._SZ_A8R8G8B8` | nv2a_regs.h:1198 |
| 0x07 SZ_X8R8G8B8 | format-enum | `..._SZ_X8R8G8B8` | nv2a_regs.h:1199 |
| 0x0B SZ_I8_A8R8G8B8 | format-enum | `..._SZ_I8_A8R8G8B8` | nv2a_regs.h:1200 |
| 0x0C L_DXT1_A1R5G5B5 | format-enum | `..._L_DXT1_A1R5G5B5` | nv2a_regs.h:1201 |
| 0x0E L_DXT23_A8R8G8B8 | format-enum | `..._L_DXT23_A8R8G8B8` | nv2a_regs.h:1202 |
| 0x0F L_DXT45_A8R8G8B8 | format-enum | `..._L_DXT45_A8R8G8B8` | nv2a_regs.h:1203 |
| 0x10 LU_IMAGE_A1R5G5B5 | format-enum | `..._LU_IMAGE_A1R5G5B5` | nv2a_regs.h:1204 |
| 0x11 LU_IMAGE_R5G6B5 | format-enum | `..._LU_IMAGE_R5G6B5` | nv2a_regs.h:1205 |
| 0x12 LU_IMAGE_A8R8G8B8 | format-enum | `..._LU_IMAGE_A8R8G8B8` | nv2a_regs.h:1206 |
| 0x13 LU_IMAGE_Y8 | format-enum | `..._LU_IMAGE_Y8` | nv2a_regs.h:1207 |
| 0x17 LU_IMAGE_G8B8 | format-enum | `..._LU_IMAGE_G8B8` | nv2a_regs.h:1208 |
| 0x19 SZ_A8 | format-enum | `..._SZ_A8` | nv2a_regs.h:1209 |
| 0x1A SZ_A8Y8 | format-enum | `..._SZ_A8Y8` | nv2a_regs.h:1210 |
| 0x1B LU_IMAGE_AY8 | format-enum | `..._LU_IMAGE_AY8` | nv2a_regs.h:1211 |
| 0x1C LU_IMAGE_X1R5G5B5 | format-enum | `..._LU_IMAGE_X1R5G5B5` | nv2a_regs.h:1212 |
| 0x1D LU_IMAGE_A4R4G4B4 | format-enum | `..._LU_IMAGE_A4R4G4B4` | nv2a_regs.h:1213 |
| 0x1E LU_IMAGE_X8R8G8B8 | format-enum | `..._LU_IMAGE_X8R8G8B8` | nv2a_regs.h:1214 |
| 0x1F LU_IMAGE_A8 | format-enum | `..._LU_IMAGE_A8` | nv2a_regs.h:1215 |
| 0x20 LU_IMAGE_A8Y8 | format-enum | `..._LU_IMAGE_A8Y8` | nv2a_regs.h:1216 |
| 0x24 LC_IMAGE_CR8YB8CB8YA8 | format-enum | `..._LC_IMAGE_CR8YB8CB8YA8` | nv2a_regs.h:1217 |
| 0x25 LC_IMAGE_YB8CR8YA8CB8 | format-enum | `..._LC_IMAGE_YB8CR8YA8CB8` | nv2a_regs.h:1218 |
| 0x27 SZ_R6G5B5 | format-enum | `..._SZ_R6G5B5` | nv2a_regs.h:1219 |
| 0x28 SZ_G8B8 | format-enum | `..._SZ_G8B8` | nv2a_regs.h:1220 |
| 0x29 SZ_R8B8 | format-enum | `..._SZ_R8B8` | nv2a_regs.h:1221 |
| 0x2C SZ_DEPTH_Y16_FIXED | format-enum | `..._SZ_DEPTH_Y16_FIXED` | nv2a_regs.h:1222 |
| 0x2E LU_IMAGE_DEPTH_X8_Y24_FIXED | format-enum | `..._LU_IMAGE_DEPTH_X8_Y24_FIXED` | nv2a_regs.h:1223 |
| 0x2F LU_IMAGE_DEPTH_X8_Y24_FLOAT | format-enum | `..._LU_IMAGE_DEPTH_X8_Y24_FLOAT` | nv2a_regs.h:1224 |
| 0x30 LU_IMAGE_DEPTH_Y16_FIXED | format-enum | `..._LU_IMAGE_DEPTH_Y16_FIXED` | nv2a_regs.h:1225 |
| 0x31 LU_IMAGE_DEPTH_Y16_FLOAT | format-enum | `..._LU_IMAGE_DEPTH_Y16_FLOAT` | nv2a_regs.h:1226 |
| 0x35 LU_IMAGE_Y16 | format-enum | `..._LU_IMAGE_Y16` | nv2a_regs.h:1227 |
| 0x3A SZ_A8B8G8R8 | format-enum | `..._SZ_A8B8G8R8` | nv2a_regs.h:1228 |
| 0x3B SZ_B8G8R8A8 | format-enum | `..._SZ_B8G8R8A8` | nv2a_regs.h:1229 |
| 0x3C SZ_R8G8B8A8 | format-enum | `..._SZ_R8G8B8A8` | nv2a_regs.h:1230 |
| 0x3F LU_IMAGE_A8B8G8R8 | format-enum | `..._LU_IMAGE_A8B8G8R8` | nv2a_regs.h:1231 |
| 0x40 LU_IMAGE_B8G8R8A8 | format-enum | `..._LU_IMAGE_B8G8R8A8` | nv2a_regs.h:1232 |
| 0x41 LU_IMAGE_R8G8B8A8 | format-enum | `..._LU_IMAGE_R8G8B8A8` | nv2a_regs.h:1233 |

Count check: 42 defined values, matching the ~42 the task expected. The tables
are sized `[66]` (`texture.c:26`, `vk/constants.h:157`, `gl/constants.h:211`);
0x42 = 66, i.e. one past the highest defined value 0x41. **24 index values in
`[0,0x41]` have no row**: 0x08, 0x09, 0x0A, 0x0D, 0x14, 0x15, 0x16, 0x18, 0x21,
0x22, 0x23, 0x26, 0x2A, 0x2B, 0x2D, 0x32, 0x33, 0x34, 0x36, 0x37, 0x38, 0x39,
0x3D, 0x3E (derived by set-differencing the enum list above against 0..0x41 —
VERIFIED against the table bodies, which have no designated initializer for any
of them).

### B. Texture-related methods

All in `hw/xbox/nv2a/nv2a_regs.h`; each has 4 slots at stride 64 bytes.

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Texture data offset | method | `NV097_SET_TEXTURE_OFFSET` (0x1B00) | nv2a_regs.h:1183 |
| Format/shape word | method | `NV097_SET_TEXTURE_FORMAT` (0x1B04) | nv2a_regs.h:1184 |
| Wrap modes | method | `NV097_SET_TEXTURE_ADDRESS` (0x1B08) | nv2a_regs.h:1238 |
| Enable / LOD clamps / anisotropy / colorkey / alphakill | method | `NV097_SET_TEXTURE_CONTROL0` (0x1B0C) | nv2a_regs.h:1239 |
| Linear image pitch | method | `NV097_SET_TEXTURE_CONTROL1` (0x1B10) | nv2a_regs.h:1243 |
| Min/mag filter, LOD bias, signed-channel bits | method | `NV097_SET_TEXTURE_FILTER` (0x1B14) | nv2a_regs.h:1245 |
| Linear image rect (w/h) | method | `NV097_SET_TEXTURE_IMAGE_RECT` (0x1B1C) | nv2a_regs.h:1253 |
| Palette DMA/length/offset | method | `NV097_SET_TEXTURE_PALETTE` (0x1B20) | nv2a_regs.h:1256 |
| Border color | method | `NV097_SET_TEXTURE_BORDER_COLOR` (0x1B24) | nv2a_regs.h:1264 |
| Bump env matrix | method | `NV097_SET_TEXTURE_SET_BUMP_ENV_MAT` (0x1B28) | nv2a_regs.h:1265 |
| Bump env scale | method | `NV097_SET_TEXTURE_SET_BUMP_ENV_SCALE` (0x1B38) | nv2a_regs.h:1266 |
| Bump env offset | method | `NV097_SET_TEXTURE_SET_BUMP_ENV_OFFSET` (0x1B3C) | nv2a_regs.h:1267 |
| Texgen matrix enable | method | `NV097_SET_TEXTURE_MATRIX_ENABLE` (0x0420) | nv2a_regs.h:1059 |
| Texgen matrix | method | `NV097_SET_TEXTURE_MATRIX` (0x06C0) | nv2a_regs.h:1066 |

Method-side sub-field masks (needed for the truncation coupling below):
`NV097_SET_TEXTURE_FORMAT_CONTEXT_DMA` nv2a_regs.h:1185,
`_CUBEMAP_ENABLE` :1186, `_BORDER_SOURCE` :1187, `_DIMENSIONALITY` (0x000000F0) :1190,
`_COLOR` (0x0000FF00) :1191, `_MIPMAP_LEVELS` :1234, `_BASE_SIZE_U/V/P` :1235-1237;
`NV097_SET_TEXTURE_CONTROL0_ENABLE/MIN_LOD_CLAMP/MAX_LOD_CLAMP` :1240-1242;
`NV097_SET_TEXTURE_CONTROL1_IMAGE_PITCH` :1244;
`NV097_SET_TEXTURE_FILTER_MIPMAP_LOD_BIAS/MIN(0x00FF0000)/MAG/ASIGNED/RSIGNED/GSIGNED/BSIGNED` :1246-1252;
`NV097_SET_TEXTURE_IMAGE_RECT_WIDTH(0xFFFF0000)/HEIGHT(0x0000FFFF)` :1254-1255;
`NV097_SET_TEXTURE_PALETTE_*` :1257-1263.

### C. PGRAPH texture register fields

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| TEXADDRESS0 base | regfield | `NV_PGRAPH_TEXADDRESS0` (0x19BC) | nv2a_regs.h:528 |
| U wrap mode (3 bits) | regfield | `NV_PGRAPH_TEXADDRESS0_ADDRU` (0x00000007) | nv2a_regs.h:529 |
| ADDRU=WRAP | state-bit | `..._ADDRU_WRAP` = 1 | nv2a_regs.h:530 |
| ADDRU=MIRROR | state-bit | `..._ADDRU_MIRROR` = 2 | nv2a_regs.h:531 |
| ADDRU=CLAMP_TO_EDGE | state-bit | `..._ADDRU_CLAMP_TO_EDGE` = 3 | nv2a_regs.h:532 |
| ADDRU=BORDER | state-bit | `..._ADDRU_BORDER` = 4 | nv2a_regs.h:533 |
| ADDRU=CLAMP_OGL | state-bit | `..._ADDRU_CLAMP_OGL` = 5 | nv2a_regs.h:534 |
| Cylindrical wrap U | state-bit | `NV_PGRAPH_TEXADDRESS0_WRAP_U` (1<<4) | nv2a_regs.h:535 |
| V wrap mode | regfield | `NV_PGRAPH_TEXADDRESS0_ADDRV` (0x00000700) | nv2a_regs.h:536 |
| Cylindrical wrap V | state-bit | `..._WRAP_V` (1<<12) | nv2a_regs.h:537 |
| P wrap mode | regfield | `NV_PGRAPH_TEXADDRESS0_ADDRP` (0x00070000) | nv2a_regs.h:538 |
| Cylindrical wrap P | state-bit | `..._WRAP_P` (1<<20) | nv2a_regs.h:539 |
| Cylindrical wrap Q | state-bit | `..._WRAP_Q` (1<<24) | nv2a_regs.h:540 |
| TEXADDRESS1/2/3 | regfield | `NV_PGRAPH_TEXADDRESS1..3` | nv2a_regs.h:541-543 |
| TEXCTL0_0 base | regfield | `NV_PGRAPH_TEXCTL0_0` (0x19CC) | nv2a_regs.h:544 |
| Colorkey mode | regfield | `NV_PGRAPH_TEXCTL0_0_COLORKEYMODE` (0x03) | nv2a_regs.h:545 |
| Alpha-kill enable | state-bit | `NV_PGRAPH_TEXCTL0_0_ALPHAKILLEN` (1<<2) | nv2a_regs.h:546 |
| Max anisotropy (log2) | regfield | `NV_PGRAPH_TEXCTL0_0_MAX_ANISOTROPY` (0x30) | nv2a_regs.h:547 |
| Max LOD clamp | regfield | `NV_PGRAPH_TEXCTL0_0_MAX_LOD_CLAMP` (0x0003FFC0) | nv2a_regs.h:548 |
| Min LOD clamp | regfield | `NV_PGRAPH_TEXCTL0_0_MIN_LOD_CLAMP` (0x3FFC0000) | nv2a_regs.h:549 |
| Texture unit enable | state-bit | `NV_PGRAPH_TEXCTL0_0_ENABLE` (1<<30) | nv2a_regs.h:550 |
| TEXCTL0_1/2/3 | regfield | `NV_PGRAPH_TEXCTL0_1..3` | nv2a_regs.h:551-553 |
| TEXCTL1_0 base | regfield | `NV_PGRAPH_TEXCTL1_0` (0x19DC) | nv2a_regs.h:554 |
| Linear image pitch | regfield | `NV_PGRAPH_TEXCTL1_0_IMAGE_PITCH` (0xFFFF0000) | nv2a_regs.h:555 |
| TEXCTL1_1/2/3 | regfield | `NV_PGRAPH_TEXCTL1_1..3` | nv2a_regs.h:556-558 |
| TEXCTL2_0/1 | regfield | `NV_PGRAPH_TEXCTL2_0/1` | nv2a_regs.h:559-560 |
| TEXFILTER0 base | regfield | `NV_PGRAPH_TEXFILTER0` (0x19F4) | nv2a_regs.h:561 |
| LOD bias (s4.8, 13 bits) | regfield | `NV_PGRAPH_TEXFILTER0_MIPMAP_LOD_BIAS` (0x00001FFF) | nv2a_regs.h:562 |
| Convolution kernel | regfield | `NV_PGRAPH_TEXFILTER0_CONVOLUTION_KERNEL` (0x0000E000) | nv2a_regs.h:563 |
| kernel=QUINCUNX | state-bit | `..._CONVOLUTION_KERNEL_QUINCUNX` = 1 | nv2a_regs.h:564 |
| kernel=GAUSSIAN_3 | state-bit | `..._CONVOLUTION_KERNEL_GAUSSIAN_3` = 2 | nv2a_regs.h:565 |
| Min filter (6 bits) | regfield | `NV_PGRAPH_TEXFILTER0_MIN` (0x003F0000) | nv2a_regs.h:566 |
| MIN=BOX_LOD0 | state-bit | `..._MIN_BOX_LOD0` = 1 | nv2a_regs.h:567 |
| MIN=TENT_LOD0 | state-bit | `..._MIN_TENT_LOD0` = 2 | nv2a_regs.h:568 |
| MIN=BOX_NEARESTLOD | state-bit | `..._MIN_BOX_NEARESTLOD` = 3 | nv2a_regs.h:569 |
| MIN=TENT_NEARESTLOD | state-bit | `..._MIN_TENT_NEARESTLOD` = 4 | nv2a_regs.h:570 |
| MIN=BOX_TENT_LOD | state-bit | `..._MIN_BOX_TENT_LOD` = 5 | nv2a_regs.h:571 |
| MIN=TENT_TENT_LOD | state-bit | `..._MIN_TENT_TENT_LOD` = 6 | nv2a_regs.h:572 |
| MIN=CONVOLUTION_2D_LOD0 | state-bit | `..._MIN_CONVOLUTION_2D_LOD0` = 7 | nv2a_regs.h:573 |
| Mag filter (4 bits) | regfield | `NV_PGRAPH_TEXFILTER0_MAG` (0x0F000000) | nv2a_regs.h:574 |
| Signed alpha | state-bit | `NV_PGRAPH_TEXFILTER0_ASIGNED` (1<<28) | nv2a_regs.h:575 |
| Signed red | state-bit | `NV_PGRAPH_TEXFILTER0_RSIGNED` (1<<29) | nv2a_regs.h:576 |
| Signed green | state-bit | `NV_PGRAPH_TEXFILTER0_GSIGNED` (1<<30) | nv2a_regs.h:577 |
| Signed blue | state-bit | `NV_PGRAPH_TEXFILTER0_BSIGNED` (1<<31) | nv2a_regs.h:578 |
| TEXFILTER1/2/3 | regfield | `NV_PGRAPH_TEXFILTER1..3` | nv2a_regs.h:579-581 |
| TEXFMT0 base | regfield | `NV_PGRAPH_TEXFMT0` (0x1A04) | nv2a_regs.h:582 |
| DMA A/B select | state-bit | `NV_PGRAPH_TEXFMT0_CONTEXT_DMA` (1<<1) | nv2a_regs.h:583 |
| Cubemap enable | state-bit | `NV_PGRAPH_TEXFMT0_CUBEMAPENABLE` (1<<2) | nv2a_regs.h:584 |
| Border source | regfield | `NV_PGRAPH_TEXFMT0_BORDER_SOURCE` (1<<3) | nv2a_regs.h:585 |
| BORDER_SOURCE_TEXTURE | state-bit | `..._BORDER_SOURCE_TEXTURE` = 0 | nv2a_regs.h:586 |
| BORDER_SOURCE_COLOR | state-bit | `..._BORDER_SOURCE_COLOR` = 1 | nv2a_regs.h:587 |
| Dimensionality (2 bits) | regfield | `NV_PGRAPH_TEXFMT0_DIMENSIONALITY` (0x000000C0) | nv2a_regs.h:588 |
| Color format (7 bits) | regfield | `NV_PGRAPH_TEXFMT0_COLOR` (0x00007F00) | nv2a_regs.h:589 |
| Mipmap levels | regfield | `NV_PGRAPH_TEXFMT0_MIPMAP_LEVELS` (0x000F0000) | nv2a_regs.h:590 |
| log2 width | regfield | `NV_PGRAPH_TEXFMT0_BASE_SIZE_U` (0x00F00000) | nv2a_regs.h:591 |
| log2 height | regfield | `NV_PGRAPH_TEXFMT0_BASE_SIZE_V` (0x0F000000) | nv2a_regs.h:592 |
| log2 depth | regfield | `NV_PGRAPH_TEXFMT0_BASE_SIZE_P` (0xF0000000) | nv2a_regs.h:593 |
| TEXFMT1/2/3 | regfield | `NV_PGRAPH_TEXFMT1..3` | nv2a_regs.h:594-596 |
| TEXIMAGERECT0 base | regfield | `NV_PGRAPH_TEXIMAGERECT0` (0x1A14) | nv2a_regs.h:597 |
| Rect width (13 bits) | regfield | `NV_PGRAPH_TEXIMAGERECT0_WIDTH` (0x1FFF0000) | nv2a_regs.h:598 |
| Rect height (13 bits) | regfield | `NV_PGRAPH_TEXIMAGERECT0_HEIGHT` (0x00001FFF) | nv2a_regs.h:599 |
| TEXIMAGERECT1/2/3 | regfield | `NV_PGRAPH_TEXIMAGERECT1..3` | nv2a_regs.h:600-602 |
| TEXOFFSET0..3 | regfield | `NV_PGRAPH_TEXOFFSET0..3` | nv2a_regs.h:603-606 |
| TEXPALETTE0 base | regfield | `NV_PGRAPH_TEXPALETTE0` (0x1A34) | nv2a_regs.h:607 |
| Palette DMA select | state-bit | `NV_PGRAPH_TEXPALETTE0_CONTEXT_DMA` (1<<0) | nv2a_regs.h:608 |
| Palette length code | regfield | `NV_PGRAPH_TEXPALETTE0_LENGTH` (0x0000000C) | nv2a_regs.h:609 |
| LENGTH_256/128/64/32 | state-bit | `..._LENGTH_256/128/64/32` = 0/1/2/3 | nv2a_regs.h:610-613 |
| Palette offset | regfield | `NV_PGRAPH_TEXPALETTE0_OFFSET` (0xFFFFFFC0) | nv2a_regs.h:614 |
| TEXPALETTE1/2/3 | regfield | `NV_PGRAPH_TEXPALETTE1..3` | nv2a_regs.h:615-617 |
| Border color | regfield | `NV_PGRAPH_BORDERCOLOR0` (0x180C) | nv2a_regs.h:397 |
| Per-stage shader/tex mode | regfield | `NV_PGRAPH_SHADERPROG` (0x199C) | nv2a_regs.h:521 |
| Shadow compare func | regfield | `NV_PGRAPH_SHADOWCTL_SHADOW_ZFUNC` (0x07) | nv2a_regs.h:524 |
| Max texture units | state-bit | `NV2A_MAX_TEXTURES` = 4 | nv2a_regs.h:1508 |
| Cubemap face alignment | state-bit | `NV2A_CUBEMAP_FACE_ALIGNMENT` = 128 | nv2a_regs.h:1518 |

### D. Derived shape / host-side concepts

| concept | kind | canonical symbol | defined at file:line |
|---|---|---|---|
| Decoded texture shape | state-bit | `TextureShape` | pgraph/texture.h:35-45 |
| Per-format basic info | state-bit | `BasicColorFormatInfo` | pgraph/texture.h:47-51 |
| Texture enabled predicate | state-bit | `pgraph_is_texture_enabled()` | pgraph/pgraph.h:416-421 |
| Stage active predicate | state-bit | `pgraph_is_texture_stage_active()` | pgraph/pgraph.h:409-414 |
| Compressed predicate | state-bit | `pgraph_is_texture_format_compressed()` | pgraph/pgraph.h:423-428 |
| Per-slot dirty flags | state-bit | `PGRAPHState::texture_dirty[4]` | pgraph/pgraph.h:161 |
| LOD-bias fixed→float | state-bit | `pgraph_convert_lod_bias_to_float()` | pgraph/texture.h:67-74 |
| S3TC format enum | format-enum | `enum S3TC_DECOMPRESS_FORMAT` | pgraph/s3tc.h:30-34 |
| GL min-filter map | state-bit | `pgraph_texture_min_filter_gl_map[8]` | gl/constants.h:82-91 |
| GL mag-filter map | state-bit | `pgraph_texture_mag_filter_gl_map[5]` | gl/constants.h:93-99 |
| GL wrap map | state-bit | `pgraph_texture_addr_gl_map[6]` | gl/constants.h:101-108 |
| VK min-filter map | state-bit | `pgraph_texture_min_filter_vk_map[8]` | vk/constants.h:27-36 |
| VK mag-filter map | state-bit | `pgraph_texture_mag_filter_vk_map[5]` | vk/constants.h:38-44 |
| VK wrap map | state-bit | `pgraph_texture_addr_vk_map[6]` | vk/constants.h:46-53 |
| Fragment-shader tex state | state-bit | `PshState` (`rect_tex/snorm_tex/dim_tex/tex_cubemap/tex_x8y24/shadow_map/conv_tex/alphakill/colorkey_mode/border_*`) | glsl/psh.h:37-77 |

---

## Sites

### S1. Format tables — TABLE-ENTRY rows

One row per format per backend. `pgraph` column = `kelvin_color_format_info_map`
(`pgraph/texture.c`); `vk` = `kelvin_color_format_vk_map` (`vk/constants.h`);
`gl` = `kelvin_color_format_gl_map` (`gl/constants.h`).

| concept | file:line | role | notes |
|---|---|---|---|
| SZ_Y8 | pgraph/texture.c:27 | TABLE-ENTRY | `{1,false}` |
| SZ_Y8 | vk/constants.h:158-161 | TABLE-ENTRY | `R8_UNORM`, swizzle RRR1 |
| SZ_Y8 | gl/constants.h:212-214 | TABLE-ENTRY | `GL_R8/RED/UBYTE`, swizzle RRR1 |
| SZ_AY8 | pgraph/texture.c:28 | TABLE-ENTRY | `{1,false}` |
| SZ_AY8 | vk/constants.h:162-165 | TABLE-ENTRY | `R8_UNORM`, RRRR |
| SZ_AY8 | gl/constants.h:215-217 | TABLE-ENTRY | `GL_R8`, RRRR |
| SZ_A1R5G5B5 | pgraph/texture.c:29 | TABLE-ENTRY | `{2,false}` |
| SZ_A1R5G5B5 | vk/constants.h:166-168 | TABLE-ENTRY | `A1R5G5B5_UNORM_PACK16`, identity |
| SZ_A1R5G5B5 | gl/constants.h:218-219 | TABLE-ENTRY | `GL_RGB5_A1/BGRA/USHORT_1_5_5_5_REV` |
| SZ_X1R5G5B5 | pgraph/texture.c:30 | TABLE-ENTRY | `{2,false}` |
| SZ_X1R5G5B5 | vk/constants.h:169-172 | TABLE-ENTRY | `A1R5G5B5`, A→ONE |
| SZ_X1R5G5B5 | gl/constants.h:220-221 | TABLE-ENTRY | `GL_RGB5` (no swizzle mask) |
| SZ_A4R4G4B4 | pgraph/texture.c:31 | TABLE-ENTRY | `{2,false}` |
| SZ_A4R4G4B4 | vk/constants.h:173-175 | TABLE-ENTRY | `A4R4G4B4_UNORM_PACK16` (EXT-promoted format) |
| SZ_A4R4G4B4 | gl/constants.h:222-223 | TABLE-ENTRY | `GL_RGBA4/BGRA/USHORT_4_4_4_4_REV` |
| SZ_R5G6B5 | pgraph/texture.c:32 | TABLE-ENTRY | `{2,false}` |
| SZ_R5G6B5 | vk/constants.h:176-178 | TABLE-ENTRY | `R5G6B5_UNORM_PACK16` |
| SZ_R5G6B5 | gl/constants.h:224-225 | TABLE-ENTRY | `GL_RGB565/RGB/USHORT_5_6_5` |
| SZ_A8R8G8B8 | pgraph/texture.c:33 | TABLE-ENTRY | `{4,false}` |
| SZ_A8R8G8B8 | vk/constants.h:179-181 | TABLE-ENTRY | `B8G8R8A8_UNORM` |
| SZ_A8R8G8B8 | gl/constants.h:226-227 | TABLE-ENTRY | `GL_RGBA8/BGRA/UINT_8_8_8_8_REV` |
| SZ_X8R8G8B8 | pgraph/texture.c:34 | TABLE-ENTRY | `{4,false}` |
| SZ_X8R8G8B8 | vk/constants.h:182-185 | TABLE-ENTRY | `B8G8R8A8_UNORM`, A→ONE |
| SZ_X8R8G8B8 | gl/constants.h:228-229 | TABLE-ENTRY | `GL_RGB8` (alpha dropped by internal format, no swizzle) |
| SZ_I8_A8R8G8B8 | pgraph/texture.c:36 | TABLE-ENTRY | `{1,false}` — **source** bpp (palette index) |
| SZ_I8_A8R8G8B8 | vk/constants.h:186-188 | TABLE-ENTRY | `B8G8R8A8_UNORM`, comment `// Converted` |
| SZ_I8_A8R8G8B8 | gl/constants.h:232-233 | TABLE-ENTRY | bpp field 1 but `GL_RGBA8/BGRA/UINT_8_8_8_8_REV` (4 B/px upload) |
| L_DXT1_A1R5G5B5 | pgraph/texture.c:38 | TABLE-ENTRY | `{4,false}` — placeholder; real size via block math |
| L_DXT1_A1R5G5B5 | vk/constants.h:189-191 | TABLE-ENTRY | `R8G8B8A8_UNORM` `// Converted` (overridden to BC1 at runtime) |
| L_DXT1_A1R5G5B5 | gl/constants.h:235-236 | TABLE-ENTRY | `GL_COMPRESSED_RGBA_S3TC_DXT1_EXT`, `gl_format = 0` sentinel |
| L_DXT23_A8R8G8B8 | pgraph/texture.c:39 | TABLE-ENTRY | `{4,false}` |
| L_DXT23_A8R8G8B8 | vk/constants.h:192-194 | TABLE-ENTRY | `R8G8B8A8_UNORM` `// Converted` |
| L_DXT23_A8R8G8B8 | gl/constants.h:237-238 | TABLE-ENTRY | `GL_COMPRESSED_RGBA_S3TC_DXT3_EXT` |
| L_DXT45_A8R8G8B8 | pgraph/texture.c:40 | TABLE-ENTRY | `{4,false}` |
| L_DXT45_A8R8G8B8 | vk/constants.h:195-197 | TABLE-ENTRY | `R8G8B8A8_UNORM` `// Converted` |
| L_DXT45_A8R8G8B8 | gl/constants.h:239-240 | TABLE-ENTRY | `GL_COMPRESSED_RGBA_S3TC_DXT5_EXT` |
| LU_IMAGE_A1R5G5B5 | pgraph/texture.c:41 | TABLE-ENTRY | `{2,true}` |
| LU_IMAGE_A1R5G5B5 | vk/constants.h:198-200 | TABLE-ENTRY | `A1R5G5B5_UNORM_PACK16` |
| LU_IMAGE_A1R5G5B5 | gl/constants.h:241-242 | TABLE-ENTRY | `GL_RGB5_A1` |
| LU_IMAGE_R5G6B5 | pgraph/texture.c:42 | TABLE-ENTRY | `{2,true}` |
| LU_IMAGE_R5G6B5 | vk/constants.h:201-203 | TABLE-ENTRY | `R5G6B5_UNORM_PACK16` |
| LU_IMAGE_R5G6B5 | gl/constants.h:243-244 | TABLE-ENTRY | `GL_RGB565` |
| LU_IMAGE_A8R8G8B8 | pgraph/texture.c:43 | TABLE-ENTRY | `{4,true}` |
| LU_IMAGE_A8R8G8B8 | vk/constants.h:204-206 | TABLE-ENTRY | `B8G8R8A8_UNORM` |
| LU_IMAGE_A8R8G8B8 | gl/constants.h:245-246 | TABLE-ENTRY | `GL_RGBA8/BGRA` |
| LU_IMAGE_Y8 | pgraph/texture.c:44 | TABLE-ENTRY | `{1,true}` |
| LU_IMAGE_Y8 | vk/constants.h:207-210 | TABLE-ENTRY | `R8_UNORM`, RRR1 |
| LU_IMAGE_Y8 | gl/constants.h:247-249 | TABLE-ENTRY | `GL_R8`, RRR1 |
| LU_IMAGE_G8B8 | pgraph/texture.c:45 | TABLE-ENTRY | `{2,true}` |
| LU_IMAGE_G8B8 | vk/constants.h:211-214 | TABLE-ENTRY | `R8G8_UNORM`, RGRG |
| LU_IMAGE_G8B8 | gl/constants.h:251-253 | TABLE-ENTRY | `GL_RG8`, RGRG |
| SZ_A8 | pgraph/texture.c:46 | TABLE-ENTRY | `{1,false}` |
| SZ_A8 | vk/constants.h:215-218 | TABLE-ENTRY | `R8_UNORM`, `ONE,ONE,ONE,R` |
| SZ_A8 | gl/constants.h:255-257 | TABLE-ENTRY | `GL_R8`, `ONE,ONE,ONE,RED` |
| SZ_A8Y8 | pgraph/texture.c:47 | TABLE-ENTRY | `{2,false}` |
| SZ_A8Y8 | vk/constants.h:219-222 | TABLE-ENTRY | `R8G8_UNORM`, RRRG |
| SZ_A8Y8 | gl/constants.h:258-260 | TABLE-ENTRY | `GL_RG8`, RRRG |
| LU_IMAGE_AY8 | pgraph/texture.c:48 | TABLE-ENTRY | `{1,true}` |
| LU_IMAGE_AY8 | vk/constants.h:223-226 | TABLE-ENTRY | `R8_UNORM`, RRRR |
| LU_IMAGE_AY8 | gl/constants.h:261-263 | TABLE-ENTRY | `GL_R8`, RRRR |
| LU_IMAGE_X1R5G5B5 | pgraph/texture.c:49 | TABLE-ENTRY | `{2,true}` |
| LU_IMAGE_X1R5G5B5 | vk/constants.h:227-230 | TABLE-ENTRY | `A1R5G5B5`, A→ONE |
| LU_IMAGE_X1R5G5B5 | gl/constants.h:264-265 | TABLE-ENTRY | `GL_RGB5` |
| LU_IMAGE_A4R4G4B4 | pgraph/texture.c:50 | TABLE-ENTRY | `{2,true}` |
| LU_IMAGE_A4R4G4B4 | vk/constants.h:231-233 | TABLE-ENTRY | `A4R4G4B4_UNORM_PACK16` |
| LU_IMAGE_A4R4G4B4 | gl/constants.h:266-267 | TABLE-ENTRY | `GL_RGBA4` |
| LU_IMAGE_X8R8G8B8 | pgraph/texture.c:51 | TABLE-ENTRY | `{4,true}` |
| LU_IMAGE_X8R8G8B8 | vk/constants.h:234-237 | TABLE-ENTRY | `B8G8R8A8_UNORM`, A→ONE |
| LU_IMAGE_X8R8G8B8 | gl/constants.h:268-269 | TABLE-ENTRY | `GL_RGB8` |
| LU_IMAGE_A8 | pgraph/texture.c:52 | TABLE-ENTRY | `{1,true}` |
| LU_IMAGE_A8 | vk/constants.h:238-241 | TABLE-ENTRY | `R8_UNORM`, `ONE,ONE,ONE,R` |
| LU_IMAGE_A8 | gl/constants.h:270-272 | TABLE-ENTRY | `GL_R8`, `ONE,ONE,ONE,RED` |
| LU_IMAGE_A8Y8 | pgraph/texture.c:53 | TABLE-ENTRY | `{2,true}` |
| LU_IMAGE_A8Y8 | vk/constants.h:242-245 | TABLE-ENTRY | `R8G8_UNORM`, RRRG |
| LU_IMAGE_A8Y8 | gl/constants.h:273-275 | TABLE-ENTRY | `GL_RG8`, RRRG |
| SZ_R6G5B5 | pgraph/texture.c:55 | TABLE-ENTRY | `{2,false}` — **source** bpp; CPU-converted to 3 B/px |
| SZ_R6G5B5 | vk/constants.h:246-248 | TABLE-ENTRY | `R8G8B8_SNORM` `// Converted` |
| SZ_R6G5B5 | gl/constants.h:277-278 | TABLE-ENTRY | `GL_RGB8_SNORM/RGB/BYTE`, `/* FIXME: This might be signed */` |
| SZ_G8B8 | pgraph/texture.c:56 | TABLE-ENTRY | `{2,false}` |
| SZ_G8B8 | vk/constants.h:249-252 | TABLE-ENTRY | `R8G8_UNORM`, RGRG |
| SZ_G8B8 | gl/constants.h:279-281 | TABLE-ENTRY | `GL_RG8`, RGRG |
| SZ_R8B8 | pgraph/texture.c:57 | TABLE-ENTRY | `{2,false}` |
| SZ_R8B8 | vk/constants.h:253-256 | TABLE-ENTRY | `R8G8_UNORM`, `G,R,R,G` |
| SZ_R8B8 | gl/constants.h:282-284 | TABLE-ENTRY | `GL_RG8`, `GREEN,RED,RED,GREEN` |
| LC_IMAGE_CR8YB8CB8YA8 | pgraph/texture.c:59 | TABLE-ENTRY | `{2,true}` — source bpp; converted to 4 B/px |
| LC_IMAGE_CR8YB8CB8YA8 | vk/constants.h:257-259 | TABLE-ENTRY | `R8G8B8A8_UNORM` `// Converted` |
| LC_IMAGE_CR8YB8CB8YA8 | gl/constants.h:286-287 | TABLE-ENTRY | `GL_RGBA8/RGBA/UINT_8_8_8_8_REV`, bpp field is 2 |
| LC_IMAGE_YB8CR8YA8CB8 | pgraph/texture.c:60 | TABLE-ENTRY | `{2,true}` |
| LC_IMAGE_YB8CR8YA8CB8 | vk/constants.h:260-262 | TABLE-ENTRY | `R8G8B8A8_UNORM` `// Converted` |
| LC_IMAGE_YB8CR8YA8CB8 | gl/constants.h:288-289 | TABLE-ENTRY | `GL_RGBA8/RGBA` |
| SZ_DEPTH_Y16_FIXED | pgraph/texture.c:62 | TABLE-ENTRY | `{2,false,depth=true}` |
| SZ_DEPTH_Y16_FIXED | vk/constants.h:269-272 | TABLE-ENTRY | `R16_UNORM // FIXME`, `R,ZERO,ZERO,ZERO` |
| SZ_DEPTH_Y16_FIXED | gl/constants.h:296-298 | TABLE-ENTRY | `GL_DEPTH_COMPONENT16`, `RED,ZERO,ZERO,ZERO`, depth |
| LU_IMAGE_DEPTH_X8_Y24_FIXED | pgraph/texture.c:63-64 | TABLE-ENTRY | `{4,true,depth=true}` |
| LU_IMAGE_DEPTH_X8_Y24_FIXED | vk/constants.h:273-278 | TABLE-ENTRY | `R32_UINT`, `R,ONE,ZERO,ZERO`, `// FIXME` |
| LU_IMAGE_DEPTH_X8_Y24_FIXED | gl/constants.h:299-301 | TABLE-ENTRY | `NV2A_GL_DEPTH_X8_Y24_INTERNAL/DEPTH_STENCIL/UINT_24_8` |
| LU_IMAGE_DEPTH_X8_Y24_FLOAT | pgraph/texture.c:65-66 | TABLE-ENTRY | `{4,true,depth=true}` |
| LU_IMAGE_DEPTH_X8_Y24_FLOAT | vk/constants.h:279-284 | TABLE-ENTRY | `R32_UINT`, same swizzle as FIXED (no float distinction) |
| LU_IMAGE_DEPTH_X8_Y24_FLOAT | gl/constants.h:302-305 | TABLE-ENTRY | comment: uses fixed-point to match surface hack |
| LU_IMAGE_DEPTH_Y16_FIXED | pgraph/texture.c:67-68 | TABLE-ENTRY | `{2,true,depth=true}` |
| LU_IMAGE_DEPTH_Y16_FIXED | vk/constants.h:285-288 | TABLE-ENTRY | `R16_UNORM // FIXME`, `R,ZERO,ZERO,ZERO` |
| LU_IMAGE_DEPTH_Y16_FIXED | gl/constants.h:306-308 | TABLE-ENTRY | `GL_DEPTH_COMPONENT16/USHORT` |
| LU_IMAGE_DEPTH_Y16_FLOAT | pgraph/texture.c:69-70 | TABLE-ENTRY | `{2,true,depth=true}` |
| LU_IMAGE_DEPTH_Y16_FLOAT | vk/constants.h:289-292 | TABLE-ENTRY | `R16_UNORM`, `R,ZERO,ONE,ZERO` (B=1 flags float) |
| LU_IMAGE_DEPTH_Y16_FLOAT | gl/constants.h:309-311 | TABLE-ENTRY | `NV2A_GL_Z16_FLOAT_TYPE`, `RED,ZERO,ONE,ZERO` |
| LU_IMAGE_Y16 | pgraph/texture.c:72 | TABLE-ENTRY | `{2,true}` |
| LU_IMAGE_Y16 | vk/constants.h:293-296 | TABLE-ENTRY | `R16_UNORM`, RRR1 |
| LU_IMAGE_Y16 | gl/constants.h:313-315 | TABLE-ENTRY | `GL_R16/RED/USHORT`, RRR1 |
| SZ_A8B8G8R8 | pgraph/texture.c:73 | TABLE-ENTRY | `{4,false}` |
| SZ_A8B8G8R8 | vk/constants.h:297-299 | TABLE-ENTRY | `R8G8B8A8_UNORM`, identity |
| SZ_A8B8G8R8 | gl/constants.h:316-317 | TABLE-ENTRY | `GL_RGBA8/RGBA/UINT_8_8_8_8_REV` |
| SZ_B8G8R8A8 | pgraph/texture.c:74 | TABLE-ENTRY | `{4,false}` |
| SZ_B8G8R8A8 | vk/constants.h:300-303 | TABLE-ENTRY | `R8G8B8A8_UNORM`, `G,B,A,R` |
| SZ_B8G8R8A8 | gl/constants.h:318-319 | TABLE-ENTRY | `GL_RGBA8/BGRA/UINT_8_8_8_8` (no swizzle mask) |
| SZ_R8G8B8A8 | pgraph/texture.c:75 | TABLE-ENTRY | `{4,false}` |
| SZ_R8G8B8A8 | vk/constants.h:304-307 | TABLE-ENTRY | `R8G8B8A8_UNORM`, `A,B,G,R` |
| SZ_R8G8B8A8 | gl/constants.h:321-322 | TABLE-ENTRY | `GL_RGBA8/RGBA/UINT_8_8_8_8` |
| LU_IMAGE_A8B8G8R8 | pgraph/texture.c:76 | TABLE-ENTRY | `{4,true}` |
| LU_IMAGE_A8B8G8R8 | vk/constants.h:308-310 | TABLE-ENTRY | `R8G8B8A8_UNORM`, identity |
| LU_IMAGE_A8B8G8R8 | gl/constants.h:324-325 | TABLE-ENTRY | `GL_RGBA8/RGBA/UINT_8_8_8_8_REV` |
| LU_IMAGE_B8G8R8A8 | pgraph/texture.c:77 | TABLE-ENTRY | `{4,true}` |
| LU_IMAGE_B8G8R8A8 | vk/constants.h:311-314 | TABLE-ENTRY | `R8G8B8A8_UNORM`, `G,B,A,R` |
| LU_IMAGE_B8G8R8A8 | gl/constants.h:326-327 | TABLE-ENTRY | `GL_RGBA8/BGRA/UINT_8_8_8_8` |
| LU_IMAGE_R8G8B8A8 | pgraph/texture.c:78 | TABLE-ENTRY | `{4,true}` |
| LU_IMAGE_R8G8B8A8 | vk/constants.h:315-318 | TABLE-ENTRY | `R8G8B8A8_UNORM`, `A,B,G,R` |
| LU_IMAGE_R8G8B8A8 | gl/constants.h:328-329 | TABLE-ENTRY | `GL_RGBA8/RGBA/UINT_8_8_8_8` |

### S2. Format-driven CPU decode and dispatch

| concept | file:line | role | notes |
|---|---|---|---|
| Palette expand (I8→BGRA8) | pgraph/texture.c:338-352 | DECODE | 1 B/px in → 4 B/px out; `size = w*h*d*4` |
| YUY2 → RGB | pgraph/texture.c:353-379 | DECODE | `convert_yuy2_to_rgb`; `assert(depth == 1)` at :360 |
| UYVY → RGB | pgraph/texture.c:374-375 | DECODE | `convert_uyvy_to_rgb` |
| R6G5B5 → RGB8_SNORM | pgraph/texture.c:380-396 | DECODE | 2 B/px in → **3 B/px** out (`size = w*h*3` at :382) |
| Fall-through (no conversion) | pgraph/texture.c:397-399 | DISPATCH | returns `NULL`; callers then use raw/unswizzled data |
| Compressed-format predicate | pgraph/pgraph.h:423-428 | DISPATCH | DXT1/DXT23/DXT45 only |
| kelvin→S3TC enum (VK) | vk/texture.c:78-90 | DISPATCH | `default: assert(false)` at :88 |
| kelvin→native BC (VK) | vk/texture.c:94-106 | DISPATCH | returns BC1/BC2/BC3 or 0 |
| GL internal fmt→S3TC enum | gl/texture.c:960-973 | DISPATCH | `default: assert(!"Invalid format")` at :971 |
| DXT decode entry (2D) | pgraph/s3tc.c:430-491 | DECODE | multithreaded above 128 blocks (`s3tc.c:268`) |
| DXT decode entry (3D) | pgraph/s3tc.c:322-394 | DECODE | z-block parallel |
| BC1 color decode | pgraph/s3tc.c:34-69 | DECODE | 3-color+alpha mode when `c0 <= c1` (s3tc.c:196) |
| Partial-block clipping | pgraph/s3tc.c:173-176 | DECODE | `y < height` / `x < width` guards |
| DXT3 alpha | pgraph/s3tc.c:204-215 | DECODE | 4-bit explicit alpha |
| DXT5 block | pgraph/s3tc.c:224 | DECODE | (function head) |
| Swizzle mask generation | pgraph/swizzle.c:52-74 | DECODE | Morton masks; `assert((x^y^z) == mask_bit-1)` at :70 |
| Unswizzle (scalar) | pgraph/swizzle.c:205-246 | DECODE | bpp-multiversioned via macro at :252-276 |
| Unswizzle NEON 2D RGBA8 | pgraph/swizzle.c:119-148 | DECODE | aarch64 only, `bpp==4 && depth==1` (swizzle.c:219) |
| `unswizzle_rect` wrapper | pgraph/swizzle.h:46-55 | DECODE | depth=1 shim |
| Android RGBA8 pre-convert list | gl/texture.c:81-116 | DISPATCH | 27 formats routed to a manual RGBA8 upload |
| Android per-format expand | gl/texture.c:149-372 | DECODE | `default: g_assert_not_reached()` at :367 |
| Android swizzle suppression | gl/texture.c:118-136 | DISPATCH | formats whose swizzle is baked into the conversion |
| Android upload prep | gl/texture.c:374-409 | DISPATCH | overrides ifmt/fmt/type to `GL_RGBA8/RGBA/UBYTE` |

### S3. Shape decode and length computation

| concept | file:line | role | notes |
|---|---|---|---|
| TEXFMT0 → `TextureShape` | pgraph/texture.c:194-326 | READ | reads TEXCTL0_0, TEXCTL1_0, TEXFMT0, TEXIMAGERECT0, SHADERPROG |
| Texture VRAM address | pgraph/texture.c:81-103 | READ | TEXFMT0_CONTEXT_DMA selects `dma_a`/`dma_b`; TEXOFFSET0 |
| Palette VRAM addr+length | pgraph/texture.c:105-141 | READ | TEXPALETTE0; `default: assert(false)` at :124 |
| Total texture byte length | pgraph/texture.c:143-192 | READ | linear = `height*pitch`; else per-level sum; cubemap ×6 aligned to 128 |
| DXT block size selection | pgraph/texture.c:166-169 | DISPATCH | DXT1→8, else 16 |
| Cubemap face alignment | pgraph/texture.c:182 | READ | `NV2A_CUBEMAP_FACE_ALIGNMENT` |
| Mip-level clamping | pgraph/texture.c:281-306 | READ | clamps to `max_mipmap_level+1` and to `MAX(log_w,log_h)+1` |
| 3D mip special case | pgraph/texture.c:296-304 | DISPATCH | `FIXME: What about 3D mipmaps?` |
| Border flag derivation | pgraph/texture.c:324 | READ | `border = border_source != BORDER_SOURCE_COLOR` |
| LOD-bias sign extension | pgraph/texture.h:67-74 | READ | 13-bit signed / 256.0 |
| Cubemap layer size (VK) | vk/texture.c:122-156 | READ | duplicates the length math with border doubling |

### S4. Vulkan backend

| concept | file:line | role | notes |
|---|---|---|---|
| Per-level CPU layout build | vk/texture.c:162-438 | DECODE | linear / 2D+cubemap / 3D branches |
| Linear-format sanity | vk/texture.c:185-192 | READ | asserts dimensionality/cubemap/linear invariants |
| Border doubling | vk/texture.c:206-211 | READ | `MAX(16, w*2)`; pitch scaled by `s.pitch / s.width` |
| Linear path decode | vk/texture.c:215-243 | DECODE | `assert(s.levels == 1)` at :232 |
| Native-BC direct upload | vk/texture.c:274-289 | DISPATCH | copies compressed blocks verbatim |
| CPU DXT decompress (2D) | vk/texture.c:290-309 | DECODE | `assert(converted)` :295 |
| Swizzled 2D decode | vk/texture.c:312-352 | DECODE | `unswizzle_rect` then `pgraph_convert_texture_data` |
| Cubemap border discard | vk/texture.c:331-341 | DECODE | crops back to `s.width/height`; FIXMEs |
| 3D DXT always CPU-decoded | vk/texture.c:373-390 | DISPATCH | comment: Vulkan doesn't guarantee BC for 3D images |
| Swizzled 3D decode | vk/texture.c:393-428 | DECODE | `unswizzle_box` + convert |
| Format lookup at upload | vk/texture.c:517 | READ | `kelvin_color_format_vk_map[state->color_format]` |
| BC override at upload | vk/texture.c:519-527 | DISPATCH | skipped for `dimensionality == 3` |
| Texture replacement inject | vk/texture.c:538-578 | DISPATCH | only for `B8G8R8A8_UNORM` / `R8G8B8A8_UNORM` |
| Staging copy + regions | vk/texture.c:580-648 | WRITE | one `VkBufferImageCopy` per (layer, level) |
| Layout transitions | vk/texture.c:667-679 | WRITE | uses `vkf.vk_format` |
| Dump hook | vk/texture.c:686-692 | READ | passes `vkf.vk_format` **and** `state->color_format` |
| Zeta surface→texture | vk/texture.c:707-899 | WRITE | reads `kelvin_color_format_vk_map` at :732 |
| Direct color surface bind | vk/texture.c:905-949 | WRITE | no copy; barrier only |
| Direct zeta surface bind | vk/texture.c:955-1004 | WRITE | D16 only (asserts at :961-962) |
| Color surface→texture copy | vk/texture.c:1006-1083 | WRITE | format at :1025 |
| Host texel size | vk/texture.c:1085-1100 | DISPATCH | switch over 10 `VkFormat`s, `default: return 0` |
| Surface/texture compat | vk/texture.c:1102-1119 | DISPATCH | compares `host_bytes_per_pixel` to `vk_format_texel_size` |
| Dummy 16×16 white texture | vk/texture.c:1121-1252 | WRITE | `R8_UNORM`, filled 0xFF |
| Linear-filter capability | vk/texture.c:1282-1287 | READ | indexes `texture_format_properties[kelvin_format]` |
| Texture creation entry | vk/texture.c:1289-1940 | READ/WRITE | main per-slot path |
| TEXFILTER0 read | vk/texture.c:1304-1305 | READ | into cache key `key.filter` (:1330) |
| TEXADDRESS0 read | vk/texture.c:1306-1307 | READ | into `key.address` (:1331) |
| BORDERCOLOR0 read | vk/texture.c:1308-1309 | READ | into `key.border_color` (:1332) |
| Max anisotropy read | vk/texture.c:1312-1314 | READ | `1 << TEXCTL0_0_MAX_ANISOTROPY` |
| Palette in cache key | vk/texture.c:1321-1327 | READ | only when `SZ_I8_A8R8G8B8` (:1310-1311) |
| Expected-format recheck | vk/texture.c:1455-1471 | DISPATCH | invalidates cached image if BC/non-BC format changed |
| Cache-miss format select | vk/texture.c:1612-1630 | DISPATCH | BC disabled for s2t, replacements, 3D |
| Image create | vk/texture.c:1638-1653 | WRITE | `mipLevels = linear ? 1 : levels`; cubemap → 6 layers |
| Image view + swizzle apply | vk/texture.c:1740-1756 | WRITE | `.components = vkf.component_map` |
| Border color (custom ext) | vk/texture.c:1761-1788 | WRITE | integer path for `R32_UINT` |
| Border color (fallback) | vk/texture.c:1789-1800 | DISPATCH | 3-way bucket to TRANSPARENT/OPAQUE_BLACK/OPAQUE_WHITE; `// FIXME` |
| Signed-channel bits | vk/texture.c:1802-1809 | READ | four `NV2A_UNIMPLEMENTED` (no-ops) |
| Mag/min filter lookup | vk/texture.c:1811-1823 | READ | **both use the min map**; see Coupling C6 |
| Mipmap enable | vk/texture.c:1825-1829 | DISPATCH | off for linear and `*_LOD0` min modes |
| Mipmap nearest/linear | vk/texture.c:1831-1834 | DISPATCH | `*_NEARESTLOD` → NEAREST |
| LOD bias clamp | vk/texture.c:1836-1842 | READ | clamped to `maxSamplerLodBias` |
| Sampler create info | vk/texture.c:1846-1869 | WRITE | wraps from `lookup_texture_address_mode` |
| Address-mode lookup | vk/texture.c:53-57 | READ | `assert(0 < idx && idx < 6)` |
| Sampler cache | vk/texture.c:1871-1907 | DISPATCH | compares filters/wraps/aniso/lod/border |
| Per-slot bind loop | vk/texture.c:1977-2072 | DISPATCH | skips slot when `!pgraph_is_texture_enabled` (:1996) |
| Texture reg snapshot cache | vk/texture.c:2021-2058 | READ | 8 regs: TEXOFFSET0, TEXFMT0, TEXCTL0_0, TEXCTL1_0, TEXFILTER0, TEXADDRESS0, BORDERCOLOR0, TEXIMAGERECT0 + SHADERPROG bits |
| Format properties probe | vk/texture.c:2356-2362 | READ | one query per row of `kelvin_color_format_vk_map` |
| BC capability probe | vk/texture.c:2364-2383 | READ | requires BC1_RGBA/BC2/BC3 sampleable |
| BC status print | vk/texture.c:2384-2391 | WRITE | stderr / android log |
| Descriptor image info | vk/draw.c:2738-2741, 2917-2920 | READ | picks `tex_surface_direct_views[i]` when set |
| Descriptor image info | vk/shaders.c:456-459, 545-549 | READ | same selection in shader-descriptor path |
| texScale uniform (VK) | vk/shaders.c:1193-1206 | WRITE | forces `scale = 1.0` when `!f_basic.linear` |

### S5. OpenGL backend

| concept | file:line | role | notes |
|---|---|---|---|
| Per-slot bind loop | gl/texture.c:675-958 | DISPATCH | `pgraph_is_texture_enabled` at :684 |
| TEXFILTER0 / TEXADDRESS0 / BORDERCOLOR0 read | gl/texture.c:699-701 | READ | fresh every call |
| Max anisotropy read | gl/texture.c:702-704 | READ | `1 << MAX_ANISOTROPY` |
| Signed-channel bits | gl/texture.c:707-710 | READ | four `NV2A_UNIMPLEMENTED` (no-ops) |
| VRAM range validation | gl/texture.c:422-433, 725-758 | DISPATCH | skips + unbinds on out-of-range texture or palette |
| Cache key build | gl/texture.c:842-853 | WRITE | `TextureKey` hashed with `fast_hash` |
| Content-hash invalidate | gl/texture.c:872-887 | DISPATCH | destroys binding when data hash changed |
| Surface→texture upload | gl/texture.c:912-923 | WRITE | `pgraph_gl_render_surface_to_texture` |
| Apply sampler params | gl/texture.c:542-673 | WRITE | min/mag/lod-bias/wrap/aniso/border |
| Linear min-filter fixup | gl/texture.c:560-573 | DISPATCH | demotes mipmap min modes to `*_LOD0` for linear textures |
| Min filter → GL | gl/texture.c:575-579 | WRITE | `pgraph_texture_min_filter_gl_map[min_filter]` — **no bounds assert** |
| Mag filter → GL | gl/texture.c:580-584 | WRITE | `pgraph_texture_mag_filter_gl_map[mag_filter]` — **no bounds assert** |
| LOD bias → GL | gl/texture.c:585-591 | WRITE | gated on `supported_extensions.texture_lod_bias` |
| Wrap S/T/R | gl/texture.c:593-641 | WRITE | asserted bounds at :594/:610/:627; GLES border-clamp fallback |
| Anisotropy | gl/texture.c:643-652 | WRITE | clamped to `max_texture_max_anisotropy` |
| Border color | gl/texture.c:654-672 | WRITE | only when a wrap mode is `ADDRU_BORDER` and `!is_bordered`; `/* FIXME: Color channels might be wrong order */` |
| Upload entry | gl/texture.c:975-1276 | WRITE | switch on `gl_target` |
| Border doubling | gl/texture.c:996-1001 | READ | same formula as VK |
| Linear 2D upload | gl/texture.c:1008-1050 | WRITE | `assert(s.pitch % f.bytes_per_pixel == 0)` at :1010 |
| Compressed 2D/cube upload | gl/texture.c:1067-1108 | DECODE+WRITE | CPU-decompresses then uploads `GL_RGBA8` (:1097) |
| Cubemap border strip | gl/texture.c:1079-1106 | DISPATCH | `UNPACK_SKIP_PIXELS/ROWS = 4` |
| Swizzled 2D/cube upload | gl/texture.c:1109-1165 | DECODE+WRITE | `unswizzle_rect` + convert; border offset uses `source_bpp` (:1135) |
| 3D compressed upload | gl/texture.c:1183-1211 | DECODE+WRITE | `s3tc_decompress_3d` → `GL_RGBA8` |
| 3D swizzled upload | gl/texture.c:1212-1261 | DECODE+WRITE | `unswizzle_box` + convert |
| Target selection | gl/texture.c:1289-1314 | DISPATCH | cubemap / linear / 1D / 2D / 3D; `assert(false)` default |
| Cubemap face stride | gl/texture.c:1326-1367 | READ | recomputes per-face length independent of `pgraph_get_texture_length` |
| Mip base/max level | gl/texture.c:1372-1378 | WRITE | skipped for linear formats |
| Swizzle mask apply | gl/texture.c:1380-1403 | WRITE | GLES per-channel vs desktop `SWIZZLE_RGBA` |
| texScale uniform (GL) | gl/shaders.c:876-881 | WRITE | no `linear` guard (unlike VK) |
| GL surface→texture compat | gl/surface.c:1377-1446 | DISPATCH | explicit surface-format × texture-format allow-list |

### S6. Method writes (register producers)

| concept | file:line | role | notes |
|---|---|---|---|
| SET_TEXTURE_OFFSET | pgraph/pgraph.c:3634-3641 | WRITE | raw write; sets `texture_dirty[slot]` |
| SET_TEXTURE_FORMAT | pgraph/pgraph.c:3643-3680 | WRITE | field-by-field remap into TEXFMT0; sets dirty |
| SET_TEXTURE_CONTROL0 | pgraph/pgraph.c:3682-3689 | WRITE | raw; sets dirty |
| SET_TEXTURE_CONTROL1 | pgraph/pgraph.c:3691-3698 | WRITE | raw; sets dirty |
| SET_TEXTURE_FILTER | pgraph/pgraph.c:3700-3707 | WRITE | raw; sets dirty |
| SET_TEXTURE_IMAGE_RECT | pgraph/pgraph.c:3709-3716 | WRITE | raw; sets dirty |
| SET_TEXTURE_PALETTE | pgraph/pgraph.c:3718-3737 | WRITE | field remap; sets dirty |
| SET_TEXTURE_ADDRESS | pgraph/pgraph.c:2118-2122 | WRITE | raw; **does not** set `texture_dirty` |
| SET_TEXTURE_BORDER_COLOR | pgraph/pgraph.c:3739-3743 | WRITE | raw; **does not** set `texture_dirty` |
| SET_TEXTURE_SET_BUMP_ENV_MAT | pgraph/pgraph.c:3745-3757 | WRITE | slots <16 discarded; swizzled into BUMPMAT00/01/11/10 |
| SET_TEXTURE_SET_BUMP_ENV_SCALE | pgraph/pgraph.c:3759-3769 | WRITE | slot 0 discarded |
| SET_TEXTURE_SET_BUMP_ENV_OFFSET | pgraph/pgraph.c:3771-3781 | WRITE | slot 0 discarded |
| Fast-path ADDRESS entries | pgraph/pgraph.c:430-433 | WRITE | `MF_DIRECT` — no dirty flag |
| Fast-path BORDER_COLOR entries | pgraph/pgraph.c:436-439 | WRITE | `MF_DIRECT` — no dirty flag |
| Fast-path OFFSET/CTL0/CTL1/FILTER/IMAGE_RECT | pgraph/pgraph.c:586-613 | WRITE | `MF_TEX(reg, slot)` |
| Fast-path dirty apply | pgraph/pgraph.c:652-661 | WRITE | sets `texture_dirty[slot]` on change |
| Fast-path dirty apply (atomic) | pgraph/pgraph.c:684-693 | WRITE | same, lockless dispatch |
| Register category tagging | pgraph/pgraph.c:129-143 | WRITE | TEXCTL0_0/TEXFILTER0/TEXFMT0 are SHADER; 7 regs are TEXTURE |
| Flush forces all dirty (VK) | vk/render_thread.c:274-276, 317-319 | WRITE | `texture_dirty[i] = true` for all 4 |
| Mark textures dirty by range | vk/texture.c:440-473 | WRITE | overlap test against texture + palette ranges |
| Mark textures dirty by range | gl/texture.c:492-510 | WRITE | LRU visitor form |

### S7. Fragment-shader state and GLSL emission

| concept | file:line | role | notes |
|---|---|---|---|
| Colorkey mask by format | glsl/psh.c:40-60 | READ | `X1R5G5B5`/`X8R8G8B8` (SZ and LU) → `0x00FFFFFF` |
| PSH texture state build | glsl/psh.c:140-241 | READ | per-slot; gated by stage-active + `TEXCTL0_0_ENABLE` (:146-151) |
| `alphakill` / `colorkey_mode` | glsl/psh.c:153-154 | READ | from TEXCTL0_0 |
| `dim_tex` | glsl/psh.c:157 | READ | from TEXFMT0_DIMENSIONALITY |
| `rect_tex` (linear) | glsl/psh.c:160-161 | READ | indexes `kelvin_color_format_info_map` **unbounded** |
| `tex_x8y24` | glsl/psh.c:162-166 | READ | the two X8_Y24 depth formats |
| `tex_cubemap` | glsl/psh.c:170-171 | READ | from TEXFMT0_CUBEMAPENABLE |
| Border logical/real size | glsl/psh.c:172-214 | READ | `NV2A_UNIMPLEMENTED` for linear/cubemap borders (:210-212) |
| `snorm_tex` | glsl/psh.c:216-222 | READ | GL renderer only; `SZ_R6G5B5`; `/* VK/desktop GL: ... FIXME */` |
| `shadow_map` | glsl/psh.c:224 | READ | `= f.depth` from the format table |
| Convolution filter | glsl/psh.c:226-240 | READ | asserts kernel ∈ {QUINCUNX, GAUSSIAN_3} at :235-236 |
| Sampler type selection | glsl/psh.c:663-736 | EMIT-SHADER | `usampler2D` for x8y24 on VK; asserts on unhandled dims |
| Shadow comparison operators | glsl/psh.c:738-745 | EMIT-SHADER | maps `SHADOW_ZFUNC` to GLSL operators |
| Shadow-map fetch + compare | glsl/psh.c:747-800 | EMIT-SHADER | NEVER→0, ALWAYS→1; 24-bit MSB extraction at :764-776 |
| Border coordinate adjust | glsl/psh.c:802-820 | EMIT-SHADER | `(uv*logical + 4) * inv_real` |
| Convolution filter emit | glsl/psh.c:822-84x | EMIT-SHADER | 3×3 Gaussian weights; `assert(dim_tex == 2)` at :824 |
| `norm%d()` helper emit | glsl/psh.c:1489-1505 | EMIT-SHADER | only when `rect_tex[i]`; divides by `textureSize/texScale[i]` |
| PROJECT2D emit | glsl/psh.c:1189-1219 | EMIT-SHADER | cubemap remap, convolution, 2D/3D branches |
| PROJECT3D emit | glsl/psh.c:1220-1228 | EMIT-SHADER | shadow-map branch |
| CUBEMAP emit | glsl/psh.c:1229-1238 | EMIT-SHADER | `remapCubeTo2D` when the texture is not really a cubemap |
| PASSTHRU emit | glsl/psh.c:1239-1242 | EMIT-SHADER | asserts no border |
| BUMPENVMAP emit | glsl/psh.c:1254-1279 | EMIT-SHADER | `snorm_tex` branch selects raw `.bg` vs `sign3()` |
| BUMPENVMAP_LUM emit | glsl/psh.c:1280-1309 | EMIT-SHADER | plus `bumpScale`/`bumpOffset` |
| BRDF emit | glsl/psh.c:1310-1315 | EMIT-SHADER | outputs `vec4(0.0)` + `NV2A_UNIMPLEMENTED` |
| DOT_ST emit | glsl/psh.c:1316-1327 | EMIT-SHADER | border adjust on `dotST%d` |
| DOT_ZW emit | glsl/psh.c:1328-1335 | EMIT-SHADER | depth write commented out (`// FIXME`) |
| Dot-map mode guard | glsl/psh.c:1178-1182 | EMIT-SHADER | `assert(dot_map[i] < 8)`; `NV2A_UNIMPLEMENTED` for >3 |
| Bump uniforms | glsl/psh.c:1740-1753 | WRITE | `bumpMat`/`bumpScale`/`bumpOffset`/`texScale` |

### S8. Texture dump / replacement (VK-only)

| concept | file:line | role | notes |
|---|---|---|---|
| Hardcoded VkFormat numbers | vk/texture_dump.c:42-54 | TABLE-ENTRY | 13 `#define`s; **6 do not match the real enum** — see C7 |
| RGBA8 conversion switch | vk/texture_dump.c:101-206 | DECODE | 9 cases + `default` that memcpys only if `size == w*h*4` |
| DXT re-decompress attempt | vk/texture_dump.c:212-232 | DISPATCH | switches on `color_format`, runs **before** the format switch |
| Job processing | vk/texture_dump.c:234-286 | DECODE | writes `<dump>/<titleid>/<hash>.png` |
| Enqueue + dedup | vk/texture_dump.c:400-463 | WRITE | skips `w<4 || h<4`, queue cap 256 |
| Env configuration | vk/texture_dump.c:336-342 | READ | `XEMU_TEXTURE_DUMP`, `XEMU_TEXTURE_DUMP_PATH` |
| `.raw` header | vk/texture_replace.c:51-59 | TABLE-ENTRY | magic `"RAW4"`, `uint16` w/h |
| PNG → `.raw` decode | vk/texture_replace.c:146-174 | DECODE | `stbi_load(..., 4)` → always RGBA8 |
| mmap + validate | vk/texture_replace.c:180-222 | READ | checks magic and size |
| Folder scan | vk/texture_replace.c:227-329 | READ | filenames must be exactly 16 hex chars + `.png` (:278) |
| Lookup (blocking lazy load) | vk/texture_replace.c:492-529 | READ | blocks the caller until the loader thread finishes |
| Needs-upload query | vk/texture_replace.c:596-616 | READ | `has_replacement && !already_applied` |
| Mark applied | vk/texture_replace.c:618-625 | WRITE | |
| Env configuration | vk/texture_replace.c:420-434 | READ | `XEMU_TEXTURE_REPLACE`, `XEMU_TEXTURE_REPLACE_PATH` |

---

## Coupling points (must-agree, unenforced)

### C1. bytes-per-pixel / converted-format agreement (the named example)

**What must agree.** For each format, five independent places encode a size or a
layout for the same pixels, and nothing cross-checks them:

1. `kelvin_color_format_info_map[fmt].bytes_per_pixel` — `pgraph/texture.c:26-79`
2. the CPU decode in `pgraph_convert_texture_data` — `pgraph/texture.c:328-405`
3. `kelvin_color_format_vk_map[fmt].vk_format` — `vk/constants.h:157-319`, and its
   host size in `vk_format_texel_size` — `vk/texture.c:1085-1100`
4. `kelvin_color_format_gl_map[fmt]`'s `{bytes_per_pixel, gl_internal_format,
   gl_format, gl_type}` — `gl/constants.h:211-330`
5. `texture_dump.c`'s per-`vk_format` unpackers — `vk/texture_dump.c:101-206`

**The invariant is deliberately asymmetric**: `bytes_per_pixel` is the *guest
source* stride, while the VK/GL format is the *host destination* layout. For 36 of
the 42 formats these coincide. For **six** they do not, and the code depends on
each consumer knowing which meaning applies:

| format | guest bpp | host bytes/px | where the split is created |
|---|---|---|---|
| `SZ_I8_A8R8G8B8` | 1 (`texture.c:36`) | 4 (`vk/constants.h:187`, `gl/constants.h:233`) | `texture.c:338-352` |
| `L_DXT1_A1R5G5B5` | 4 placeholder (`texture.c:38`) | 4 (RGBA8) or 8 B/block (BC1) | `vk/texture.c:274-309`, `gl/texture.c:1067-1108` |
| `L_DXT23_A8R8G8B8` | 4 placeholder (`texture.c:39`) | 4 or 16 B/block | same |
| `L_DXT45_A8R8G8B8` | 4 placeholder (`texture.c:40`) | 4 or 16 B/block | same |
| `SZ_R6G5B5` | 2 (`texture.c:55`) | **3** (`R8G8B8_SNORM`, `vk/texture.c:1094`) | `texture.c:380-396` |
| `LC_IMAGE_*` (0x24/0x25) | 2 (`texture.c:59-60`) | 4 | `texture.c:353-379` |

**Where it is consumed correctly.** The VK layout builder recomputes
`converted_size` from the conversion's own out-parameter
(`vk/texture.c:321-323`, filled at `pgraph/texture.c:401-403`) while advancing the
*source* pointer by `width*height*f.bytes_per_pixel` (`vk/texture.c:351`). The
surface/texture compatibility check compares host sizes only
(`vk/texture.c:1116-1118`), not `bytes_per_pixel`.

**What breaks if they diverge.**

- If a format's `bytes_per_pixel` were changed to the *host* size, all four
  source-stride uses break at once — length computation
  (`pgraph/texture.c:160`), source-pointer advance (`vk/texture.c:351`,
  `gl/texture.c:1164`), unswizzle element size (`vk/texture.c:318-319`,
  `gl/texture.c:1112-1113`), and the linear-pitch alignment assert
  (`vk/texture.c:216`, `gl/texture.c:1010`). Result: wrong VRAM ranges hashed and
  uploaded, mip levels reading past each other, and a likely abort at
  `vk/texture.c:216`.
- If a VK format is changed without updating `vk_format_texel_size`
  (`vk/texture.c:1085-1100`), the switch returns `0` for the new format and
  `check_surface_to_texture_compatiblity` (`vk/texture.c:1117-1118`) can never
  match — surface-to-texture silently degrades to a stale VRAM upload. There is no
  compile-time or run-time check tying the two lists together.
- If a VK format is changed without updating `texture_dump.c`, the dump
  silently produces no file (see C7).
- **Concrete live instance**: `gl/texture.c:1135` computes the cubemap border skip
  as `pixel_data += 4 * source_bpp + 4 * row_pitch`, where `source_bpp` is
  `f.bytes_per_pixel` on non-Android (`gl/texture.c:1125`) — i.e. the *guest* bpp,
  applied to a buffer that for `SZ_R6G5B5`/`I8_A8R8G8B8` holds *converted* pixels
  of a different width. For those two formats with a bordered cubemap the offset
  is wrong. (VERIFIED code paths; whether any test hits that combination is
  **INFERRED-unknown** — see Uncertainties.)

### C2. Format-table row parity across three tables

**What must agree.** All three `[66]` tables must have a row for exactly the same
42 indices: `pgraph/texture.c:26`, `vk/constants.h:157`, `gl/constants.h:211`.

**What breaks.** A row present in `pgraph` but missing in VK yields
`vkf.vk_format == 0` → **abort** at `vk/texture.c:1632`. A row present in `pgraph`
but missing in GL yields `gl_internal_format == 0` and `gl_format == 0`; because
`gl_format == 0` is the *compressed-texture sentinel* (`gl/texture.c:1067`,
`gl/texture.c:1183`), GL would route the texture into the S3TC decoder and hit
`assert(!"Invalid format")` at `gl/texture.c:971` — **abort**. Conversely a row
added to VK/GL but not to `pgraph` leaves `bytes_per_pixel == 0` → `abort()` at
`pgraph/texture.c:266`. Nothing enforces parity at build time; the tables are
three independent designated-initializer literals.

### C3. `pgraph_is_texture_format_compressed` vs the three DXT dispatchers

**What must agree.** Four independent lists of "which formats are DXT":

- `pgraph/pgraph.h:423-428` (drives length math at `pgraph/texture.c:156` and
  `vk/texture.c:126`, `vk/texture.c:245`)
- `kelvin_format_to_s3tc_format` — `vk/texture.c:78-90`
- `kelvin_format_to_native_bc` — `vk/texture.c:94-106`
- `try_decompress_dxt` — `vk/texture_dump.c:212-232`
- plus GL's *indirect* test `f.gl_format == 0` (`gl/texture.c:1067`, `:1183`)
  and `gl_internal_format_to_s3tc_enum` (`gl/texture.c:960-973`)

**What breaks.** If `pgraph_is_texture_format_compressed` says yes but
`kelvin_format_to_s3tc_format` has no case, `assert(false)` at `vk/texture.c:88`
— **abort**. If it says no but the format really is block-compressed, length math
at `pgraph/texture.c:157-163` computes `w*h*bpp` instead of block counts,
producing a wrong VRAM length used both for hashing (`vk/texture.c:1517`) and for
dirty tracking (`vk/texture.c:455-456`). GL's sentinel test is a *different
predicate entirely* — it keys off `gl_format == 0` rather than the format id, so a
future non-DXT format with `gl_format == 0` would be misrouted.

### C4. Guest method field width vs PGRAPH register field width

**What must agree.** `SET_TEXTURE_*` handlers either raw-copy the 32-bit parameter
into the PGRAPH register or `PG_SET_MASK` individual fields; readers then extract
with the *PGRAPH* masks, which are narrower in three cases:

| field | method mask | PGRAPH mask | writer | reader |
|---|---|---|---|---|
| color format | `0x0000FF00` (8 bits) — nv2a_regs.h:1191 | `0x00007F00` (7 bits) — nv2a_regs.h:589 | pgraph.c:3672 | texture.c:229 |
| dimensionality | `0x000000F0` (4 bits) — nv2a_regs.h:1190 | `0x000000C0` (2 bits) — nv2a_regs.h:588 | pgraph.c:3671 | texture.c:217-218 |
| image rect W/H | `0xFFFF0000`/`0x0000FFFF` (16 bits) — nv2a_regs.h:1254-1255 | `0x1FFF0000`/`0x00001FFF` (13 bits) — nv2a_regs.h:598-599 | raw write pgraph.c:3715 | texture.c:236-240 |
| filter MIN | `0x00FF0000` (8 bits) — nv2a_regs.h:1247 | `0x003F0000` (6 bits) — nv2a_regs.h:566 | raw write pgraph.c:3706 | texture.c:256, vk/texture.c:1815, gl/texture.c:552 |

`SET_MASK` (`nv2a_regs.h:27-33`) masks the shifted value, so the excess bits are
**silently dropped** for the two `PG_SET_MASK` cases. For the two raw-write cases
the bits are stored but never read back.

**What breaks.** A test writing `SET_TEXTURE_FORMAT` colour `0x80`+ lands as
`0x00` (`SZ_Y8`) with no diagnostic. A `SET_TEXTURE_IMAGE_RECT` wider than 8191
wraps. A `SET_TEXTURE_FILTER` MIN of 0x40+ wraps into the low 6 bits.

### C5. `texture_dirty[]` producers vs the VK bind fast-skip

**What must agree.** Every method that can change a texture's *sampler* or *image*
must either set `pg->texture_dirty[slot]` or be re-read unconditionally.

**The gap.** `SET_TEXTURE_ADDRESS` (`pgraph/pgraph.c:2118-2122`, fast path
`pgraph/pgraph.c:430-433`) and `SET_TEXTURE_BORDER_COLOR`
(`pgraph/pgraph.c:3739-3743`, fast path `pgraph/pgraph.c:436-439`) **do not** set
`texture_dirty`. But both values are part of the VK cache key
(`vk/texture.c:1331-1332`) and of the VK sampler (`vk/texture.c:1850-1860`,
`:1860`). `pgraph_vk_bind_textures` returns early when
`check_textures_dirty()` is false (`vk/texture.c:1986-1991`, predicate at
`vk/texture.c:1942-1952`), and the per-slot loop `continue`s at
`vk/texture.c:2005-2009` when the slot is not dirty and not `possibly_dirty` —
neither path re-reads TEXADDRESS0/BORDERCOLOR0.

The GL backend does **not** have this gap: `pgraph_gl_bind_textures` re-reads both
registers every call (`gl/texture.c:700-701`) and the reuse path still calls
`apply_texture_parameters` (`gl/texture.c:788-796`), which diffs `addru/addrv/
addrp/border_color` against the binding (`gl/texture.c:595`, `:609`, `:626`,
`:662`).

**What breaks.** On VK, a wrap-mode-only or border-colour-only change between
draws is not picked up until something else dirties the slot. **INFERRED** from
the control flow above — I did not observe this at runtime.

### C6. VK mag-filter map is declared but never used

`pgraph_texture_mag_filter_vk_map` is defined at `vk/constants.h:38-44` and is
referenced exactly once in the whole tree — inside `ARRAY_SIZE` in the bounds
assert at `vk/texture.c:1813`. The actual lookup uses the **min** map for both
filters: `vk_mag_filter = pgraph_texture_min_filter_vk_map[mag_filter]`
(`vk/texture.c:1819`) and `vk_min_filter = pgraph_texture_min_filter_vk_map[min_filter]`
(`vk/texture.c:1820`).

**What must agree.** The two maps' first five entries. Comparing
`vk/constants.h:27-36` with `vk/constants.h:38-44`: index 0 → `0`/`0`, 1 →
`NEAREST`/`NEAREST`, 2 → `LINEAR`/`LINEAR`, 4 → `LINEAR`/`LINEAR` agree; **index 3
disagrees** (min map gives `VK_FILTER_NEAREST`, mag map gives `0`). Index 3 is not
a documented MAG value, so today this is benign.

**What breaks.** Anyone editing `pgraph_texture_mag_filter_vk_map` to fix a
mag-filter bug changes nothing, because the array is dead. The GL backend does use
its own mag map (`gl/texture.c:582`), so the two renderers would silently diverge.

### C7. `texture_dump.c` hardcoded VkFormat numbers vs the real `VkFormat` enum

`vk/texture_dump.c:42-54` re-declares Vulkan format numbers rather than including
`<vulkan/vulkan.h>`. The values it is compared against come from
`kelvin_color_format_vk_map` via `(uint32_t)vkf.vk_format` at `vk/texture.c:690`.
Checked against `thirdparty/SDL2/src/video/khronos/vulkan/vulkan_core.h`
(the `VkFormat` enum body at lines 1405-1630 — core `VkFormat` values are frozen
ABI, so this header is authoritative):

| symbol in texture_dump.c | value used | real value | header line | match |
|---|---|---|---|---|
| `VK_FMT_R8_UNORM` (`:42`) | 9 | 9 | vulkan_core.h:1416 | yes |
| `VK_FMT_R8G8_UNORM` (`:43`) | 16 | 16 | vulkan_core.h:1423 | yes |
| `VK_FMT_R8G8B8_SNORM` (`:44`) | 25 | 24 | vulkan_core.h:1431 | **no** (25 is `R8G8B8_USCALED`) |
| `VK_FMT_R8G8B8A8_UNORM` (`:45`) | 37 | 37 | vulkan_core.h:1444 | yes |
| `VK_FMT_B8G8R8A8_UNORM` (`:46`) | 44 | 44 | vulkan_core.h:1451 | yes |
| `VK_FMT_A8B8G8R8_UNORM_PACK32` (`:47`) | 50 | 51 | vulkan_core.h:1458 | **no** (50 is `B8G8R8A8_SRGB`) |
| `VK_FMT_R5G6B5_UNORM_PACK16` (`:48`) | 84 | 4 | vulkan_core.h:1411 | **no** |
| `VK_FMT_A1R5G5B5_UNORM_PACK16` (`:49`) | 86 | 8 | vulkan_core.h:1415 | **no** |
| `VK_FMT_A4R4G4B4_UNORM_PACK16` (`:50`) | 105 | 1000340000 | vulkan_core.h:1630 | **no** |
| `VK_FMT_R16_UNORM` (`:51`) | 70 | 70 | vulkan_core.h:1477 | yes (but unused in the switch) |
| `VK_FMT_BC1_RGBA_UNORM` (`:52`) | 131 | 133 | vulkan_core.h:1540 | **no** (131 is `BC1_RGB_UNORM`); unused |
| `VK_FMT_BC2_UNORM` (`:53`) | 135 | 135 | vulkan_core.h:1542 | yes; unused |
| `VK_FMT_BC3_UNORM` (`:54`) | 137 | 137 | vulkan_core.h:1544 | yes; unused |

Only the first nine appear as `case` labels (`vk/texture_dump.c:110-182`); the
last four are dead defines.

**What breaks.** For `R5G6B5`, `A1R5G5B5`, `A4R4G4B4` and `R6G5B5`(→`R8G8B8_SNORM`)
the case never matches, so control reaches `default:` at
`vk/texture_dump.c:194-202`, which only memcpys when `size == num_pixels * 4`.
Those buffers are 2 or 3 bytes per pixel, so the condition fails and the function
returns `NULL` (`:199-200`), and `process_dump_job` jumps to `out:`
(`vk/texture_dump.c:248-250`) — **all 16-bit-packed and R6G5B5 textures are
silently never dumped**. No error, no log. This directly undermines any
dump-then-replace workflow for those formats.

### C8. Dump-path DXT double-decompression

`upload_texture_image` hands the dump queue `base->decoded_data`
(`vk/texture.c:686-691`). That buffer is *compressed blocks* only on the native-BC
path (`vk/texture.c:280-289`); on every other path it is already CPU-decompressed
RGBA8 (`vk/texture.c:290-309`, `vk/texture.c:376-390`). But
`process_dump_job` runs `try_decompress_dxt` **first**, keyed only on
`job->color_format` (`vk/texture_dump.c:238-240`, dispatcher at `:212-232`), and
that succeeds for any DXT format id.

**What must agree.** The decision "is `decoded_data` compressed?" is made at
`vk/texture.c:274-276` (from `r->texture_compression_bc_supported` and
`state->dimensionality != 3`) but is **not** communicated to the dump job — the
job carries only `vk_format` and `color_format`, not a compressed flag.

**What breaks.** When BC is unsupported, or for 3D DXT textures, the dumper
re-runs `s3tc_decompress_2d` on already-decompressed RGBA8 and writes a garbage
PNG. It cannot over-read: a `w*h*4` RGBA8 buffer is always at least as large as
the `w*h/2` (DXT1) or `w*h` (DXT3/5) bytes the decoder reads. So the failure mode
is corrupt output, not a crash. (The size reasoning is **INFERRED** arithmetic from
`s3tc.c:438` block counts and `s3tc.c:440` allocation, but the code paths are
VERIFIED.)

### C9. `texture_format_properties[]` is indexed by kelvin format, filled from the mapped VK format

`pgraph_vk_init_textures` fills the array once per row of
`kelvin_color_format_vk_map` (`vk/texture.c:2356-2362`), so entry *i* describes
the properties of `kelvin_color_format_vk_map[i].vk_format`.
`is_linear_filter_supported_for_format` then indexes it by kelvin format
(`vk/texture.c:1282-1287`) — consistent.

**But** when the native-BC override fires (`vk/texture.c:1619-1630`), the image is
actually created with `VK_FORMAT_BC1/2/3_*` while the linear-filter query at
`vk/texture.c:1818` still reports the properties of `R8G8B8A8_UNORM`. Nothing
re-queries. **What breaks**: on a device where RGBA8 supports linear filtering but
the BC format does not, the sampler would request `VK_FILTER_LINEAR` on an image
whose format lacks `SAMPLED_IMAGE_FILTER_LINEAR`. The BC capability probe at
`vk/texture.c:2377` only checks `VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT`, not the
linear-filter bit. (Reachability is device-dependent — **INFERRED**.)

### C10. GL cubemap face stride recomputed instead of shared

`pgraph_get_texture_length` computes per-face length at `pgraph/texture.c:153-184`;
`generate_texture` recomputes essentially the same quantity at
`gl/texture.c:1326-1354` to derive the per-face byte offsets, and
`get_cubemap_layer_size` computes it a **third** time at `vk/texture.c:122-156`.
The three differ in detail: the VK and GL versions apply border doubling
(`vk/texture.c:132-135`, `gl/texture.c:1337-1340`) while
`pgraph_get_texture_length` does **not** (`pgraph/texture.c:153-184` has no border
adjustment).

**What breaks.** `pgraph_get_texture_length`'s result is what gets hashed
(`vk/texture.c:1517`, `gl/texture.c:874`) and what defines the dirty-tracking range
(`vk/texture.c:455-456`, `vk/texture.c:1487`). For a bordered cubemap the hashed
range is smaller than the range actually read by the layout builder, so edits to
the border region can go undetected and the texture is not re-uploaded.
(**INFERRED** consequence; the three differing computations are VERIFIED.)

### C11. `texScale` linear-guard divergence between renderers

VK forces `scale = 1.0` for non-linear formats (`vk/shaders.c:1197-1203`); GL does
not (`gl/shaders.c:876-881`). `texScale[i]` is consumed only inside the generated
`norm%d()` helper (`glsl/psh.c:1492`), which is only emitted when `rect_tex[i]` is
true (`glsl/psh.c:1489`), i.e. only for linear formats. So today the guard is
redundant and the divergence has no visible effect — **INFERRED** from those three
sites. It becomes a real divergence the moment `texScale` acquires a second use.

### C12. Live-register vs snapshot-register read paths (currently dormant)

`pgraph_get_texture_shape` reads the **live** register file via `pgraph_reg_r`
(`pgraph/texture.c:86`, `:90`, `:110`, `:198-200`, `:220`, `:236`, `:239`), while
`create_texture` reads filter/address/border/anisotropy via `pgraph_vk_reg_r`
(`vk/texture.c:1304-1314`, `:2028-2057`), which is a snapshot-aware accessor
(`vk/renderer.h:1372-1379`).

**Currently harmless**: `r->active_snap` is declared at `vk/renderer.h:994` and
read at `vk/renderer.h:1375` but is **never assigned anywhere in the repository**
(verified by a whole-tree grep for `active_snap`, which returns only those three
lines). So `pgraph_vk_reg_r` always falls through to `pgraph_reg_r` today.

**What breaks.** The moment snapshotting is turned on, the shape would come from
live registers and the sampler state from the snapshot, for the same draw.

---

## Stubs and gaps

`NV2A_UNIMPLEMENTED` is a **compiled-out no-op** in default builds
(`hw/xbox/nv2a/debug.h:48-50`, `:66-67`). `assert` always aborts
(`include/qemu/osdep.h:311-312`).

| symbol | file:line | kind | what behaviour it gates | ABORTS? |
|---|---|---|---|---|
| unimplemented colour format | pgraph/texture.c:263-267 | `abort` | any format with `bytes_per_pixel == 0` (24 table gaps) | **YES** — `fprintf` + `abort()` |
| colour format range | pgraph/texture.c:261 | assert | `color_format < 66` (values 0x42-0x7F) | **YES** |
| texture offset in DMA | pgraph/texture.c:99 | assert | `offset < dma_len` | **YES** |
| palette offset in DMA | pgraph/texture.c:137 | assert | `palette_offset < palette_dma_len` | **YES** |
| palette length code | pgraph/texture.c:124 | assert | `TEXPALETTE0_LENGTH` outside 0-3 | **YES** (unreachable: 2-bit field) |
| linear + cubemap | pgraph/texture.c:149 | assert | linear formats must not be cubemaps | **YES** |
| linear + dim != 2 | pgraph/texture.c:150, :271 | assert | linear formats must be 2D | **YES** |
| cubemap + dim != 2 | pgraph/texture.c:181 | assert | | **YES** |
| tex_mode 0x02 with unit off | pgraph/texture.c:222 | assert | `assert(pgraph_is_texture_enabled(...))` | **YES** |
| dimensionality==3 override | pgraph/texture.c:223-226 | commented-out | volumetric override disabled | no |
| levels > 0 | pgraph/texture.c:294 | assert | after mip clamping | **YES** |
| mip discard heuristic | pgraph/texture.c:283-284 | FIXME | "Is this actually needed?" | no |
| 3D mipmaps | pgraph/texture.c:297 | FIXME | "What about 3D mipmaps?" | no |
| YUV depth != 1 | pgraph/texture.c:357-360 | assert + TODO/FIXME | volumetric YUV textures | **YES** |
| YUV colourspace gating | pgraph/texture.c:361-362 | FIXME | ignores CONTROL0 colourspace bit | no |
| R6G5B5 depth != 1 | pgraph/texture.c:381 | assert | volumetric R6G5B5 | **YES** |
| s3tc format dispatch | vk/texture.c:88 | assert | non-DXT reaching the DXT decoder | **YES** |
| linear dim != 2 | vk/texture.c:186 | assert | | **YES** |
| cubemap dim/linear | vk/texture.c:189-190 | assert | | **YES** |
| 1D textures | vk/texture.c:192 | assert | `assert(s.dimensionality > 1)` — **VK has no 1D texture support** | **YES** |
| pitch not pixel-aligned | vk/texture.c:216 | assert | linear pitch % bpp != 0 | **YES** |
| linear width shrink | vk/texture.c:225 | assert | `adjusted_width <= s.width` | **YES** |
| linear mip levels | vk/texture.c:232 | assert | `assert(s.levels == 1)` for linear | **YES** |
| s3tc alloc failure | vk/texture.c:295, :381 | assert | | **YES** |
| cubemap border preservation | vk/texture.c:332-341 | FIXME | border texels discarded on cubemaps | no |
| bounds checking | vk/texture.c:161 | FIXME | "Bounds checking" (absent) in the layout builder | no |
| decoded size non-zero | vk/texture.c:586 | assert | | **YES** |
| staging allocation | vk/texture.c:605, :645 | assert | after 3 fallback attempts | **YES** |
| zeta s2t preconditions | vk/texture.c:710-711, :961-962 | assert | colour/stencil aspect mismatch | **YES** |
| unmapped VK format | vk/texture.c:1632 | assert | `assert(vkf.vk_format != 0)` — format present in `pgraph` table but not VK table | **YES** |
| dimensionality range | vk/texture.c:1633-1636 | assert | `0 < dim < 4` | **YES** |
| image creation OOM | vk/texture.c:1738 | assert | after pool drain + LRU flush retries | **YES** |
| custom border colour | vk/texture.c:1790 | FIXME | falls back to 3 fixed border colours (`:1791-1799`) | no |
| `TEXFILTER0_ASIGNED` | vk/texture.c:1802-1803 | NV2A_UNIMPLEMENTED | signed alpha channel | no — compiled out |
| `TEXFILTER0_RSIGNED` | vk/texture.c:1804-1805 | NV2A_UNIMPLEMENTED | signed red channel | no — compiled out |
| `TEXFILTER0_GSIGNED` | vk/texture.c:1806-1807 | NV2A_UNIMPLEMENTED | signed green channel | no — compiled out |
| `TEXFILTER0_BSIGNED` | vk/texture.c:1808-1809 | NV2A_UNIMPLEMENTED | signed blue channel | no — compiled out |
| mag filter range | vk/texture.c:1813 | assert | `mag_filter < 5` — MAG is a 4-bit field (0-15) | **YES** for MAG ≥ 5 |
| min filter range | vk/texture.c:1816 | assert | `min_filter < 8` — MIN is a 6-bit field (0-63) | **YES** for MIN ≥ 8 |
| wrap mode range | vk/texture.c:55 | assert | `0 < idx < 6`; **wrap mode 0 aborts** | **YES** |
| image pool invariant | vk/texture.c:2138 | assert | | **YES** |
| cache alloc | vk/texture.c:2262 | assert | | **YES** |
| finalize invariants | vk/texture.c:2398, :2407 | assert | | **YES** |
| Android format fallthrough | gl/texture.c:367 | `g_assert_not_reached` | format in `android_texture_needs_rgba8_upload` but not in the convert switch | **YES** (Android builds only) |
| S3TC enum from GL ifmt | gl/texture.c:971 | assert | `assert(!"Invalid format")` | **YES** |
| GL_TEXTURE_1D upload | gl/texture.c:1004-1006 | assert | `assert(false)` — **1D texture upload is unimplemented** | **YES** |
| linear pitch alignment | gl/texture.c:1010 | assert | | **YES** |
| 3D + linear | gl/texture.c:1179 | assert | | **YES** |
| unknown gl_target | gl/texture.c:1269-1271 | assert | | **YES** |
| cubemap + linear | gl/texture.c:1291-1292, :1297 | assert | | **YES** |
| dimensionality default | gl/texture.c:1309-1311 | assert | dim outside 1-3 | **YES** |
| binding refcount | gl/texture.c:1424 | assert | | **YES** |
| wrap mode range S/T/R | gl/texture.c:594, :610, :627 | assert | `addr* < 6` | **YES** |
| **min filter range (GL)** | gl/texture.c:575-579 | *(none)* | **no bounds check** — 6-bit index into an 8-entry array | no — **out-of-bounds read** |
| **mag filter range (GL)** | gl/texture.c:580-584 | *(none)* | **no bounds check** — 4-bit index into a 5-entry array | no — **out-of-bounds read** |
| `TEXFILTER0_*SIGNED` (GL) | gl/texture.c:707-710 | NV2A_UNIMPLEMENTED | signed channels | no — compiled out |
| border colour channel order | gl/texture.c:663 | FIXME | "Color channels might be wrong order" | no |
| texture disabled/stage active | gl/texture.c:685 | FIXME | open question in comment | no |
| surface→cubemap face | gl/texture.c:824 | FIXME | render-to-cubemap-face unsupported | no |
| cubemap border (GL) | gl/texture.c:1083-1085, :1130-1132 | FIXME | border texels discarded | no |
| invalid VRAM range | gl/texture.c:725-758 | log + skip | logs and unbinds instead of aborting | no — GL-only safety net absent in VK |
| swizzle mask exclusivity | pgraph/swizzle.c:70 | assert | non-power-of-two dimensions | **YES** |
| s3tc dimension | pgraph/s3tc.c:326-328, :434-435 | assert | zero width/height/depth | **YES** |
| surface→texture format compat | gl/surface.c:1381 | FIXME | "Better checks/handling on formats" | no (returns false) |
| zeta→colour s2t (GL) | gl/surface.c:1392-1395 | FIXME | unsupported, returns false | no |
| cubemap s2t (GL) | gl/surface.c:1397-1400 | FIXME | unsupported | no |
| mip-level s2t (GL) | gl/surface.c:1402-1405 | FIXME | unsupported | no |
| border on linear/cubemap | glsl/psh.c:210-212 | NV2A_UNIMPLEMENTED | leaves `border_logical_size = 0` → no coordinate adjustment | no — compiled out |
| `snorm_tex` on VK/desktop GL | glsl/psh.c:223 | FIXME | left `false`; bump-map input treated as unsigned | no |
| convolution kernel value | glsl/psh.c:235-236 | assert | kernel outside {1,2} when MIN==CONVOLUTION_2D_LOD0 | **YES** |
| shadow map + BUMPENVMAP/DOT_ST | glsl/psh.c:694-697 | assert | `assert(!"Shadow map support not implemented for this mode")` | **YES** |
| shadow map + CUBEMAP/DOT_RFLCT/DOT_STR_CUBE | glsl/psh.c:717-720 | assert | same | **YES** |
| shadow map + DPNDNT_AR/GB | glsl/psh.c:729-732 | assert | same | **YES** |
| unhandled sampler dims | glsl/psh.c:688, :700 | assert | `assert(!"Unhandled texture dimensions")` | **YES** |
| cubemap assumption | glsl/psh.c:721, :733 | assert | `assert(dim == 2)` for cube/dependent modes | **YES** |
| convolution dim | glsl/psh.c:824 | assert | `assert(dim_tex[tex] == 2)` | **YES** |
| point sprite + linear tex3 | glsl/psh.c:1155 | assert | `assert(!rect_tex[3])` | **YES** |
| border on PASSTHRU | glsl/psh.c:1240 | assert | | **YES** |
| BUMPENVMAP stage index | glsl/psh.c:1255, :1281 | assert | `assert(i >= 1)` | **YES** |
| unhandled bump dims | glsl/psh.c:1277, :1304 | assert | | **YES** |
| PS_TEXTUREMODES_BRDF | glsl/psh.c:1310-1315 | NV2A_UNIMPLEMENTED | emits `vec4(0.0)` | no — compiled out |
| DOT_ZW depth output | glsl/psh.c:1334 | FIXME | `gl_FragDepth` write commented out | no |
| dot-map mode > 3 | glsl/psh.c:1180-1182 | NV2A_UNIMPLEMENTED | | no — compiled out |
| dot-map range | glsl/psh.c:1178 | assert | `assert(dot_map[i] < 8)` | **YES** |
| bump 3D r-coordinate | glsl/psh.c:1273, :1300 | FIXME | "Does hardware pass through the r/z coordinate or is it 0?" | no |
| unbounded format-table index | glsl/psh.c:159-160 | *(none)* | `kelvin_color_format_info_map[color_format]` with a 7-bit field into a 66-entry array | no — **out-of-bounds read** for 0x42-0x7F |

---

## Suites plausibly exercised

Confidence key: **high** = the suite name maps onto a code path I read and the
mapping is unambiguous; **medium** = mapping is clear but which specific sites fire
depends on test parameters I have not seen; **low** = I am reasoning about test
content I have not read.

### Texture_format — confidence **high** (sites), **medium** (per-format outcome)
Exercises the full S1 table three times over: `pgraph/texture.c:26-79`,
`vk/constants.h:157-319`, `gl/constants.h:211-330`; shape decode
`pgraph/texture.c:194-326`; length math `pgraph/texture.c:143-192`; unswizzle
`pgraph/swizzle.c:205-246`; CPU conversions `pgraph/texture.c:328-405`
(palette, YUV, R6G5B5); GL upload `gl/texture.c:1109-1165`; VK upload
`vk/texture.c:312-352`. Aborts to expect if the suite sweeps the whole 7-bit field:
`pgraph/texture.c:261` (format ≥ 0x42) and `pgraph/texture.c:263-267` (any of the
24 table gaps). Those two are the most likely suppressors of a full-sweep run.

### Texture_DXT — confidence **high**
`pgraph_is_texture_format_compressed` (`pgraph/pgraph.h:423-428`); block-size
selection (`pgraph/texture.c:166-169`, `vk/texture.c:247-251`,
`gl/texture.c:1069-1071`); the whole of `pgraph/s3tc.c` including the partial-block
clip at `s3tc.c:173-176` (matters for non-multiple-of-4 dimensions, which is
exactly what `physical_width = (width+3) & ~3` at `s3tc.c:436` is for); the VK
native-BC path (`vk/texture.c:94-106`, `:274-289`, `:1619-1630`) versus the CPU
path (`vk/texture.c:290-309`); the 3D-always-CPU rule (`vk/texture.c:373-390`); GL
always CPU-decompresses and uploads RGBA8 (`gl/texture.c:1074-1098`,
`gl/texture.c:1199-1207`). Note the GL and VK results are expected to differ
in *host* format (RGBA8 vs BC) but not in sampled values.

### Texture_cubemap — confidence **high**
`TEXFMT0_CUBEMAPENABLE` decode (`pgraph/texture.c:215-216`); the three separate
face-stride computations (`pgraph/texture.c:180-184`, `gl/texture.c:1326-1367`,
`vk/texture.c:122-156`) — see C10; VK cube image flags
(`vk/texture.c:1645`, `:1652`) and `VK_IMAGE_VIEW_TYPE_CUBE`
(`vk/texture.c:1743-1745`); GL six-face upload (`gl/texture.c:1356-1367`); border
strip discard (`gl/texture.c:1079-1106`, `vk/texture.c:331-341`); shader-side
`tex_cubemap` and `remap2DToCube` (`glsl/psh.c:170-171`, `:1199-1203`, `:1229-1238`).
Asserts that can abort here: `pgraph/texture.c:149`/`:181`, `vk/texture.c:189-190`,
`gl/texture.c:1291-1292`.

### Texture_perspective — confidence **medium**
`PS_TEXTUREMODES_PROJECT2D`/`PROJECT3D` emission (`glsl/psh.c:1189-1228`) and
`textureProj` with the `norm%d()` remap for linear textures
(`glsl/psh.c:1489-1505`, `:1176`); `z_perspective` state (`glsl/psh.c:106-107`).
Which of the two modes fires depends on the test's `SHADERPROG` setting, which I
have not read.

### Texture_render_target — confidence **high**
VK: `check_surface_to_texture_compatiblity` (`vk/texture.c:1102-1119`),
`vk_format_texel_size` (`vk/texture.c:1085-1100`), direct colour bind
(`vk/texture.c:905-949`), zeta direct bind (`vk/texture.c:955-1004`), zeta copy
path (`vk/texture.c:707-899`), colour copy path (`vk/texture.c:1006-1083`), the
shelved-surface scan (`vk/texture.c:1389-1402`), and the scale factor
(`vk/texture.c:1429-1431`, `:1655-1658`). GL: the explicit format allow-list
(`gl/surface.c:1413-1441`) and `pgraph_gl_render_surface_to_texture`
(`gl/texture.c:912-923`). The two allow-lists are structurally different — GL
enumerates format pairs, VK compares byte sizes — so a mismatch between the
renderers on this suite is expected rather than surprising.

### Texture_shadow_comparator — confidence **high**
`f.depth` in the format table (the five depth rows: `pgraph/texture.c:62-70`)
feeding `state->shadow_map[i]` (`glsl/psh.c:224`); `SHADOW_ZFUNC` read
(`glsl/psh.c:103-105`); operator table (`glsl/psh.c:738-745`); emission
(`glsl/psh.c:747-800`) including the NEVER/ALWAYS short-circuits (`:749-757`) and
the 24-bit `usampler2D` MSB extraction on VK (`:764-776`, sampler type at
`:679-681`, `:705-707`); VK format rows `R16_UNORM`/`R32_UINT` with the
"green = 24-bit, blue = float" swizzle convention (`vk/constants.h:264-292`) and
the parallel GL rows (`gl/constants.h:291-311`). Aborts to expect if the suite
combines a depth texture with a non-PROJECT mode: `glsl/psh.c:694-697`,
`:717-720`, `:729-732`.

### Texture_signed_component_tests — confidence **high** on the gap, medium on scope
The four `*SIGNED` bits are read and then discarded on both renderers:
`vk/texture.c:1802-1809` and `gl/texture.c:707-710`, both via a macro that is a
no-op (`hw/xbox/nv2a/debug.h:66-67`). The only signed handling anywhere is the
`SZ_R6G5B5`-specific `snorm_tex` flag, and it is set **only** for the OpenGL
renderer (`glsl/psh.c:219-222`, with `/* VK/desktop GL: snorm_tex left at default
(false) — FIXME */` at `:223`) plus the `R8G8B8_SNORM`/`GL_RGB8_SNORM` table rows
(`vk/constants.h:246-248`, `gl/constants.h:277-278`). Expect VK and GL to disagree
on this suite by construction.

### Bump_map — confidence **high**
Method handlers `pgraph/pgraph.c:3745-3781` (note the discarded slots at `:3748`,
`:3762`, `:3774` and the `BUMPMAT00/01/11/10` swizzle at `:3754-3756`); uniform
upload `glsl/psh.c:1740-1749`; emission `glsl/psh.c:1254-1309`; the `snorm_tex`
branch at `:1257` and `:1283` (see the previous entry — VK always takes the
`sign3()` branch); sampler-type restriction `glsl/psh.c:691-701`; the
`assert(i >= 1)` stage guard at `:1255`/`:1281`.

### Image_blit — confidence **low/medium**
Image_blit is the 2D blit class, not the texture pipeline. Its contact with these
files is indirect: blit writes to VRAM must reach the texture dirty machinery —
`pgraph_vk_mark_textures_possibly_dirty` (`vk/texture.c:440-473`) and
`pgraph_gl_mark_textures_possibly_dirty` (`gl/texture.c:492-510`) — and the
content-hash comparison (`vk/texture.c:1515-1521`, `:1563`;
`gl/texture.c:872-887`). If the blit destination is later sampled, the swizzle
helpers (`pgraph/swizzle.c`) are shared. I did **not** read the blit
implementation, so I cannot say which of these it actually reaches.

### Surface_format — confidence **medium**
Only touches this sweep through the surface↔texture format maps:
`kelvin_surface_color_format_map` / `kelvin_surface_color_format_vk_map` /
zeta variants (`vk/constants.h:332-416`), the GL equivalents
(`gl/constants.h:340-373`), and the compatibility gates
(`vk/texture.c:1102-1119`, `gl/surface.c:1377-1446`). The surface pipeline proper
(`gl/surface.c`, `vk/surface.c`) was out of scope and I did not read it.

---

## Uncertainties

1. **Which hardware formats the 24 table gaps correspond to.** I can enumerate the
   missing indices exactly (0x08-0x0A, 0x0D, 0x14-0x16, 0x18, 0x21-0x23, 0x26,
   0x2A-0x2B, 0x2D, 0x32-0x34, 0x36-0x39, 0x3D-0x3E) but the repo defines no names
   for them, so I cannot say whether any is a real NV2A format that games or tests
   use. In particular 0x2D sits inside the depth-format run (0x2C, 0x2E-0x31) and
   looks like it *should* be a depth format, but I have no evidence for that and am
   not asserting it.

2. **Whether any nxdk_pgraph_tests suite actually reaches the aborting asserts.**
   I did not read the test suite; the repo contains no copy of
   `abaire/nxdk_pgraph_tests` that I found. The abort column in "Stubs and gaps" is
   accurate about *what the code does*, not about *what the tests trigger*.

3. **The `pgraph_texture_mag_filter_vk_map` index-3 disagreement (C6).** Index 3 is
   not a named MAG value in `nv2a_regs.h` (only MIN values 1-7 are named at
   `nv2a_regs.h:567-573`; MAG has no named values at all). Whether hardware ever
   produces MAG == 3, and what it means, I do not know.

4. **`psh.c:160` out-of-bounds vs `texture.c:261` abort — which fires first.** Both
   are reachable for `color_format` ≥ 66. In the VK draw path `pgraph_vk_bind_textures`
   is called at `vk/draw.c:1194` before `pgraph_vk_bind_shaders` at `vk/draw.c:1212`,
   which suggests the assert would usually win; but `pgraph_vk_bind_textures`
   early-returns when nothing is dirty (`vk/texture.c:1986-1991`) while PSH state can
   still be rebuilt, so the ordering is not guaranteed. In the GL path the two calls
   are in different functions (`gl/draw.c:180` vs `gl/draw.c:462/507/553/595`) and I
   did not trace the call graph. **Unresolved.**

5. **Whether C5 (TEXADDRESS/BORDERCOLOR not dirtying on VK) is observable.** The
   control-flow gap is verified, but I did not check whether some other per-draw
   path forces a re-bind often enough to mask it. `pipeline_state_dirty`
   (`vk/texture.c:2067-2069`) is set only when bindings changed, which does not
   help here.

6. **`VK_FORMAT_A4R4G4B4_UNORM_PACK16` availability.** `vk/constants.h:174` and
   `:232` use it. In the header it is `1000340000` (`vulkan_core.h:1630`), i.e. from
   `VK_EXT_4444_formats` / Vulkan 1.3. I did not check whether the instance/device
   setup in `vk/instance.c` requires that version or extension, so I cannot say
   whether those two rows can produce `VK_ERROR_FORMAT_NOT_SUPPORTED` at image
   creation on older drivers.

7. **Which vulkan headers the build actually uses.** `vk/constants.h:25` includes
   `<vulkan/vulkan.h>` from the system include path; the only copy I found in-tree
   is `thirdparty/SDL2/src/video/khronos/vulkan/vulkan_core.h`. Core `VkFormat`
   values are frozen ABI so the C7 comparison holds regardless, but I did not
   confirm which header the compiler resolves.

8. **Android-only paths.** `gl/texture.c:30-410` and several `#ifdef __ANDROID__`
   blocks change format handling substantially (forcing RGBA8 uploads for 27
   formats, suppressing swizzles, NEON conversions). I read them but did not
   evaluate whether their per-format behaviour matches the desktop path — that is a
   whole second format-agreement surface I have not audited.

9. **`pgraph_convert_texture_data` return-size contract.** GL calls it with
   `converted_size == NULL` in all three call sites (`gl/texture.c:1014`, `:1116`,
   `:1225`) and then re-derives the stride from `f.bytes_per_pixel`; VK passes a
   real pointer (`vk/texture.c:221`, `:323`, `:410`). I traced the GL arithmetic
   for `SZ_R6G5B5` and `I8_A8R8G8B8` and it appears to work out because
   `GL_UNPACK_ROW_LENGTH` is set to 0 in those cases (`gl/texture.c:1037-1039`,
   `:1150-1153`), but I did not test it and the cubemap-border offset at
   `gl/texture.c:1135` is the one place I believe it does not (see C1). Treat that
   sub-claim as **INFERRED**.

10. **`Image_blit` coverage.** Not read. See the suite entry.

11. **Whether the `possibly_dirty` / `dirty_check_frame` caching in VK
    (`vk/texture.c:484-506`, `:1481-1510`, `:2005-2043`) can miss a VRAM edit.**
    The logic is intricate (a frame-scoped memoization of
    `memory_region_test_and_clear_dirty`, which is itself destructive — it clears
    the bits it reads at `vk/texture.c:480-481`). I did not attempt to prove or
    disprove correctness; flagging it as an area that would repay a dedicated read.

12. **`s3tc_decompress_2d` thread-args `block_size` is never initialized**
    (`pgraph/s3tc.c:444-450`, `:467-473` leave the `.block_size` member at 0 while
    `S3tcWorkerArgs` declares it at `s3tc.c:403`). `s3tc_worker_func`
    (`s3tc.c:406-428`) never reads it, so this is dead-but-uninitialized rather
    than a bug — but I did not check whether any other consumer of that struct
    exists.
