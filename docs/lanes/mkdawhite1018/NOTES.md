# lane.mkdawhite1018 -- NOTES (#1058)

Mortal Kombat: Deadly Alliance (4D57000C): arena floors and walls draw flat white.

Status (10-18 11:10 PDT, attempt 2): **blocked on the harness at Step 1 again, on a second
defect** (section 7.1). The re-queued run `1792345978-mkdawhite1018-1601447` failed at 11:05
with `title not on device`. The first fix works: the disc now transfers and its sha matches.
`dev_push` then requires the copy to be mode 660, a rule written for the read-write titles disk.
The disc sits on the SD card, whose mount pins its mode at 770, so the check fails. The doctor's
retry failed the same way, so by the stop rule I am not re-queuing. The lever, a read-only disc
push in `ensure_title_staged`, is in 7.1. Once it is deployed, re-queue `1792345978` unchanged.
Nothing about the white floors has been measured since 10-06.

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

The dispatcher claimed it at 11:03:41 and it ended in ERROR at 11:05:18 with the same symptom as attempt 1, `title not on device`, from a
**different cause**.

### 7.1 The second push defect: the titles-disk mode rule applied to a disc on the SD card

dispatcher.log, this request:

```
29387: 10-18 11:03:41 request 1792345978-mkdawhite1018-1601447 from mkdawhite1018: ...
29392: 10-18 11:05:14   /storage/E6C6-D7AA/Games/XBox/4D57000C-Mortal_Kombat_Deadly_Alliance.xiso.iso.new: mode 770 after chmod 660; the app could not open it read-write
29393: 10-18 11:05:18   stage: found /mnt/d/hakux-staging/sweep/4D57000C-...xiso.iso but the push to /storage/E6C6-D7AA/Games/XBox/4D57000C-...xiso.iso failed (dispatcher.log)
29395: 10-18 11:06:51   /storage/E6C6-D7AA/Games/XBox/4D57000C-Mortal_Kombat_Deadly_Alliance.xiso.iso.new: mode 770 after chmod 660; the app could not open it read-write
29396: 10-18 11:06:52   stage: found ... but the push ... failed (dispatcher.log)   <- the doctor's push-iso retry
```

- **The dispatchpush1018 fix works.** The push completed, and `dev_push`'s sha check passed:
  `dev_make_660` runs only after that check (:1052-1053), and no `the device's copy does not match`
  line was logged.
- **The failure is `dev_make_660`.** `dev_push` (dispatcher.sh:1043-1056) checks the copy, then
  calls `dev_make_660 "$dst.new"` (:1053). Its last line also requires
  `dev_mode "$dst" = 660` (:1055). Both come from the titles disk's rule, "THE DISK MUST BE
  MODE 660" (:801-812). That disk lives in the app's internal x1box directory, and xemu opens it
  read-write.
- **A disc on the SD card cannot meet that rule, and does not need to.** `DEVICE_ISO_ROOT` is
  `/storage/E6C6-D7AA/Games/XBox`, the card. Android synthesizes the card's file modes from the
  mount, so `chmod 660` has no effect and the mode reads back 770: the log line says exactly
  that. The app opens a disc read-only. On 10-06 it booted this same disc from this same path
  (pathfind `runs/deadly-alliance-1006/result.json:5`, `"iso": "/storage/E6C6-D7AA/Games/XBox/4D57000C-..."`).
- **Both failures are one call site.** The claim and the doctor's `fix push-iso`
  (dispatch_doctor.sh:181-189) both reach `dev_push` through `ensure_title_staged`
  (dispatcher.sh:1249). Every title missing from the Nova is blocked, not only this one.
- **Why the selftests passed:** `99-dev-push-wslpath.sh` and the three fixtures dispatchpush1018
  fixed use a fake `adb` whose chmod works. No fixture models a mount that ignores chmod.

**The lever** (harness, outside this lane's files): give `dev_push` a read-only mode for the
disc push, which skips the 660 step and the final mode check but keeps the sha check:

```
dev_push() {
    local src="$1" dst="$2" ro="${3:-}" want wsrc
    ...
    [ -n "$ro" ] || dev_make_660 "$dst.new" || { dev_push_drop "$dst"; return 1; }
    adb_call ... "mv -f '$dst.new' '$dst'" ... || { dev_push_drop "$dst"; return 1; }
    [ "$(dev_sha256 "$dst")" = "$want" ] && { [ -n "$ro" ] || [ "$(dev_mode "$dst")" = 660 ]; }
}
# ensure_title_staged, :1249:
    if dev_push "$src" "$DEVICE_ISO_ROOT/$title" ro; then
```

The selftest fragment for it: a fake `adb` whose `chmod` is a no-op and whose `stat` reports 770.
The disc push must succeed under it, and the titles-disk push must still fail. The titles disk
and the hdd-guard push (:1669, :1802) keep the 660 rule unchanged.

This cause has failed twice (the claim, then the doctor's retry 93 s later), so by the stop rule
this lane does not re-queue until the fix is deployed. Then re-queue `1792345978` unchanged
(request.json in its result dir).

### 7.2 What remains open

Nothing about the white floors has been measured on the 10-18 build. The desktop route is still
closed: C: has 21 GB free (`df -h /mnt/c`, 11:09 PDT) against deskrun.py's 40 GB guard. Sections 1-4
stand as written. The Step 2 reading is prepared: the `gd` dump's per-stage records carry
`fmt`, `off`, `addr` (TEXADDRESS), `ctl0`, `fil`, `bv` (`z` means the dummy texture was bound),
`gh`/`th` and `key` (the schema comment at renderer.c:1856-1901; the writer at :3539).
`gdread.py DUMP draw F N` decodes the combiner stages and final combiner and prints each enabled
texture stage (gdread.py:224-255), and `chain.py DUMP shader HASH psh` prints the fragment GLSL. Hypotheses 1 (dummy)
and 2 (border) are one field each in that record.

Upstream xemu's compatibility page lists this title with no reported issues (tested on 0.8.113,
xemu.app/titles/4d57000c). That is a user report, not a measurement, but it points at fork code
rather than at NV2A behaviour that upstream also lacks.

## Questions

- (answered) Who takes the `dev_push` fix (6.2)? lane.dispatchpush1018 did; it folded as 127cf0f2c1.
- (open, for lane.local) Who takes the second `dev_push` fix (7.1: the read-only disc push that
  skips the 660 step on the SD card)? It is a harness file outside this lane's `Files:`. Every disc
  staged to the Nova fails until it lands, not only this title.

## Addendum (hostops, jam duty, 2026-10-18 ~19:4x PDT)

The 7.1 harness fix landed: lane.devpushro1018 added `dev_push`'s `ro` parameter
(skips `dev_make_660` + the final mode check, keeps the sha256 check) and it
folded to master as `f473f6b4c4` (18:47:41 PDT); `ensure_title_staged`'s disc-push
branch (dispatcher.sh:1260) already calls `dev_push "$src" "$DEVICE_ISO_ROOT/$title" ro`.
Confirmed live in the dispatcher's own tree (/home/justin/hakuX, HEAD == origin/master).
Re-queued request 1792345978 unchanged as `1792377843-mkdawhite1018-4522138.req` in
dispatch/queue/ (same ref da6e8949dc, same route, same env). Resuming the lane to
pick it up.

## Attempt 3 (2026-10-18, continuing from the addendum above)

Attempt 2 did not conclude; it stopped the moment the addendum above was written, waiting
on `1792377843-mkdawhite1018-4522138` with nothing measured yet. This attempt picks that run
up and reads it.

### 8. Step 1 result: the defect reproduces on Turnip

`1792377843-mkdawhite1018-4522138` finished (`DONE`, `dispatch/results/0-1792377843-mkdawhite1018-4522138/`).
`request.json`: `ref da6e8949dc`, title `4D57000C`, `seconds 420`, `device nova`,
`env XEMU_FRAME_DUMP=8,images,gd,after170,cap256`, route the absolute path to this lane's
`mkda-arcade.route` (passed without the `.route` suffix -- `request.sh` appends it and
resolves bare names under `docs/testing/titles/routes/`; the lane's own route lives
elsewhere, so it has to be passed as an absolute path with the suffix stripped).

- `logcat.txt:110`: `Driver: PurpleVK public driver (PurpleVK 26.3.0-devel (git-62ac221a33))`.
- `logcat.txt:146,148`: `[gpl569] ext=1 lib=1 fast=1 interp=1 requested=3 mode=3`.
  Both confirm Turnip, mode=3 (full graphics-pipeline-library), never the stock driver.
- `frames/f00005.png` and `route-frames/230209-gameplay.png`: Shang Tsung vs. Johnny Cage,
  stone-courtyard arena -- floor and the two side walls are flat white; fighters, HUD, pillars,
  and torches render correctly.
- `frames/f00010.png`: a second arena (vs. Sonya), same pattern: floor and walls white.
- Sampled floor pixels directly with PIL on both frames: exactly `(255,255,255)`, not merely
  bright. That rules out an overbright-lighting-gradient reading and points at a texture,
  surface, or saturating-combiner cause rather than a lighting one.

**This settles Step 1: the defect is not the stock driver.** It reproduces unchanged on the
current Turnip build. Proceeding to Step 2.

### 9. Step 2: the draw chain that produces the floor

Read with `docs/lanes/haloshadow1017/tools/chain.py` and `texids.py` against the pulled dump
(`dispatch/results/0-1792377843-mkdawhite1018-4522138/pulled/framedump_1792389801.jsonl`).
The same three-stage structure recurs in every frame checked (frame 0 and frame 6 both show
it with the same shader hashes, so it is the title's normal floor-render path, not a one-off):

1. **Floor-paint pass** -- draws n0-10 and n14-19, shader `6e768052`, large vertex counts
   (51-1845), `kind` truncated from `inline_array`/`inline_elements`/`inline_buffer`
   (`nv2a_diag_log_draw_call` callers in `hw/xbox/nv2a/pgraph/vk/draw.c:10880,10967,11053,11148`),
   **zero texture stages enabled**, combiner `A = v0.rgb` (vertex diffuse colour),
   `B = invert(zero) = 1` -- a pure vertex-colour passthrough. Renders into offscreen
   surface `0x36b6000`.
2. **Blur-chain pass** -- draws n11-13 and n20-22, shader `e2c935ad`, 4-vertex quads,
   `s2t=1`. A 3-tap ping-pong blur: `0x36b6000 -> 0x3603000 -> 0x36a6000 -> 0x3603000`
   (frame 6 shows the identical chain at the identical addresses, plus a second parallel
   chain through `0x3564000` feeding the composite's second texture slot at n130).
3. **Composite pass** -- draw n129 (frame 0) / n129-130 (frame 6), shader `d8cb02a6`,
   cnt 84, targets the main backbuffer `0x3dc8000`. Combiner stage0:
   `v0.rgb * t0.rgb`; stage1: `c0(=0xffffffff) * r0` (passthrough). The texture stage's
   `bv` field reads `"d"` -- bound via `tex_surface_direct`, i.e. the live Vulkan image
   view of the blurred surface, not a guest-VRAM copy and not the dummy texture.

That direct-bind finding **rules out two of NOTES.md's working hypotheses (§4) for this
draw**: the dummy texture is not bound (`bv` would read `"z"`), and the texture is not
"never uploaded" -- there is no upload step in this path at all; it is GPU-to-GPU.

**Red herring, corrected before writing it up:** n129's bound surface `0x3603000` carries
`gh=0e42bd26e77159f5`, which matches the guest-memory hash recorded right after n11's
write to that address, not n13's *later* write to the same address. That looked at first
like a stale-surface-cache bug -- the s2t binding sampling an old render into a reused
address within one frame. It is not: `fdump_put_tex_gd` (`renderer.c:3539-3556`) computes
`gh` by hashing `d->vram_ptr` -- **guest system-VRAM bytes** -- and a `tex_surface_direct`
binding (`bv:"d"`) never round-trips through guest VRAM; the live GPU image is sampled
directly. So a stale `gh` on a direct-bound stage is an expected artifact of the dump tool,
not evidence of anything wrong in the render. Recording this so the next reader of this
dump doesn't spend the same half hour on it.

**What Step 2 has NOT settled:** whether draws n0-10/n14-19 write correct (non-white)
vertex colour into `0x36b6000` in the first place, whether the `e2c935ad` blur shader
produces white from correct input, or whether there is a read-after-write hazard from
reusing one Vulkan image as render target then texture three times within one frame
without an intervening barrier/layout transition. The `gd` dump carries no pixel data for
these 128x128 offscreen targets -- register/combiner state only -- so none of the three
can be told apart from this dump alone.

### 10. Follow-up run queued: rtt readback of the blur-chain targets

Queued `1792390708-mkdawhite1018-4087588` (`docs/testing/request.sh`, env
`XEMU_FRAME_DUMP=8,images,gd,after170,cap256,rtt,rttmax16384`, same route
`mkda-arcade`, same title, `--priority study`). `rttmax16384` raises the per-texture
readback cap to 128x128 = 16384 texels, matching the blur targets' size, so the pulled
dump should carry actual pixel values for `0x36b6000`, `0x3603000`, `0x36a6000`, and
`0x3564000` at the point each is bound as a texture -- which of the three hypotheses in
§9 holds falls out directly: white already in the floor-paint target means the paint pass
is wrong; correct colour there but white after the blur means the blur shader or its s2t
read is wrong; correct colour even after the blur but white at the composite means a
GPU-side hazard between passes.

As of this writing the request sits unclaimed in `dispatch/queue/`
(`1792390708-mkdawhite1018-4087588.req`). One discrepancy worth recording: this request
was queued without `--ref`, so it resolved to lane HEAD (`24fc4738c5` at queue time,
now `a1e5a7d504` after the origin/master merge below) rather than `da6e8949dc`, the ref
Step 1 ran on. Checked `git diff --stat da6e8949dc 24fc4738c5 -- hw/xbox/nv2a`: empty --
no NV2A code changed between those two refs, so the rebuild is semantically identical,
only slower to install. (The master merge below brings in two further nv2a vk changes --
`HAKUX_S2T_FB`, gta3car1018, #1049, and a dipwin profiling window, gta3instr1018, #1049 --
both unrelated to this path: `HAKUX_S2T_FB` is off by default and addresses a title
sampling the *same* target it is currently drawing into, not this title's 3-tap ping-pong
across *different* targets; dipwin is a profiling counter window. Neither changes what
Step 2 found.)

Merged `origin/master` into this branch before writing this section (lane was 100 commits
behind at session start); merge was clean, no conflicts, new HEAD `a1e5a7d504`.

Step 3 (fix or lever) and Step 4 (FINDINGS.md, tracker row) wait on this run's result.

`[lane.mkdawhite1018] waiting:` on `1792390708-mkdawhite1018-4087588` -- whether the
offscreen blur-chain targets hold real floor colour or white, which of the three
candidates in §9 is the cause.

## Resuming attempt 3 (continuation): why the prior turn stopped where it did

The prior turn of this attempt ended correctly, not short: `1792390708-mkdawhite1018-4087588`
was queued and still unclaimed, this is a headless session that cannot wait across turns on an
external dispatch result (a `run_in_background` command or a Monitor dies with the session; the
dispatcher does not), and the lane contract's own pattern for exactly this case is to write
`WAITING`, say so in `NOTES.md`/`PR.md`, and end the turn -- which that turn did. This turn
resumes because the run has since finished (`DONE` in its result dir); §11 reads it.

### 11. The rtt pixel readback: the white is not a blur artefact, and it is already present at the first hop

`1792390708-mkdawhite1018-4087588` finished (`DONE`). `logcat.txt:110`: `Driver: PurpleVK public
driver`; `logcat.txt:146`: `[gpl569] ... mode=3` -- Turnip, confirmed again. The pulled dump is
`pulled/framedump_1792393451.jsonl` plus one `.bin` per `rb` (readback) entry it logged.

**Correction to §9's "3-tap ping-pong blur" label.** The dump's own `shader` record for
`e2c935adecd1aeb2` (the chain's shader) gives the fragment GLSL verbatim. Its stage 0 is not a
convolution:

```
vec4 t0 = textureProj(texSamp0, vec3((pT0.xy) + texelTieBias0 * pT0.w, pT0.w));
...
mux_sum.rgb = clamp(vec3(((max(v0.rgb, 0.0) * max(t0.rgb, 0.0)) + ...)), -1.0, 1.0);
r0.rgb = mux_sum.rgb;
...
fragColor.rgb = max(r0.rgb, 0.0) + mix(...) /* all-zero operands here */;
```

That is `output = v0.rgb * t0.rgb`, a single bilinear sample modulated by the draw's vertex
colour -- a copy/resample, not a blur. (The combiner-stage reading in §9 for the *composite*
draw, `v0.rgb * t0.rgb` then a passthrough final combiner, was already correct and this
confirms it against the actual generated shader rather than the decoded register state alone.)
"3-tap ping-pong" was this attempt's own mislabel from the draw-address pattern (three draws,
addresses alternating); correcting it here so the next reader doesn't inherit it.

**The chain, this run's addresses** (same structure as §9, renumbered because addresses are
per-run):

- Chain A: draw 11 reads a 256x256 surface at `0x35bf000` (`s2t=1`, `bv:"d"`, never written
  within this dump's window -- see below), writes 128x128 `0x350c000`. Draw 12 reads
  `0x350c000`, writes `0x35af000`. Draw 13 reads `0x35af000`, writes back to `0x350c000`
  (chain A's final).
- Chain B: draw 18 reads the same `0x35bf000` source, writes 128x128 `0x3474000`. Draw 19 reads
  `0x3474000`, writes `0x35af000` (the same scratch address chain A used). Draw 20 reads
  `0x35af000`, writes back to `0x3474000` (chain B's final).
- Composite: draw 75 (640x480, into the backbuffer `0x3c9c000`) samples chain B's final
  (`0x3474000`). Draw 76 samples chain A's final (`0x350c000`).

`rttmax16384` (128x128 = 16384 texels, matching these targets) made the dump pull real pixels,
one `.bin` per `rb` entry, decoded as BGRA8 (`vkfmt:44`):

| draw | role | file | solid-white RGB (255,255,255) |
|---|---:|---|---:|
| 11 | own OUTPUT, chain A seed | `f000_n0011_color0.bin` | 14981/16384 = 91.4% |
| 12 | IN (=11's OUT) | `f000_n0012_srf0.bin` | 91.4% (identical set) |
| 12 | own OUTPUT | `f000_n0012_color0.bin` | 90.6% |
| 13 | IN (=12's OUT) | `f000_n0013_srf0.bin` | 90.6% |
| 13 | own OUTPUT, chain A final | `f000_n0013_color0.bin` | 89.8% |
| 18 | own OUTPUT, chain B seed | `f000_n0018_color0.bin` | 92.4% |
| 20 | own OUTPUT, chain B final | `f000_n0020_color0.bin` | 90.7% |
| 75 | composite backbuffer POST | `f000_n0075_post0.bin` | backbuffer is near-white too (dominant colour `(255,255,254)`) |

(Full table in `/tmp/mkda_decode.py`'s output, not committed -- it's a 20-line summarizer over
the pulled `.bin` files, reproducible from the dump; the numbers above are its output.) The
white-with-varying-alpha pixels (`(255,255,255,0)` through `(255,255,255,255)` mixed in) and the
dark pixels are `(0,0,0,alpha)` -- i.e. every pixel in this buffer is either white or black,
only alpha varies continuously. That is consistent with a single-channel mask/glow buffer stored
as alpha with RGB pinned, which is a legitimate rendering technique -- **if** RGB is meant to be
pinned white. The composite's combiner (`v0.rgb * t0.rgb`) only reproduces that pinned white
when the vertex colour `v0` is also ~white; it does not on its own explain why the engine would
want the arena floor literally white, so this is evidence of an upstream problem, not proof of
where it is.

**This settles which of §9's three candidates is live, and rules out the other two:**
- Not a GPU read-after-write hazard across passes within this frame: draw 11's *own output*,
  computed from a source this frame never previously drew to, is already 91.4% white. There is
  no "stale previous content" available to hazard against -- the white is new, this frame,
  for this address, on the first draw that touches it.
- Not the blur shader producing white from correct input (there is no blur shader; see the
  correction above). A straight `v0.rgb * t0.rgb` modulate cannot manufacture white from
  non-white input unless `v0` is itself white -- which is plausible for a full-surface quad
  draw (dump does not decode `vtxD0`'s resolved value here, only the shader source; the next
  dump should request `diag` or a `gdread.py`-style replay to pull it) -- or `t0.rgb` is
  already ~white at the sample.
- That leaves the input: `0x35bf000`, 256x256, `s2t=1`, `bv:"d"` (direct Vulkan-image bind of a
  SurfaceBinding `pgraph_vk_surface_get` found at that address -- `hw/xbox/nv2a/pgraph/vk/texture.c:3682`).
  **No draw in this entire dump (any frame, 0-7) writes `color.addr == "0x035bf000"`** (checked
  programmatically against all `t:"draw"` records). The surface exists -- `pgraph_vk_surface_get`
  only returns a binding pgraph created at some point -- but nothing in the ~150 ms this dump
  covers (`after170`, armed 170 s into the soak) renders into it. It is being resampled,
  unchanged, every frame, from whatever it last held.

**Why "after170" could not have caught the write, and what that implies.** `after170` arms the
dump 170 real seconds into the run (`renderer.c:2247-2250`, `after_s` bound 0-3600, parsed from
the token's trailing digits). The route's own comments (`mkda-arcade.route`) record the fight
starting ~84 s after launch and staying in one arena after that; the dump covers a window deep
into steady-state gameplay, nowhere near arena load. If this floor-glow surface is baked once
per arena/round load (a plausible, legitimate pattern -- precompute a static glow/AO map for a
static arena, resample it every frame via `s2t` direct-bind rather than re-render it) then no
frame in a 170s-in window would ever show a write to it, bug or not. **This dump cannot
distinguish "the bake happened correctly before 170s and is being read correctly since" from
"the bake never produced real floor colour (an empty/undefined image sampled as white) and
nothing since has corrected it."** Both produce exactly the data above.

**Next run queued:** `1792394397-mkdawhite1018-1306972`, same route and title, `--ref
da6e8949dc` (same ref Step 1 used -- no `hw/xbox/nv2a` diff from this lane's current HEAD,
reconfirmed), env `XEMU_FRAME_DUMP=8,images,gd,rtt,rttmax16384,after65,cap256`, `--seconds 150`.
`after65` arms the dump ~15-20s before the route's own round-start mark (~84s), so the capture
window should span the stage-card-to-ROUND-1 transition where an arena/round-load bake, if that
is what this is, would happen; `seconds 150` leaves ~65s of post-round-start gameplay in the
window too, enough to also re-capture the composite for comparison against this run's. If a draw
writes `0x35bf000`-equivalent (addresses will differ run to run; match by the `[256,256,...]`
`key` and the `s2t`-sampling draws immediately after it) and its OWN rtt-read output is not
white, the bake is the point of failure and this pins it to whatever renders that bake (a new
Already-tried entry: "3-tap ping-pong blur hypothesis", commit this attempt, verdict REFUTED --
not a blur, confirmed from generated GLSL; the input surface's bake is the live hypothesis). If
the bake write, when captured, is itself already white or never appears at all in a window that
now covers it, that points at the bake's OWN input (deeper in the chain) or at the surface
binding/creation path (`create_surface_image`, `hw/xbox/nv2a/pgraph/vk/surface.c:4136`, which
leaves a freshly-created image's content host/driver-defined -- no explicit clear -- and a
recycled pool image, `surface_image_pool_acquire`, carries over whatever a *different*,
unrelated surface last held). That second file is outside this lane's `Files:` until Step 0 is
pushed (it already is) and only for a fix or diagnostics-only instrument, per the brief's
constraints, so reading it further waits on this run's answer rather than being explored blind.

This is a continuation of the same investigation, not a repeat of a failed cause (the stop rule
in the brief is about a void/failure recurring for the same reason; `1792390708` succeeded and
answered part of the question). One more dump, same tools, same route, is the right next step
rather than reading the surface-creation code blind without a frame to anchor it to.

`[lane.mkdawhite1018] waiting:` on `1792394397-mkdawhite1018-1306972` -- whether the
floor-glow source surface is baked (and renders real colour) somewhere in the arena-load window,
or whether the white already shows up at its first write (or never gets a write even in this
wider window), which decides whether Step 3's lever is the bake's own draw or the surface
creation/pool-reuse path in `surface.c`.
