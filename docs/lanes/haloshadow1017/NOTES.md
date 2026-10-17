# lane.haloshadow1017 -- NOTES (#1038)

Status (10-17): Step 0 done and pushed with this file. No code under hw/, android/ or ui/ has been
edited. Next: the desktop experiment, then an instrument that reads back the 128x128 texture the
projection actually samples.

**Attempt 1 did not finish: it hit the 301-turn cap** (session log
`haloshadow1017.20261017T174853Z.json`, `terminal_reason max_turns`) while L2 was running in the
foreground. Sections 6.1-6.2 and the tools `projgd.py`, `rbread.py` and deskrun.py's save-state
arguments were written but not committed; attempt 2 committed them first. L2 was killed with the
session, its dump left unmoved in `build-linux/run/dump`. The desktop-only `hw/xbox/xid.c` edit
(no bound controller for a `-device usb-xbox-gamepad` given on the command line, needed to load
the Nova's two-pad state) is kept as `tools/desk-xid-unbound.patch` and is not part of the PR.

Issue: **#1038** (tracker row origin/board nv2a_issues.toml:6478). The brief's #433 was a placeholder.

## 1. The chain (frame 4 of the 10-17 Nova dump, confirmed against the dump)

Dump: `/home/justin/hakux-work/captures/halo-shadow-1017/framedump/framedump_1792257837.jsonl`
(0.5.2-rc1, `rtt gd`, 8 frames). Read with `tools/chain.py` (per-draw guest state through
x1port1012's gdread) and `tools/texids.py` (per-stage host identity).

| Step | Draws (group 1) | Shader | State | Target |
|---|---|---|---|---|
| Casters | 735-739 | 42d12efb | white silhouette, alpha = t0.a | 0x212f000 128x128 R5G6B5 swizzled, no zeta |
| Blur | 740 | 45f8b322, SHADERPROG 0x8421 | 4 stages all sample 0x212f000 (4-tap), inline_buffer fan of 4 (prim 7) | 0x2127000 128x128 R5G6B5 |
| Projection | 741-747 | 4ab25e73, SHADERPROG 0x21 (stages 0,1 PROJECT2D) | t0 = 0x2127000 (TEXFMT 0x0771058a SZ_R5G6B5, TEXADDRESS BORDER), t1 = 0x03bbc000 16x16 AY8 falloff (CLAMP); BLEND 0x30a; 60 indices (20 triangles), prim 5 | 0x22c4000 640x480, zeta 0x2198000 |

Groups 2-4 are draws 748-760, 761-774, 775-788.

The projection's combiner, from the dumped GLSL of psh 4ab25e73:

```
Stage0  r0.rgb = v0.aaa
Stage1  r0 = (1-t1)*r0 ;  r1 = t0*(1-c0)          c0 = 0x00080808, c1 = 0x00ffffff
Stage2  r0 = (1-r0) + r0*(1-r1) = 1 - r0*r1
final   rgb = 1 - r0 = (1-t1) * v0.a * t0 * (1-c0)  =: S ;  alpha from dot(1-r0, c1); alpha test
blend   0x30a = EN, SFACTOR ZERO, DFACTOR ONE_MINUS_SRC_COLOR:  dst' = dst * (1 - S)
```

**So the neutral ("no shadow") texel of 0x2127000 is BLACK, not white.** S is proportional to t0;
t0 = 0 leaves the floor untouched, t0 = 1 (the silhouette) darkens it by (1-t1)*v0.a*0.97. The
in-shader border (caae5e7906) substitutes borderColor[0] outside [0,1]; the border colour
registers are 0, so the outside is neutral. (The dump's `rs.bcol` 0xbfffffff, which the brief read
as the border colour, is BLENDCOLOR.)

## 2. Measured facts

| # | Fact | Instrument |
|---|---|---|
| F1 | BORDERCOLOR for both stages is 0; TEXADDRESS 0x00010404 (BORDER on u,v). | chain.py on the dump |
| F2 | **Both 128x128 targets hold correct content on the host.** In slot2's guest RAM (a save state first downloads every draw-dirty surface, `pgraph_vk_pre_savevm_trigger`, renderer.c:4109): 0x212f000 = 2 values, 12,095 x 0x0000 + 4,289 x 0xffff (white silhouette on black); 0x2127000 = 17 values, 11,467 x 0x0000, 3,653 x 0xffff, the rest blurred edge values (0xbdf7 228, 0x4208 213, 0xef7d 147, 0x1082 142 ...). Images: `captures/halo-shadow-1017/hxsram/0212f000_sw_x4.png`, `02127000_sw_x4.png`. | tools/hxsram.py on slot2.stream (xbox.ram block; pc.ram is zeros) |
| F3 | The neutral texel is 0 (section 1), and the targets' background IS 0. The clear lands and the blur works. | F2 + the psh |
| F4 | In f004 the dark area is the projected [0,1] footprint (a parallelogram), with a gradient across it and **no silhouette visible**; the floor outside it is unchanged. | framedump/f004.png, tools/sqcrop.py |
| F5 | Draw 741's stage 0 binds img ...928240, `s2t 0` (a copy, not the direct view), th 0 (an s2t-path node), surface dirty 1. Draw 740's four stages bind two different images for the one address (...924190 for s0/s1, ...9234a0 for s2/s3). | tools/texids.py |
| F6 | The caster/blur `rs.blend` 0x112 (group 1) vs 0x302 (groups 2-4): bit 3 (EN) is 0 in both, so blending is off on those draws either way. | decode of NV_PGRAPH_BLEND |

Caveats on F2: slot2 was saved by a build I cannot name (shots.tsv carries no build; the dump
session's logcat is 0.5.2-rc1 with surfgpu and fastpaths ON). The RAM shows what the host target
held at the moment of that build's last download of it. It says nothing about the image the
projection's stage 0 samples, which is a separate host object (F5).

## 3. Already tried

Searched by three subagents and by me (command lists in section 3.1). Every row was re-checked
against the commit or NOTES line it cites.

| approach | where (commit, lane, NOTES line) | verdict | what it means here |
|---|---|---|---|
| Direct bind of a sampled colour surface (August regime) | 03cb21a03b (03-25); 997c8d0b30 (04-03, per-texture view with the texture format's swizzle, else copy) | the August build ran it; defect present (owner, August video) | the defect survives a regime with no copy at all |
| CPU decode of 565 by replication; s2t refuses converted formats | f009555537 (09-12) | landed; defect present in 0.5.1-rc1 | the defect survives a regime with a download + VRAM upload |
| GPU decode, `HAKUX_S2T_CVT` | 6cbcb60bc7 (10-16), default c3660fdd86 (10-17); fps1015 NOTES 713-749, 915-929 | arithmetic equals the CPU decode on all 65,536 words; Blend_surface byte-identical | the 10-17 capture ran it and shows the defect. The decode arithmetic is not suspect; what wraps it (which image is copied, when, which view is bound) is not covered by that check |
| Border colour from the register, in the shader | caae5e7906, 5edcbb2e23 (09-10); releases/v0.4.0-j1.md:25-30 | landed (Texture_border_color 56,419 -> 16,205) | acts outside [0,1] only; Halo's outside is correct (F4), the defect is inside |
| Bordered-length probe removal | bb1f62d32d (09-13) | BORDER_SOURCE=TEXTURE only | not Halo's case (COLOR) |
| CLAMP_TO_BORDER -> CLAMP_TO_EDGE fallback | 55c1ce5ac6 (03-29) | x1box only, never on master | not our code |
| VkSampler cache keyed by border colour | 1666e81d7a (04-06) | in the August code; never measured here | a stale sampler changes addressing at the edges, not a uniform inside |
| Pad-bit sampling override (copy path for pad formats) | 4946433d87 (09-12), 2f23dd9ce5 | pad formats only | R5G6B5 has no pad bits; also the commit's design note: neither TextureKey nor TextureImageConfig records a view's swizzle |
| CLEAR stamps the pad constant | 1f9eac66c4, 637b4f1d2a, 6824749e83, 55de5edfff (#164) | pad formats only | R5G6B5 has no pad bits |
| Inline clear via vkCmdClearAttachments | 36d519a2e2 (03-25); master vk/draw.c ~10214-10393 | in the August code; never measured for this chain | F2/F3: the clear lands on the host target. Refuted as the cause here |
| Fully cleared binding marked cleared | 51721e36aa (09-27, #414) | postdates August | same as above |
| R5G6B5 clear-colour decode (/31, /63) | pgraph.c ~5631 (upstream) | never measured against hardware | COLORCLEARVALUE is 0 here; every decode of 0 is 0. Refuted here |
| #184 rebind when a sampled surface is written | 1213f50c90; remote NOTES 1559-1664; NOT REACHED 2182-2226; board 3385-3393 | fixed-verified; three paths unreached, incl. a "stage 0, PROJECT2D" case-2 control (2217) | open lead for H-A: Halo writes and re-samples both targets 4x a frame |
| #1033 uniform attribute skipped on the super-fast path | fps1015 NOTES 943-962; draw.c:7486-7490 still unfixed; board 6459 | open, blocked | could give draw 740 or the projection a stale v0. v0.a only scales S, and S = 0 where t0 = 0, so it cannot draw a square on its own. H-D |
| Inline buffer cap / growth | 09241e46a6 (03-23), 878507db2f (09-12) | the overflow was live in August; fixed; defect persisted | not the cause |
| s2t skipped while an upload is pending; `possibly_dirty` via cached VRAM checks | 344a87bdd1 (03-31), 25493a599b (03-07) | in the August code; never measured here | H-A lead: either can serve stale VRAM in place of the target |
| GTA SA projected shadow chain | gtasagpu1011 NOTES 532-547, 741-748, 960-981; 597df4af82 | "Shadow: no renderer defect", faint by design | different chain (X8R8G8B8, CLAMP, a game-drawn black border line). Reuse its readers (fdread.py, stillcmp.py); not its question |
| Blend_surface 128x128 R5G6B5 swatch flips | zrtz272 NOTES 183-206 | unexplained; unguarded | H-A lead (nondeterministic s2t content at Halo's exact shape). Halo's square is every frame on every soldier, so a nondeterministic cause would have to be near-certain here |
| PoP projected shadows, 256x256 R5G6B5 | fps1015 NOTES 568-588 | cost only | candidate second title with the same chain shape |
| Halo plateau downloads are all `cvt` | halo1016 NOTES 57-60, 346-361 | perf | confirms Halo's 565 targets took the download regime before S2T_CVT |
| Desktop Halo | x1port1012 NOTES 470-482, 687-689, 806-825 | menu ring only; attract demo ~112 s in on the Nova | no desktop run has reached soldiers; the attract demo is the route-free way in |
| Render-to-texture diverges from silicon | tracker #4 (104, 136-139) | fixed-part; GENERAL->GENERAL barrier present and correct | the direct-view barrier was checked then; the copy path's is not covered |
| Depth shadow comparator | #30/#35/#46, psh.c:584, 19c74e95da | depth formats only | not an R5G6B5 colour texture |
| PROJECT2D texel-tie bias, texture-perspective bit | c9ed762cd5, 18dc4f11e2, 2d903ff204 | postdate August | precision only; cannot make a uniform inside |
| DXVK #5388: Halo border channel mapping on A8L8 | web (search snippet) | wrong border channels broke Halo CE's motion sensor | the border colour is 0 here (F1); not this |
| Upstream xemu square shadows: TWS #1867, UC #1603, GTA SA #1246 | web (search snippets only; GitHub fetch refused) | open upstream, no fix found | the defect class exists upstream too; nothing to port |
| Upstream PR #1651 / #1937 (Halo, Conker shadows missing; z clamp) | web (snippets) | unknown merge state | missing shadows, not squares |

**"dark square" / "black square"** appears nowhere in the repo but this lane. No Halo-specific
code exists under hw/xbox/nv2a (`4D530004` only under docs/ and .github).

### 3.1 What was searched

- git, all refs (`git -C <wt> log --all ...`):
  - `--grep` (case-insensitive, extended): `clear.?surface|clear colou?r|COLOR_CLEAR_VALUE|pgraph_vk_clear|clear value`;
    `R5G6B5|565|5/6-bit|6-bit|replicat|S2T_CVT`; `border|TEXADDRESS|CLAMP_TO_BORDER|bcol`;
    `PROJECT2D|projective|SHADER_STAGE_PROGRAM|texture stage program|textureProj|texture-perspective|PS_TEXTUREMODES_PROJECT`;
    `surface.to.texture|render.to.texture|render target sampled|s2t|texture_matches_surface|surface used as (a )?texture|sampled while|written while sampled|SURFACE_DOWN|swizzle.?surface`;
    `shadow` (since 2025-06); `halo|dark square|black square|#1038`; `#184\b`; `#1033\b`;
    `inline.?buffer|inline_array|PRIM_TYPE_QUADS|\bquads\b`;
    `component.?mapping|VkComponentMapping|component swizzle|view swizzle|COMPONENT_SWIZZLE` (-- hw/xbox/nv2a).
  - `-S` / `-G` on hw/xbox/nv2a: `HAKUX_S2T_CVT`, `CLEAR_SURFACE`, `inline_clear|vkCmdClearAttachments|get_clear_color|COLOR_CLEAR_VALUE`,
    `R5G6B5`, `BORDER_SOURCE`, `border_?[cC]olou?r|borderColor|CLAMP_TO_BORDER|custom_border`, `PROJECT2D`,
    `check_surface_to_texture_compatib|surface_to_texture|texture_matches_surface|s2t_cvt`,
    `HAKUX_VTX_HAZARD`, `HAKUX_REPORT_EARLY`, `HAKUX_FLDCW_CHAIN`, `HAKUX_IBC`.
  - every hw/xbox/nv2a commit on master 2026-04-01..09-10 (none between 0384c8718c, 04-09, and 09-08:
    the August build ran 04-09 code).
- Tracker: `git show origin/board:nv2a_issues.toml`, rows 1038, 1033, 184, 46, 35, 4, 59, 44, 939, 1039, 1018, 804.
- Lane NOTES: gtasagpu1011, zrtz272, fps1015, remote (#184), x1port1012, defaulton1017, halo1016; docs/testing/desktop-runs.md.
- docs/ grep for `shadow`, border, PROJECT2D, clear colour (4,702 + 243 hits; 26 files read, tables/scoreboards skipped).
- MainActivity.kt FASTPATHS_VARS (38-42: REPORT_ASYNC, TEXSCAN, DRAWREC, UNI_BULK, UNI_UBERCACHE,
  UNI_FOGCACHE, POSTED_PUT, LOCKFREE_WAKE, all on by default) and HAKUX_SURFGPU=1 (205-206). The
  0.5.2 C defaults: S2T_CVT, REPORT_EARLY, FLDCW_CHAIN, VTX_HAZARD on; IBC off. On the desktop,
  SURFGPU, TEXSCAN, REPORT_ASYNC and DRAWREC are off unless set.
- Web (no GitHub contact; github.com fetches were refused, so issue bodies are snippets): xemu issues
  and compatibility page for Halo CE, square/black shadows in other titles, X1 BOX changelogs,
  Cxbx-Reloaded reports, DXVK, c20.reclaimers.net (Halo renders 128x128 shadow maps per object).

## 4. Symptoms and their accounts (current)

| # | Symptom | Account so far |
|---|---|---|
| 1 | The whole projected square darkens, not only the silhouette | Stage 0 returns non-zero rgb across [0,1] although the target holds 0 there (F2, F3). The fault is between the correct host target and the value stage 0 samples. Which link: section 5 |
| 2 | Tint, ~x0.83 R/B, ~x0.71 G (lane.xbox's reading) | Not established. The floor is mottled and that reading did not match regions. With c0 grey, S can only be tinted if t0 is. To be measured by region with a numeric judge |
| 3 | The floor outside the square is unchanged | Accounted: outside [0,1] the shader substitutes borderColor[0] = 0 (caae5e7906, F1), so S = 0 |
| 4 | blend 0x112 (group 1) vs 0x302 (groups 2-4) | Accounted: EN = 0 in both (F6); no effect |
| 5 | Since August, across builds and titles | The defect survived three surface-to-texture regimes (direct bind, CPU decode, GPU cvt). The cause must be in what all three share: the binding cache, the view or sampler, the shader, or the vertex/coordinate path. Not in any one regime's decode |
| 6 | Desktop shows it? | Unknown. Next experiment |

## 5. Hypotheses (ranked by P; re-ranked on F1-F6, then on the code reads in 5.1)

| id | Hypothesis | P | Already-tried row | Hit / miss, and the instrument |
|---|---|---|---|---|
| H-A | Stage 0 samples an image that does not hold the target's content: a stale binding (#184's unreached paths), a copy ordered before draw 740 or skipped by the `draw_time` test, a pool image never written, **the dummy texture**, or a descriptor that names another node's view while `texture_bindings[0]` is right | 0.45 (was 0.35) | #184 rebind; 344a87bdd1 / 25493a599b; zrtz272 swatch flip; #274 retired-view-to-dummy | **I1** (`rttmax16384`: 128x128 readbacks of the sampled surface "srf" and the texture copy "tex" at draw 741) and **I3** (schema 10's "bv"/"pv"/"tv" and "ptd", and "pvi" for a foreign view). Hit: "bv" is "z" or "x", or "ptd" is 1, or the "tex" copy is uniform or differs from "srf". Miss: "bv":"n", "ptd":0 and "tex" is the blurred silhouette on 0 |
| H-C | The view or sampler returns constant rgb: component mapping ONE in rgb, or a view format whose read of 0 is not 0 | 0.12 (was 0.30) | 997c8d0b30, 4946433d87 (view swizzle design) | Lowered: SZ_R5G6B5 maps to R8G8B8A8_UNORM with an identity mapping (constants.h:219), and the cvt writes that format. Still open for a view created with another node's format. I3's "pvi" readback and a view-format field would close it |
| H-E | The pixel shader is mistranslated: t0 is read from another unit, or stage 1's input mapping differs from the guest's | 0.10 | new: searched the psh history above and the dumped GLSL, nothing yet | **I4** (read stage-0 sampler binding in the GLSL against the descriptor set). Hit: texSamp0 is bound to another stage's image |
| H-B | The texture coordinates collapse onto one texel, and the square is the clipped ground geometry | 0.05 | new: searched PROJECT2D history (tie bias only), nothing | F4 argues against it: the [0,1] boundary falls on the square's edge, so bc varies correctly, and the fetch uses the same coordinate. A VS replay with save-state vertices would settle it |
| H-G | Blending is not applied (S written directly) | 0.02 | new: searched blend history, nothing for 0x30a | With t0 = 0 the alpha test discards the fragment, so this cannot draw a square from a correct texture |
| H-D | t1 or v0.a wrong (#1033 on the projection) | 0 for the square | #1033 | Scales S only; S = 0 wherever t0 = 0. Could explain a tint or gradient error, not the square |
| H-other | Anything not above (zeta, the vertex hazard path, Adreno driver) | 0.26 (was 0.18) | -- | the desktop experiment splits core from driver |

### 5.1 What moved H-A up and H-C down (code reads, 10-17)

- **The dummy texture is constant white.** `create_dummy_texture` (texture.c:2514-2640) makes a
  16x16 R8_UNORM filled with 0xff, viewed R,R,R,R, so it samples (1,1,1,1). Bound at stage 0, t0 = 1
  and S = (1-t1)·v0.a·(1-c0): the full [0,1] parallelogram with t1's gradient and no silhouette.
  That is F4 exactly. Paths that put the dummy, or another view, under stage 0:
  - texture.c:2843 (texture outside VRAM), 3909 (stage not enabled or not decodable), 4016 (the LRU
    could serve no node on a first bind);
  - `pgraph_vk_texture_surface_view_retired` (texture.c:4299): a slot whose pushed info names a
    retired surface view is pointed at the dummy until its rebuild;
  - `push_tex_infos[i]` is rebuilt only when `texture_bindings_changed` is set (shaders.c:938,
    draw.c:6120 and 6308). `pgraph_vk_bind_textures` sets it when the node or `slot_view` changes;
    a path that changes what the slot samples without either leaves the old infos pushed.
- **The Nova pushes descriptors** (logcat line 503, VK_KHR_push_descriptor), so the push infos are
  what the GPU reads. `tex_desc_cache` (the descriptor-set path) is not on the Nova's path.
- **H-C's mechanism is absent for this format.** SZ_R5G6B5's texture view is R8G8B8A8 with an
  identity mapping; R5G6B5 has no alpha, so a pad-alpha override cannot touch rgb.
- **I3 is built (schema 10)**, diagnostics only, armed by the frame dump: per stage "bv" ("n" the
  binding's view, "d" the direct surface view, "z" the dummy's, "x" another), "pv"/"tv" the handles,
  per draw "ptd" (infos changed since the last push), an "rb" entry "pvi" reading the image of
  the live node that owns a foreign "pv", and 16-bit surface readback so "srf" of the R5G6B5 targets
  is written.

Superseded: the brief's S1 (non-neutral background: clear missing, misdecoded or late) and S3
(swizzle mismatch) are refuted by F2/F3. Its S2 (draw 740 reads stale input) is refuted for the save
moment: the blur output is correct. Its S5 (border edge texels) cannot darken the inside.

## 6. Plan

1. Desktop experiment (brief's first): C: >= 40 GB, then the x1port1012 desktop to the attract demo,
   frame-dump with images, look for squares. In parallel, read the copy and view code (I2/I4 offline).
   Desktop build: `tools/deskbuild.sh` (configured as x1port1012's build-linux); runs:
   `tools/deskrun.py TOTAL_S OUTDIR SPEC [ENV=V ...]` (refuses under 40 GB free on C:, lists new crash
   dumps). The Nova's defaults are set by env on the desktop: HAKUX_SURFGPU=1 and the eight
   fastpaths vars =1 (MainActivity.kt:206-220); the ubershader (HAKUX_GPL=3) is the core's default.
2. I1 + I3 (built, schema 10): `rttmax16384` reads back the 128x128 sampled surface and texture copy
   at the projection, and "bv"/"pv"/"ptd"/"pvi" say which view the descriptor names.
3. Queue the same dump for the Nova (owner holds it; queued requests run when it frees).

## 6.1 L2 prediction (written before the run, 10-17)

L1 (desktop, slot2 loaded, the Nova's env switches) shows no squares. The one difference found so
far in the projection's path is pipeline construction: the Nova logs `[gpl569] ext=0 lib=0 ...
requested=3 mode=0` (no VK_EXT_graphics_pipeline_library on Adreno, so monolithic pipelines and the
specialised VS's uniform layout), the desktop runs mode 3 (GPL libraries, uniforms uploaded into
the uber layout, `gd.uv` 1, `gd.gu` 0 once the specialised pipeline is swapped in).

L2 = L1 + `HAKUX_GPL=0`, same state, same frame window.
- Hit: squares on the soldiers in the ppm frames, and rbread.py shows the projection changing the
  whole footprint (thousands of px, not ~200) while tex0==srf0 stays 16384/16384. Then the cause is
  in the mode-0 path (monolithic pipeline or the specialised layout's uniform upload).
- Miss: ~200 px changed per caster, no squares. Mode is ruled out; the remaining Nova/desktop
  differences are the CPU side (the Nova's FP JIT and FP safe are ON; the desktop is x86 TCG) and
  the driver (out by the owner's ruling).

## 6.2 L1's answer was the instrument's (10-17)

L1: the desktop loads slot2 and draws soldiers. Spec `8,images,rttmax16384,gd,after15,cap2400` with the
Nova's env switches on. In f003, rbread.py gives tex0==srf0 16384/16384 at all 23 projection draws (a
correct silhouette on black). The one draw with pre/post (n442) changes 200 px at x0.613 in r, g
and b alike: a correct soft shadow, and no squares in the frames.

**That run cannot see the defect.** `rttmax16384` makes every projection draw read back its 128x128
stage 0 (`fdump_log_draw_readbacks`), and a readback calls `pgraph_vk_finish(SURFACE_DOWN)`
(renderer.c:3333). The GPU is serialised at every projection draw, and the next draw finds no
render pass, so it takes the full pre-draw path. The dump records this itself: on the desktop all 23
projection draws have `gd.path` 2. On the Nova (spec `8 rtt gd images`, rtt at its default 64x64
bound, so 128x128 is never read back and nothing finishes there), in f004 each group's first one or
two draws have path 2 and **every later draw has path 0, the super-fast path**:

| | draws (f004 / f003) | gd.path | ubo offsets |
|---|---|---|---|
| Nova, group 1 | n741 | 2 (cp 4) | 641920 / 648192 |
| Nova, group 1 | n742 | 2 (cp 3) | 649472 / 655744 |
| Nova, group 1 | n743-747 | **0** | same as n742 |
| Nova, groups 2-4 | first draw 2, the rest **0** | | |
| Desktop L1, all groups | n442-483 | 2 | 0 / 8480 |

The guest's input agrees: the texgen/texture-matrix constants (c60-79) match to 3 digits between
the two dumps, as do the vertex arrays (`vr`) and the inline attribute values (`va`). The CPU side
(the Nova's FP JIT) hands the GPU the same projection.

On a super-fast draw, begin_draw (draw.c:7486-7490) skips `bind_descriptor_sets`,
`push_vertex_attr_values` and `push_geom_line_params`. Those are the lines the #1033 Already-tried
row leaves open. The super-fast block itself pushes textures only when `texture_state_gen` moved,
and vertex attribute values only when `vertex_attr_gen` moved and the descriptors match.

L2 (L1 + `HAKUX_GPL=0`) was already running and carries the same masking. It still tests the mode
under serialisation, but it cannot clear the super-fast path.

**L2's result (read in attempt 2 from the dump the cap left behind, 7 of 8 frames):** miss, as
the masking predicted. f003's 30 projection draws: tex0==srf0 16384/16384 at every one; the one
draw with pre/post changes 101 px at x0.670 r=g=b. Mode 0 under serialisation draws a correct
shadow.

### L3 prediction (before the run)

L3 = L1's env with the Nova's spec (`8,images,rtt,gd,after15,cap2400`), so nothing finishes at the
projection.
- Hit: the squares appear on the desktop, and the projection draws after each group's first take
  path 0. Then the defect is reproducible on the desktop, and serialisation hides it. It is not an
  Android-only path.
- Miss: no squares while path 0 is taken. Then the super-fast path alone does not draw the square
  on lavapipe, and the next legs are GPL mode 0 without the finish (L4), then a tiler-only ordering
  question that only the Nova can answer.

**L3's result (attempt 2, run 12:39): miss.** The desktop now takes the Nova's path pattern (each
group's first projection draw path 2, the rest path 0; f003 n459-517), and still draws no square.
Shot-matched against the owner's still `s2-02.png` (the close-up the state loads into; the desktop's
f000-f007 are inside that shot): at the right-hand soldier's feet the Nova draws a large dark
parallelogram covering the whole floor patch; L1 and L3 draw a thin soft streak beside the feet
(crops: `build-linux/run/L1|L3/..._f003.png` (480,230)-(640,360) against s2-02 (900,480)-(1280,780)).
The super-fast path alone does not draw the square on lavapipe.

Both devices enable VK_EXT_custom_border_color and VK_KHR_push_descriptor (logcat 499-500; L3
qemu.log 34-37), so neither is an Android-only difference. The named one left is GPL mode 0
(Nova, no VK_EXT_graphics_pipeline_library) vs mode 3 (desktop).

### L4 prediction (before the run)

L4 = L3 + `HAKUX_GPL=0`: the Nova's pipeline mode, the Nova's path pattern, no serialisation.
- Hit: the square at the right soldier's feet in f000-f007 (the s2-02 shot). The cause is in mode 0's
  pipeline or uniform path, and the desktop reproduces the defect from here on.
- Miss: the thin streak again. Mode is out; next are the other env/Android-only differences
  (a full diff of the Nova's logged switches against the desktop's).

**L4's result (run 12:47): miss.** `[gpl569] requested=0 mode=0`; f003's projection draws n738-796
take path 2 on each group's first and path 0 on the rest, as on the Nova. This run's f003 is the
wide shot of the Nova's f004 and the owner's s2-03 (the central soldier on the lit platform). On
the desktop the central soldier has a small soft shadow at the feet; the Nova draws the large
mauve parallelogram there. `build-linux/run/L4/framedump_1792266358_f003.png` against
`captures/halo-shadow-1017/framedump/f004.png`.

**So: same core, same state, same switches, same pipeline mode, same draw paths. The desktop is
right and the Nova is wrong.** An Explore pass over hw/xbox/nv2a for `__ANDROID__` branches and
vendor checks found none that changes what a sampled texture returns or what coordinate a
fragment uses (the list is in section 6.3). What remains is how the GPU executes the same command
stream. Lavapipe runs every command in submission order on one CPU queue, with no tiling, so a
missing or too-narrow barrier never shows on it. A tiler (Adreno) and the desktop GPUs in the
upstream reports would show one.

### 6.3 Android-only and device-dependent code (Explore pass, 10-17)

- No `__ANDROID__` branch in hw/xbox/nv2a touches sampling, views, samplers, the psh/vsh GLSL or
  the s2t paths. The Android branches are the AHB/EGL present path, VMA block sizes, memory budget
  thresholds, the inline-buffer cap, early context init and a duplicate-NOP assert.
- vendorID is used only for the pipeline-cache identity (renderer.c:45-170).
- Device-capability-dependent: the GPL mode (instance.c:1278), the cvt pass's buffer offset
  alignment (`minStorageBufferOffsetAlignment`, surface.c:6513), NEAREST forced on a format without
  linear filtering (texture.c:3655), push constants for uniform attributes by
  `maxPushConstantsSize` (shaders.c:2246), and the custom-border sampler cache, whose key omits the
  view format (texture.c:3712-3730; `customBorderColorWithoutFormat` is not enabled).
- MainActivity.kt sets only XEMU_RENDERER, HAKUX_GPL (0 only with the ubershader off), HAKUX_SURFGPU
  and the eight fastpaths vars. The desktop legs set the same.

### L5 prediction (before the run): sync validation

H-S (new: searched `git log --all -i --grep 'barrier|hazard|sync.?val|SYNC-HAZARD'` on
hw/xbox/nv2a, see 3.1; #4's GENERAL->GENERAL barrier check covered the direct view only): a
missing or too-narrow barrier in the shadow chain, invisible on lavapipe.

L5 = L4's env + Khronos validation 1.3.275 (Ubuntu's `vulkan-validationlayers`, extracted to
`/home/justin/hakux-work/desktop/vvl/root`, not installed) with synchronization validation
(the core's own `validation_layers` config switch, instance.c:293-353).
- Hit: a SYNC-HAZARD (RAW or WAR) naming an image or buffer of the chain: the 128x128 targets,
  the stage 0 copy the projection samples (the dump's `img`), or the cvt pass's buffer. The
  message names the commands; that is the mechanism to fix.
- Miss: no hazard on the chain's objects. Then a missing barrier is not the cause as far as the
  validation layer can see, and H-S drops.

## 7. Desktop crash log

(none yet)

## 8. Questions

(none yet)
