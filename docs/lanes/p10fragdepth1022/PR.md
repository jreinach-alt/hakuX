# p10fragdepth1022: no conservative depth qualifier keeps LRZ under LESS/LEQUAL, so P10 arm A has no code (#433)

State: draft

Lane: p10fragdepth1022            Issue: #433 (0.5)
Base: master @ b944110629
Files: docs/lanes/p10fragdepth1022/PR.md
Prediction: none: no code change
Needs device: no
Needs NDK: no

P10 arm A (fps30 plan) would declare `layout(depth_less)` or `layout(depth_greater)` on `gl_FragDepth` wherever
the written depth is provably on one side of `gl_FragCoord.z`. The aim is to let the Adreno driver keep LRZ and
early-Z for depth-writing fragment shaders. The written value would not change. Every depth-tested NV2A draw takes
this path, because `depth_needed = depth_test || depth_write || depth_clipping` (`glsl/psh.c:409`).

The result is negative. On Turnip, a depth-writing shader keeps LRZ only with `depth_greater` under LESS/LEQUAL, or
with `depth_less` under GREATER/GEQUAL. The four titles (GTA III, GTA SA, Blinx 2, Fable) test with LESS/LEQUAL
as far as the tree records (the D3D8 default, and the GTA SA captures), on a non-reversed depth range.

Their written depth is `floor(interpolated + polygon offset)`. With a zero or negative offset that is at or below
the interpolated value. Only a positive offset of a unit or more puts it above, and the offset is a runtime
uniform. So `depth_greater` does not hold. `depth_less` holds roughly in some states, but under LESS/LEQUAL it
leaves the draw on `LATE_Z` with LRZ off, exactly as no qualifier does. No qualifier both holds and helps, so this
branch carries no source change.

## Already tried

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

Nothing has been tried. The question was open.

## The driver: what Turnip does with each qualifier

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

## The compare ops

- NV2A `ZFUNC` maps 1:1 to `VkCompareOp` (`vk/constants.h:112`). It is set in the pipeline
  (`vk/draw.c:3481-3484`) and as dynamic state (`:7767-7771`).
- The viewport is `minDepth 0, maxDepth 1` (`vk/draw.c:7678-7679, 8813`), so the depth range is not reversed and
  an NV2A LESS is a host LESS.
- The D3D8 default is `LESSEQUAL`. The GTA SA captures record it (`lanes/gtasagpu1011/NOTES.md:424`).
- The draw-reorder path accepts only LESS/LEQUAL (`vk/draw.c:8044-8046`).
- No per-title `ZFUNC` histogram exists in the tree. A GREATER/GEQUAL draw, if any, is a corner case and would not
  move a per-flip GPU figure.

So the qualifier that would have to hold is `depth_greater` (written >= interpolated).

## Direction: written depth vs `gl_FragCoord.z`, per encoding and state

Definitions:

- `z_v`: the rasteriser's interpolation of `gl_Position.z / gl_Position.w`, so `gl_FragCoord.z = z_v / clipRange.y`.
- `z_s`: the depth the fragment shader rebuilds from the barycentrics (`psh.c:2995-3238`). On the fixed-function
  path its `vtxPos.z` is `ffScreenZ(tPosition)` (`vsh-ff.c:1330`), while `gl_Position.z` keeps the matrix product.
  So `z_s` and `z_v` can differ by float rounding in either direction.
- `o`: the polygon offset, `depthOffset + depthFactor*triMZ` (`psh.c:3134-3135`). It is a uniform from
  `NV_PGRAPH_ZOFFSETBIAS` / `ZOFFSETFACTOR` (`psh.c:4546-4568`), so its sign can change per draw without a
  recompile. D3D decal bias is usually negative, toward the viewer.
- `clipRange.y` is `0x1000000` for float storage and `0xFFFFFF` for D24 unorm storage (`glsl/common.c:153-154`).

| Encoding | State | Written (`psh.c`) | Interpolated | Relation |
|---|---|---|---|---|
| D24 | D32S8 float storage (today, all four titles) | `min(floor(z_s+o), 2^24-1) / 2^24` (`:4174`) | `z_v / 2^24` | With `o = 0`: written <= interpolated by up to 1 unit, except near integer `z_s` where `z_s > z_v` can put it above. `o < 0`: lower still. `o >= 1`: above. Never provably >= (so not `depth_greater`). Not provably <= either. |
| D24 | D24 unorm storage (P1, `HAKUX_ZETA_D24`) | `nextafter(min(floor(z_s+o), 2^24-1) / 2^24)` (`:4156-4158`) | `z_v / (2^24-1)` | The sign depends on `frac(z_s)` and on `z`. Neither direction. |
| D24/D16 | clamp to CLIP_MIN/MAX (`depth_clipping` off, `:3248-3249`) | clamped | unclamped | Raised below CLIP_MIN, lowered above CLIP_MAX. Neither direction. |
| D16 | -- | `floor(z_s+o) / 65535` (`:4164`) | `z_v / 65535` | As D24 float: <= up to errors and offset. Not >=. |
| F24 | -- | `(bits(z) >> 7) / 2^24` (`:4182-4185`) | `z_v / 1e30` (`util.h:26`) | Far above at small z. Below at the top (`bits(1e30)>>7 = 0xE293E5`, about 0.885, against 1.0). Neither direction. |
| F16 | -- | `((bits(z) - 0x3C000000) >> 11) / 65535`, 0 below 2^-6 (`:4214-4217`) | `z_v / 511.9375` | Above in the middle. 0 (below) under 2^-6. Equal at the top (`0xFFFF`), and below just under it, where the `>> 11` truncation drops a code faster than `z_v` falls. Neither direction. |
| any | `z_perspective` (w-buffer, `:2948-2993`) | built from `w`, plus the slope offset | z-based | Unrelated quantities. Neither direction. |
| any | DOT_ZW / texm3x2depth (#279, `:3576`) | `dot(i-1)/dot(i)`, floored | z-based | Unrelated. Neither direction. |

`depth_greater` holds in no row. `depth_less` comes closest only for D24/D16 on float storage with `o <= 0`. Even
there it is not exact: near integer depths the `ffScreenZ` vs matrix rounding can put the written value above.
It would also need the offset sign, which is a uniform, in the shader key. Under LESS/LEQUAL it buys nothing
anyway (table above). `depth_unchanged` would need written == interpolated, which `floor()` breaks wherever
`frac(z) != 0`.

## Change

None. No source file is touched. `HAKUX_FRAGDEPTH` and `psh_depth_qual` are not added, because a switch whose
only arm is identical to today in both text and driver behaviour would measure nothing.

## Cache key

Not applicable, because nothing is emitted differently. For reference, a future qualifier keyed on `depth_format`,
`z_perspective` and `depth_clipping` would read fields already in `PshState`. A qualifier keyed on the polygon
offset sign would need a new key field, because that sign is a uniform today.

## Checks

| Check | Result |
|---|---|
| `cc_wt.py ... -DNV2A_PERF_LOG=1` / `=0` | Not run: no C file changed. |
| Desktop glslang shader-gen test | None exists. `grep -rl -i glslang docs/testing tests` finds only prose in `docs/testing/nv2a_issues.toml` and two prediction JSON files. |
| Selftest fragments matching `psh\.c\|FragDepth\|shader_state\|SHADER_STATE_LAYOUT` | `75-nv2a-index-drift.sh`, `86-nightly-notes.sh`. `SELFTEST_ONLY="75-nv2a-index-drift 86-nightly-notes" timeout 900 bash docs/testing/jobs/selftest.sh`: `117 passed, 0 failed, PARTIAL: 2 of 160 fragments`, exit 0. Neither fragment tests depth code (index line drift and nightly notes), and no anchor moved because no source moved. |

## A different mechanism, not arm A (for a separate item)

`depth_greater` could be made true by moving the interpolated value instead of the written one. Bias
`gl_Position.z` toward the near plane by more than one depth unit, plus the largest negative polygon offset, plus
the `ffScreenZ` / rasteriser error. The fragment shader never reads `gl_FragCoord.z`: it reads only `.xy`
(`psh.c:2289, 2866, 2884, 2964, 2997`) and rebuilds depth from `vtxPos`. The written value is unchanged.

This is not arm A. It changes both vertex shader paths and the value that LRZ is built from. Open issues:

- **LRZ write.** LRZ write stays on for `writes_pos` (`tu_lrz.cc:1212-1215`). LRZ would hold the biased, nearer
  depth, and could then reject a later fragment whose real depth passes. Whether LRZ's Z16 conservative rounding
  absorbs a bias of a few 2^-24 units is not bounded anywhere: `lrz.rst:116-124` says only that comparisons have
  "some slack".
- **Per-draw bias.** The bias must track the per-draw polygon offset.
- **Clipping and clamping.** It moves near-plane clipping and the depth-clamp boundary.
- **Coverage.** It does not cover F24, F16, w-buffer or DOT_ZW shaders.
- **Gate.** It would need the 10 depth suites as a pixel gate before any device A/B.

## Risks not closed

- **Fork contents.** The fork's `tu_lrz.cc` at 62ac221a33 was not read. The conclusion assumes that it matches
  upstream 25.2+ for this block.
- **Per-title compare ops.** No per-title `ZFUNC` histogram exists. A title with many GREATER/GEQUAL depth-tested
  draws would reopen `depth_less` for D24/D16 float storage, with the integer-depth exception above still to be
  closed.
