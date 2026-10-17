# bindpose1017 NOTES (#1043)

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
| 3c2338eb2b - d4d292c9ca | revert on 3c2338eb2b | debug2 | owner, 12:15 | debug2 | pending | lane.local |

## Crash log (desktop)

None yet.

## Questions (non-blocking)

1. Which HDD image does debug2 use, and is it the same file the release package uses? The THPS4 cache partition
   (E1) lives there. If lane.local can pull a copy (adb), I can read the X/Y/Z cache partitions offline for 41560017
   and 5454000C files and compare them with the goldens `titles.qcow2`.
2. Does debug2's or the release package's `shared_prefs` carry an `env_vars` value, a per-game setting for these
   titles, or a custom GPU driver?
