# haloring1017 -- Halo CE main-menu ring (#939)

Lane: haloring1017 (Opus). Issue #939. Branch `lane/haloring1017` off master @ 9abd80e90c.
Brief: `/home/justin/hakux-work/briefs/haloring1017.md`.

The owner's goal is the ring the way the console draws it. Every surface turns with the ring, and the bright mottled
grey layer covers the whole ring, the unlit side included.

[lane.haloring1017] working: (c) is answered. The inside band turns on screen off the stock driver: slope 0.88 on the
desktop, 1.02 on Turnip (run 13, PurpleVK confirmed from its log). The lane narrows to (a).

## Attempt 1 did not finish: the turn cap

Attempt 1 ended at 15:57 PDT on the 301-turn cap, partway through M2b's last fit. It was not blocked and was not
waiting on anything. M1, M2 and M2b's clock were committed (948dc20f1c). The interrupted fit (`run13map.sh`) had
already written its `n4` rows and 80 of its `n5` rows to scratch (`hr/m2c/bandfit.tsv`). Attempt 2 read those rows
rather than running the fit again; they are reported under M2b.

## Step 0: what was searched

| where | query | found |
|---|---|---|
| `git log --all --grep` | `#939`, `939`, `halo`, `ring` | the x1port1012 chain: 0af0042d92, 223f216d7c, 71f81f53c6, bd4a85aa77, 9cd57a0398, 1294c5892d, 18fb801de7, fabfdd4fa0, 4ee5a7411d, 82e0e26bb3, 5d4b689ed9, 3710b8bb24, c48566def4, 56fdef2c85, 52aa206f93/56834e79cd, 303461b264; the bind-pose lane; this lane's 687f87f269. None changes cube sampling, texcoords, combiners or VP output setup |
| `git log --all -S`/`--grep` | `CUBEMAP`, `cube`, `remapCubeTo2D`, `face` | cube fixes A16, A17. None is for #939 |
| same | `texgen`, `TEXGEN`, `texture matrix`, `PROJECT2D`, `textureProj` | A18. Nothing on PROJECT2D's q under a VP |
| same | `c13`, `XVSS`, `S2TSHELF`, `constant`, `VP const` | A19 |
| same | `combiner`, `final combiner`, `SPECFOG`, `PSH_UBER`, `fog` | A20 |
| same | `FIST`, `FRNDINT`, `rounding mode` | A21 |
| same | `SPECULAR_ENABLE`, `LIGHTING_ENABLE`, `SEPARATE_SPECULAR`, `oD1`, `vtxD1` | A22. No x1port1012 doc reads these switches for the ring draws |
| same | `output.*init`, `vec4(0.0,0.0,0.0,1.0)`, `unwritten` | nothing: the VP outputs have been initialised to the constant (0,0,0,1) since upstream (`vsh.c:578-591`) |
| `docs/lanes/x1port1012/NOTES.md` (origin/master, 961 lines) | lines 188-961 read in full | A1-A15 |
| `docs/lanes/fistdefault1016/NOTES.md` | read in full | A21 |
| tracker `origin/board:nv2a_issues.toml` | `[issue.939]`, #40, #51, #273, #1038, #1039 | #939 open, owner lane.haloring1017, status note has the stock-driver caveat. #1038/#1039 closed 10-17 as the stock driver. #40 a degenerate cube direction (a9f8ef3bee). #51 DOT_STR_3D. #273 sphere map (Q under sphere mapping untested). None names the menu ring |
| forge #939 (127.0.0.1:3330) | body + comments | lane.local's body (10-11); jobs 10-16 21:59 (the inside surface stays static and the outer grey hull rotates; easy to miss); lane.local 10-16 22:50 (0.5.2 target) |
| `MainActivity.kt` FASTPATHS_VARS, defaults | `:37-42`; `vk/surface.c:6379`, `vk/reports.c:550`, `translate.c:3182`, `cpu-exec.c:1820`, `tcg-target.c.inc:4321` | 8 fast paths on (REPORT_ASYNC, TEXSCAN, DRAWREC, UNI_BULK, UNI_UBERCACHE, UNI_FOGCACHE, POSTED_PUT, LOCKFREE_WAKE). S2T_CVT, REPORT_EARLY and FLDCW_CHAIN on unless =0. IBC off unless 1/2. FIST_ROUND on unless =0, aarch64 only (a no-op on x86_64, where CVTSD2SI rounds per MXCSR). fp_jit on (`config_spec.yml:366`). Ubershader and SURFGPU on. The `env_vars` pref overrides all of these (`xemu_android.cpp:1015`) |
| web (xemu issues and compat, X1 BOX, Cxbx-Reloaded) | "Halo menu ring", "Halo main menu ring texture", "xemu Halo ring", "Cxbx Halo demo graphics" | no upstream issue for the menu ring. xemu's Halo compat lists other defects (#865 water, #866 lines, #659, #602, #2087). **Cxbx-Reloaded PR #2109** ("Initialize vertex shader outputs to vertex shader attribute values", Dec 2020): on hardware an unwritten VS output takes its attribute register's current value; "fixes some Halo demo graphics"; components the input lacks default to (0,0,0,1), and copying zw broke font rendering. Known from search snippets only (GitHub fetch is denied here) |

## Already tried

`A` rows are prior work. "x1 NOTES" means `docs/lanes/x1port1012/NOTES.md` on origin/master.

| # | approach | where | verdict | what it means here |
|---|---|---|---|---|
| A1 | triage video clips timed by the soak clock | x1 NOTES 246-282 (lane.xbox) | void: missed the window | aim every dump by the dump's own arm clock (`after` counts from emulator start, about 14 s after the soak mark); check the ring is in the dump before judging |
| A2 | audit run: XVSS and S2TSHELF probes | x1 NOTES 341-433, run 0-1792165273-x1port1012-921745 | XVSS never reached; S2TSHELF 0 hits | neither path runs in the menu, so neither is a candidate for (a) or (c) |
| A3 | the 8 fast paths off (Nova) | x1 NOTES 434-497, run 1792166308-x1port1012-1386872, ref 223f216d7c | (b) unchanged; deterministic per boot | rules them out for (b) only. Its video is a free look at (a) and (c) with the fast paths off (driver to confirm from its log) |
| A4 | owner's console check | x1 NOTES 498-610 | two symptoms: (a) layer missing, (b) bursts | (c) came later (forge 10-16 21:59), on the stock driver |
| A5 | `gd` per-draw dump, schema 9 | 7a1889054a; x1 NOTES 613-621; `docs/lanes/x1port1012/tools/gdread.py` | works | reuse it. Dumps dg1/dg2/dg3/r12/r13 sit in x1port1012's `build-linux/run/` (scratch) |
| A6 | hull draw `n5` taken apart (VP, 4 textures, 8 stages, final combiner) | x1 NOTES 623-683 | complete for `n5` only | `n4` (terrain strip), `n6` (inner rim, multiply pass, own base 0x02be8000) and `n0` (planet) never taken apart |
| A7 | PSHDBG single-term isolation on the desktop | x1 NOTES 685-699; `psh.c.pshdbg.bak` in x1 scratch | mode 5 near black; modes 4, 6, 7 segfault at 47-54 s | do not rely on it until the interface crash is fixed |
| A8 | H1 the reflection term wrong | x1 NOTES 720 | open, P 0.6 before step 3 | step 3 (A15) puts the term's ceiling below the console's brightness. See R1 |
| A9 | H1a cube face stride | x1 NOTES 721, 914-920 | refuted: faces continuous only at stride 2816, hakuX's | not rebuilt |
| A10 | H1b cube face orientation | x1 NOTES 722 | weighs against (seams fit GL orientation); a global mirror not excluded | the global mirror is the only part left (R1b) |
| A11 | H1c eye, normals, skinning | x1 NOTES 723 | weighs against: c4 is the projection's eye, normals unit and outward | not rebuilt |
| A12 | H2/H3/H7, (b) | x1 NOTES 724-726, 744-886; 5d4b689ed9, 52aa206f93 | root cause: the aarch64 FIST lowered to FCVTZS (truncate); fixed by FIST_ROUND, default-on | do not reopen (b). It shows the ring's turn is c13.w, a guest-computed texture u-scroll |
| A13 | H4 the detail map t1 is the layer | x1 NOTES 727 | weighs against: t1 mean 65 multiplies a dark base | holds only if the base it multiplies is wrong too |
| A14 | H5 v0.a non-zero on hardware | x1 NOTES 728 | open, 0.2 | R3 |
| A15 | step 3: reflection at the photo-5 pose, term magnitudes, later draws, the final combiner | x1 NOTES 910-950 | R hits dark texels of faces 1 and 4 (~0.003); no term as hakuX computes it reaches the console's brightness; no draw after `n5` adds light; final `rgb = r0 + v0.a*(1 - r0)` | the console layer needs a term hakuX computes wrongly or not at all |
| A16 | cube sampling fixes | 1c85282a73, ee208a0bb9 (bordered cube faces); a9f8ef3bee, f66099643c reverted (degenerate direction, #40); 8b50aefbd4, 28eeff3d88, a8086d8905 (DOT_STR_3D, #51); e33e6925eb, 67f88870d9 (DOT_RFLCT_SPEC_CONST); de06bd39e3 (texture outside VRAM, dummy); e654516849 (TEXSCAN) | each fixed its own title's case | the hull's stage 3 is plain CUBEMAP (`texture(texSamp3, pT3.xyz)`, `psh.c:3422-3432`), so only the shared upload path touches it; A9 checked the upload |
| A17 | run 13, FIST_ROUND on the Nova | x1 NOTES 887-908, run 1-1792184446-x1port1012-1339105 | (b) gone, (a) remains | its video is the Turnip footage for (c). The driver is to confirm from its log |
| A18 | texgen and texture matrices | 0965b30a26 (#273 sphere map R.z), dbc563a45d (texgen on a channel that lacks it), 1d9c3e4c0f (#274 SFP/fixed-function uniform) | fixed-function only | the hull runs a vertex program; whether `n4`/`n6`/`n0` do is unread |
| A19 | VP constants | d9c0ed0b8e (#233: constant write-back, RDI past c[191]); f3acdd0912 XVSS; 18fb351588 S2TSHELF | (#233) fixed its case; A2 for the switches | c13 reaches the hull correctly (A12) |
| A20 | combiner paths | f9c44ffd51 (PSH_UBER, default off); 09ee9e2256 (fog factor to 8 bits) | | the ubershader is a second copy of the combiner semantics; any combiner fix must land in both |
| A21 | FIST rounding | a87841e366, c09eb8fc36 (#82), 1b4fb04cec (#67), 5d4b689ed9, 52aa206f93; `fistdefault1016` NOTES | done | x86_64 is unaffected, so the desktop is a clean (b)-free reference |
| A22 | colour outputs under a VP | f0829404af (LIGHTING_ENABLE gates the colour outputs under a VP), fb9cf8c742, 63be3ebf75, c82266b2b5 (#53), 2bedc113aa (#281 NaN clamp) | fixed their titles | the hull's generated VS passes oD0 and oD1 through clamped (`hull_vsh.glsl:497, 511`), so this gating does not touch `n5`. Unread for `n4`/`n6` |
| A23 | HAKUX_VTX_HAZARD | brief (10-11) | zero vtx_hazard finishes in two menu sessions | not a cause |
| A24 | SPECULAR_ENABLE gating of oD1 (`vsh.c:1111-1127`), this lane's own check | `hull_vsh.glsl:511` | not the hull's cause | unchecked for `n4`/`n6` |

## Symptoms

| | symptom | known where | account |
|---|---|---|---|
| (a) | bright mottled grey layer missing over the whole ring | desktop lavapipe; Nova run 13 | open |
| (c) | the inside surface does not rotate | Nova release app 0.5.1-rc1 on the **stock** driver only | **the stock driver (R4)**: the band turns in the guest (M1), on the desktop (M2, slope 0.88) and on Turnip (M2b, slope 1.02). See "The account of (c)" |
| (a)+(c) | one cause or two | | two. (c) is the driver; (a) reproduces on lavapipe and Turnip, so it is the emulator's |
| (b) | bursts | fixed (A12) | only as far as a mechanism touches c13.w |

## Hypotheses

P is this lane's estimate before measuring. It moves from lane.xbox's ranking on A15: step 3 puts the reflection
term's ceiling, as hakuX computes it (cube texel x fresnel v1.rgb about 0.5 x t2.r x v1.a about 0.34), below the
console's brightness.

| id | hypothesis | symptom | P | row | hit | miss | instrument |
|---|---|---|---|---|---|---|---|
| R1 | the reflection term is wrong: R lands on the wrong face, or v1 scales it to near zero | (a) | 0.35 | A8, A10, A15 | the console look returns with the cube term forced to a bright face and v1 replaced | forcing it gives a coloured sheen, not grey crater mottling | `swr.py`-style software render of `n5` from the dg dump, and a desktop PSHDBG mode once A7's crash is fixed |
| R1b | ...the global cube mirror | (a) | in R1 | A10 | the mirrored R lands on face 0 or 4 (bright) over most of the hull at photo 5's pose | mirrored R still on dark faces | `vpemu.py` R per vertex, face histogram per mirror |
| R2 | another draw (`n4`, `n6`, `n0`) ignores its own scroll | (c) | 0.3 if (c) reproduces -> 0.02 (M2, M2b: `n4` follows its scroll; `n6` has none by design) | new: searched x1 NOTES and git, nothing (A6 left them undone) | across consecutive frames, a per-frame change in the draw's guest state that its generated shader does not use | every per-frame change is used, and the output moves | `gdread.py diff` over consecutive frames, per draw |
| R2b | the guest computes `n4`'s scroll wrongly (a CPU defect, like (b)) | (c) | 0.1 -> 0.02 (M1: missed; the rates agree to three figures, on Turnip, run 13) | new: A12 measured c13.w on `n5` only | `n4`'s w rate (0.0000977/frame, ~8x below `n5`'s 0.00078) times its c13.x gives a different angular rate from `n5`'s | rates agree, so the guest means the band to turn at the hull's speed | `gdread.py draw` for c13 on `n4`/`n5` in two frames |
| R3 | v0.a non-zero on hardware: the final combiner lerps toward c0_8 (white) | (a), and a common wash of `n4`+`n5` | 0.2 | A14 | a software render with v0.a = k matches photo 5's brightness and keeps faint panel lines; the terrain band whitens by the same k | the panel lines vanish before the brightness is reached, or the band's whitening differs | software render against the pose-matched pair |
| R4 | the static inside surface was the stock driver | (c) | 0.25 -> **0.9** (M2, M2b: hit) | new: searched tracker #1038/#1039 (stock-driver defects that week), nothing on #939 | (c) absent in run 13's Turnip video and on the desktop | (c) present off the stock driver | run 13's video; a desktop clip; per-draw scroll in a `gd` dump |
| R5 | other combiner or final-combiner semantics, or the fast paths, for (a) | (a) | 0.1 | A3 (for (b) only), A20 | a fast-paths-off clip (A3's video) shows the layer, or a combiner op proves wrong against the hardware docs | | A3's video; reading `psh.c` against nv2a docs |
| R7 | `n5` follows `n4` in the same shader with only c13 changed; the second draw's constants never reach the GPU | (c) | 0.05 -> 0 off the stock driver (M2, M2b: each scrolls at its own rate) | new (M1). Code read: `vsh.c:1213` copies all of c[] every draw; `shaders.c:2108-2138` marks the upload by dirty flag or by layout hash, so a c13 change is caught either way | on screen, one of `n4`/`n5` scrolls at the other's rate or not at all | each scrolls at its own c13.w rate | M2 (`bandfit.py`) |
| R6 | unwritten VP outputs take the attribute registers' current values on hardware (Cxbx-R PR #2109); hakuX sets them to (0,0,0,1). The hull never writes oT0/oT1/oT2.zw (the PROJECT2D q), oT3.w, oB0, oB1 | (a), perhaps (c) | 0.1 | new: searched hakuX git and `vsh.c`, nothing; Cxbx-R PR #2109 | inline attribute values for v9-v12 (or the slots each output maps to) give q != 1, and a render with that q matches the console | q = 1 under that model | the `gd` dump's inline attribute values; a software render |

## Measurements

### M1: (c) in the guest's own state (run 13, Turnip, `gd` frame 100; `constmove.py`, `otwrites.py`, `ringuv.py`)

The ring does not turn by moving geometry. Every ring draw carries bone 0 only: v5 = (0, 253) and v6 = 32767 on
every vertex, so c60-62 (the ring's model matrix) with weight 1. The second index, 253, is out of range with weight 0.
The surfaces turn by scrolling texture u: oT0.x = c13.x*u + c13.y*v + c13.w.

| draw | count | shader | what it is | c13.w per frame | du/dtheta (`ringuv.py`, raw u) | angular rate = step / (c13.x du/dtheta) |
|---|---|---|---|---|---|---|
| `n5` | 4362 | ac5a40cb | outer hull; s0 green panels, s1 crater grey, s3 cube | +0.00078085 | 0.157 /rad: s = 48.67 u wraps 48 times per turn | 1.02e-4 rad/frame |
| `n4` | 864 | ac5a40cb (the hull's own shader) | inside terrain band; s0 0x02ad4000, 2048x128 terrain and cloud | +0.0000976 (exactly 1/8 of `n5`'s) | 0.0196 /rad: s wraps 6 times per turn | 1.02e-4 rad/frame |
| `n6` | 510 | 1a607806 | inside multiply pass; s0 0x02be8000, 1024x32 white trapezoid, a lit/dark mask | constant (c15 = 48.67, c16) | u 0.0204..0.0409 x 48.67 = one wrap | 0: fixed to the sun, by design |

Correction (after M2): the first version of this table put the angular rate at 0.00497 rad/frame, taking c13.x as 1.
c13.x is 48.67 on both draws, so the rate is 1.02e-4 rad/frame, one turn in about 34 minutes at 30 frames a second.
The ratio, the point of the table, is unchanged. On Turnip (run 13, frames 0-599) both scrolls step by one fixed
amount per frame, sd 0, and `n4` = (`n5` - 0.02745) / 8 exactly (`c13series.py`).

So the guest turns the inside terrain at the hull's angular rate, to three figures. R2b misses. `n6` is meant to stay
still: it is the day/night mask, not a surface. The rate is measured in the guest's state as hakuX records it, so it
cannot see what happens to c13 after the dump: uniform upload, caching, or the driver. `n4` and `n5` run one shader
back to back, and only c13 (and the textures) change between them. A missed c13 upload for the second draw of a
shader would freeze one of the two. Whether (c) shows on screen off the stock driver is M2.

The bone mechanism of #1043 (the stock driver mishandles relative-addressed c[A0+N]) cannot freeze this geometry,
because nothing on the ring moves by bone. Every vertex reads bone 0.

### M1b: x1port1012's software render of the hull (unrecorded in its NOTES)

`x1port1012/build-linux/run/swr.py` renders `n5` from the dump in software, term by term. Its last panel set
(console photo 5, hakuX run 13, then t1 x 10, t2.r, t0, and the full combiner) shows the console's bright mottling
looks like t1 (the crater grey, 0x02be4000) at full strength with t2.r's structure. hakuX's combiner draws t1 as a
dim multiplier of t0's green panels.

### M2: (c) on screen, desktop, off the stock driver (`deskrun.py`, `bandfit.py`, `bandsum.py`)

Run m2a, 2026-10-17, on the desktop (lavapipe):
- the build is 0.5.2-rc1, `xemu_commit 160728983a`, with the release app's environment (`HAKUX_SURFGPU`,
  `REPORT_ASYNC`, `TEXSCAN`, `DRAWREC`, `UNI_BULK`, `UNI_UBERCACHE`, `UNI_FOGCACHE`, `POSTED_PUT`, `LOCKFREE_WAKE`);
- `XEMU_FRAME_DUMP=300,gd,images,after74`, with guest RAM saved at +98.5 s, inside the dump window;
- it exited 0 at 230 s. No crash: `wsl-crashes/` was empty before and after, and C: had 57 GB free.

`bandfit.py` asks whether a surface turns on screen. For each fifth frame and each draw it does three things:
- runs the hull's vertex program on the draw's records in RAM with that frame's constants;
- rasterises `n4` and `n5` with a joint z-buffer;
- scans a texture offset d, correlating the dumped image's luminance with the draw's stage-0 texture at
  (c13.x u + c13.y v + d, oT0.y).

A surface that turns has its best d* follow c13.w (slope 1). A static one has d* constant (slope 0).

The cull is the dump's own state: SETUPRASTER 0x10400000 (cull back, FRONTFACE clear, so hakuX uses
VK_FRONT_FACE_CLOCKWISE), which culls area < 0 in the tool's convention. The opposite sign (x1port1012's `swr.py`)
puts the far band in front of the near hull. With no cull, `n4` has no visible pixel. The overlay
(`dbg=`) matches the image only with the dump's sign. **Any software render of (a) must use this sign; `swr.py`'s
may be wrong at some poses.**

| draw | frames | c13.w span | slope d*/c13.w | rms about "turns" | rms about "static" | median r at c13.w / at frame 0's c13.w |
|---|---|---|---|---|---|---|
| `n5` hull (control) | 52, f0-f295 | 0.177-0.437 (266 texels, lod 0) | **1.013 +- 0.015** | 8.3 texels | 81.3 texels | 0.183 / 0.047 |
| `n4` inside band | 24, f35-f170 (`n4` >= 1000 px; 0 px at f0) | 0.0227-0.0377 (3.8 texels, lod 3) | **0.881 +- 0.020** | 0.18 texels | 1.04 texels | 0.253 / 0.190 |

**On the desktop the inside band turns.** Its on-screen texture follows the guest's c13.w at slope 0.88, and static
(slope 0) is 44 standard errors away. Over this window the band's c13.w is the hull's / 8 - 0.00343 exactly, so it
turns at the hull's angular rate.

The 12% shortfall is a lag of 0.45 texels at lod 3 over the whole span. It is not (c), which would be slope 0. A
missed or stale upload cannot produce it either, because that is all or nothing per frame. The likely account is the
fit itself: the strip is 3-8 px wide at one mip, while the 150k-px hull at lod 0 gives 1.01. A pose with a wide band
would test that (M2b's anchors, or a desktop window like `pair1`'s).

Why (c) is easy to see as "static" even when it is not: one turn takes about 34 minutes. From this camera, just
outside the hull at radius 19.7, the band in view is the far side of the ring, about 38 units away. It slides about
3.4 texels at lod 3 in 4.5 s. The near hull turns at the same angular rate, but its nearest face is about 0.4 units
away (r max 19.27), so it visibly streams.

Side finding (desktop only): in frames 0-45 the band's per-frame step is irregular (0.0000837-0.000195), and
`n4` = `n5`/8 + c does not hold there (residual up to 0.004 in `n5` units). Turnip's run 13 has sd 0 over 600
frames. Frames that take two ticks on the slower desktop explain the doubled steps, but not the sub-tick 0.0000837.
Not followed; it does not touch (c).

### M2b: (c) on screen, Turnip, run 13's video (`vidmap.py`, `run13anchors.sh`, `run13map.sh`)

Run 13 dumped `gd` without images, so its pixels come from its 60 s video (1280x960 at 59.94 fps). The dump's wall
clock and the video's disagree by 1-2 s (the host clock steps back), and a pose 1-2 s wrong makes `bandfit.py` fit
noise. Pass 1 on the wall clock (`clockfit.py`) gave r* 0.04-0.15 with d* scattered.

A ring silhouette cannot set the clock (`vidmap.py`'s docstring). The ring covers 27-58% of the screen in every
frame, and its outline changes by 0.2% per frame.

What works is an anchor. Take one video frame and every dump frame within 75 of the wall clock's guess. Fit the hull
with no scroll scan (pad5=0.0) at each frame's own c13.w. Only the true frame has both the pose and the scroll right.

| video t | dump frames scanned | peak frame | r at peak | next best (+-1 frame) | d* - c13.w at peak |
|---|---|---|---|---|---|
| 17.4 s | 15-165 | f124 | 0.223 | 0.165 | +0.00009 (under one tick) |
| 24.4 s | 225-375 | f334 | 0.260 | 0.194 | +0.00009 |
| 31.4 s | 435-585 | f543 | 0.387 | 0.349 | +0.00047 |

The line through them is t = 13.2513 + 0.0334128 f, which is 29.93 dump frames per video second. The residuals are
0.006, -0.011 and 0.006 s, all under a third of a game frame.

**The driver.** Run 13's logcat (`dispatch/results/1-1792184446-x1port1012-1339105/logcat.txt`) has these lines:
- line 3: `Loading custom Vulkan driver: vulkan.purple.so`;
- line 111: `Driver: PurpleVK public driver (PurpleVK 26.3.0-devel (git-62ac221a33))`;
- line 144: `[gpl569] ext=1 lib=1 fast=1 interp=1 requested=3 mode=3`.

So run 13 ran on Turnip, not the stock driver. The app is `com.jreinach.hakux.debug` at ref 5d4b689ed9, with
`HAKUX_FIST_ROUND=1`.

**The fit** (`run13map.sh`): every fifth dump frame, on the anchored clock, gave a video frame (`vidmap.py`, 120
frames). `bandfit.py` then fitted `n4` and `n5` on those frames, and `bandsum.py` summarised the result.

| draw | frames | c13.w span | slope d*/c13.w | rms about "turns" | rms about "static" | median r at c13.w / at the first frame's |
|---|---|---|---|---|---|---|
| `n5` hull (control) | 80, f0-f395 | 0.282-0.590 (316 texels, lod 0) | **1.003 +- 0.000** | 0.38 texels | 92.6 texels | 0.206 / -0.011 |
| `n4` inside band | 44, f0-f55 and f430-f595 | 0.0318-0.0899 (14.9 texels, lod 3) | **1.020 +- 0.001** | 0.12 texels | 5.51 texels | 0.227 / 0.077 |
| `n4`, f0-f55 only | 11 | 1.25 texels | 1.024 +- 0.043 | | | |
| `n4`, f430-f595 only | 33 | 4.0 texels | 1.026 +- 0.007 | | | |

The band is out of view between f60 and f425 (0 px). The session ended before the `n5` rows for f400-f595 were
written; the 80 rows already written are enough for a control.

**On Turnip the inside band turns.** Its on-screen texture follows the guest's scroll at slope 1.02, inside each
window as well as across the gap between them. The fit is cleaner than on the desktop (0.88): the band here is
3-13k px wide against the desktop's 3-8 px strip, which supports M2's reading that the desktop's 12% shortfall came
from the fit.

### The account of (c)

(c) does not reproduce off the stock driver:
- in the guest's state, the band's scroll is the hull's angular rate to three figures (M1);
- on the desktop (lavapipe, 0.5.2-rc1 code, the release app's environment), the band follows its scroll at slope 0.88
  +- 0.02 (M2);
- on the Nova with Turnip (run 13), it follows at slope 1.02 +- 0.001 (M2b).

So R4 holds: the owner's sighting of 10-16 was on the release app before it had a custom driver (#1043), which is the
stock Qualcomm driver. The same week, #1038 and #1039 turned out to be stock-driver defects. Per the owner's rule of
10-17, the stock driver is not used or tested, so the stock-driver mechanism is not looked for.

Two differences between the sighting and these runs remain untested:
- the build type: the release package against run 13's `.debug` package. The desktop run used the 0.5.2-rc1 code
  with the release environment, but not an Android release build;
- the pose: the owner watched a longer stretch of the menu than any of these windows.

A Turnip run of the release package, when the Nova frees, closes the first. It is queued with the (a) measurement,
not on its own.

A second effect makes (c) easy to see even when the band turns. One turn takes about 34 minutes. From the menu camera
the band in view is the far side of the ring, about 38 units away, and it slides about 0.75 texels a second at lod 3.
The near hull turns at the same angular rate, but its surface is less than half a unit from the camera, so it visibly
streams. On a screen, the far band can read as still beside the near hull. That reading would hold on the console
too, though, so it does not explain a difference between the two.

**What (c) does to (a)'s hypotheses.** The ring's geometry never moves (M1: every vertex reads bone 0). So the cube
reflection R, which depends only on the eye and the normal, is fixed to the screen on every renderer, the console
included. The owner says every surface turns on the console, and that includes the bright layer. If the console's
layer is the reflection term (R1), its turning must come from its t2.r mask, which does scroll with c13. The cube part
then has to be close to uniform over the ring: one bright face, or a mirror that lands on one. A layer that turns
rules out a reading of (a) in which the cube's own detail makes the layer.

## Plan

1. ~~(c) off the stock driver~~: done (M2, M2b). R4 holds.
2. (a): which draw is the console's layer on, and what term makes it. Take apart `n6` (it runs over the hull's pixels
   too) and `n0` far enough to say whether either can lighten the hull.
3. (a): the software render of `n5` with R3's k, R1's forced face and mirror, and R6's q, judged by region against
   the pose-matched console photos. Then fix A7's crash and check the leaders on the desktop.

Before every desktop run that may crash, `df -B1G /mnt/c` must show at least 40 GB free. After every run, delete only
this run's own dumps in `wsl-crashes/`, by exact name, and log each crash here.
