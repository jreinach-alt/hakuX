# haloring1017 -- Halo CE main-menu ring (#939)

Lane: haloring1017 (Opus). Issue #939. Branch `lane/haloring1017` off master @ 9abd80e90c.
Brief: `/home/justin/hakux-work/briefs/haloring1017.md`.

The owner's goal is the ring the way the console draws it. Every surface turns with the ring, and the bright mottled
grey layer covers the whole ring, the unlit side included.

[lane.haloring1017] working: Step 0 committed; first measurement (c) off the stock driver.

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
| (c) | the inside surface does not rotate | Nova release app 0.5.1-rc1 on the **stock** driver only | open: first measurement |
| (a)+(c) | one cause or two | | open |
| (b) | bursts | fixed (A12) | only as far as a mechanism touches c13.w |

## Hypotheses

P is this lane's estimate before measuring. It moves from lane.xbox's ranking on A15: step 3 puts the reflection
term's ceiling, as hakuX computes it (cube texel x fresnel v1.rgb about 0.5 x t2.r x v1.a about 0.34), below the
console's brightness.

| id | hypothesis | symptom | P | row | hit | miss | instrument |
|---|---|---|---|---|---|---|---|
| R1 | the reflection term is wrong: R lands on the wrong face, or v1 scales it to near zero | (a) | 0.35 | A8, A10, A15 | the console look returns with the cube term forced to a bright face and v1 replaced | forcing it gives a coloured sheen, not grey crater mottling | `swr.py`-style software render of `n5` from the dg dump, and a desktop PSHDBG mode once A7's crash is fixed |
| R1b | ...the global cube mirror | (a) | in R1 | A10 | the mirrored R lands on face 0 or 4 (bright) over most of the hull at photo 5's pose | mirrored R still on dark faces | `vpemu.py` R per vertex, face histogram per mirror |
| R2 | another draw (`n4`, `n6`, `n0`) ignores its own scroll | (c) | 0.3 if (c) reproduces | new: searched x1 NOTES and git, nothing (A6 left them undone) | across consecutive frames, a per-frame change in the draw's guest state that its generated shader does not use | every per-frame change is used, and the output moves | `gdread.py diff` over consecutive frames, per draw |
| R2b | the guest computes `n4`'s scroll wrongly (a CPU defect, like (b)) | (c) | 0.1 | new: A12 measured c13.w on `n5` only | `n4`'s w rate (0.0000977/frame, ~8x below `n5`'s 0.00078) times its c13.x gives a different angular rate from `n5`'s | rates agree, so the guest means the band to turn at the hull's speed | `gdread.py draw` for c13 on `n4`/`n5` in two frames |
| R3 | v0.a non-zero on hardware: the final combiner lerps toward c0_8 (white) | (a), and a common wash of `n4`+`n5` | 0.2 | A14 | a software render with v0.a = k matches photo 5's brightness and keeps faint panel lines; the terrain band whitens by the same k | the panel lines vanish before the brightness is reached, or the band's whitening differs | software render against the pose-matched pair |
| R4 | the static inside surface was the stock driver | (c) | 0.25 | new: searched tracker #1038/#1039 (stock-driver defects that week), nothing on #939 | (c) absent in run 13's Turnip video and on the desktop | (c) present off the stock driver | run 13's video; a desktop clip; per-draw scroll in a `gd` dump |
| R5 | other combiner or final-combiner semantics, or the fast paths, for (a) | (a) | 0.1 | A3 (for (b) only), A20 | a fast-paths-off clip (A3's video) shows the layer, or a combiner op proves wrong against the hardware docs | | A3's video; reading `psh.c` against nv2a docs |
| R6 | unwritten VP outputs take the attribute registers' current values on hardware (Cxbx-R PR #2109); hakuX sets them to (0,0,0,1). The hull never writes oT0/oT1/oT2.zw (the PROJECT2D q), oT3.w, oB0, oB1 | (a), perhaps (c) | 0.1 | new: searched hakuX git and `vsh.c`, nothing; Cxbx-R PR #2109 | inline attribute values for v9-v12 (or the slots each output maps to) give q != 1, and a render with that q matches the console | q = 1 under that model | the `gd` dump's inline attribute values; a software render |

## Plan

1. (c) off the stock driver:
   - check run 13's driver from its log;
   - in run 13's video, track the inside band against the hull across the menu;
   - in a desktop `gd` dump (dg1 is on disk), compare per-draw c13 over consecutive frames for `n4`, `n6` and `n0`.
2. Take apart `n4`, `n6` and `n0`, the way A6 took apart `n5`.
3. (a): the software render of `n5` with R3's k, R1's forced face and mirror, and R6's q. Then fix A7's crash and
   check the leaders on the desktop.

Before every desktop run that may crash, `df -B1G /mnt/c` must show at least 40 GB free. After every run, delete only
this run's own dumps in `wsl-crashes/`, by exact name, and log each crash here.
