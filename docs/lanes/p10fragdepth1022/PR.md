# p10fragdepth1022: HAKUX_FRAGDEPTH=off leaves the depth word to fixed function where it lands within one unit, so the shader no longer forces late Z (#433)

State: draft

Lane: p10fragdepth1022            Issue: #433 (0.5)
Base: master @ b944110629
Files: docs/lanes/p10fragdepth1022/PR.md, hw/xbox/nv2a/pgraph/glsl/psh.c, hw/xbox/nv2a/pgraph/glsl/psh.h,
hw/xbox/nv2a/pgraph/glsl/shaders.c, hw/xbox/nv2a/pgraph/pgraph.c, hw/xbox/nv2a/pgraph/vk/draw.c,
hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/shaders.c
Prediction: on Blinx 2 (GPU-bound; P1 measured no change there), `HAKUX_FRAGDEPTH=off` against the same build
  unset gives a lower GPU R/flip, with `psh_depth_ff` covering most depth-tested draws, and every leg of the
  10 depth suites passes under `off`. Falsifier: GPU R/flip ratio (off / unset) > 0.95 while `psh_depth_ff`
  covers > 80 % of depth-tested draws, or any depth-suite leg failing under `off`
Needs device: yes, for the depth-suite A/B and the Blinx 2 pair
Needs NDK: no
Selftest: 65-status-objective 75-nv2a-index-drift 86-nightly-notes 99-dipwin-counters -- the fragments whose
  text names psh.c, draw.c, shader_state or SHADER_STATE_LAYOUT

The fps30 plan's P10 has two arms. Arm A (a conservative-depth layout on `gl_FragDepth`) has no qualifier that
both holds and keeps LRZ under LESS/LEQUAL; that analysis is kept below as its own section. Arm B, this change,
drops the `gl_FragDepth` write where fixed-function depth stores a word within one unit of the one the write
stores, behind `HAKUX_FRAGDEPTH=off`. Unset or `on` is today's shader, byte for byte.

## Arm B

### Mechanism

Every depth-tested NV2A draw writes `gl_FragDepth` today, because `depth_needed = depth_test || depth_write ||
depth_clipping` (`glsl/psh.c:523-524`) and the write follows `depth_needed`. On Turnip a depth-writing fragment
shader sets `force_late_z` (`tu_lrz.cc:1188-1189`) and, with no conservative layout, invalidates LRZ for the rest
of the render pass (`tu_lrz.cc:1235-1278`; arm A below).

Without the write the host stores the rasteriser's own depth: the interpolated `oPos.z / clipRange.y`
(`vsh-prog.c:912`, `vsh-ff.c:1304`), tested and written by the pipeline's compare op and write enable
(`vk/draw.c:3504-3515`, dynamic at `:7787-7801`), and clamped to the viewport's `[0, 1]` by `depthClampEnable`
(`vk/draw.c:3453-3455`; viewport `minDepth 0, maxDepth 1`). The shader keeps the ZCLAMP CULL discard
(`psh.c:3369-3373`), which still reads the shader's own depth, so the draw is a kill shader: Turnip gives it
`EARLY_Z_LATE_Z` with the LRZ test and no LRZ write (`TU_LRZ_FORCE_DISABLE_WRITE`, `tu_shader.cc:3739-3740`),
and the render pass's LRZ is no longer invalidated by it.

`clipRange.y` (`glsl/common.c:142-155`) is `0xFFFF` for Z16, `0x1000000` for Z24S8 on float storage and `0xFFFFFF`
for Z24S8 on D24 unorm storage, so the stored value is the guest's depth word scaled exactly as the write scales
it.

### When the write is omitted

`pgraph_glsl_psh_depth_write()` (`psh.c:116-150`) returns `PSH_DEPTH_WRITE_FF` only when all of these hold:

1. the arm is active: `HAKUX_FRAGDEPTH=off`, the device has `depthClamp`, and Z24S8 maps to `D24_UNORM_S8` or
   `D32_SFLOAT_S8` (`vk/shaders.c:1231-1266`);
2. `depth_needed`;
3. the depth format is D24 or D16 (fixed point);
4. not `z_perspective` (w-buffer);
5. no texture stage is `DOT_ZW`;
6. ZCLAMP is CULL (`depth_clipping`);
7. no polygon offset for the current fill mode (`polygon_offset`);
8. not `clip_max_saturates` (D24 on float storage with `CLIP_MAX > 16777215`).

### Kept cases and why

| Counter | Case | Why fixed function cannot reproduce it |
|---|---|---|
| `env` | `HAKUX_FRAGDEPTH` unset or `on` | Today's behaviour. |
| `f24` | F24 (float Z24) | The stored word is the float encoding of z, `(bits(z) >> 7)` (#16), not z scaled. Fixed function stores only z scaled. |
| `f16` | F16 | As F24: `(bits(z) - 0x3C000000) >> 11`, flushed to 0 under 2^-6. |
| `wbuf` | `z_perspective` (w-buffer) | Depth is the interpolated w, with the slope offset taken once at the triangle's first covered pixel (`wbufSlopeStep`). The rasteriser interpolates screen z. |
| `dotzw` | DOT_ZW / texm3x2depth (#279) | Depth is `dot(i-1) / dot(i)` from the texture stages, per pixel. |
| `clamp` | ZCLAMP CLAMP | Depth is clamped to CLIP_MIN/CLIP_MAX, which are uniforms. Depth clamp reaches only the viewport's `[0, 1]`. |
| `poff` | polygon offset enabled for the fill mode | See "Polygon offset" below. |
| `zsat` | D24 on float storage, `CLIP_MAX > 16777215` | The write saturates at `0xFFFFFF` (#266). Fixed function stores up to `CLIP_MAX / 2^24`, which sits above the `0xFFFFFF` clear and fails LEQUAL against it. On D24 unorm storage `clipRange.y = 0xFFFFFF` and depth clamp saturates at the same word, so it is not kept there. |
| (no draw) | Z24S8 on `D16_UNORM` (the last-resort fallback) | `z / 0xFFFFFF` keeps 16 of the 24 bits: not within one unit. The arm switches itself off for the whole run and logs `fragdepth: HAKUX_FRAGDEPTH=off has no effect`. Same without `depthClamp`, where the host would clip at `[0, 1]` instead of saturating. |

The polygon-offset test uses the fill-mode enable without the primitive type, so a line or point draw with the
fill enable set keeps its write. That is conservative: it keeps today's shader.

### Accepted difference per storage

NV2A stores `floor(z + o)` clamped to the format's maximum word. The write reproduces that from the shader's
rebuilt `z_s` (`psh.c:4296-4310`). Fixed function stores the rasteriser's `z_v`, converted by the host. For a
unorm image Vulkan's float-to-unorm conversion returns one of the two representable values nearest the input, so
fixed function rounds where NV2A floors. `z_v` and `z_s` are two fp32 reconstructions of the same plane, so they
can straddle an integer.

| Storage | `HAKUX_ZETA_D24` | Fixed function stores | Against the write |
|---|---|---|---|
| Z16 on `D16_UNORM` | either | nearest integer to `z_v`, either neighbour | `{0, +1}`; `-1` only where `z_v` falls just below an integer `z_s`. fp32 carries 8 bits under the 16-bit unit, so `|z_v - z_s|` is far below one unit. Within one LSB. |
| Z24S8 on `D32_SFLOAT_S8` | `0` (default) | `fp32(z_v / 2^24)` | Below `2^23` (normalised `< 0.5`) the float keeps a fraction and the guest-side read-back truncates it: `floor(z_v)`, so `0`, `+/-1` at a straddle. In `[2^23, 2^24)` one float ULP is one unit, so the stored word is `z_v` rounded: `{0, +1}`. Within one LSB, except as in the top-binade note below. |
| Z24S8 on `D24_UNORM_S8` | `1` | nearest unit to `fp32(z_v / 0xFFFFFF) * 0xFFFFFF` | The write floors and adds one float ULP so the conversion lands on the floor (`psh.c:4307-4310`). Fixed function has no nudge: `{0, +1}` nominal. |

**Top binade.** For Z24 on either storage, in `[2^23, 2^24)` one fp32 ULP of the normalised depth is one unit.
The `z_v` interpolation and the normalising divide each carry about half a unit there, on top of the round
against floor. Rare pixels can land at `-1` or `+2`. The write itself is `floor(z_s)` from an fp32 `z_s` with the
same ULP, so the reference is already that coarse there. This is not provably within one LSB. The `_ZB` legs
below decide it; a `_ZB` leg outside one unit means arm B does not ship for that storage.

**The depth test sees the fraction on float storage.** Below `2^23` an FF word keeps a sub-unit fraction. Two
surfaces within one unit of each other compare by that fraction where NV2A, comparing floored words, sees a tie.

### Polygon offset: NV2A units against Vulkan `depthBias`

- **NV2A.** `o = ZOFFSETBIAS + ZOFFSETFACTOR * m`, where `m` is the triangle's maximum depth slope in depth-word
  units per pixel (`triMZ`). Both terms are in units of the format's word (2^-24 of the range for Z24, 2^-16
  for Z16), and they are added before the floor (`psh.c:3263`, `:3364`; uniforms at `psh.c:4665-4690`). Under the
  w-buffer the slope term is taken once per primitive (`wbufSlopeStep`).
- **Vulkan.** `o = m' * depthBiasSlopeFactor + r * depthBiasConstantFactor`, with `m'` in normalised depth per
  pixel (`m / clipRange.y`) and `m'` itself an implementation-defined approximation, clamped by
  `depthBiasClamp`.
  - On a float image `r = 2^(e - 23)`, with `e` the maximum exponent of the primitive's normalised depth. In
    24-bit units that is `2^(e + 1)`: one unit only for a primitive reaching the top binade, half a unit one
    binade down, and so on. Mapping NV2A's absolute bias needs `depthBiasConstantFactor = ZOFFSETBIAS * 2^-(e+1)`
    per primitive, which no per-draw state expresses.
  - On a unorm image `r` is implementation-defined, at most `2 * 2^-n`. `VK_EXT_depth_bias_control`
    (`depthBiasExact`) would pin it; Turnip does not expose it.
  - The bias is added after interpolation and converted by rounding, not floored.
- **Pipeline.** `depthBiasEnable` is baked `VK_FALSE` and no `vkCmdSetDepthBias` is issued (`vk/draw.c:3468-3478`).

So polygon-offset draws keep the write. The cost is limited to decal and shadow passes; the enable bits reach the
shader state under the arm (below).

### The change

| File:line | What |
|---|---|
| `glsl/psh.h:134-135` | `PshState.polygon_offset`, `PshState.clip_max_saturates`: set only under the arm. |
| `glsl/psh.h:155-176` | `pgraph_glsl_psh_fragdepth_off()`, `enum PshDepthWrite` (`NONE`, `WRITE_FF`, then the `KEPT_*` reasons), `pgraph_glsl_psh_depth_write()`. |
| `glsl/psh.h:320` | `GenPshGlslOptions.frag_depth_ff`: the decision, in the module key. |
| `glsl/psh.c:42-65` | Reads `HAKUX_FRAGDEPTH` once (static), prints the init line to stderr and, on Android, to `hakuX-perf`. |
| `glsl/psh.c:67-79` | `pgraph_glsl_polygon_offset_raster()`: the fill-mode test, shared with the uniform code (`:4665-4666`, same result). |
| `glsl/psh.c:81-150` | The decision and its reasons. |
| `glsl/psh.c:741-754` | `set_psh_state` fills the two fields under the arm. |
| `glsl/psh.c:4248-4255` | The write is emitted unless the key says FF and the key's state agrees. The depth computation above it stays, because the CULL discard reads it. |
| `glsl/shaders.c:111-116` | Under the arm a dirty `NV_PGRAPH_ZCLIPMAX` marks the shader state dirty. |
| `pgraph.c:68-77` | Under the arm the three `POFFSET*ENABLE` bits leave the `SETUPRASTER` dynamic mask, so toggling one moves `shader_state_gen`. `init_pipeline_key` already strips them, so no extra pipelines. |
| `pgraph.c:135-140` | Under the arm `NV_PGRAPH_ZCLIPMAX` gets `REG_CAT_SHADER`. This is the first call to read the env (`pgraph.c:1406`, before the dynamic masks at `instance.c:1424`), so the init line prints here. |
| `vk/shaders.c:1231-1266`, `vk/renderer.h:2044` | `pgraph_vk_psh_frag_depth_ff()`: the arm, gated on `depthClamp` and the Z24S8 host format. Logs once if it has no effect. |
| `vk/shaders.c:1312-1325` | Module key: `frag_depth_ff = (decision == FF)`; `polygon_offset` and `clip_max_saturates` cleared. |
| `vk/draw.c:47-54`, `:1101-1122`, `:1210`, `:7949-7957` | Counters (`NV2A_PERF_LOG` only). |

Init lines (stderr; logcat tag `hakuX-perf`):

```
fragdepth: HAKUX_FRAGDEPTH=off: gl_FragDepth omitted where fixed-function depth stands in (P10 arm B)
fragdepth: HAKUX_FRAGDEPTH=unset: gl_FragDepth written on every depth draw
fragdepth: HAKUX_FRAGDEPTH=off has no effect: depthClamp <0|1>, Z24S8 host format 0x<fmt>
```

Counter line, every 60 frames on `hakuX-stall`, in the `NV2A_PERF_LOG` per-window block beside the `ubosz` and
texture-bind lines:

```
psh_depth[psh_depth_ff=N psh_depth_kept=N nowrite=N env=N f24=N f16=N wbuf=N dotzw=N clamp=N poff=N zsat=N]
```

It is counted in `begin_draw` over draws with `ZENABLE` set. `psh_depth_kept` is the sum of `env` through `zsat`.
`nowrite` is a depth-tested draw whose state has no `depth_needed`. Unset, every such draw counts as `env` and
`psh_depth_ff` is 0. Coverage = `psh_depth_ff / (psh_depth_ff + psh_depth_kept + nowrite)`.

### Cache key and `SHADER_STATE_LAYOUT_VERSION`

- **Placement.** The three new bools sit in existing padding. A size probe of the built structs gives
  `sizeof(ShaderState)`, `sizeof(PshState)` and `sizeof(VshState)` unchanged; the new fields sit at offsets 433
  and 434 of `PshState` and 3 of `GenPshGlslOptions`.
- **Zero is today.** Both the state and the module key are `memset` to 0 before they are filled
  (`glsl/shaders.c:79`; `vk/shaders.c`, `memset(psh_key, ...)`), so a key persisted by the base build carries 0
  in all three bytes. 0 is the base behaviour: no field is read as anything but "write as before".
- **No bump.** `SHADER_STATE_LAYOUT_VERSION` stays 5 (`vk/renderer.c:60-74`), because no persisted key changes
  meaning:
  - Unset or `on`: every key this build computes is byte-identical to the base build's key for the same state, so
    `shader_module_keys.bin` and the pipeline keys stay valid and no warm-up is lost.
  - `off`: the module key carries only the decision. A kept draw has today's module key and module, in the
    persisted file too, because `polygon_offset` and `clip_max_saturates` are cleared from it. Only FF draws add
    keys, each with `frag_depth_ff = 1`.
  - Replay across a switch: a persisted `frag_depth_ff = 1` key replayed while unset compiles a module no draw
    binds. That costs a compile, never a wrong image: the shader drops the write only when the key's own state
    also gives FF (`psh.c:4251-4253`), so no key can drop the write for F24, F16, w-buffer, DOT_ZW or CLAMP.
  - Downgrade: an older build reads the byte as padding and compiles the writing shader.
- **The precedent.** Version 4 was bumped because a padding field's 0 meant the wrong shader on some devices.
  Here 0 means the shader the persisted key was made for. No enum value enters a key: `PshDepthWrite` is a return
  type and a counter index only.
- **Bindings under the arm.** The binding (`ShaderState`) carries both fields, so a poff toggle or a CLIP_MAX
  change rebinds to the right module through the existing hash. The pipeline key is unchanged.

### Device A/B pair 1: arm B FAILS (lane.local, 2026-10-23 02:40 PDT)

Nova, ref 31770d97e5, both arms on `hdd.img` (`hdd_disc.json` action `set`, restored), `GPU: PurpleVK`, 941
captures each. B = `1-1792747304-p10fragdepth1022-28875` (`HAKUX_FRAGDEPTH=off`, its `omitted where
fixed-function depth stands in` line present). A = `...-28949` (`=on`, `written on every depth draw`). The
registered prediction is `predictions/p10fragdepth1022-pixels.json`. 880 of 941 captures are byte-identical
between the arms, so the differences below are the arm, not noise.

| Leg | Result |
|---|---|
| 1 Void | Neither arm is void |
| 2 must_not_move | **Fails:** 684 captures, 1 moved. `Depth_function/DepthFunc_ZB` went 0 -> 9216 px (max 8, none off by one) |
| 3 No new blank | **Fails:** `Depth_buffer_fixed_function/z16_Cn_FZn_M00ffff` and `z16_Cy_FZn_M00ffff` are ok in A, white-content in B |
| 4 Colour | **Fails:** B is worse in 55 captures, better in 1 (`Stencil`, -30000) |
| 5 `_ZB` | Not decided from scores. z16 `DepthFmt_*_FZn_M00ffff_ZB` 0 -> 76744 px, every one off by one but max 255 (a carry across the decoded byte?). z24 `Mffffff_ZB` 6770 -> 51302 |

The largest B-worse rows by suite are `Color_zeta_overlap/Swap` 0 -> 165447 (max 4), 32 `Depth_buffer` (up to
76744), 8 `Depth_buffer_fixed_function` (z16 FZn), 4 `Depth_Clamp/depth_equal_Ofs*` (0 -> 54084-76510, max 255,
none off by one: an EQUAL compare after polygon offset no longer matches), and 9 `ZPass_pixel_count` (up to 8192).

So pair 2 and the Blinx 2 pair do not run. Any retry has to explain the depth_equal_Ofs rows (the polygon offset
mapping, "Polygon offset: NV2A units against Vulkan `depthBias`") and Color_zeta_overlap/Swap, which the kept-case
list does not cover. The comparison script is `p10_pair.py` in the lane.local scratchpad of session 8d26cd5d.

### Device A/B: the plan as registered

The suites are the 10 depth suites of fpsbelow1012 section 14, as registered in
`docs/testing/predictions/fpsbelow1012-zetad24-pixels.json` (`disc.suites`).

`--suites` list:

```
--suites "Clear,Color zeta overlap,Depth Clamp,Depth buffer,Depth buffer fixed function,Depth function,Stencil,Stencil func,W buffering,ZPass pixel count"
```

Pair 1, default storage (D32S8 float), same ref on both arms:

- A: no `--env`.
- B: `--env HAKUX_FRAGDEPTH=off`.

Pair 2, D24 unorm storage, only if P1's `HAKUX_ZETA_D24=1` is to ship with arm B:

- A: `--env HAKUX_ZETA_D24=1`.
- B: `--env HAKUX_ZETA_D24=1 --env HAKUX_FRAGDEPTH=off`.

Legs (any failed leg means arm B does not ship):

1. **Void.** A B arm is void without the logcat line `fragdepth: HAKUX_FRAGDEPTH=off: gl_FragDepth omitted where
   fixed-function depth stands in (P10 arm B)`, or with `has no effect`. An A arm is void without
   `fragdepth: HAKUX_FRAGDEPTH=unset`.
2. **must_not_move.** Captures whose depth draws are all kept must be byte-identical between the arms:
   - `Depth_buffer/DepthFmt_*_FZy_*` (F24/F16);
   - `Depth_buffer_fixed_function/*_FZy_*`;
   - `Depth_Clamp/depth_clamp_W1_*` and `Depth_Clamp/depth_equal_WBuf_*` (w-buffer);
   - `W_buffering/*` (every test sets CLAMP);
   - on pair 1 only, the z24 captures of `Depth_buffer_fixed_function` and `Depth_function`, which set
     `CLIP_MAX = 16777216` (`zsat`).
3. **No new blank.** No capture is blank in B that is not blank in A.
4. **Colour.** No capture's golden score in B is worse than in A.
5. **`_ZB` (decoded depth).** Where fixed function stands in, every decoded depth word is within one unit of A:
   - `Depth_buffer` z16 and z24 `FZn` (`MaxDepthBufferValue` gives `CLIP_MAX = 0xFFFF` or `0xFFFFFF`, so FF, not
     `zsat`);
   - `Depth_Clamp/depth_clamp_W0_C0_ZB0_*`.

Blinx 2 pair (`4D530065-Blinx_2_Battle_of_Time_Space_Blinx_2_Masters_of_Time_Space.xiso.iso`, Nova, the route and
length P1 used), one arm unset and one with `--env HAKUX_FRAGDEPTH=off`. Read GPU R/flip per window and the
`psh_depth[...]` line. The prediction holds if R/flip falls with coverage high. The falsifier is in the header.

### Checks (no device)

| Check | Result |
|---|---|
| `python3 -I .../cc_wt.py <wt> <file> -DNV2A_PERF_LOG=1`, then `=0`, on `glsl/psh.c`, `glsl/shaders.c`, `pgraph.c`, `vk/shaders.c`, `vk/draw.c` | All 10 exit 0, 0 errors. Warnings, the same for both values: 0, 0, 2, 2, 16. All are outside the change (`pgraph.c:270`, `profile.h:190`, `vk/shaders.c:1509,1792`, `vk/draw.c:1465-1559, 5960, 8034`). |
| Same with `-D__ANDROID__` and an `android/log.h` stub, on `glsl/psh.c`, `vk/shaders.c`, `vk/draw.c` | Exit 0, 0 errors. This covers the logcat calls and the `#ifdef __ANDROID__` counter line. |
| Struct sizes and offsets | `ShaderState`, `PshState` and `VshState` sizes unchanged against base. New field offsets: 433, 434 (`PshState`), 3 (`GenPshGlslOptions`). |
| `SELFTEST_ONLY="65-status-objective 75-nv2a-index-drift 86-nightly-notes 99-dipwin-counters" timeout 900 bash docs/testing/jobs/selftest.sh` | See below. |
| `nv2a_index.py check` | Stale, with 23 changes in this tree. Base b944110629 is already stale, with 9. Not regenerated here, because a regeneration needs a dated tests tree. |

Selftest output (with this PR.md in place): `selftest: 148 passed, 0 failed, PARTIAL: 4 of 160 fragments`, exit 0.

## Arm A (no code): a conservative depth qualifier keeps LRZ only where it does not hold

Arm A would declare `layout(depth_less)` or `layout(depth_greater)` on `gl_FragDepth` wherever the written depth
is provably on one side of `gl_FragCoord.z`, so that the Adreno driver keeps LRZ and early-Z for depth-writing
fragment shaders. The written value would not change.

The result is negative. On Turnip, a depth-writing shader keeps LRZ only with `depth_greater` under LESS/LEQUAL,
or with `depth_less` under GREATER/GEQUAL. The four titles (GTA III, GTA SA, Blinx 2, Fable) test with LESS/LEQUAL
as far as the tree records (the D3D8 default, and the GTA SA captures), on a non-reversed depth range.

Their written depth is `floor(interpolated + polygon offset)`. With a zero or negative offset that is at or below
the interpolated value. Only a positive offset of a unit or more puts it above, and the offset is a runtime
uniform. So `depth_greater` does not hold. `depth_less` holds roughly in some states, but under LESS/LEQUAL it
leaves the draw on `LATE_Z` with LRZ off, exactly as no qualifier does. No qualifier both holds and helps, so arm
A adds no code.

### Already tried

Commands:

- `git log --all --no-merges --oneline -i -E --grep "<term>"`, one term per row.
- `git log --oneline --no-merges -i -E --grep "depth|zfloor|FragDepth|D24|zeta" -- hw/xbox/nv2a/pgraph/glsl/psh.c`
- `grep -rn -i -E "depth_less|depth_greater|DepthGreater|DepthLess|conservative depth|LRZ" docs --include=*.md`

The form `git log --grep -i -E "..."` returns nothing. `--grep` takes `-i` as its pattern, so options must come
before `--grep`.

| Source | Query | Hits | What they did |
|---|---|---|---|
| git log | `FragDepth` | 5: a33fa42bc3, 23a8962df2 (2026-09-10, depth scale and float encoding), 9308e9eab5 (2026-09-10, renderer naming; forcing `gl_FragDepth = 0.25` changed none of 144 captures), 39c75c291f (2026-03-12, codegen tidy), 798ad30819 (2025-02-28, w-buffer depth) | The written value only. None declares a layout. |
| git log | `depth_less\|depth_greater\|depth_unchanged\|DepthLess\|DepthGreater\|DepthReplacing` | 0 | -- |
| git log | `conservative depth` | 0 | -- |
| git log | `LRZ` | 0 | -- |
| git log | `early-?z\|early_fragment\|EarlyFragment` | 0 (no-merges) | -- |
| git log | `HAKUX_FRAGDEPTH\|psh_depth_qual` | 0 | -- |
| psh.c log | depth terms | 25, including 24546d197b (DOT_ZW #279), c2336637cf (D24 saturate #266), 7f29351a7a (exact floor), 5ae08d2097 (F16 flush), 23a8962df2 / a33fa42bc3 (encoding, scale) | Exactness of the written value. No qualifier. |
| docs | `investigations/adreno-driver-feasibility.md:66` row (c) | 1 | Names the hypothesis ("A T0 `DepthGreater`/`DepthLess` layout where our depth is monotone might restore LRZ"). Not tried. |
| docs | `lanes/uberspike569/NOTES.md:81`, `lanes/energymap507/NOTES.md:273` | 2 | Both record that writing `gl_FragDepth` disables early depth. Not tried. |
| docs | `lanes/haloship1017/NOTES.md:135` | 1 | LRZ as a sample-count hypothesis (Halo occlusion). Unrelated. |

Nothing had been tried; neither arm A nor arm B.

### The driver: what Turnip does with each qualifier

Reference tree: mesa main 4c18636110f (`VERSION` 26.3.0-devel, 2026-09-25).

The relevant Turnip code:

- **`src/freedreno/vulkan/tu_lrz.cc:1188-1189`.** `force_late_z = writes_pos && !early_fragment_tests` is set
  before any early return. With LRZ invalid or depth test off, a depth-writing shader is still late-Z.
- **`tu_lrz.cc:1235-1263`.** This is the decision. `disable_lrz_due_to_fs` is true for layout `NONE` or `ANY`.
  For `GREATER` it is true unless the compare op is `LESS` or `LESS_OR_EQUAL`. For `LESS` it is true unless the
  compare op is `GREATER` or `GREATER_OR_EQUAL`. `UNCHANGED` is "always OK". Then
  `cmd->state.lrz.force_late_z = disable_lrz_due_to_fs;`.
- **`tu_lrz.cc:1271-1278`.** With the disable set, no known direction yet, and GPU direction tracking (a7xx),
  `tu_lrz_invalidate()` is called. LRZ is lost for the rest of the render pass, not just for the draw.
- **`tu_lrz.cc:1212-1215`.** LRZ write is not turned off for `writes_pos`, only for kill or sample mask
  (`TU_LRZ_FORCE_DISABLE_WRITE`, `tu_shader.cc:3739-3740`). `no_earlyz` comes only from `writes_memory`
  (`ir3_compiler_nir.c:6275-6277`). `depth_layout` is copied from NIR (`:6283-6285`).
- **`tu_cmd_buffer.cc:8279-8282`.** With LRZ enabled and `writes_pos`, the z mode goes from `EARLY_Z` to
  `EARLY_Z_LATE_Z`, which is the only early-Z a depth-writing shader can get.
- **`tu_cmd_buffer.cc:8314-8317`.** `force_late_z` forces `A6XX_LATE_Z`.

So under LESS/LEQUAL:

| Qualifier | LRZ | z mode |
|---|---|---|
| none (today) | invalidated for the render pass (`tu_lrz.cc:1276`) | `LATE_Z` |
| `depth_less` | same as none | `LATE_Z` |
| `depth_greater` | kept | `EARLY_Z_LATE_Z` |
| `depth_unchanged` | kept | `EARLY_Z_LATE_Z`, but the value must equal `gl_FragCoord.z` |

The `tu_ignore_frag_depth_direction` drirc (`00-turnip-defaults.conf:77,88`) matches only "Sons Of The Forest" and
"Creed: Rise to Glory" by application name. It does not apply to hakuX.

**Version.** The fleet driver is `PurpleVK 26.3.0-devel (git-62ac221a33)`, Driver Version 26.2.99, on Adreno (TM)
740 (a7xx). It is printed by `xemu-vulkan: GPU:` in
`captures/fpsnext1019/runs/fable-h2/logcat.txt:11604,11610`. The fork sha 62ac221a33 is not in the local upstream
clone, so the fork's own `tu_lrz.cc` is not readable here.

The qualifier logic came upstream in 847ad80e03e ("tu/lrz: Consider FS depth layout when gl_FragDepth is
written", 2025-03-24). The drirc escape came in f03be478a9c (2025-05-05). Both are first in `mesa-25.2.0`
(`git tag --contains`). A 26.3.0-devel build is about a year newer than that, so the fleet driver carries this
block unless the fork removed it. Nothing in hakuX's notes says it did.

### The compare ops

- NV2A `ZFUNC` maps 1:1 to `VkCompareOp` (`vk/constants.h:112`). It is set in the pipeline
  (`vk/draw.c:3509-3514`) and as dynamic state (`:7798-7801`).
- The viewport is `minDepth 0, maxDepth 1`, so the depth range is not reversed and an NV2A LESS is a host LESS.
- The D3D8 default is `LESSEQUAL`. The GTA SA captures record it (`lanes/gtasagpu1011/NOTES.md:424`).
- The draw-reorder path accepts only LESS/LEQUAL.
- No per-title `ZFUNC` histogram exists in the tree. A GREATER/GEQUAL draw, if any, is a corner case and would not
  move a per-flip GPU figure.

So the qualifier that would have to hold is `depth_greater` (written >= interpolated).

### Direction: written depth vs `gl_FragCoord.z`, per encoding and state

Definitions:

- `z_v`: the rasteriser's interpolation of `gl_Position.z / gl_Position.w`, so `gl_FragCoord.z = z_v / clipRange.y`.
- `z_s`: the depth the fragment shader rebuilds from the barycentrics. On the fixed-function path its `vtxPos.z`
  is `ffScreenZ(tPosition)` (`vsh-ff.c:1330`), while `gl_Position.z` keeps the matrix product. So `z_s` and `z_v`
  can differ by float rounding in either direction.
- `o`: the polygon offset, `depthOffset + depthFactor*triMZ`. It is a uniform from `NV_PGRAPH_ZOFFSETBIAS` /
  `ZOFFSETFACTOR`, so its sign can change per draw without a recompile. D3D decal bias is usually negative,
  toward the viewer.
- `clipRange.y` is `0x1000000` for float storage and `0xFFFFFF` for D24 unorm storage.

| Encoding | State | Written | Interpolated | Relation |
|---|---|---|---|---|
| D24 | D32S8 float storage (default) | `min(floor(z_s+o), 2^24-1) / 2^24` | `z_v / 2^24` | With `o = 0`: written <= interpolated by up to 1 unit, except near integer `z_s` where `z_s > z_v` can put it above. `o < 0`: lower still. `o >= 1`: above. Neither direction is provable. |
| D24 | D24 unorm storage (P1, `HAKUX_ZETA_D24`) | `nextafter(min(floor(z_s+o), 2^24-1) / 2^24)` | `z_v / (2^24-1)` | The sign depends on `frac(z_s)` and on `z`. Neither direction. |
| D24/D16 | clamp to CLIP_MIN/MAX (`depth_clipping` off) | clamped | unclamped | Raised below CLIP_MIN, lowered above CLIP_MAX. Neither direction. |
| D16 | -- | `floor(z_s+o) / 65535` | `z_v / 65535` | As D24 float: <= up to errors and offset. Not >=. |
| F24 | -- | `(bits(z) >> 7) / 2^24` | `z_v / 1e30` | Far above at small z. Below at the top (`bits(1e30)>>7 = 0xE293E5`, about 0.885, against 1.0). Neither direction. |
| F16 | -- | `((bits(z) - 0x3C000000) >> 11) / 65535`, 0 below 2^-6 | `z_v / 511.9375` | Above in the middle. 0 (below) under 2^-6. Equal at the top (`0xFFFF`), and below just under it, where the `>> 11` truncation drops a code faster than `z_v` falls. Neither direction. |
| any | `z_perspective` (w-buffer) | built from `w`, plus the slope offset | z-based | Unrelated quantities. Neither direction. |
| any | DOT_ZW / texm3x2depth (#279) | `dot(i-1)/dot(i)`, floored | z-based | Unrelated. Neither direction. |

`depth_greater` holds in no row. `depth_less` comes closest only for D24/D16 on float storage with `o <= 0`. Even
there it is not exact: near integer depths the `ffScreenZ` vs matrix rounding can put the written value above.
It would also need the offset sign, which is a uniform, in the shader key. Under LESS/LEQUAL it buys nothing
anyway (table above). `depth_unchanged` would need written == interpolated, which `floor()` breaks wherever
`frac(z) != 0`.

### A different mechanism (for a separate item)

`depth_greater` could be made true by moving the interpolated value instead of the written one. Bias
`gl_Position.z` toward the near plane by more than one depth unit, plus the largest negative polygon offset, plus
the `ffScreenZ` / rasteriser error. The fragment shader never reads `gl_FragCoord.z`: it reads only `.xy` and
rebuilds depth from `vtxPos`. The written value is unchanged.

This is neither arm. It changes both vertex shader paths and the value that LRZ is built from. Open issues:

- **LRZ write.** LRZ write stays on for `writes_pos` (`tu_lrz.cc:1212-1215`). LRZ would hold the biased, nearer
  depth, and could then reject a later fragment whose real depth passes. Whether LRZ's Z16 conservative rounding
  absorbs a bias of a few 2^-24 units is not bounded anywhere: `lrz.rst:116-124` says only that comparisons have
  "some slack".
- **Per-draw bias.** The bias must track the per-draw polygon offset.
- **Clipping and clamping.** It moves near-plane clipping and the depth-clamp boundary.
- **Coverage.** It does not cover F24, F16, w-buffer or DOT_ZW shaders.

## Risks not closed

- **Top binade.** Z24 depth in `[2^23, 2^24)` can land at `-1` or `+2` against the write on either storage. Only
  the `_ZB` legs bound it.
- **A kept pass followed by a coplanar FF pass.** The write stores `floor(z)` exactly. A later FF pass over the
  same geometry stores `z_v`, with a fraction on float storage or rounded up on unorm. Under LEQUAL or EQUAL the
  FF pass can then fail where NV2A, comparing equal floored words, passes. This needs consecutive passes whose
  decisions differ: polygon offset enabled with zero bias on one pass only, DOT_ZW on one pass only, or CLIP_MAX
  changing between passes. The depth suites draw single passes, so a title shows it first, as z-fighting or a
  missing second pass.
- **`gl_Position` invariance.** No vertex shader declares `invariant gl_Position`. Two passes over the same
  geometry with different vertex programs (FF base, programmable detail) can differ in `z_v` by an ULP. The write's
  floor absorbs that except at an integer straddle; FF depth on float storage does not, so an EQUAL or LEQUAL
  second pass can fail. A remedy is `invariant gl_Position` on both vertex paths under the arm.
- **CULL edge.** The discard tests the shader's `z_s` against CLIP_MIN/CLIP_MAX, while the stored value is `z_v`.
  A pixel kept at `z_s <= CLIP_MAX` can store a `z_v` a fraction above it. At `CLIP_MAX = 0xFFFFFF` on float
  storage that word sits a fraction above the `0xFFFFFF` clear.
- **Wedge geometry.** The geometry-shader wedge (`glsl/geom.c:137-390, 477-490`) emits corner depth that the
  rasteriser interpolates under FF, and the key cannot single it out. `W_param` (#223) exercises it and is not in
  the gate.
- **LRZ write stays off.** The CULL discard makes every FF draw a kill shader, so LRZ is tested and kept valid
  but not written by these draws. The gain is early-Z and an LRZ buffer that survives the pass, not LRZ
  rejection fed by these draws.
- **CPU cost under the arm.** POFFSET toggles and CLIP_MAX writes now move `shader_state_gen` and run the
  shader-state check. Unset, nothing changes.
- **Precompile churn.** Switching the env between runs leaves the other arm's FF module keys in the persisted
  set, compiled at warm-up and not bound.
- **Uber family path.** The uber family path (`HAKUX_PSH_UBER`, default off) was not exercised with the flag.
- **Stale `depth_needed`.** Under extended dynamic state 1, a `ZENABLE` toggle does not reach `depth_needed`.
  This predates the change; the decision inherits it.
- **Fork contents.** The fork's `tu_lrz.cc` at 62ac221a33 was not read. The early-Z and LRZ behaviour above
  assumes that it matches upstream 25.2+ for this block.
- **Per-title compare ops.** No per-title `ZFUNC` histogram exists.
