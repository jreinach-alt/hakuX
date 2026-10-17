# bindpose1017 NOTES (#1043)

**Status (read first, 2026-10-17 ~13:45 PDT): root cause found, and it is not in the code.** Every bad result ran on the
stock Qualcomm Adreno driver. Every good one ran on Mesa Turnip T30 (`vulkan.purple.so`, PurpleVK). The same apk
bytes are good in `.debug` (Turnip installed since 09-11) and bad in `debug2` (no driver installed). The fix is to load
Turnip in the package; under the owner's 10-17 rule the stock driver is never used or tested. The owner accepted it by
eye on `.debug` (Turnip), and 0.5.2-rc1's own code (160728983a) animates THPS4 on the desktop (r4). Update 2 at the end
has the evidence, an account of each symptom, and the remedies. Updates 1 and earlier are kept as written, apart from
one corrected premise.

Ack: Addenda 1-3 read (2026-10-17 ~12:40 PDT): the issue is #1043. The window is the fold 3c2338eb2b, which the owner's
hand bisect makes the first bad build. FIST_ROUND, FLDCW_CHAIN, S2T_CVT, REPORT_EARLY, XVSS and S2TSHELF are excluded,
and 4f0111232c is excluded by the owner's revert run. Device requests use `--priority blocker`. Builds go through
lane.local while it holds the Nova.

## Step 0: already tried

What I searched:
- `git log --all -S` and `--grep` for FIST, FLDCW, flcr, FPCR, fp_jit, RC, vertex_attr_gen, DMA_VERTEX, XVSS, v0-hash,
  UBO, vshconst, transform constant, skinning, matrix palette, blend weight, bind pose, T-pose, and
  check_driver_identity_and_wipe_caches.
- Every `docs/lanes/*/NOTES.md` for bind pose, T-pose, arms outstretched, skinning, blend, palette, THPS4 / 41560017,
  Max Payne 2 / 5454000C, uniform attribute, and super-fast.
- The tracker (`origin/board:nv2a_issues.toml`): #939 (line ~6169), #1018 (~6319), #1043 (6498), and the FIST audit
  (~3040).
- `MainActivity.kt` FASTPATHS_VARS (38-42), and defaulton1017's "Verdict per switch".
- A web search for THPS4 and Max Payne 2 bind-pose reports in xemu, X1 BOX, Cxbx-R and xboxrecomp, and for x87
  rounding and FPCR bugs in aarch64 x86 emulators.

| approach | where | verdict | what it means here |
|---|---|---|---|
| FIST_ROUND on by default (aarch64 FIST rounds per FPCR) | 52aa206f93, 5d4b689ed9, 56834e79cd; x1port1012 NOTES ~726-905; #939 | built for Halo #939(b) | Excluded: 3c2338eb2b is bad and predates it (Addendum 3). Do not split on `HAKUX_FIST_ROUND`. |
| FLDCW_CHAIN on by default | d70f782f45, 7f6b99db87; halo1016 FLDCW census; #1018 | in rc1 only | Excluded: 0.5.1-rc1 and 3c2338eb2b are bad. |
| S2T_CVT, REPORT_EARLY defaults | 7f6b99db87, fbafbac000; defaulton1017 "Verdict per switch" | 10-16 and later | Excluded: they postdate the first bad build. |
| XVSS v0-hash skip switch | f3acdd0912 | not an ancestor of 3c2338eb2b | Excluded. |
| S2TSHELF | 18fb351588 | not an ancestor of 3c2338eb2b | Excluded. |
| DMA_VERTEX bumps vertex_attr_gen | 4f0111232c (fold, A9b) | owner: 3c2338eb2b with it reverted is still bad | Excluded. |
| Stale vertex-shader constants | #233: d9c0ed0b8e, 84a67b9cf8 | fixed | Before the window, so it is in the good build. This mechanism class has bitten before. |
| Uniform values kept on create_pipeline's early return | #274: 1d9c3e4c0f, ae373844cb | fixed (create_pipeline path only) | Before the window. fps1015 says the same hole is still open on the super-fast path (row below). |
| Vertex-buffer staleness | forza414: 85347ffbd1, 73028d46f6; ring53 | fixed | Before the window. |
| OPT_UNIFORM_SKIP | 2c8db2902c | in tree | Before the window. |
| "Transform constants are lost" claim | 2ddae97a77, retracted in f465f0369d | retracted | Do not cite. |
| Inline (uniform) attribute change bumps no gen, so the super-fast path keeps the old value | fps1015 NOTES 943-962 (Texture_shadow_comparator, 64 of 288 captures on device) | open; fix withheld ("WAITING (vk/draw.c, withheld)") | Regressed between e654516849 (10-10) and 0e5fab6bef (10-16). ccb2749973 (VTX_HAZARD default) is an ancestor of 8455537f10, so the draw-path candidates left in that window are the fold's 4f0111232c, d4d292c9ca and 172d94de1f, plus 10-13..10-16 work. It is the only known live mechanism that holds a vertex attribute at an old value. **Overlap: test it in the fold.** |
| SPIR-V cache served across builds | 09-25 stale-cache incident; `check_driver_identity_and_wipe_caches` (vk/renderer.c:96, SHADER_STATE_LAYOUT_VERSION 5 at :74); spv_cache keyed by `fast_hash(glsl)` (vk/glsl.c:442-468) | by reading | A changed GLSL cannot load an old SPIR-V. No shader-generator file changes in the fold. B3 stays low. |
| Default-on screen | defaulton1017 (Halo, MKSM, Top Spin, RalliSport, SHAR, Conker, Amped 2, TSC) | neither title screened; no animation check | No coverage of this symptom. |
| fastpaths ON/OFF screen | fastpaths1010 NOTES:383 | MP2 "passed", "not reviewed by eye" | No animation evidence either way. |
| Bind-pose or T-pose reports | all lane NOTES, the tracker, the web | none found in any title or emulator | **new**: nothing to reuse. |
| x87 rounding in recompilers and emulators | xboxrecomp (JSRF animation tables, `_ftol` via llrint); Mainkill1/xemu#236 (FLDCW block-exit staleness); Box64 (reads RC on every FIST) | CPU side | The bisect excludes CPU code: the fold changes none. |

## The fold, read against the mechanism

A bind pose that still moves through the world means every vertex follows one matrix. That happens when the blend
indices or weights read constant, so every vertex takes bone 0 with weight 1. It also happens when the bone palette
never reaches the draw (identity), or when the game never poses the skeleton (no animation data, or a fallback path).
The good and bad builds differ by the fold. `git diff --stat dd5e3cb3c6 8455537f10` over the emulator directories is
empty. The fold's emulator commits are below.

| commit | what it changes | can it hold blend attributes or the palette? |
|---|---|---|
| d4d292c9ca A7 | `vmaFlushAllocation` before each staging-to-device copy; the UBO barrier's destination adds FRAGMENT_SHADER | No, by reading. A flush on a non-coherent type makes the copy read *newer* bytes, and on a coherent type it is a no-op. A wider barrier only adds ordering. Neither can leave a constant at an old value. Owner revert run pending. |
| cbda0e85fd A4 | core EDS1 names take the EXT pointers when NULL; a missing depth/stencil command turns EDS1 off; a missing cull/front-face fails device creation | No. "No change on a device that reports 1.3", and the Nova's Adreno reports 1.3 (to confirm from logcat: no `extended dynamic state disabled` line). Cull, depth and stencil cannot move vertices. |
| de06bd39e3 A2 | a texture outside VRAM binds the dummy texture; `check_texture_dirty` clamps to VRAM | No. NV2A vertex programs cannot sample textures, so skinning never reads one. |
| 172d94de1f A9a | a rejected pipeline-cache file retries with an empty cache | No. A driver-validated blob holds no guest state. |
| 4f0111232c A9b | DMA_VERTEX bumps vertex_attr_gen | Excluded by the revert run. It adds an invalidation, so it causes fewer super-fast hits. |
| audio A1, A3, A6, A8 | bad voice data skips the voice (no assert); ADPCM index clamped; HRTF history cleared; HRTF normalisation `continue` | No guest animation path waits on these. A skipped bad voice is silence, and the game's clock is not APU-driven in either title. Low; kept for completeness. |
| d0eb2410b2 A5 | setup wizard flash-ROM size check | UI only. |

**Reading result:** no fold commit changes how vertex data, vertex constants or attribute values reach a draw on a
Vulkan 1.3 device. That conflicts with the bisect, so one of three things is true:
- the bisect's anchor is not like-for-like (H-env, below);
- one of these reads is wrong; or
- the change works through timing (A7's flush or barrier changing where a race lands, the fps1015 class).

## Symptoms, with their current account

1. THPS4: the skater and the pedestrians hold one pose, arms and legs out, with no animation. *Not seen by me yet; the
   owner's report only.*
2. Max Payne 2: Max, the same.
3. Both animated at acceptance. I checked the THPS4 frames myself: run n-41560017-1013d, apk 0874bf321e41,
   `com.jreinach.hakux.debug`, goldens HDD `titles.qcow2`, `fastpaths: ON`.
   - `010-submenu`: Tony Hawk on the career menu, arms down, holding his board.
   - `014-gameplay`: the skater from behind, arms down, board in hand.
   - `074-hold`: the skater riding, with "Ollie the Bum" standing with his arms down.
4. Halo animates on the same rc1 install the same morning, so whatever it is spares Halo.
5. 0.5.1-rc1, 56fdef2c85, 3c2338eb2b and 3c2338eb2b minus 4f0111232c: all bad on the owner's debug2 install.
6. The desktop: not run yet.
7. The characters still move through the world (the owner: "static" means the pose). To confirm from frames.
8. lane.local reports that dispatcher runs booted the bisect builds to a black screen. No account yet. It would matter
   if it touches the dispatcher leg below.

**MP1 cross-check:** run n-54540003-1014d, Max Payne 1 on debug build 0.5.0-1013-08f1fb4a90, which is post-fold. In
frames `022-hold` and `025-hold`, Max has his arms down and is animated. MP1 is a different engine generation from MP2,
so this is weak evidence. Still, a post-fold build animated a Remedy title when run by the dispatcher.

## Hypotheses (P x win; every one wins the release)

| id | hypothesis | P | already-tried row | hit | miss |
|---|---|---|---|---|---|
| H-env | The good anchor is not like-for-like. Every "bad" result comes from the owner's installs: debug2 bisect apks installed over shared app data and HDD, and the release package. The only "good" result is a 10-13 dispatcher run (debug package, goldens HDD, caches cleared on apk change). Sub-causes: (E1) the HDD's per-title cache partition holds bad animation data from an earlier session, which explains why Halo is spared; (E2) app settings or the `env_vars` pref; (E3) a custom GPU driver (GpuDriverHelper); (E4) app caches. | 0.45 | new: searched lanes, tracker, web; nothing | 8455537f10 built as debug2 and installed over the same data is **bad** too, or 3c2338eb2b/rc1 run by the dispatcher (its own package and HDD) **animates** | 8455537f10-debug2 animates on the same install |
| H-race | A fold commit changes timing, most likely A7's flush or barrier on Adreno, so a pre-existing hole (fps1015's super-fast-path class) now drops the palette or blend attributes. | 0.2 | fps1015 row | the d4d292c9ca revert animates; or the desktop Texture_shadow_comparator moves between 8455537f10 and 3c2338eb2b | the revert is still bad, and the desktop suite matches across the fold |
| H-read | One of the reads above is wrong: a fold commit directly changes attribute or constant delivery. | 0.15 | new: searched the fold diffs | the straight bisect on debug2 (f763fe6d40..5dfea123a3) names one commit, and its diff has a path to the attribute | the bisect names nothing consistent |
| H-audio | An audio commit changes something a game's animation waits on. | 0.05 | new: searched apu/vp diffs | the bisect lands on 81b542ca3e, 79981e045c, 10c83bfa06 or d88374737c | it lands elsewhere |
| H-B3 | A stale shader from another build in the app's caches. | 0.05 | SPIR-V cache row | bad on debug2, good after the owner (with OK) clears `spv_cache`, `pipeline_keys/`, `vk_pipeline_cache.bin` and `shader_module_keys.bin` | still bad with empty caches |
| H-B5 | Device state. | 0.05 | Nova A/B/X/Y memory (10-17) | — | the owner rebooted before the 4f0111232c-revert run and it was still bad, so this is mostly spent |

### Discriminators, in order

1. **8455537f10 as debug2, installed over the same data** (Addendum 3's first item; lane.local builds it). Bad
   separates H-env from all the code hypotheses at once.
2. **The d4d292c9ca revert** (the owner's run in flight): splits H-race.
3. **Desktop, input-free:** Texture_shadow_comparator at 8455537f10 vs 3c2338eb2b on lavapipe. It shows whether the
   fold moves attribute delivery at all, independent of the device and of app data.
4. **The dispatcher leg** once the Nova frees: rc1 (or 3c2338eb2b) THPS4 from the kept path, in the dispatcher's own
   package with the goldens HDD. If it animates, H-env is confirmed and the cause sits in the owner's install. That
   leaves a diff of the shared_prefs, the HDD cache partition and the GPU-driver setting.

## Update 1 (~13:00 PDT): the anchor is bad, so the code is excluded

lane.local reports these results from the owner's hand tests on the Nova:
- 8455537f10 built as debug2 and installed over the same data: **bad**.
- ~~The dispatcher's original cached 8455537f10 apk, run by hand in the test-builds app: **bad**.~~ **Wrong, corrected
  13:10:** lane.local has no record of a hand test of that apk in `.debug`. Every bad test it can trace was on
  debug2, release or the Thor. Run in `.debug` by the dispatcher and by hand, that apk is **good** (Update 2).
- minusA7 (the d4d292c9ca revert), minusA9 and 3c2338eb2b: bad.
- The owner also sees the bind pose on the Thor on 0.5.2-rc1 (release app).

So the same code that animated on 10-13 in the dispatcher's run does not animate on the owner's installs today. No
commit in 8455537f10..160728983a is the cause, and **there is no release interim to give**: every build since 10-13
behaves the same here. What differs is the environment the 10-13 run had and the owner's installs do not.

The shader caches (lane.local's lead), by reading:
- spv_cache is keyed by `fast_hash(GLSL)` (vk/glsl.c:442-468).
- shader_module_keys.bin and pipeline_keys/<title id>.bin hold keys, and the GLSL is generated again from them
  (compile_worker.c:1352-1366).
- vk_pipeline_cache.bin holds driver binaries matched by full create-info.
- No generator changed in the window.

So no build in play writes a module that another reuses wrongly. debug2's caches were created at 11:25, and the first
debug2 test (0.5.1-rc1, ~11:30) was already bad. If that was THPS4's first launch there, it was bad with empty caches.
lane.local is still having the owner clear the cache and retest, which is cheap.

The other things the owner's installs share: the HDD image (debug2's was "pre-filled"), the settings, and the device.
Both good runs used the dispatcher's goldens `titles.qcow2`: THPS4 on 10-13 and MP1 on 10-14. Xbox titles keep cached
disc files on the HDD's X/Y/Z cache partitions per title, and saves in `E:\UDATA\<title id>`. Damaged per-title data
would hit THPS4 and MP2 on every build using that HDD and spare Halo.

| id | hypothesis | P | hit | miss |
|---|---|---|---|---|
| H-HDD | The owner's HDD image holds bad per-title data for these titles (cache partition files, or UDATA). | 0.4 | the same build animates with a fresh HDD or a copy of goldens `titles.qcow2` on the owner's device | still bad with a fresh HDD |
| H-settings | A setting the installs share: the `env_vars` pref, a custom GPU driver (GpuDriverHelper), or a per-game setting. | 0.2 | shared_prefs show a non-default; the bind pose clears when it is reset | defaults throughout |
| H-device | A device-level change since 10-13 (the Android GPU driver or system update) on both the Nova and the Thor. | 0.15 | a clean dispatcher run (its package, goldens HDD, caches cleared) of 8455537f10 today is **bad** too | that run animates |
| H-B3 | The shader caches. | 0.05 | animates after Settings > Clear shader cache | still bad |
| H-code | Any fold commit. | 0.02 | — | the 8455537f10-debug2 result above |

lane.xbox's question still stands for the mechanism: does each title skin by fixed-function `SET_SKIN_MODE` (matrices
0-3 as uniforms) or by a vertex program with a constant-register palette? A desktop gd dump of THPS4's main menu
answers it with no input. The menu's 3D skatepark has skaters in it (good-run frame `007-main_menu`), so the dump gives
CSV0_D skin mode and program/FFP per draw. The desktop build is at 3c2338eb2b in a scratch worktree,
`/home/justin/hakux-work/wt/bp1017desk`.

## Builds: exactly what each one is

| build | sha | package | installed how | app data | result | source |
|---|---|---|---|---|---|---|
| THPS4 acceptance | 8455537f10 (apk 0874bf321e41, the 10-13 01:54 master restore) | com.jreinach.hakux.debug | dispatcher | dispatcher's; goldens HDD `titles.qcow2`; caches cleared on apk change | good | n-41560017-1013d frames 010, 014, 074 |
| MP1 | 08f1fb4a90 (0.5.0-1013, post-fold) | com.jreinach.hakux.debug | dispatcher | dispatcher's | good (MP1) | n-54540003-1014d frames 022, 025 |
| 0.5.2-rc1 | 160728983a | com.jreinach.hakux (release) | owner, over 0.5.1, data kept | owner's | bad | owner 10-17 morning |
| 0.5.1-rc1 | b12a313033 | com.jreinach.hakux.debug2 | owner | debug2 (mcpx, flash, eeprom, HDD pre-filled by lane.local) | bad | Addendum 1 |
| 56fdef2c85 | 56fdef2c85 | debug2 | owner | debug2 | bad | Addendum 3 / #1043 row |
| 3c2338eb2b | 3c2338eb2b | debug2 | owner | debug2 | bad | same |
| 3c2338eb2b - 4f0111232c | revert on 3c2338eb2b | debug2 | owner, after a reboot | debug2 | bad | same |
| 3c2338eb2b - d4d292c9ca | revert on 3c2338eb2b | debug2 | owner, 12:15 | debug2 | bad | lane.local, ~13:00 |
| 8455537f10 | 8455537f10 | debug2 | owner, over the same data | debug2 | **bad** | lane.local, ~13:00 |
| 8455537f10 (the dispatcher's own cached apk) | 8455537f10 | test-builds app | owner | that app's | **bad** | lane.local, ~13:00 |
| 0.5.2-rc1 on the Thor | 160728983a | release | owner | the Thor's | bad | lane.local, ~13:00 |

## Update 2 (~13:30 PDT): the variable is the GPU driver

### The split

lane.local ran the same commit in both packages (13:00, the Nova, owner watching). I read the driver line in every
log I could find. MainActivity logs `GPU driver: ...` and xemu logs `GPU: ...`; on this Adreno 740 only Turnip
exposes `VK_EXT_graphics_pipeline_library`, so `[gpl569] ext=` gives the driver away even where the `GPU:` line has
rolled out.

| run | package | driver line | `[gpl569]` | result | source |
|---|---|---|---|---|---|
| THPS4 acceptance, 10-13 07:58, apk 0874bf321e41 (8455537f10) | .debug | (not in the kept logcat) | `ext=1 lib=1 ... mode=3` | animates (frames 010, 014, 074) | n-41560017-1013d/screen-logcat.txt:7 |
| MP2 acceptance, 10-08 06:23 | .debug | (not kept) | `ext=1 lib=1 ... mode=3` | animates (030-038 cutscene, 040/051/075/099 Max walking with his arms down) | n-5454000C-1007/screen-logcat.txt |
| 8455537f10, accepted apk 0874bf321e41, dispatcher launch, 13:00 | .debug | `Loading custom Vulkan driver: vulkan.purple.so`; `GPU: PurpleVK-public Adreno (TM) 740 (git-62ac221a33)` | `ext=1 ... mode=3` | animates (lane.local) | for-c4/current-xemu-debug.log |
| 8455537f10 rebuilt (fc483f00a957), dispatcher and hand launch, 13:01-13:05 | .debug | same | `ext=1 ... mode=3` | animates | for-c4/logcat-good-rebuilt-dbg-1301.txt, logcat-good-hand-launch-1305.txt:9 |
| 8455537f10 and the bisect builds | debug2 | `GPU: Adreno (TM) 740 \| Driver: Qualcomm Technologies Inc. Adreno Vulkan Driver`; `files/gpu_driver/` empty | — | bind pose | for-c4/current-xemu-debug2.log |
| 0.5.2-rc1 (owner, release app), 10-17 09:06 and 09:23 | release | `GPU driver: no custom driver installed, using system default` | `ext=0 lib=0 fast=0 interp=0 requested=3 mode=0` | bind pose (owner) | nova-rc1-input-0835.log:3413,3815; r1/logcat.txt:407,809 |
| 0.5.2-rc1 on the Thor, 10-16 19:25 | release | `no custom driver installed, using system default` | `ext=0 ... mode=0` | bind pose (owner) | thor-live.log:10738,11191 |
| 0.5.2-rc1 (160728983a) on the desktop, r4, 13:25 | desktop, the release app's defaults (`HAKUX_SURFGPU=1`, the eight fast-path switches =1) | lavapipe (llvmpipe, LLVM 20.1.2) | `ext=1 lib=1 fast=1 interp=1 requested=3 mode=3` | animates: t0225 a pedestrian walking, arms down; t0286 one skater mid-air with knees tucked, one crouched in a grab, a pedestrian with arms at his sides; t0301 a skater with knees bent | `bp1017desk/run/r4rc1/` (scratch), qemu.log:53 |

Same apk bytes, two packages, two drivers, two results. Build bytes, launch path, validation layer, HDD and settings
are all excluded by the `.debug` rows. lane.local found xemu.toml identical apart from paths. Nothing rolled the driver
back: the release app on the Nova (installed 09-06), the Thor (wiped 10-16 19:06) and debug2 (first installed 10-17
11:15) never had one. Both titles were accepted on Turnip; lane.local reports neither had ever run on stock before
this morning. So this is a first sighting on stock, not a regression in 0.5.2.

### Every symptom, accounted for

1. THPS4: skaters and pedestrians in bind pose. On stock only. On Turnip (.debug) and lavapipe (desktop r1, r3) the
   same code animates.
2. MP2: Max in bind pose. On stock only. Animated on Turnip at acceptance (10-08); the frames are listed above.
3. Both animated at acceptance: both acceptance runs were on Turnip (`ext=1`).
4. Halo animates on the same rc1 install. Halo does not skin through this path. On the desktop at the THPS4 menu, six
   vertex programs carry the palette skinning (`ARL(A0, v2.x)`, `DP4(R0.x, v0, c[A0+15])`): relative-addressed
   constant reads. Whatever the stock driver does wrong, it does it to those programs. Under the owner's rule that is
   not measured (see the remedy table, R4).
5. The bisect (0.5.1-rc1, 56fdef2c85, 3c2338eb2b, both reverts, 8455537f10): all bad because all ran in debug2, on
   stock. Calling 3c2338eb2b the "first bad build" was an inference from a package on stock. No commit is implicated.
6. The desktop: animates on lavapipe in both modes. r1 is mode 3 (uber, then specialised). r3 is mode 4, every
   covered draw through the uber interpreter: frames t0301/t0316 show a hand at the face, then arms forward, and
   t0331/t0347/t0361 show three different air-trick poses. The bad packages never run the uber stage (stock: `ext=0`,
   mode 0, monolithic specialised pipelines), so neither desktop mode is in their path.
7. The characters still move through the world: consistent with every vertex following one bone matrix. Not
   measured further on stock (R4).
8. lane.local's dispatcher runs of bisect builds that booted to a black screen: per lane.local (13:40), those dispatcher
   and pathfind runs took the Nova while the owner was using it. It was fixed by taking `hold/nova`, and it is not a
   build defect.

### Hypotheses, closed

| id | P before | verdict |
|---|---|---|
| H-settings, E3 (custom GPU driver) | 0.2 | **Hit.** The driver line splits every row above. |
| H-HDD | 0.4 | Miss. `.debug` hand launch on its own 200 MB disk animates. debug2 on hdd-goldens.qcow2 (lane.local) did not need finishing once the driver split showed. |
| H-device | 0.15 | Miss. Same Nova, same hour, both results. |
| H-B3 (shader caches) | 0.05 | Miss by reading (spv_cache keyed on the full GLSL text, glsl.c:452-468), and not needed. |
| H-code, H-race, H-read, H-audio | ≤0.02 | Miss: the same bytes animate in `.debug`. |
| H-uber (this session: the uber interpreter drops A0 or the palette) | — | Miss: desktop r3 (mode 4) animates, and stock never runs the uber stage. |

### Remedies, ranked by P × win

| # | remedy | P it clears the bind pose | win | status |
|---|---|---|---|---|
| R1 | Install Turnip T30 in the owner's release app and on the Thor: Settings > GPU Driver, the zip at `/sdcard/Android/data/<pkg>/files/gpu_drivers/` (recipe in lane.local's memory). | 0.95. Every Turnip row animates and every stock row doesn't, with the same bytes both ways. | The owner's installs today. Unblocks 0.5.2 testing. | **Chased: lane.local (the release interim below).** debug2 has T30 since ~13:30. The release app's zip is staged, waiting on the owner's tap. The Thor is out of service. |
| R2 | Turnip by default on Adreno 6xx/7xx: bundle a driver in the APK, install or load it when `files/gpu_driver/` is empty, keep the menu as the override, fall back to the system driver elsewhere. This is turnipfork's recipe, `docs/investigations/adreno-driver-feasibility.md:214-218`. | 0.9 on Adreno 6xx/7xx. Turnip's support for other Adreno generations is not covered by any test. | Every player on an Adreno handheld who never installs a driver. Today that is every release user, and the release falls back to stock. | **Chased to its decision.** Two blockers, both the owner's: (a) the PurpleVK build's licence and redistribution terms are not recorded anywhere in the repo (packager MrPurple666, fork commit 62ac221a33). Our own Mesa build from pinned `4c18636110` (MIT) matched T30 on 220 captures (`feasibility.md:142-146`). (b) 09-26 parked Turnip work until after 0.5. Today's rule ("never use or test the stock driver") reverses the premise of that parking. About 13-19 MB of APK. |
| R3 | Guard at launch: on a kgsl device with no custom driver, stop before the Vulkan instance and say the Turnip driver is needed, with the install path. Also, name Turnip as required on the compat page and in the README (driverline1013 already names T30 as the driver tested on). | 0 by itself, but no player runs stock silently. | Every stock user learns why. | Proposed. It is cheap once R2 is decided, and the guard is moot if R2 lands. |
| R4 | Work around the stock compiler in the generated vertex GLSL (the relative-addressed `c[]` read). | unknown | Stock users only. | **Not chased: the owner's 10-17 rule** ("never use or test the stock driver"; a bad-on-stock result is not a bug to chase). |

### Release interim

**The switch that clears the defect is the GPU driver: load Turnip T30 in the package.** No commit is needed or
implicated. ~~0.5.2-rc1's code animates THPS4 on Turnip: the accepted 8455537f10 apk and its rebuild both did~~
**Corrected 13:45:** that sentence spoke for 8455537f10, not for rc1. 3c2338eb2b..160728983a changes 1,775 lines of
hw/, target/ and tcg/ (pgraph.c, the vk renderer, draw, surface and texture, fpu_helper, translate.c), and no run had
shown that code animating on a non-stock driver. Desktop r4 does: 160728983a with the release app's default switches
animates THPS4 on lavapipe in mode 3 (the table above). Sent to lane.local, the contact for #1043 now that lane.xbox
is on Halo only.

Driver state at 13:40 (lane.local): debug2 now has T30 (sha 1d80dfa0..., the same as `.debug`). The Nova release app
has the zip staged in `files/gpu_drivers` and in `/sdcard/Download`, and it is waiting on the owner's tap in Settings >
GPU Driver. The Thor is untouched (out of service). `ext=1` on release and debug2 is not yet confirmed.

### Verification: what was measured, and what was not

| check | build | driver | who | result |
|---|---|---|---|---|
| Owner, by eye, on the Nova (accepted as the acceptance per lane.local 13:40) | `.debug`: the dispatcher run, a hand launch, and a no-validation-layer build | Turnip T30 | owner | no bind pose |
| Kept-path frames from the acceptance runs | 8455537f10 (apk 0874bf321e41) and the 10-08 MP2 build | Turnip T30 (`ext=1`) | pathfind | THPS4 010/014/074, MP2 030-038/040/051-099 animate |
| Desktop r4 | 0.5.2-rc1, 160728983a | lavapipe, mode 3 | this lane | THPS4 animates (t0225, t0286, t0301) |

**Not measured: the Nova kept-path named frames on 0.5.2-rc1 in a Turnip package.** The brief asked for them. They were
not run, by the owner's direction relayed by lane.local at 13:40: the owner has judged this by eye and does not want
Nova time spent on long runs, and the frames are to be run only if the owner asks. Not covered either way:
- MP2 on rc1's code on any non-stock driver. The desktop has no route driver, so MP2 doesn't reach Max.
- The release app on Turnip, which needs the owner's tap in Settings > GPU Driver.

The owner's first play of the release app after that tap is the check for both. If they are wanted as frames, the
recipe is pathfind in `.debug` on a 0.5.2 debug build:
- THPS4 `pathknow/paths/41560017.json` steps 7-10 `submenu` and 11-12 `gameplay`, against acceptance frames 010, 014
  and 074.
- MP2 `pathknow/paths/5454000C.json` steps 29-37 `cutscene` and 39 `gameplay`, against acceptance frames 040, 075 and
  099.

pathfind drives the device itself and request.sh can't replay a pathknow path, so this lane can't queue it.

### What the next lane should not repeat

- Before reading any device result as a code result, read the package's driver line: `Loading custom Vulkan driver`
  or `GPU: PurpleVK` against `Qualcomm Technologies Inc. Adreno Vulkan Driver`, or `[gpl569] ext=1` against `ext=0`.
  This lane spent its Step 0 and a hand bisect of seven builds on a split that one log line decides.
- Do not move `.debug`'s `files/gpu_driver` aside to "check stock" (owner, 10-17).
- A good Turnip result on one sha says nothing about a later sha when a stock package hid every result in between.
  This lane first wrote "rc1 animates on Turnip" on the strength of 8455537f10 alone. r4 (rc1 on the desktop) is the
  run that backs the sentence.
- `tools/cachels.py` lists an image's X/Y/Z cache partitions and one title's UDATA/TDATA, with a short-chain and
  zero-cluster check per file. The HDD was not the cause here, but the tool is general.

## Crash log (desktop)

`/mnt/c/Users/Justin/AppData/Local/Temp/wsl-crashes/` was empty after each run, and C: stayed at 57 GB free.

| run | build | what | crash |
|---|---|---|---|
| r1 | 3c2338eb2b, lavapipe, mode 3 | THPS4 to the main menu, 300 s, an image every 15 s | none |
| r2 | same | 330 s, a 3-frame gd dump at t0317 (the skinning census) | none |
| r3 | same, `HAKUX_GPL=4` | 360 s, an image every 15 s, a 3-frame dump at t0347 | none |
| r4 | 160728983a (0.5.2-rc1), lavapipe, mode 3, the release app's default switches | 330 s, an image every 15 s | none |

## Questions (non-blocking)

1. For the owner, R2: bundle a Turnip driver as the default on Adreno 6xx/7xx in the release APK? If yes, ours
   (pinned Mesa, MIT) or PurpleVK T30 (licence unrecorded)? Is it before 0.5.2 or after? lane.local is putting this to
   the owner. It is undecided, and it is the owner's call; this lane does not wait on it.
2. ~~For lane.local: the black-screen boots (symptom 8).~~ Answered 13:40: the bisect runs took the Nova while the owner
   was using it, and it is not a build defect (symptom 8 above).

[lane.bindpose1017] ready: root cause (stock Adreno driver vs Turnip T30), every symptom accounted for, remedies
ranked. The release interim is to load Turnip T30, and 0.5.2-rc1's code animates on the desktop. R2 is the owner's,
with lane.local. The Nova kept-path frames were not run, by the owner's direction.
