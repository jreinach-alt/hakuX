# haloring1017 -- Halo CE main-menu ring (#939)

Lane: haloring1017 (Opus). Issue #939. Branch `lane/haloring1017` off master @ 9abd80e90c.
Brief: `/home/justin/hakux-work/briefs/haloring1017.md`.

The owner's goal is the ring the way the console draws it. Every surface turns with the ring, and the bright mottled
grey layer covers the whole ring, the unlit side included.

[lane.haloring1017] blocked: (a) needs a console capture that a phone photo cannot give. (c) is answered: the stock
driver. The inside band turns on screen off it, at slope 0.88 on the desktop and 1.02 on Turnip (run 13, PurpleVK
confirmed from its log). (a) is made inside the hull draw if anywhere (M3). A software render reproduces hakuX's hull
to r 0.977 (M4), and it is the judge for the console photos.

Photos 1-4 hold no hull at their poses on the Nova dump (M10). On photo 5 the console's hull has hakuX's structure:
the same texture phase, the same cube mask, the same cube face layout (M5, M9, M10). Its extra brightness, face 0's
included, is inside what the photo's own dark-level lift at that place predicts. That lift is fitted on the space
background, which both machines draw the same (M11). No measurement shows the console drawing more than hakuX, and
nothing in hakuX's state for the hull is wrong. What would settle (a) is "Root cause and remedies" remedy 1, a
capture card on the console with frames judged against hakuX's framebuffer, or remedy 2, the owner viewing both
machines on one TV. Both are asked of lane.xbox (board request 10-18 06:35 PDT and its follow-up). The PR is ready as
analysis and tools.

## Attempt 1 did not finish: the turn cap

Attempt 1 ended at 15:57 PDT on the 301-turn cap, partway through M2b's last fit. It was not blocked and was not
waiting on anything. M1, M2 and M2b's clock were committed (948dc20f1c). The interrupted fit (`run13map.sh`) had
already written its `n4` rows and 80 of its `n5` rows to scratch (`hr/m2c/bandfit.tsv`). Attempt 2 read those rows
rather than running the fit again; they are reported under M2b.

## Attempt 2 did not finish: the turn cap again

Attempt 2 ended at 19:02 PDT on the 301-turn cap, right after committing M7 (0eef3e0548). It was not blocked and was
not waiting on anything. It spent its turns on photo 5 alone (M5-M7): one photo, at a pose where the hull is lit
everywhere, which cannot part the two accounts left. Attempt 3 (2026-10-18) starts with the four other console
photos, looking for the unlit hull, and commits after each measurement.

## Attempt 3 did not finish: the turn cap a third time

Attempt 3 (10-18 05:29-07:03 PDT) ended on the 301-turn cap. It was not blocked. Its last commit (60ce32f010, 06:33)
holds M8, M9 and the board request. After that the Nova dump landed (06:39), and attempt 3 started M10 without
committing it: three new tools (`faceedge.py`, `glarefit.py`, `framepick.py`), a frame-rate fix in `vidpose.py` (the
new run's video is on a 120/1 base, not 59.94), an outside-the-photo mask in `posefit.py`, and `margin=`/`exclude=`
in `photocal.py`. Their outputs sat in scratch only (`hr/sw/n14`). Attempt 4 commits the tools first, reads those
outputs instead of re-running them where they are complete, and commits after every measurement.

## Attempt 4: the last, and how it ends

Attempt 4 (10-18 07:38 PDT onward) committed attempt 3's tools, then M10 (photos 1-4 on the Nova dump; glare; cube
edges), then M11 (the background's gain field). It ends with the PR ready and (a) blocked on an owner-side
instrument (see the top line), not on the turn cap. Nothing is left uncommitted.

What is still open, exactly:
- (a)'s cause. No measurement shows a difference that is the console's and not the photo's or the display's.
- The lane.xbox board request (10-18 06:35) and its follow-up are unanswered: the capture card, the same-TV view, and
  the #939 comment for (c).
- A7's PSHDBG crash on the desktop. It is not needed for (a) unless a capture shows a gap. Desktop runs stay paused
  under 40 GB free on C: (32 GB at the end of attempt 4).

The next lane, if a capture lands, should not re-run photos 1-5. It should pose the capture's frames with
`posefit.py` against a fresh `gd` dump at the same menu time, render with `hullsw.py` (add `n6` first: M10), and
calibrate on the overlays with `photocal.py`. A capture card needs no `gainfield.py` correction, which is the point.

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
| (a) | bright mottled grey layer missing over the whole ring | desktop lavapipe; Nova run 13 | **open, and not shown by any measurement.** It is made in `n5`, if anywhere (M3). On photo 5, the one console image with a dump at its pose, the console's hull is hakuX's structure (M5, M9, M10). Its extra brightness is inside what the photo's own dark-level lift at that place predicts (M11, R11 0.5). The owner's by-eye account may be the display (R13 0.3). A real gap up to about hakuX's own dark-face level fits inside the photo's error (R10, R12, R5 together about 0.2). See "Root cause and remedies" |
| (c) | the inside surface does not rotate | Nova release app 0.5.1-rc1 on the **stock** driver only | **the stock driver (R4)**: the band turns in the guest (M1), on the desktop (M2, slope 0.88) and on Turnip (M2b, slope 1.02). See "The account of (c)" |
| (a)+(c) | one cause or two | | two. (c) is the driver; (a) reproduces on lavapipe and Turnip, so it is the emulator's |
| (b) | bursts | fixed (A12) | only as far as a mechanism touches c13.w |

## Hypotheses

P is this lane's estimate before measuring. It moves from lane.xbox's ranking on A15: step 3 puts the reflection
term's ceiling, as hakuX computes it (cube texel x fresnel v1.rgb about 0.5 x t2.r x v1.a about 0.34), below the
console's brightness.

| id | hypothesis | symptom | P | row | hit | miss | instrument |
|---|---|---|---|---|---|---|---|
| R1 | the reflection term is wrong: R lands on the wrong face, or v1 scales it to near zero | (a) | 0.35 -> 0.1 (M6: a bright face everywhere, with the fresnel, adds nothing over D) -> 0.03 for the wrong face (M10: the console steps at hakuX's 0\|5 edge and not at the 3\|5 edge); a wrong scale is R12 | A8, A10, A15 | the console look returns with the cube term forced to a bright face and v1 replaced | forcing it gives a coloured sheen, not grey crater mottling | `swr.py`-style software render of `n5` from the dg dump, and a desktop PSHDBG mode once A7's crash is fixed |
| R1b | ...the global cube mirror | (a) | in R1 -> 0.03 (M6: none of 48 signed axis permutations beats the identity) -> 0.01 (M10: the console steps at hakuX's 0\|5 cube edge) | A10 | the mirrored R lands on face 0 or 4 (bright) over most of the hull at photo 5's pose | mirrored R still on dark faces | `vpemu.py` R per vertex, face histogram per mirror |
| R2 | another draw (`n4`, `n6`, `n0`) ignores its own scroll | (c) | 0.3 if (c) reproduces -> 0.02 (M2, M2b: `n4` follows its scroll; `n6` has none by design) | new: searched x1 NOTES and git, nothing (A6 left them undone) | across consecutive frames, a per-frame change in the draw's guest state that its generated shader does not use | every per-frame change is used, and the output moves | `gdread.py diff` over consecutive frames, per draw |
| R2b | the guest computes `n4`'s scroll wrongly (a CPU defect, like (b)) | (c) | 0.1 -> 0.02 (M1: missed; the rates agree to three figures, on Turnip, run 13) | new: A12 measured c13.w on `n5` only | `n4`'s w rate (0.0000977/frame, ~8x below `n5`'s 0.00078) times its c13.x gives a different angular rate from `n5`'s | rates agree, so the guest means the band to turn at the hull's speed | `gdread.py draw` for c13 on `n4`/`n5` in two frames |
| R3 | v0.a non-zero on hardware: the final combiner lerps toward c0_8 (white) | (a), and a common wash of `n4`+`n5` | 0.2 -> 0.1 (M6: v4 is 2 components on both draws, so the premise holds; but the floor is inert at this pose, a lerp leaves the lower hull's texture-led pattern unexplained, and one k does not fit both draws' levels) | A14 | a software render with v0.a = k matches photo 5's brightness and keeps faint panel lines; the terrain band whitens by the same k | the panel lines vanish before the brightness is reached, or the band's whitening differs | software render against the pose-matched pair |
| R4 | the static inside surface was the stock driver | (c) | 0.25 -> **0.9** (M2, M2b: hit) | new: searched tracker #1038/#1039 (stock-driver defects that week), nothing on #939 | (c) absent in run 13's Turnip video and on the desktop | (c) present off the stock driver | run 13's video; a desktop clip; per-draw scroll in a `gd` dump |
| R5 | other combiner or final-combiner semantics, or the fast paths, for (a) | (a) | 0.1 | A3 (for (b) only), A20 | a fast-paths-off clip (A3's video) shows the layer, or a combiner op proves wrong against the hardware docs | | A3's video; reading `psh.c` against nv2a docs |
| R7 | `n5` follows `n4` in the same shader with only c13 changed; the second draw's constants never reach the GPU | (c) | 0.05 -> 0 off the stock driver (M2, M2b: each scrolls at its own rate) | new (M1). Code read: `vsh.c:1213` copies all of c[] every draw; `shaders.c:2108-2138` marks the upload by dirty flag or by layout hash, so a c13 change is caught either way | on screen, one of `n4`/`n5` scrolls at the other's rate or not at all | each scrolls at its own c13.w rate | M2 (`bandfit.py`) |
| R6 | unwritten VP outputs take the attribute registers' current values on hardware (Cxbx-R PR #2109); hakuX sets them to (0,0,0,1). The hull never writes oT0/oT1/oT2.zw (the PROJECT2D q), oT3.w, oB0, oB1 | (a), perhaps (c) | 0.1 -> 0.03 (M5: t0 and t2.r land on the console at the dump's own scale and phase, which a q != 1 would move) | new: searched hakuX git and `vsh.c`, nothing; Cxbx-R PR #2109 | inline attribute values for v9-v12 (or the slots each output maps to) give q != 1, and a render with that q matches the console | q = 1 under that model | the `gd` dump's inline attribute values; a software render |
| R8 | the cube's LOD: on hardware the hull's reflection samples a coarse mip of the 64x64 cube (near each face's mean) where hakuX samples a fine one, so the reflection is t2.r times a near-constant over the whole hull, not only where a bright face is hit | (a), and (b)'s flicker source | 0.3 (new, M6) -> 0.01 (M7: each face's mean is the same at every mip, and the screen LOD is 0) | new: M6's t2.r-without-cube fit | the reflection with the cube at a coarse LOD fits the console's rank and level better than at hakuX's LOD | no LOD bias raises the fit over D + c·t2.r's | `termfit.py` with an LOD bias on t3 |
| R9 | the fresnel oD1 differs on hardware (its inputs: v5/v6's formats, or an unwritten register), so oD1.rgb·oD1.a is near-constant | (a) | 0.15 (new, M6) -> 0.2 (M7: on the pixels where t2.r and D disagree, the excess follows t2.r) -> 0.07 (M9: hakuX's mask t2.r·oD1.rgb·oD1.a fits best, a flat or t2.r-only mask worse; the pooled t2.r loading is one screen region, face 3, flat in t2.r inside it) | new | a near-constant oD1 with the cube at hakuX's or a coarse LOD fits the console | the fresnel-shaped term fits as well as a flat one | `termfit.py`; the VP's oD1 inputs read from the dump |
| R10 | the hull's diffuse counts for ~1.4x more on hardware (the detail map t1 at a higher level, or the s6 sum t0·t1 + t0·t1 scaled differently) | (a) | 0.3 (new, M7: D x 1.5 + X0 is the best joint fit; the hull's gain is flat over hakuX's mid-range) -> 0.3 (M9: rejected pooled at 95%, but inside each cube face the console is hakuX's own pattern at 1.07-1.50x; the gain is not one constant across faces) -> 0.15 (M10: faces 3 and 5's gain is mostly the photo's own lift at their place, R11; what is left is face 0's 1.5x, where D and X0 are collinear, so a gain there is R12's as much as R10's) -> 0.07 (M11: face 0's excess is inside what the background's gain field at its place predicts) | M7 `texregs.py`: no LOD bias or clamp; t1's mips cap the lift at x1.39 | the unlit hull stays dark on the console, and a desktop render with D x k matches photo 5 | the console lights the unlit hull | a console photo of the unlit side; `hullsw.py` with D x k |
| R11 | part of photo 5's hull excess is the photo, not the console: the camera or TV reads brighter on the right, where cube face 3 falls at that pose | (a)'s size, not its presence | 0.4 that it is part, 0.05 that it is all (new, M9: the background reads +0.013, and +0.046 in its bright half, at x 480-640 against -0.03 at the left; face 3's flat +0.115 sits there) -> **0.7 that it is most of faces 3 and 5's lift**, 0.15 that it is all of (a) on photo 5 (M10: the background at face 3's place and level is lifted as much as face 3, 0.177 to 0.267 against 0.150 to 0.270; the lift is smooth across the 3\|5 cube edge, step -0.027, CI -0.076 to +0.019; not veiling glare, whose coefficient is negative) -> **0.5 that it is all of photo 5's hull excess** (M11: a gain field fitted on the background alone predicts the excess on faces 0 and 3 inside its interval, and face 5 at its low edge; level alone does not; the interval still leaves room for a layer about as bright as hakuX's own face 3) | new | at photos 1-4 the excess follows the photo's position, not the cube face or the lighting | the excess follows a face or a term wherever it falls on the photo | M10: photos 1-4 hold no hull at their poses, so the test ran on photo 5's background and cube edges instead (`glarefit.py`, `faceedge.py`) |
| R12 | the reflection's amplitude is about 2x hakuX's on hardware (oD1, the cube texel or the stage-7 product), with hakuX's face layout and mask | (a) on the bright face | 0.2 (new, M10: the console's step at the 0\|5 edge is 1.7x hakuX's, at hakuX's place; M9's face-0 fit 1.95x). Against: no input or combiner word in `n5`'s state gives a factor of 2 (c4.w 2, c12.w 1, specular alpha passed, two-side off), and a phone's local tone mapping sharpens steps -> 0.08 (M11: face 0's excess is inside the background gain field's prediction; the step's excess interval reaches zero; the profile across the edge is a sharpening camera's overshoot and undershoot, and glarefit's 6 px halo is negative) | new | a fixed-exposure console capture shows the bright face's reflection at about 2x hakuX's, against an overlay of known level | the capture's reflection matches hakuX's | the console clip (board request to lane.xbox) |
| R13 | the owner's by-eye difference is the display. hakuX draws the hull's values as the console does. The console's TV, through its dark-level response (and an off-axis view), shows the unlit hull's crater texture, 2·t0·t1·oD0 at fb 0.07-0.15 in hakuX. The screen hakuX was watched on shows it near black | (a) as the owner saw it | 0.3 (new, M11). For: photo 5's hull is hakuX's under the photo's own dark-level lift (M11); inside each face it is hakuX's pattern (M9); the face layout is hakuX's (M10); nothing in `n5`'s state gives a factor. Against: the owner calls the layer bright and the sprite. hakuX's reflection on the dark faces is about fb 0.02-0.03 (X0 on face 5, M10), too faint for any display to show as a pattern. And whether the owner watched hakuX on the console's TV is not recorded | new | hakuX on the console's own TV (HDMI from the Thor or a desktop), or one capture card on both, shows the same unlit hull | the same display still shows the console's layer and not hakuX's | the owner's comparison on one display; a capture card's frames against hakuX's framebuffer |

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

### M3: (a) is made inside `n5` (run 13 f540, `gdread.py draws`, blend words)

Frame 540 has 94 draws and no skips. The draws that touch the hull's pixels, in order:

| draw | count | what | can it lighten the hull? |
|---|---|---|---|
| `n0` | 1227 | planet, additive | no: it draws before the hull, which has blend off and overwrites it |
| `n1` | 51 | additive | no: before the hull |
| `n2`, `n3` | quads | alpha | no: before the hull |
| `n4` | 864 | the band, the hull's shader | it is the band |
| `n5` | 4362 | the hull, blend off (0x542) | it is the hull |
| `n6` | 510 | inner rim, DST_COLOR x ZERO | no: a multiply, it can only darken |
| `n7` | quad | multiply by a final rgb of 1 | no: leaves the image unchanged |
| `n8`-`n93` | quads | the menu's overlays | not over the hull except the logo, menu text and reticle |

So the console's layer is a different value of `n5`'s own output. Nothing else could add it.

`n5`'s inputs, from the generated VS (`vsh_48c74844.glsl` slots 0-44) and the frame's constants:
- oD0.rgb = max(N.z, 0)·(1, 1, 1) + max(-N.z, 0)·(0.604, 0.573, 0.761) + (0.271, 0.278, 0.388). It is at least 0.27
  everywhere, so the hull's darkness on hakuX comes from the textures, not from the lighting.
- oD1 = (normalize(E)·N)·(0.620, 0.643, 0.376, 0.8) + (0.380, 0.357, 0.624, 0.2): 1 face-on, (0.38, 0.36, 0.62, 0.2)
  grazing.
- oD0.w = v4.z. v4 is the texcoord, two shorts (S1 x 2), so its z is the missing-component default, 0.

The final combiner (SPECFOG0 0x340f010d, SPECFOG1 0x0c111800, SPECFOGFACTOR0 0xffffffff) is
`(1 - v0.a)·r0 + v0.a·white + r1`, with r1 = 0. So v0.a is a lerp toward white: R3's k, where a nonzero v4.z would
put a white wash over the whole ring, lit and unlit sides alike.

The combiner (`psh_48c74844.glsl` 362-403, the words in `combwords.py`):
- r0 = 2·t0·t1·(oD0 + t2.g) + cube(R)·oD1.rgb·t2.r·oD1.a;
- each step is clamped to [-1, 1];
- t2.b lerps toward a white change colour, so it has no effect.

### M4: a software render of `n4`+`n5` that reproduces hakuX (`hullsw.py`, `swcheck.py`, `combwords.py`)

`hullsw.py` renders the band and the hull from a `gd` dump and RAM in numpy:
- the VS as generated;
- rasterisation with a z-buffer and the dump's cull, perspective-correct;
- the four textures from RAM, trilinear, with the LOD from each pixel's footprint; the cube with GL face orientation;
- the combiner as generated, with the constants read from the frame's registers.

It refuses a draw whose combiner words differ from the transcribed ones. It writes every term per pixel.

**Control:** desktop dump m2a, f290, against hakuX's own image of that frame, with the menu overlays kept out
(91,492 hull px):

| measure | value |
|---|---|
| render - image, mean (r, g, b) | +0.002, -0.001, -0.002 |
| luminance r, per pixel / 4 px blur / 16 px blur | 0.977 / 0.991 / 0.996 |
| best shift | (0, 0) |
| image ~ a·diffuse + b·reflection + c | a 0.998, b 0.979, c 0.001 |

So the render is hakuX's hull to within a few hundredths. Any term it is missing against the console is missing in
hakuX too, and swapping one term (k, the cube face, q, t1's strength) shows what hakuX would draw with that change.

### M5: console photo 5 in frame pixels, at its own pose and scroll (`photoreg.py`, `posefit.py`, `photojudge.py`)

Photo `console5-V-hull-right.jpg` (owner, 10-16) is put into the 640x480 frame in three steps, each checked by a
measure the step before did not fit.

1. **Registration on the overlays.** The menu's 2D overlays (HALO logo, menu text) are the same picture on both
   machines wherever the ring is. The template is the per-pixel minimum over run 13's 120 video frames
   (v00794-v01986), which keeps the overlays on black. A quadratic warp (12 terms) is fitted by Lucas-Kanade on the
   template's edge pixels, from a blur of 8 px down to 1. NCC at the finest level is 0.755 on the logo rectangle and
   0.716 on the menu text. A first try on a full hakuX frame was pulled 14 px off by the ring's own edges; the
   overlay-only template fixed that.
2. **Pose by silhouette.** The ring's geometry never moves; the camera does. Rasterising `n4`+`n5` at each frame of run
   13's dump against the photo's ring mask (Otsu threshold, overlays out), the best IoU is 0.791 at f506. f504-f510
   are all >= 0.785. f543, the frame used before, is lower.
3. **Scroll phase, an independent check.** The hull's textures scroll by c13.w at 0.00078 per frame, one t0 period
   every ~43 s. Nothing above fixed the photo's phase. Scanning a phase d added to oT0.x over the whole period
   (500 steps), the console hull's luminance (3 px blur, overlays out, 65,106 px) correlates with each scrolled
   texture as follows:

| term at the hull's pixels | r at the best d | best d | mean r over d (sd) | z of the peak |
|---|---|---|---|---|
| t2.r (the reflection mask) | 0.635 | -0.001 | 0.375 (0.078) | 3.3 |
| t0 (the base map) | 0.566 | -0.001 | 0.348 (0.060) | 3.6 |
| t1 (detail, 10x finer) | 0.279 | flat | 0.260 (0.013) | 1.5: below the photo's resolution |
| hakuX's final, as rendered | 0.592 | (d = 0 only) | | |

   The peak is one sharp bump (r drops to 0.53 at d = +-0.006) at the dump's own phase, d = 0. So the photo and f507
   share the scroll phase as well as the pose. The menu's scroll runs on the same clock as its camera loop, and the
   registration and the pose are right: a wrong pose would not land the texture on its own phase.

So photo 5 can be compared with the render at f507 pixel for pixel. Two first readings:
- **The console's hull shows the same textures as hakuX's**: the crater streaks of t0 and t2.r line up in a zoom of
  the upper hull. The layer is not a new picture, it is these maps drawn brighter and greyer.
- **The console follows t2.r better than hakuX's own output does** (0.635 against 0.592). t2.r is the mask of the
  reflection term, which hakuX draws only where the cube is bright (the hull's left edge at this pose). That is R1's
  reading, and the owner's ("the sprite ... applied across the entire ring, including the dark portions").

Mean luminance by region (photo units for the console; framebuffer units for the render):

| region | px | console photo | hakuX final | hakuX diffuse | hakuX reflection |
|---|---|---|---|---|---|
| hull, y < 300 | 84,150 | 0.370 | 0.139 | 0.106 | 0.033 |
| hull, y >= 300 | 21,367 | 0.438 | 0.164 | 0.144 | 0.020 |
| band (`n4`) | 10,762 | 0.703 | 0.565 | 0.384 | 0.182 |

The photo's tone curve (`photocal.py`, from the flat parts of the overlays over space) is steep in the mid-tones
(green: framebuffer 0.21 -> photo 0.34, 0.32 -> 0.50, 0.56 -> 0.73) and the camera clips blue above 0.21. Read
through it, the console's band is about hakuX's (photo 0.70 ~ framebuffer 0.55, hakuX 0.565) while the console's hull
is about 1.6x hakuX's (photo 0.37-0.44 ~ framebuffer 0.23-0.26, hakuX 0.14-0.16). That curve rests on a few hundred
overlay pixels per bin, so it sets the size of the gap, not the model; the model is decided by pattern (M6).

### M6: what the console's hull is made of (`termfit.py`, `floorfit.py`; controls `vidratio.py`, `edgecmp.py`)

**Controls first.**
- `hullsw.py` now clips triangles at the near plane (w >= 1e-4) as the GPU does. Before, it dropped every triangle
  with a vertex behind the eye: `n4` 91 of 288, `n5` 458 of 1440 at f504. M4's control at f290 is unchanged: r 0.977,
  render - image +0.002/-0.001/-0.002, fit a 0.998 b 0.979.
- `vidratio.py`, the render at f504 against run 13's own Turnip video at that time (v01806). Video / render luminance
  ratio:

  | draw | median | p10 | p90 | r |
  |---|---|---|---|---|
  | band | 0.99 | 0.82 | 1.09 | 0.906 |
  | hull | 1.03 | 0.75 | 2.11 | 0.402 |

  The hull's r is low because the hull's fine texture is below the video's resolution (greyscale, compressed). Under 4%
  of either draw has a ratio below 0.6. So at photo 5's pose the render is what hakuX draws on Turnip: no later pass
  darkens the hull and no geometry differs.
- `edgecmp.py`: the render's band/hull edges sit on hakuX's video edges and on the console's. I first read a narrow
  bright strip on the console as a narrower band (a geometry difference); it is the band's own darker inner edge.
  Retracted.

**Pattern (`termfit.py`, f507, 3 px blur, 65,106 hull px).** The console's tone curve is unknown in detail, so models
are compared by rank (Spearman) r with the console's luminance; a monotone curve leaves ranks alone. Each model is
D + c·X, with D = 2·t0·t1·(oD0 + t2.g), and c scanned for its best r:

| model | c | rank r: all | upper hull | lower hull |
|---|---|---|---|---|
| hakuX as drawn, D + X0 | 1 | 0.600 | 0.627 | 0.348 |
| D alone | 0 | 0.646 | 0.696 | 0.337 |
| D + c·X0 (the reflection rescaled) | 0.22 | 0.664 | 0.709 | 0.355 |
| D + c·t2.r·oD1.rgb·oD1.a (cube = 1) | 0.05 | 0.646 | | |
| D + c·t2.r·oD1.a | 0.05 | 0.649 | | |
| D + c·t2.r (no cube, no fresnel) | 0.22 | **0.669** | 0.709 | **0.445** |
| t2.r alone | | 0.633 | | 0.516 |
| t0 alone | | 0.613 | | 0.538 |

- **The console's hull pattern is hakuX's diffuse term.** Adding the reflection at hakuX's strength lowers the fit
  (0.646 to 0.600).
- **No cube orientation helps.** Over the 48 signed axis permutations of R, the best (+x-y+z) reaches 0.664; the
  identity ranks 3rd, also at 0.664. Forcing a bright cube everywhere, with the fresnel, adds nothing over D. So R1's
  forced face and R1b's mirror do not produce the console.
- **The textures' t2.r, without the cube or the fresnel, is the one addition that helps**, and most on the lower hull
  (0.337 to 0.445), where t2.r and t0 alone each beat hakuX's whole model. Where hakuX's shading darkens the hull, the
  console's pattern is the textures', not the shading's.

**R3 by pattern and level (`floorfit.py`, f507).** The dump's vertex array records read v4 as type 1 (S1), 2 bytes, 2
components on both `n4` and `n5`, so v4.z is the missing-component default (0 in hakuX) on both draws. The VP uses it
as oD0.w (the final combiner's lerp toward white) and as the floor of both lighting max()es. hullsw rendered with
v4.z = k:

| k | hull rank r (all / lower) | hull: render / floor alone | band: render | console in fb units (hull / band) |
|---|---|---|---|---|
| 0 | 0.588 / 0.349 | 0.133 / 0.133 | 0.531 | 0.245 / 0.643 |
| 0.1 | 0.599 / 0.375 | 0.228 / 0.142 | 0.578 | |
| 0.2 | 0.594 / 0.372 | 0.316 / 0.145 | 0.625 | |
| 0.35 | 0.592 / 0.370 | 0.445 / 0.146 | 0.695 | |

- **The floor barely acts**: +0.01 in level and in rank r. At this pose the visible hull is already lit above any
  small floor (oD0 ~0.85, M3), so the lower hull's texture-led pattern is not the floor.
- **The console sits ~0.11 above hakuX on both draws**, through the L curve of `cal5fb` (the desktop framebuffer's
  overlays). By region: upper hull +0.114, lower hull +0.108, band +0.112. Between the upper hull and the band the
  slope is 0.995. A lerp toward white adds k·(1 - x), less to the brighter band, so one k cannot fit both: the hull
  needs k 0.13, the band k 0.24. An addition that is the same on both draws fits; a lerp fits only if the curve is
  off by about 0.05 in the band's range.
- The console's colour is not readable yet. The overlays that calibrate the camera are tinted, so blue against green
  depends on the overlays' own colour. Uncalibrated, the console's hull is equally blue-grey (b/g ~1.2-1.3) at every
  level of hakuX's render, where hakuX runs from green (0.80) to lavender (1.17).

The two readings point the same way: the console adds a texture-shaped term over the whole hull, about 0.22·t2.r in
hakuX's units (mean ~0.11), not gated by the cube's bright faces or by the fresnel. That is the owner's description:
the "sprite" (t2.r, the reflection's mask) "applied across the entire ring, including the dark portions". Within
hakuX's own combiner, the term that carries t2.r is the reflection, cube(R)·oD1.rgb·t2.r·oD1.a. So the console's
reflection is t2.r times something near-constant and non-zero: the cube's lookup or the fresnel differs, not the
mask. M7 tests the cube's LOD (a coarse mip is the face's mean everywhere) and the fresnel's inputs.

### M7: the level gap, the photo's smear, and what the hull's state rules out (f507; `transfer.py`, `excessmap.py`, `regvalid.py`, `chromafit.py`, `reflfit.py`, `detailfit.py`, `texregs.py`, `t1scale.py`, `excessreg.py`, `normcheck.py`, `termpanel.py`)

**A better curve.** `cal5v1806.npz` is `photocal.py` taken on the space background of hakuX's own Turnip video frame
at the photo's pose (v01806, f504.3), so it has data across the hull's whole range (fb 0.08-0.33), where the overlay
curve (M5, M6) had none. Photo L -> fb: 0.07 -> 0, 0.21 -> 0.14, 0.37 -> 0.25, 0.55 -> 0.33, 0.68 -> 0.44-0.55
(flat: the camera clips there), 0.96 -> 0.91-0.97.

**The photo's smear (`regvalid.py`).** `photoreg.py` clamps its sample position to the photo. Photo 5 ends near frame
x 587, so every frame pixel right of it took the photo's edge column, smeared. That was **13.9% of the hull** (14,625
of 105,517 px) and none of the band, in every M5-M6 hull statistic. `overlay_min_v.png` masks it; M7's numbers use it.
M6's rank table moves by a few hundredths (hakuX as drawn 0.600 -> 0.707 all; D + c·X0 best c 0.22 -> 0.37) and none of
its orderings change.

**The gap, per draw (`transfer.py`, masked).** Console against hakuX's render, in fb units, binned by hakuX's value:

| draw | core px | console mean | hakuX render | hakuX video | fit console = g x hakuX + b | r per pixel |
|---|---|---|---|---|---|---|
| hull `n5` | 51,515 | 0.205 | 0.147 | 0.147 | g 1.40, b +0.010 | 0.730 |
| band `n4` | 4,890 | 0.578 | 0.532 | 0.511 | g 0.83, b +0.176 (ratio 1.44 at hakuX 0.2 falling to 1.01 at 0.84) | 0.671 |

The hull's ratio is about flat from hakuX 0.10 to 0.21 (1.42-1.75) and drops in the darkest bin (0.78 at hakuX 0.07)
and the brightest (1.28). So on the hull the console is a **gain, ~1.4x**, not an addition: an added layer would lift
the darkest bin most. The band is near 1.0 except in its dark parts. `excessmap.py` (`excess507v.png`): the hull's
excess grows down the frame (rows 0-150 +0.028, 150-250 +0.053, 250-350 +0.114) and with each of D and t2.r by quartile
(D: +0.007, +0.056, +0.095, +0.075; t2.r: +0.006, +0.055, +0.077, +0.094). Where either is lowest, the console
matches hakuX.

**Colour (`chromafit.py`).** Read back per channel through `cal5v1806`'s R/G/B curves, the console's hull is (0.289,
0.185, 0.183) against hakuX's (0.136, 0.153, 0.146). By channel the hull ratio is R 2.13, G 1.21, B 1.25 and the band's
R 1.25, G 0.98, B 0.98. The red curve is flat in the darks (photo R 0.075-0.163 for fb 0-0.2, because the space
background has almost no red), so the red reading is the curve, not the console. In G and B, which are well
determined, **the hull is ~1.23x hakuX and the band ~0.98x**.

**Re-fits on the masked overlay.**

| `reflfit.py`: D + c·(a part of X0), c scanned | best c | rank r: all / upper / lower / band | level at c = 1, hull / band |
|---|---|---|---|
| full X0 (cube, oD1.rgb, oD1.a) | 0.37 | 0.748 / 0.822 / 0.359 / 0.423 | 0.147 / 0.532 |
| cube only | 0.20 | 0.745 | |
| t2.r only (no cube, no fresnel) | 0.30 | 0.746 (lower 0.459) | |

Console: hull 0.219, band 0.554 in fb units. `detailfit.py` asks whether the detail map is the gap. hakuX's t1 on
screen has a mean of 0.310, and its LOD (lod1) runs p10/50/90 -0.04 / 1.31 / 3.66:

| t1 variant | rank r: all / upper / lower | level of D + X0 |
|---|---|---|
| as hakuX samples it | 0.707 / 0.774 / 0.348 | 0.147 |
| t1 = mip 5 everywhere (mean 0.423) | 0.636 | 0.188 |
| t1 = 0.5 (neutral) | 0.652 | 0.216 |
| t1's detail kept, scaled x 0.5/0.255 | 0.745 / 0.816 / 0.360 | 0.258 |

A neutral detail map gives the console's level (0.216 against 0.219) but loses rank. Keeping the detail and lifting
its mean gives both rank and too much level. **Two accounts now fit about equally**: the console's detail map counts
for more (D x ~1.4), and an extra t2.r-shaped reflection. `excessreg.py` puts them against each other on the hull core
(blur 3, L):

| model, no constant | coefficients | R² |
|---|---|---|
| D + X0 | 1.542, 0.923 | **0.561** |
| Dn (t1 = 0.5) + t2.r | | 0.548 |
| D + t2.r | 0.696, 0.418 | 0.539 |
| D + t2.r·oD1.rgb | | 0.524 |
| Dn + X0 | 1.033, 0.542 | 0.504 |
| Dn | 1.139 | 0.463 |
| D | 1.792 | 0.423 |

With a constant, D + X0 gives 1.69, 0.925, -0.019 (R² 0.564). D and t2.r correlate at 0.786 on this hull, so a joint
fit separates them only weakly. On the few pixels where they disagree:

| pixels | n | console | hakuX | ratio |
|---|---|---|---|---|
| t2.r high, D low | 269 | 0.314 | 0.218 | 1.44 |
| t2.r low, D high | 370 | 0.162 | 0.183 | 0.89 |
| both high | 11,065 | | | 1.44 (+0.096) |
| both low | 14,287 | | | 1.11 (+0.010) |

The excess follows t2.r, not D, but on 639 pixels. The best whole-hull model keeps hakuX's reflection as is (0.92) and
scales the diffuse by ~1.5.

**What the hull's state rules out.**
- **The combiner decode.** The eight stages and the final combiner, decoded by hand from the dump's words (CTL
  0x00011008: unique c0/c1 per stage), give hull = 2·t0·t1·(oD0 + t2.g) + cube(R)·oD1.rgb·t2.r·oD1.a with
  FC0 = 0xffffffff and no clamp or complement flags. That is `hullsw.py`'s `combine()` and `psh.c`'s output. In
  detail: s0 r0.rgb = t2.g, r1.rgb = t2.r, r0.a = t2.b (0); s2 r0.rgb = 1, r1.a = t2.r·oD1.a; s4 t3 = t3·v1, v0 = v0·r0;
  s6 t0 = t0·t1 + t0·t1 (a sum, no output scale); s7 r0 = t0·v0 + t3·r1.a. Final (SPECFOG 0x340f010d / 0x0c111800):
  (1 - v0.a)·r0 + v0.a·FC0 + r1, with r1.rgb = 0 from s5.
- **The texture registers (`texregs.py`).** Every stage of both draws: TEXCTL0 0x4003ffc0 (LOD clamp min 0, max
  15.996), TEXFILTER 0x02062000 (bias 0, trilinear min, linear mag, no signed channels), wrap on stages 0-2, clamp on
  the cube. `n5`: s0 1024x512 DXT1, 9 mips; s1 128x128 DXT1, 6 mips; s2 1024x512 DXT1; s3 64x64 DXT1 cube, 5 mips.
  `n4`: s0 2048x128; s1 4x4 X8R8G8B8, a constant 0.502 grey; s2 2048x128, whose g is 1.0 everywhere (the band is fully
  self-lit). **No bias or clamp moves the detail map's mip.**
- **The textures' contents.** The detail map t1's mip means are 0.255, 0.289, 0.323, 0.357, 0.391 and 0.423 (a Halo
  detail map fading toward 0.5; even its coarsest mip gives only x1.39 over mip 0). t0's are (0.189, 0.219, 0.161) at
  every mip; t2 r 0.30, g 0.19, b 0. No DXT1 3-colour (punch-through) block in hull t1, hull t0 or band t0; in t2,
  0.7% of blocks, with no texel on index 3. **The DXT1 decode is not it.**
- **The normals (`normcheck.py`).** Each vertex's decoded normal agrees with the mesh's own face normals: |dot|
  0.99-1.0 on 100% of vertices, under hakuX's decode only (the sign follows the winding). The hull's normals turn 22°
  (median) per edge and R 24° p50 / 71° p90, which is the geometry. Per vertex |R| is p50 27 on both draws; per pixel
  it is 20.75 on the band and 0.85 on the hull, because the visible hull is about 1 unit from the eye. A cube lookup
  ignores |R|.
- **The eye and constants.** c0-c7 and the bone matrix c60-c62 are identical on `n4` and `n5`. c4 = (0.826, 1.559, 0, 2)
  is the projection's eye (c0·eye + w = 0, and the same for c1 and c3). Depth w p50 10.7 on both.
- **R8, the cube's LOD.** The cube's faces have the same mean at every mip (face 0: 0.651 at mips 0-4; face 1 0.050,
  face 2 0.073, face 3 0.130, face 4 0.238, face 5 0.143). A coarse mip changes nothing on average, and the screen LOD is
  0 anyway. Pixel shares by face: hull +x 0.21, -y 0.30, -z 0.49; band +x 0.39, -x 0.04, +z 0.57. **R8 is refuted.**
- **R6, the unwritten outputs.** The dump's current inline attribute values at `n5` are v9 (0, 0.498, 1, 0), v10
  (1, 0, 0, 1), v11 (3.1, 479.9, 0, 1) and v12 (3.1, 480.1, 0, 1): leftovers of a 2D draw. If the unwritten zw of
  oT0-oT3 took v9-v12's, as in Cxbx-R's order, then oT1-oT3's q would be 1, hakuX's value already. oT0's would be 0,
  which would wreck t0, and M5 matched t0 at the dump's own scale and phase. R6 stays at 0.03.
- **t1 at another scale (`t1scale.py`).** The hull's VP sets oT1 = oT0·c12.xy with c12.xy = (10, 10). Re-rendered with
  c12.xy = 1, 2, 5 and 10 (t1's LOD p50 -2.48, -1.48, -0.15 and 0.85). The console's structure was then correlated by
  band-pass (box r1 - r2) with each term, upper / lower hull:

  | band | hakuX final | t0 | t2.r | t1, any scale |
  |---|---|---|---|---|
  | 8-24 px | 0.876 / 0.783 | 0.816 / 0.760 | 0.746 / 0.727 | -0.2 to +0.13 |
  | 3-10 px | 0.34 / 0.39 | | | |
  | 1-4 px | nothing correlates | | | |

  **The console's mid-scale structure is hakuX's own final, led by t0.** The detail map's own pattern is not visible
  in the photo at any scale, so its level, not its pattern, is the open question.

**Caveat on the pair images.** The hakuX halves of `pair5`, `hullzoom5` and `ringzoom1` were captured on 10-16. They
are likely the stock driver and are not judged here: only run 13's Turnip video and the `hullsw.py` render are.

**Where (a) stands.** Two accounts fit photo 5 about equally, because at its pose the hull is lit everywhere
(oD0 ~0.85, M3):
- **R10**: the console's diffuse is ~1.4-1.5x hakuX's, through the detail map counting for more. No register explains
  that, and the textures' mips cap it at x1.39.
- **R1/R9**: an extra reflection-like term, t2.r times something near-constant, not gated by the cube's bright faces.

They part on the ring's **unlit side**. There D is dark whatever t1 is, so D x k stays dark. An added t2.r term lights
it, as the owner describes ("applied across the entire ring, including the dark portions"). The next measurement is a
console photo at a pose where the unlit hull shows.

### M8: photos 1-4 posed on run 13's video; no dump on disk reaches their poses (`photoreg.py` affine, `vidpose.py`, `deskrun.py` chain)

**Registration.** Photos 1-4 are warped to frame pixels the way M5 warped photo 5, on the menu's overlays. NCC per
overlay rectangle:
- photo 1: 0.827 and 0.870;
- photo 3: 0.853 and 0.925;
- photo 2: attempt 2's `reg2`;
- photo 4: 0.79-0.93. The ring crosses most of photo 4's overlays, so it is fitted affine only (`affine=1`, init
  457,666,1.62,1.15, levels 4,2,1). It uses seven rectangles on menu-text pieces clear of the ring.

**Pose.** `vidpose.py` takes the luminance NCC of each warped photo against every frame of run 13's Turnip video
(59.94 fps) over the ring's region:

| photo | the view | run 13 video t | NCC |
|---|---|---|---|
| 4 | ring vertical, planet left | 45.479 s | 0.910 |
| 3 | planet at the bottom, ring upright | 51.718 s | 0.857 |
| 2 | ring across the top, planet lower right | 54.054 s | 0.902 |
| 1 | arc at the lower left, upright | 56.307 s | 0.823 |
| 5 | M5: f506 of run 13's dump | 30.16 s | |

**No dump on disk covers 45-57 s:**
- run 13's dump covers 13.3-35.3 s;
- m2a's covers 8.6-20 s;
- m8a's covers 5.4-38.2 s (its f010 matches 5.989 s at NCC 0.970, its f599 matches 38.222 s at 0.985).

So at photos 1-4, which draw makes each pixel is unknown, and so are its D, X0 and t2.r. Those photos cannot yet be
judged by number. `unlitjudge.py` is the judge for when they can. On the hull and band core pixels (as `transfer.py`
picks them) it fits three models to the console, read in fb units through the photo's calibration:
- R10: c - X0 = g·D + b;
- R1/R9: c - D - X0 = k·t2.r + b;
- free: D, X0, t2.r and a constant.

It then bins the pixels by oD0, D and X0, and reports the two sets that part the accounts: D low with t2.r high, and D
high with t2.r low.

**By eye**, run 13's frame at each pose beside the photo:
- photos 1 and 2: the console's band (`n4`) is brighter and whiter than hakuX's;
- photo 2: the strip under the band is dark on both machines;
- photo 3: the edge-on strip is a brighter grey on the console.

None of these is attributed. Photo 2's dark strip could be the hull's unlit side, which would favour R10. It could
equally be the inner rim `n6`, whose multiply mask says nothing about either account. No P moves on them.

**The desktop run m8a** (`deskrun.py`, after74, 600 frames with images, `chain=2`):
- It exited 0, with no crash and no `wsl-crashes` dump.
- It wrote three dumps of 600 frames at about 20 fps, 30 s each. Each dump opened deletes the previous dump's files
  (`renderer.c` `fdump_clear_previous`), so only dump 3 survived. `deskrun.py` now moves each closed dump to `dump/dK`
  before writing the next marker.
- Dump 3 opened at +136 s and covers run 13's 5.4-38.2 s. m2a's dump opened at +74 s and began at 8.6 s. It is the
  same camera path, but on the desktop the path's place is not a function of the emulator clock. Aiming a desktop dump
  at a pose takes either a chain long enough to pass it, or a dump marker written on seeing the pose.

**C: after m8a: 38 GB free** (`df -B1G /mnt/c`), under the 40 GB floor. The run's dump went to `/tmp`, which lives on
the WSL disk image, and that image grows on C:. **Desktop runs that may crash are paused** until C: is back at 40 GB
or more, which takes the owner's side (moving files inside WSL does not shrink the image). This holds back A7's
PSHDBG fix and the leaders' desktop check.

**What gets the poses: a Nova `gd` dump aimed by run 13's clock.** It uses run 13's ref and env with
`XEMU_FRAME_DUMP=600,gd,noimages,after64,cap2400`. If the Nova keeps run 13's clock, its f0 lands near video 41.3 s and
its 600 frames (0.0334 s each in run 13) reach about 61.3 s, which covers the four poses with 4-5 s to spare at each
end. The run's own video
(35-95 s) is pose-matched to the photos again, and its frames map to the dump by M2b's clock fit. The request is
under "Waiting" below.

**That request failed at install** (1792328946-haloring1017-2104088, 10-18 06:16). It never reached the title. Its ref
5d4b689ed9 predates 8b49e941bd (versionCode 10). The Nova carries master's build, and the dispatcher installs with
`adb install -r` without `-d` (`docs/testing/dispatcher.sh:2258`), so Android refuses the downgrade. The dispatch doctor read it as
an ISO push failure and gave up. **Every request on a ref older than 8b49e941bd now fails the same way.**

This lane merged origin/master (f53752f4fe) and requeued the same dump on master da6e8949dc, whose emulator code is the
merge head's: **1792329678-haloring1017-2242539**. FIST_ROUND is on by default there; the env keeps it for parity with
run 13.

### M9: photo 5 split by cube face: the pooled t2.r term is a screen region, not a term (`unlitjudge.py` bootstrap; `swapfit.py`, `spatial.py`, `facefit.py`, `texfit.py`, `maskfit.py`, `facemap.py`)

This is step 3 on photo 5, the only photo with a dump at its pose. The render is `hullsw.py`'s f507
(`render_507.npz`). The photo is `reg5`, read in fb units through `cal5v1806` (M7). The judged region is the hull's
core: 51,515 px at blur 3.

**Pooled over the hull, pure R10 is rejected.** `unlitjudge.py` now bootstraps its fits over 24 px blocks, 400 draws.
Neighbouring pixels share texels and blur, so the per-pixel error would be too small.

| blur | joint: c - X0 = g·D + k·t2.r + b | free: D, X0, t2.r weights | R² R10 / R1 / free |
|---|---|---|---|
| 3 | g 1.16 (0.77-1.53), k 0.17 (0.06-0.27) | 1.00 (0.65-1.36), 0.67 (0.43-0.86), 0.25 (0.16-0.34) | 0.563 / 0.580 / 0.594 |
| 8 | g 1.20 (0.69-1.72), k 0.24 (0.12-0.36) | 0.93 (0.45-1.53), 0.63 (0.42-0.82), 0.34 (0.21-0.46) | 0.638 / 0.667 / 0.688 |

The sets that part the accounts, at blur 3:

| set | n | console | hakuX | R10 predicts | R1 predicts |
|---|---|---|---|---|---|
| D low, t2.r high | 204 | 0.310 | | 0.249 | 0.306 |
| D high, t2.r low | 247 | 0.161 | 0.195 | 0.292 | 0.220 |

k grows with blur, so it is not t1's fine detail lost to the photo's resolution.

**No structural variant of the combiner fits better** (`swapfit.py`: console = a·variant + b, hull R²):

| variant | R² |
|---|---|
| hakuX as drawn, D + X0 | **0.532** |
| t2.r added to the lighting (self-lit) | 0.508 |
| the cube term with oD1.rgb only (no oD1.a) | 0.485 |
| t2.r and t2.g swapped | 0.455 |
| the cube term without the fresnel | 0.438 |
| D alone | 0.426 |
| the cube forced to 1 (fresnel kept) | 0.392 |

**The cube term keeps hakuX's mask** (`maskfit.py`). The model is console = a·D + b·t3·MASK + c over the hull. Its
control, the same fit on hakuX's own final, returns a 1.00 and b 1.00.

| MASK | R² |
|---|---|
| t2.r·oD1.rgb·oD1.a (hakuX's), with a 1.69, b 0.92 | **0.564** |
| t2.r·oD1.a | 0.559 |
| t2.r·oD1.rgb | 0.548 |
| t2.r | 0.525 |
| oD1.rgb·oD1.a, oD1.a or oD1.rgb alone | 0.466-0.480 |
| none | 0.449 |

So the console's reflection is not ungated by the fresnel, or by t2.r. **R9's near-constant fresnel fits worse than
hakuX's.**

**Split by the cube face hakuX's R lands on, the t2.r term goes away** (`facefit.py`, `texfit.py`, `facemap.py`). At
this pose the hull's R lands on three faces.

| face | px | where on screen | hakuX | console | c - h | c - h on t2.r inside the face | console's slope on hakuX's own pattern |
|---|---|---|---|---|---|---|---|
| 0 (mean texel 0.651) | 10,497 | x 259-422, the left strip | 0.221 | 0.263 | +0.042 | +0.231, R² 0.134 | 1.50 |
| 3 (0.130) | 16,487 | x 400-590, y 131-384, lower right | 0.145 | 0.260 | **+0.115** | **+0.009, R² 0.000** | 1.28 |
| 5 (0.143) | 24,531 | x 328-572, y 0-339, upper middle | 0.116 | 0.143 | +0.027 | +0.117, R² 0.057 | 1.07 |

The last column is corr(c, h) × sd(c) / sd(h).

- **Face 3 carries 63% of the summed excess.** Its pixels have the highest t2.r (0.372; faces 0 and 5 have 0.359 and
  0.221). So across faces the excess lines up with t2.r. Inside face 3 it is flat in t2.r, in W = t2.r·oD1.rgb·oD1.a
  and in D (each R² ≤ 0.025). **The pooled k measures the region, not a term.**
- **On face 3, hakuX is dark and the console is a mottled grey, which is the owner's description.** There the console
  follows hakuX's own pattern (corr 0.55) at 1.28x, plus a flat lift (maskfit on face 3 alone: a 1.20, c +0.08). The
  cube term on face 3 is 0.005 and carries no information. The excess correlates only faintly with the cube's own
  texels (t3.b 0.19, t3.g 0.16).
- **Face 0** fits b 1.95 with a 0.79 (R² 0.724): on the bright face, the console's reflection is about twice
  hakuX's. D and X are collinear there, so that split is loose.
- **Face 5** is about a D gain of 1.8 with X at 0.26 (R² 0.458).

The gains by face (1.50, 1.28, 1.07, plus the lift on face 3) are not one gain. Neither account fits all three faces
with one constant.

**Face 3 is the photo's right side, and the photo itself reads brighter there** (`spatial.py`). Off the ring, the
photo in fb units minus hakuX's video frame (`v01806`):

| screen band | median diff | its bright half |
|---|---|---|
| y bands, top to bottom | -0.015 to -0.031 | |
| x 15-160 | -0.031 | -0.040 |
| x 160-320 | -0.031 | -0.039 |
| x 320-480 | -0.013 | -0.017 |
| x 480-640 | **+0.013** | **+0.046** |

Relative to the left, that is up to about 0.05-0.08 of face 3's +0.115. On the hull by x band, c - h is +0.03 to
+0.04 up to x 480, and +0.093 / +0.108 at x 480-540 / 540-640. The t2.r slope inside an x band is about 0.2 (x
320-540). Bands mix faces, though, so the split by face is the stricter control.

**Where (a) stands after photo 5.**
- Photo 5 does not part R10 and R1/R9, and **the pooled rejection of pure R10 does not survive the split by face**.
- On every face the console's hull is brighter than hakuX's: 1.1-1.5x on hakuX's own pattern, plus a flat +0.08 to
  +0.12 on the lower right. There hakuX's R reads cube face 3 and the hull renders dark.
- Part of that lift is the photo's right side. How much is not separable on one photo.
- No re-weighting of hakuX's own terms fits the console better than R² 0.59 (0.69 at blur 8).
- **The cube's mask is hakuX's.** That retires an ungated t2.r layer as the form of R1/R9.

What is left of (a) is a level: a gain, or a lift that varies over the screen. It needs poses where the same cube faces
fall elsewhere on the photo, which photos 1-4 give. The dump for them is 1792329678.

**A different LOD for the detail map is not the gain.** On face 5 the excess grows toward grazing angles (corr with
oD1.a -0.43), which is how a coarser t1 mip would look: t1's mip means rise 0.255 to 0.423. But TEXCTL0 is
0x4003ffc0 on every hull stage, so its anisotropy field (bits 4-5) is 0. hakuX passes that through
(`texture.c:3440`, `4399-4415`), so both machines filter isotropically. The gains of 1.07-1.50 would need t1 at mip
1.5-5, against p50 0.85 here. A different isotropic LOD formula moves it by half a mip at most.

### M10: photos 1-4 on the Nova dump cannot judge the hull; photo 5's face-3 lift is the photo (`framepick.py`, `posefit.py`, `vidpose.py` at 120/1; `photocal.py`, `unlitjudge.py`; `glarefit.py`, `faceedge.py`)

**The dump.** 1792329678-haloring1017-2242539 (Nova, master da6e8949dc) landed 10-18 06:39 with a 142 MB `gd` dump
of 600 frames and its video. Its logcat has `GPU: PurpleVK`, so it is off the stock driver. The video's time base is
120/1 (variable rate), not run 13's 59.94. `vidpose.py` now reads the rate from ffprobe.

**The poses.** Each photo is matched to the new video by `vidpose.py` (luminance NCC). The video frame is then
matched to the dump in two ways: by `framepick.py` (hullsw's render of each candidate frame against that video frame,
r over the render's ring pixels) and by `posefit.py` (ring-silhouette IoU against the photo).

| photo | video t, NCC | framepick: best frame, r vs video | posefit: best frame, IoU | n4 px | n5 px |
|---|---|---|---|---|---|
| 4 | 51.989 s, 0.905 | f124, 0.654 | f125, 0.095 | 10,130 | 0 |
| 3 | 64.468 s, 0.853 | f310, 0.927 | f309, 0.204 | 9,241 | 0 |
| 2 | 69.173 s, 0.899 | (not run) | f379, 0.507 | 15,431 | 1 |
| 1 | 73.677 s, 0.813 | f440, -0.000 (none of f440-f455 above 0) | f446, 0.443 | 21,095 | 76 |

The video times are about twice run 13's spacing (photo 4 to 1: 21.7 s here, 10.8 s in run 13), but the dump frames
are not: 316 frames, which at run 13's 0.0334 s a frame is 10.6 s. The time column is the video's frame index over
120, and that is not its clock. Only the frame mapping is used.

**The hull is not on screen at photos 1-4.** hakuX's render at each pose has 0-76 hull (`n5`) pixels. Frame 310 has
`n5` at its usual count (4362) and textures, so it is drawn and is off screen or culled. What shows is the band `n4`.
Next to it is a dark strip that the render does not draw: at photo 3 (edge-on) and under the band at photo 2, hakuX's
video and the console photo both have a dark strip with grey edges, where the render has bright band or nothing. That
is the inner rim `n6` (510 vertices, a DST_COLOR x ZERO multiply), which `hullsw.py` does not draw. By eye, console
and hakuX agree on it at photo 3.

**The band cannot be judged either:**
- **The photos' tone curve has a shoulder at the band's level.** Photo 2 (L, fb to photo): 0.27 to 0.69, 0.50 to
  0.82, 0.80 to 0.87. Photo 3 jumps from 0.08 to 0.11 at the bottom to 0.15 to 0.60. The band sits at fb 0.4-0.6. One
  photo step above fb 0.5 is 3-6 fb steps, so a 1.3x band would move the photo by about 0.02.
- **The render is not hakuX's frame on the band.** Over the render's band core, hakuX's own video reads:

  | photo | video | render | console |
  |---|---|---|---|
  | 2 | 0.109 | 0.604 | 0.117 |
  | 3 | 0.086 | 0.450 | |
  | 4 | 0.330 | 0.455 | 0.283 |

  The missing `n6` and a few pixels of placement are enough to do this. So the render is not the judge on the band,
  and video against photo needs pixels known to be band in both.

Photos 1-4 add nothing on (a). Their one by-eye remark (the console's band brighter and whiter, M8) sits in the
tone-curve shoulder and stays unattributed.

**Photo 5's lift: veiling glare is out** (`glarefit.py`, render f507, `reg5`, `cal5v1806`, video `v01806`, linear
light at gamma 2.2). On the space background, photo minus hakuX's video is fitted on a Gaussian blur of hakuX's frame:
- the coefficient is negative at every width (6 px: -0.17, CI -0.26 to -0.04; R² 0.04);
- on the hull, glare predicts +0.001 of the +0.027 excess.

So the camera or TV adding a halo from bright neighbours does not make the console's hull brighter.

**But the photo reads dark pixels brighter toward its right, at about face 3's level.** The background's brightest
tenth per x band, photo over video:

| x | 15-160 | 160-320 | 320-480 | 480-640 |
|---|---|---|---|---|
| photo / video | 0.93 | 0.86 | 1.15 | **2.46** |
| video level (linear) | 0.129 | 0.403 | 0.053 | 0.022 |

In fb units, the background at x 480-640 reads 0.177 in hakuX and 0.267 on the photo. Face 3, on that side, reads
0.150 in hakuX and 0.270 on the console. **The background at the same place and level is lifted as much as face 3
is.** Face 5, in the middle and dark, reads 0.140 against 0.185. The background at x 320-480 is lifted +0.017 there.
That fits a TV seen off-axis, whose black level rises toward one side, more than it fits a cube face.

**No step at the face 3|5 edge.** `faceedge.py` bins c - h by signed distance from the edge where hakuX's R crosses
between faces, in photo units (h through CAL's forward curve, which cannot grow a saturating step). Across the 3|5
edge, c - h ramps smoothly: +0.17 at 48 px inside face 3, +0.15 at the edge, +0.06 at 48 px inside face 5. The step
at 0 is -0.027 (CI -0.076 to +0.019). A cube term that differed between faces 3 and 5 on the console would step
there. **Face 3's lift is smooth across the cube edge, which is how the photo's position term looks.**

**A step at the face 0|5 edge, where hakuX's is, 1.7x as tall.** Across the 0|5 edge, hakuX's own final steps by
-0.123 (CI -0.20 to -0.04) and its reflection X0 by -0.079. The console steps by -0.211 (CI -0.32 to -0.07), so the
excess steps by -0.089 (CI -0.160 to +0.006). The console's step is at hakuX's edge. **So the cube's face layout on
the console is hakuX's**, which takes another mirror or face permutation off the table (R1b, A10). Its height is 1.7x
hakuX's, which matches M9's face-0 fit (the console's reflection 1.95x hakuX's).

Nothing in `n5`'s state accounts for a doubled reflection:
- the reflection vector is a true one (c4.w = 2, c12.w = 1: R = 2(E·N)N - E, x1 NOTES 648, 926);
- the specular alpha passes through (the hull's VS has no `vtxD1.w = 1.0`, so ALPHA_FROM_MATERIAL_SPECULAR is set,
  `vsh.c:106-121`);
- two-sided lighting is off (`pD0 = vtxD0`, `psh_48c74844.glsl:316`);
- the combiner words decode to hakuX's chain (M3).

A phone's local tone mapping sharpens steps against smooth areas, so the 1.7x is either the console or the camera.
One photo cannot say which.

**Where (a) stands after M10.**
- The console's hull at photo 5 has hakuX's structure: the same texture scale and phase (M5), the same cube mask
  (M9), the same cube face layout (this section).
- Its brightness differs in two ways:
  - a lift on the right and centre that the photo's background shares at the same place and level, smooth across a
    cube edge (R11);
  - a taller reflection step at the bright face's edge (1.7x), which is the console or the camera.
- No mechanism in hakuX's state for the hull reproduces either.
- The owner's account (a sprite present across the dark portions) is not reproduced by any number on these photos.
  Their dark portions read as the photo's own dark-level behaviour.
- Settling (a) takes one of two instruments. One is a console capture with a fixed exposure (the board request to
  lane.xbox, 10-18 06:35). The other is hakuX and the console photographed by one camera on one TV, so that the
  camera and the TV's off-axis response cancel.

### M11: on photo 5, the background's own gain at the hull's place predicts the hull's excess (`gainfield.py`)

M10 compared the background with the hull at matched levels in one strip on the right. `glarefit.py`'s last block went
further, but its numbers did not reach M10. That block fits the photo's departure from hakuX on the space background
as a gain field, in linear light: photo - video = video x (g0 + gx x + gy y) + c. Both machines draw the same pixels
there, so whatever the field does is the camera, the TV or the display chain. The field is then applied to hakuX's
hull. `gainfield.py` repeats the fit with three changes:
- both sides are box means (radius 3) inside their own mask, as the hull's already are. Misregistration of the fine
  background art then cannot pull the fit toward a gain of -1;
- the prediction carries a block bootstrap over 24 px blocks;
- it runs two controls.

Inputs: render f507, `reg5`, `cal5v1806`, video `v01806`. Background: 121,208 px. Hull core: 47,162 px.

| model, fitted on the background | R² | hull, all | face 0 | face 3 | face 5 | band `n4` |
|---|---|---|---|---|---|---|
| console - hakuX, linear (the excess) | | +0.028 | +0.046 | +0.041 | +0.012 | +0.092 |
| position gain, all background | 0.19 | +0.038 (0.021 .. 0.055) | +0.064 (0.032 .. 0.095) | +0.049 (0.027 .. 0.070) | +0.020 (0.012 .. 0.027) | +0.58 (0.25 .. 0.92) |
| position gain, background > 40 px off the ring | 0.07 | +0.025 (-0.027 .. 0.069) | +0.041 (-0.056 .. 0.118) | +0.032 (-0.035 .. 0.088) | +0.013 (-0.011 .. 0.035) | +0.36 (-0.62 .. 1.00) |
| level only, no position | 0.27 | +0.008 (0.004 .. 0.012) | +0.015 (0.006 .. 0.024) | +0.006 (0.004 .. 0.010) | +0.006 (0.003 .. 0.008) | -0.026 |

The gain field is g0 -0.65 (-1.00 .. -0.40), gx +1.07 (+0.47 .. +2.00), gy +4.89 (+2.20 .. +7.58). So the photo reads
dark pixels about 3x brighter in linear light at the bottom of the frame than at the top-left. The hull sits at the
bottom.

**What the table says:**
- **The position field predicts the hull's excess on faces 0 and 3.** It does so inside its interval, face 0's
  doubling included. Face 5 sits at the low edge of its interval (+0.012 against 0.012-0.027): the console is no
  brighter there than the background's field would make hakuX.
- **Level alone does not predict it** (all four outside, too low). The photo's lift depends on where a pixel is.
  M10's strip on the right said the same.
- **The hold-out is not informative.** Fitted only on background more than 40 px off the ring, every interval spans
  zero. It neither confirms nor breaks the result.
- **The band is not a control.** At 0.30 linear the band is far above the background's levels, where the photo's
  curve flattens, and a linear gain extrapolated there over-predicts it 6x. The field is a dark-level lift, not a
  true gain. The hull, at 0.013-0.050 linear, is in the background's own range.

**So on photo 5 the console's hull is no brighter than the photo's own dark-level lift at its place would make
hakuX's hull.** The same goes for face 0's 1.7x step (M10). Its excess step's interval already reached zero (-0.160 ..
+0.006), and M10's glare fit found a negative halo at 6 px (-0.17), a camera that sharpens. Overshoot on face 0's
bright side and undershoot on face 5's (excess -0.05 to -0.02 at 16-32 px) are its signature.

**The limit of this.** The prediction's interval is wide. On face 3 the console could hold a layer of up to about
+0.014 linear (fb 0.15 to 0.20) above the field's lowest prediction, about hakuX's own face-3 level, and the photo
could not tell. What photo 5 does bound is the total: the console's face 3 reads fb 0.27 through the photo's
calibration. Neither a "bright" layer over the dark faces nor its absence is shown by this photo. The photo is
consistent with none.

## Root cause and remedies

**(c): the stock Qualcomm driver (R4, 0.9).** The band turns in the guest, on lavapipe and on Turnip. Nothing to fix
in hakuX; the driver is out of scope by the owner's rule.

**(b): fixed by FIST_ROUND (A12).** Not reopened.

**(a): no root cause, because no measurement shows the console drawing more than hakuX.** Every instrument this lane
had points the other way. The one console image with a dump at its pose (photo 5) has hakuX's texture scale and phase,
cube mask and cube face layout. Its brightness is inside what the photo itself does to the background at the same
place. Photos 1-4 hold no hull at their poses. hakuX's own state for `n5` was decoded word by word, and every factor
that could scale a term was read and found to match. What is left:

| account | P | what decides it |
|---|---|---|
| R11: photo 5's excess is the photo (camera and TV off-axis) | 0.5 | already measured (M11); fixed exposure on a capture card would confirm |
| R13: the owner's by-eye difference is the display hakuX was watched on | 0.3 | hakuX and the console on one display |
| a real gap in `n5`, below photo 5's precision (R10 0.07, R12 0.08, R5 0.1; not exclusive) | 0.2 | a capture card's frames of the console against hakuX's framebuffer, at matched frames |

R11 and R13 are not exclusive: R11 is about photo 5, R13 about the owner's eye. The third row is what a code fix
would need, and it is the least likely.

**Ranked remedies, by P x win.** Here the win is closing (a) correctly, either way.

| # | remedy | P it settles (a) | win | P x win | who | chased |
|---|---|---|---|---|---|---|
| 1 | a capture card on the console's video out, frames compared with hakuX's framebuffer by `hullsw.py`, `photocal.py` (with the overlays as the calibration) and `gainfield.py` | 0.9 | full: a framebuffer-to-framebuffer judge with no camera or TV in it, and the term-by-term tools already exist | 0.9 | owner's console | yes: board request to lane.xbox, 10-18 06:35, with a follow-up asking for a capture card over a phone |
| 2 | the owner watches hakuX and the console on the same TV, the menu side by side | 0.6 (it settles R13 either way; it cannot size a remaining gap) | most: closes (a) if R13 holds, otherwise it makes the gap one display's worth and points at `n5` | 0.5 | owner, 10 min | yes: question 1 at the end of this file and in the board follow-up |
| 3 | code: the diffuse gain (R10: t1's level or the s6 sum) | 0.07 | full if true | 0.07 | lane, after 1 | no: nothing in the state supports it (M7, M11) |
| 4 | code: the reflection's amplitude (R12) | 0.08 | partial (face 0 only) | 0.04 | lane, after 1 | no: no word in `n5` gives the factor (M10) |

No code remedy is worth a device run until remedy 1 or 2 shows a gap. Two lane attempts already went to that kind of
pre-instrument fix in A1-A20.

**Measured fix: none.** Nothing was changed in hakuX, so there is nothing to measure. The PR is analysis and tools.

## Plan

1. ~~(c) off the stock driver~~: done (M2, M2b). R4 holds.
2. ~~(a): which draw~~: `n5` itself (M3).
3. (a): the software render of `n5` with R3's k, R1's forced face and mirror, and R6's q, judged by region against
   the pose-matched console photos. Then fix A7's crash and check the leaders on the desktop.
   - Photo 5: done (M5-M9). It does not part R10 from R1/R9. R9 and the ungated t2.r layer are down (M9).
   - ~~Photos 1-4~~: done (M10) on dump 1792329678 (PurpleVK). They show no hull at their poses, and the band sits in
     their tone-curve shoulder, so they cannot judge (a). R11 was tested on photo 5 instead: the face-3 lift is the
     photo's own, and the cube's face layout is hakuX's. R12, the reflection's height at the bright face, is left.
   - ~~Photo 5's gain field~~: done (M11). The background's dark-level lift at the hull's place predicts the hull's
     excess per face. R11 0.5, R12 0.08, R10 0.07; R13 (the display) new at 0.3.
   - The console side: a board request to lane.xbox for a fixed-camera clip of the menu, filed 10-18 06:35 PDT
     (`dispatch/board-requests/xbox.md`, "lane.haloring1017: #939 (a) needs a fixed-camera console clip"). It asks
     for a capture card or a locked-exposure phone on a stand, 2 minutes from the menu's first frame, and 5 s of a
     plain grey screen as a flat field. A clip shows the same hull faces at many screen positions under one
     calibration: an excess that moves with the hull is the console (R10), one that stays on the right is the photo
     (R11). The same entry asks for the #939 comment on (c) and reports the dispatcher's install without `-d`.
4. The desktop (A7's PSHDBG crash, the leaders): paused while C: is under 40 GB free (38 GB at 06:29 on 10-18,
   32 GB at the end of attempt 4). Not needed for (a) until remedy 1 or 2 shows a gap.

## Status

[lane.haloring1017] blocked: (a) needs a console capture on a capture card, judged against hakuX's framebuffer
(remedy 1), or the owner's view of hakuX and the console on one TV (remedy 2). Both are asked of lane.xbox (board
request 10-18 06:35 PDT and its follow-up, in `dispatch/board-requests/xbox.md`). The Nova dump 1792329678 landed and
is used (M10, M11). The PR is ready as analysis and tools. C: needs to be back at 40 GB free before desktop runs
resume (32 GB at the end of attempt 4).

Before every desktop run that may crash, `df -B1G /mnt/c` must show at least 40 GB free. After every run, delete only
this run's own dumps in `wsl-crashes/`, by exact name, and log each crash here.

## Questions for the owner

1. On 10-16, when you saw the bright grey layer over the dark part of the ring on the console, where were you
   watching hakuX: on the same TV, or on the handheld or a monitor? If it was a different screen, one look at hakuX's
   menu on the console's TV (HDMI from the Thor or the desktop) tests R13. If hakuX's unlit hull shows its grey
   crater texture there too, (a) is the display and closes with no code change.
2. Is a capture card available for the console's video out (component or HDMI adapter)? A phone cannot give
   framebuffer values (M10, M11). A capture card's frames go straight into this lane's judge.
