# lane.mkdawhite1018 -- NOTES (#1058)

Mortal Kombat: Deadly Alliance (4D57000C): arena floors and walls draw flat white.

Status (10-18 10:55 PDT, attempt 2): the Step 1 Nova run is re-queued as
`1792345978-mkdawhite1018-1601447` (section 7). It is the same request on the same ref, route
and dump settings, and it waits behind lane.gta3car1018's Nova hold (to ~11:20 PDT).

**Why attempt 1 did not finish:** it was blocked on the harness, not on this lane's work, and it
ended with a WAITING marker on that block. The disc push (section 6) could not run until the
`dev_push` fix landed. lane.dispatchpush1018 made the fix, it folded to master (127cf0f2c1),
and the host dispatcher's copy carries it (`dispatch/bin/dispatcher.sh:1050`,
`wsrc=$(wslpath -w "$src")`). Attempt 2 merged master and re-queued.

Status (10-18, after Step 0): **blocked on the harness at Step 1** (section 6). The Nova run
never started. The dispatcher's disc push hands Windows `adb.exe` a `/mnt/d/...` path, and
`adb.exe` cannot open one, so every staged-disc push has failed since the fast path landed on
10-17. The desktop fallback is closed by the 40 GB C: guard (C: has 30 GB). Nothing about the
white floors has been measured since 10-06.

Step 0 is done: the Already-tried table and searches are in section 3, and the sighting frames
are re-read in section 1. One correction to the brief: **the 10-06 sighting ran on Turnip, not
on the stock driver** (section 2). That makes an emulator defect the likely cause.

## 1. The sighting, re-read

| Run | Where | Build | Frames |
|---|---|---|---|
| sweep-4D57000C (10-05) | `jobs-wt/docs/lanes/pathfind/runs/sweep-4D57000C/` | tool 9dff62f2fa, `com.jreinach.hakux.debug` (hdd.json:9) | 033-101 hold |
| deadly-alliance-1006 | `wt/pathfind/docs/lanes/pathfind/runs/deadly-alliance-1006/` | HEAD 4b0f82702e, `.debug` | 020-159 hold |

Four arenas appear across the two runs. All four show the same split:

- **Drawn correctly:** both fighters, blood decals on the floor, the HUD, the sky, and the distant
  backdrop (buildings, banners, statues and mountains far from the camera).
- **White:** the arena floor and the walls and pillars near the camera. They are flat white, or
  white with a faint monochrome pattern, with no base-texture colour.

| Arena (opponent) | Frames | What is white | What is not |
|---|---|---|---|
| Hall with carved heads (Bo Rai Cho) | 1006 020-040 | floor (faint pattern visible), lower walls, near pillar faces | heads, archway, sky |
| Stone courtyard, red banners (Johnny Cage) | 1006 046-058; sweep 033, 037 | floor and the foreground pillars, all fully flat white (033) | wall, banners, braziers, mountains behind |
| Temple court (Kung Lao) | 1006 066-078; sweep 049-101 | floor: a grey-on-white swirl, no colour (081) | buildings, statue, trees behind |
| Platform in the clouds (Kenshi) | 1006 084-159 | outer floor ring, walls, pillars (099, 105, 117) | **the central floor disc and its strips are textured** (135, 111, 123), sky |

Frame 135 is the most useful single frame. One floor holds both a textured disc and a white
ring, so the defect is per material or per draw, not per arena or per frame. Every fight frame
in both runs is affected. Loading screens (043, 081) and the character select (062) are not.

The banking review called these frames "real, varied, moving play" (pathfind/OUTBOX.md:1186,
pathfind/NOTES.md:1553-1557). It judged that progress was made, not how the frames rendered.

## 2. Which driver drew the sighting

The brief assumes the sighting predates the 10-17 Turnip change and so ran on the stock driver.
The run's own logcat says otherwise:

- `deadly-alliance-1006/screen-logcat.txt:7`: `[gpl569] ext=1 lib=1 fast=1 interp=1 requested=3 mode=3`
  (pid 25260, 10-06 14:09:48). Line 2 says `ubershader: ON (#569)`, and line 3 says
  `render_mode: auto (default) title=4D57000C`.
- On the stock Adreno driver the same line reads `ext=0 ... mode=0`: haloshadow1017/NOTES.md:28
  (`[gpl569] ext=0` beside `Driver: Qualcomm ... Adreno Vulkan Driver`). instance.c:1243-1309
  forces mode 0 when the driver lacks graphics-pipeline-library, and only Turnip has that
  extension on these devices.
- Both runs used `com.jreinach.hakux.debug` (sweep hdd.json:9). That package has loaded
  `vulkan.purple.so` since 09-11 (bindpose1017/NOTES.md:4-5; pathfind/OUTBOX.md:689, a 10-05
  crash with `vulkan.purple.so` in the stack).

The sweep run has no logcat in its tree. The 1006 run has a `[gpl569] mode=3` line but no
literal `GPU: PurpleVK` line, because that log line postdates the run. So the driver question is
settled by inference, not by the brief's required line. Step 1 settles it directly.

## 3. Already tried

The searches are listed in section 3.1. A subagent did the first sweep. I re-checked each row's
code citation against this tree (base eb46eb2548).

| approach | where (commit, lane, NOTES line) | verdict | what it means here |
|---|---|---|---|
| Stale UBO offsets after a shader change | bf85fade76 ("vk: fix white textures from stale UBO offsets"), vk/shaders.c ~717 | fixed 03-08, on master | The only earlier "white textures" fix. A regression would whiten every textured draw, not some floors. Re-check in the dump only. |
| Vertex-RAM hazard (GTA SA white sky) | 3036cfb22f; gtasagpu1011/NOTES.md:166-180, 357-381; vk/vertex.c:49-89; default-on ccb2749973 | fixed, default on (after the sighting) | That white was a hole of stale pixels brightened by a post pass: hard-edged, unlit, and only in some frames (15 of 30). Here every fight frame is affected and the white is shaded. Different look, but the 10-18 build carries the fix, and Step 1 will show it. |
| Texture past VRAM binds the dummy | de06bd39e3 (10-13); vk/texture.c:3486-3518 | on master, after the sighting | The dummy (16x16 R8 0xFF, R to all channels, opaque-white border; vk/texture.c:3181-3312) samples (1,1,1,1). That gives exactly "white with lighting on top", but this path did not exist on 10-06. Grep the new run's logcat for `dummy texture bound`. |
| Undecodable texture (format gap, 1D, offset past DMA) | fe418afedf; pgraph/texture.c:175-211; vk/texture.c:4657-4666; glsl/psh.c:447-453 | on master | The dummy is bound but the stage is set to NONE, so the stage reads **black**. A format gap alone cannot make white. |
| LRU failure / retired view with no binding | vk/texture.c:4766-4769, 5074-5079; remote/NOTES.md:1647, 1895 | on master | White until the next rebuild, so transient. Not "every frame". |
| Pad-alpha / component map | 4946433d87, 07a9a2d1be, a8f2454a47, 1df8d2492a, a34d28c4b6, 77bd2977cc; vk/texture.c:2426, 3744-3807 | fixed | Alpha only; cannot whiten RGB. |
| s2t layout, pitch and view | 2c94b7ed70 (#274), c807592d02, 4fba887182, 997c8d0b30, 344a87bdd1 | fixed | Stale or garbled texels, not uniform white. Only relevant if the floor samples a render target. |
| HAKUX_S2T* switches | DRAIN vk/texture.c:1942 (489ebfe8d7, off), SHELF :1996 (18fb351588, on), WIDEN :2777 (off), SHARE :2797 (off), TEXSCAN :1913 (off), CVT vk/surface.c:6379 (on, 7f6b99db87) | dated 10-13..10-18 | All postdate the sighting, so the 10-18 run takes different s2t code than 10-06. |
| Texel expansion and format decode | f009555537 (#59), f81d0fa448, f0676dc9df, 183ed86aa6, 12305c487c (#285) | fixed | Wrong colours, not white. |
| Palette (P8) | 71e5f2477e, 1fa242bd00, b9aef0c57c | fixed | Garbled colours. An all-0xFF palette or a palette read before upload would be white. Check in the dump if a floor is P8. |
| Border colour | 959d2db5de, ee208a0bb9, caae5e7906, 5edcbb2e23 (in-shader border, 09-10); 55c1ce5ac6 (x1box clamp-to-edge, not ours); c63cdc18de, 497bac61c9 | fixed; nothing for MK | Out-of-range coordinates with a white border colour draw white. Check TEXADDRESS and BORDERCOLOR in the dump. |
| Swizzle | 3f3fe35bcc, e4fb7c245a (#109), 63c631cb5d (#87) | fixed | Scrambled texels, not white. |
| Stock driver as the root cause | bindpose1017/NOTES.md:3-9; haloshadow1017/NOTES.md:3, 177-185, 515 | both closed as stock | Does not carry over: section 2 shows this sighting ran with `mode=3` (Turnip). |
| Blend tests' white swatch | f888414fd2 | Adreno blend chain | Blend tests, not textures. |
| Pathfind MK:DA and Armageddon | 84a77cc1ad, 0d88d28927; pathfind/NOTES.md:1259-1275; OUTBOX.md:769, 937, 939, 959, 965, 1067; fastpaths1010/NOTES.md:390; owner reversal compat1017b/NOTES.md:23, 38-48 | timing only | No rendering work on either title. Nobody looked at Armageddon's arenas, which are a candidate second title. |
| #1058 itself | bc4c9db10a, a310fe825d (board); acb12840b7 (this lane's PR.md) | open, first lane | Nothing tried. |

No commit, lane or NOTES file mentions Mortal Kombat or 4D57000C rendering. No code under
hw/xbox/nv2a is specific to the title.

### 3.1 What was searched

- `git log --all` with `--grep` (case-insensitive): `white`, `untextured`, `border`,
  `component.?map`, `pad.?alpha`, `S2T`, `s2t`, `palette`, `swizzle`, `texture format`,
  `dummy texture`, `Deadly Alliance`, `4D57000C`, `Mortal Kombat`. "Untextured" found only
  perspective-bit commits (932747042c, 2c25f7195e), which are not relevant.
- `git log --all -S` on hw/xbox/nv2a: `HAKUX_S2T`, `pad_alpha`, `dummy`, `borderColor`.
- Tracker (`git show origin/board:nv2a_issues.toml`): #1058 (6528-6537) and its neighbours
  #1043 (stock bind pose), #1049 (GTA III fps) and #1045 (boot static). None of them touches
  white surfaces.
- Lanes: haloshadow1017 (NOTES 1-140, the method and section 9; tools chain.py, texids.py,
  deskrun.py, deskbuild.sh), bindpose1017 NOTES and PR.md, pathfind NOTES and OUTBOX (MK DA
  and Armageddon), belowbar1005 (every file: fps and the #804 occlusion wait, nothing on
  textures), gtasagpu1011 (the white sky), dmasurf277:66 (white there was correct), haloship1017
  (desk_route.py; NOTES 170-209, the HAKUX_PAD_FILE fix 1d1f39671b).
- docs/investigations/sweeps/sweep-texture.md: :443 describes the dummy, its line numbers stale.
  :98-99 and :1082-1086 list the format-table gaps. :882 notes the abort on a zero-bpp format.
- Code:
  - the dummy texture: vk/texture.c:3181-3312, created at :5229;
  - the decodability rule: pgraph/texture.c:175-211;
  - the format-table gaps (kelvin_color_format_info_map, pgraph/texture.c:47-103): 0x08-0x0A,
    0x0D, 0x14-0x16, 0x18, 0x21-0x23, 0x26, 0x2A, 0x2B, 0x2D, 0x34, 0x37-0x39, 0x3D, 0x3E.

## 4. Working hypotheses (to be decided by the dump, not argued here)

A floor that is white but still shaded by lighting, decals and shadows, beside a textured disc
on the same floor, fits four things:

1. a stage the combiner uses that samples the dummy texture;
2. a white border colour with coordinates outside [0,1], e.g. a texgen or texture-matrix stage
   whose coordinates come out wrong;
3. a source texture or palette that really holds 0xFF;
4. a combiner or final-combiner term that saturates. A fog or specular term would make the near
   geometry white and leave the far backdrop clean, which is what arena 2 shows.

A format gap gives black (section 3), so it is out unless the dump shows otherwise.

## 5. Plan

- Step 1: one Nova run of the 10-18 build on a recorded route into an arcade fight, with a
  `rtt gd` frame dump of a fight frame. The logcat's `GPU: PurpleVK` line is read before anything
  else.
- Step 2: read the dump for the floor draws (chain.py, texids.py). The desktop build on lavapipe
  is the fallback reference renderer.

## 6. Step 1: the Nova run that never started (10-18)

### 6.1 What was queued

Request `1792337550-mkdawhite1018-3995143`:

- Nova, ref da6e8949dc, 420 s.
- Route `mkda-arcade`: the recorded route in this directory, `mkda-arcade.route`, embedded in the
  request at queue time. Its header says how it was recorded.
- `XEMU_FRAME_DUMP=8,images,gd,after170,cap256`, `--pull 'framedump_*'`, frames every 30 s.

The route is blind, built from the nine screens all three pathfind runs saw. It is not a `gen-*`
route, so it needs no model key.

The dispatcher claimed it at 08:32:41 and wrote an ERROR before the soak:

```
staging: found /mnt/d/hakux-staging/sweep/4D57000C-Mortal_Kombat_Deadly_Alliance.xiso.iso but the push
to /storage/E6C6-D7AA/Games/XBox/4D57000C-Mortal_Kombat_Deadly_Alliance.xiso.iso failed (dispatcher.log);
title not on device
```

- The Nova held this disc at that exact path on 10-06: deadly-alliance-1006/run.log:1. It went
  off the device with the 10-08 archive.
- dispatcher.log:29292 is the claim's push failing. dispatcher.log:29294 is the doctor's
  `push-iso` failing the same way, 54 s later.
- The doctor then gave up (doctor.md: "the block is on the device/transport side").
- That is the same void twice, so this lane has not re-queued (the stop rule).

### 6.2 Why the push fails

It is not the device and it is not this title:

- **Halo hit it first.** haloring1017's request `1792328946-haloring1017-2104088` failed
  identically at 06:17 (dispatcher.log:29078) on `/mnt/d/hakux-staging/xiso/4D530004-...`.
- **No staging push has ever succeeded.** dispatcher.log runs from 09-12 to today and has no
  `stage: pushed` line in it.
- **The source path is the cause.** `ensure_title_staged` (dispatcher.sh:1211-1252, added
  6fa12571d1 on 10-17) calls `dev_push "$src" ...` with `src` from a staging root. Every
  staging root is under `/mnt/d`. `dev_push` (dispatcher.sh:1043-1051, from fa2e37531b) passes
  the path to `adb push` unchanged.
- **That breaks the documented rule.** `adb` here is `/usr/local/bin/adb -> /mnt/c/platform-tools/adb.exe`.
  AGENTS.md:827-828 says: "adb is the Windows `adb.exe`. Give it the Windows path,
  `adb push "$(wslpath -w "$f")" <device path>`; it cannot stat `/mnt/d/...`."
- **The earlier copy-in still works because of where its file lives.** `dev_push` was written
  for `titles.qcow2`, whose source is under `/home`. `adb.exe` resolves a `/home/...` argument
  against the root of its working directory's share, `\\wsl.localhost\Ubuntu\`, and that
  resolution works for `/home`.
- **The repo copy has the same line:** docs/testing/dispatcher.sh:1046.

A Windows process run from this worktree, with no device involved, shows the difference:

| Path handed to a Windows process | Result |
|---|---|
| `\\wsl.localhost\Ubuntu\home\justin\hakux-work\dispatch\logs\dispatcher.log` (control) | `True` |
| `\\wsl.localhost\Ubuntu\mnt\d\hakux-staging\sweep\4D57000C-...xiso.iso` (what `/mnt/d/...` becomes) | `Access is denied` |
| `D:\hakux-staging\sweep\4D57000C-...xiso.iso` (`wslpath -w`) | `True` |

**The lever:** in `dev_push`, hand `adb` the Windows path when the source is on a Windows drive.
One way is `adb_call 600 "push $dst" push "$(wslpath -w "$src")" "$dst.new"`. `wslpath -w`
also turns a `/home` path into the same `\\wsl.localhost\...` form that already works, so
`titles.qcow2` is unaffected. That is a harness change, outside this lane's files. The
selftest that passed the fast path (jobs/selftest.d/99-iso-roots.sh) cannot see this, because
it does not run the real `adb.exe`.

### 6.3 The other routes are closed too

- **Desktop, lavapipe.** deskrun.py:11, 32 refuses under 40 GB free on C:, because a crashing
  xemu writes a ~7.8 GB dump to C:'s wsl-crashes directory, and `ulimit -c 0` does not stop it.
  C: has 30 GB free (`df`, 10-18). I have not overridden the guard.
- **MK: Armageddon as a same-engine stand-in.** It is not on the Nova either: it was archived
  to `/mnt/d/hakux-staging/nova-archive-1008/` on 10-08. It would need the same push.
- **The 10-06 logcat as evidence.** deadly-alliance-1006/screen-logcat.txt holds 21,071 lines
  of telemetry, and none of them mention a dummy texture, an unsupported format, a palette, a
  border or a cube map. It cannot separate the four hypotheses in section 4.

### 6.4 What unblocks Step 1 (any one)

1. The `dev_push` fix above, deployed to the host dispatcher. Then re-queue
   `1792337550-mkdawhite1018-3995143` unchanged; its request.json is in the result dir.
2. The disc pushed to `/storage/E6C6-D7AA/Games/XBox/4D57000C-Mortal_Kombat_Deadly_Alliance.xiso.iso`
   by whoever may touch the Nova, which this lane may not.
3. C: back above 40 GB free, for the desktop lavapipe run (Step 2 directly, without a Turnip
   frame).

The run takes 420 s plus setup. The route reaches a round at about 84 s, and the dump starts
at 170 s.

## 7. Step 1, attempt 2 (10-18)

Request `1792345978-mkdawhite1018-1601447`, queued 10:55 PDT. It has the same fields as
`1792337550`: Nova pin, ref da6e8949dc, 420 s, route `mkda-arcade`,
`XEMU_FRAME_DUMP=8,images,gd,after170,cap256`, `--pull 'framedump_*'`, and frames every 30 s.

## Questions

- (answered) Who takes the `dev_push` fix (6.2)? lane.dispatchpush1018 did; it folded as 127cf0f2c1.
