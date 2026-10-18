# nearbar1017b -- three more near-bar titles on the 0.5.2 build

Issue #433 (0.5: 50 Playable). Second near-cap batch (first was `nearbar1017`,
folded `f799199e39`: Panzer and Aeon Flux cleared, MoH was inconclusive on an
autoplay-path stall, not fps). Brief: Turok Evolution, Burnout 3: Takedown,
Ty the Tasmanian Tiger: Night of the Quinkan -- one 600 s held run each on
the Nova, replaying each title's recorded path, judged against the Playable
bar (>= 30 fps, >= 90% of gameplay). Not a retest: 0.5.2 turned on
`HAKUX_S2T_CVT` (16-bit render-target texture path) by default, so the build
under test differs from every pre-0.5.2 run below.

## Step 0: already tried

| Title | ID | Open nv2a_issues.toml defect? | Prior held run (build, date) | Verdict | Path knowledge |
|---|---|---|---|---|---|
| Turok Evolution | 41430004 | none found (grepped "turok", "41430004": no hits in `docs/testing/nv2a_issues.toml`) | `wt/pathfind/docs/lanes/pathfind/runs/n-41430004-1007`, nova, 2026-10-07 (pre-0.5.2) | FAIL: fps_ok_share 0.8351 (83.5% of gameplay >= 30 fps, bar 90%), fps_window_median 29.85, fps_window_min 9.83, gameplay_s 612.1 (play_s 611.8), play_share 0.9997. Registry hold `turok-evolution-below-bar` (`docs/lanes/compatpage1012/registry.tsv` and `compatrefresh1013/registry.tsv`, identical rows): "Below bar by 6.5 points: needs telemetry and a fix, not a rerun." `docs/compatibility.csv:72` / `compat_notes.tsv:59` carry the same `below_bar` row, date 2026-10-07. | `docs/testing/titles/pathknow/paths/41430004.json` present and committed in this worktree. |
| Burnout 3: Takedown | 4541005B | none found (grepped "burnout 3", "burnout3", "4541005B": zero hits in `nv2a_issues.toml`; the only Burnout-named lanes found, `burnoutbrief1012`/`burnoutloop1012`/`burnoutunlock1012`, are about **Burnout Revenge** (`45410076`), a different title and a different route file -- not this one, not reused) | Two run dirs on disk, not one: `wt/pathfind/docs/lanes/pathfind/runs/n-4541005B-1013r` (2026-10-13, `result.json` only, no `verdict.json`: this was a path-finding attempt that **gave up** at `reason: "budget 40 min"`, `last_state: "submenu"`, 62 steps / 2428.8 s -- not a confirmation run, no fps data) and `.../n-4541005B-1014` (2026-10-14, the actual confirmation, pre-0.5.2) | FAIL (1014): fps_ok_share 0.8475 (84.75%), fps_window_median 30.8, fps_window_min 24.51, gameplay_s 685.8, play_s 634.9, play_share 0.9257. One hitch (183.2 ms, classified "both": shader+texture). No row in `compat_notes.tsv`/`compatibility.csv`/either registry.tsv for this title at all -- it never got ledger-filed. | `docs/testing/titles/pathknow/paths/4541005B.json` exists only as an **untracked** file in the `wt/pathfind` worktree (`git -C wt/pathfind status --porcelain` shows `?? docs/testing/titles/pathknow/paths/4541005B.json`; `git log --all` for that path, not re-checked here since `nearbar1017` already established the identical pattern for Aeon Flux's path file and the fix is the same: copy it locally to replay, do not commit it from this lane). Series hints exist: `pathknow/hints/series-burnout.md` and `pathknow/hints/pub-4541.md` (both committed, both describe the profile/menu flow, not the race route itself). |
| Ty the Tasmanian Tiger: Night of the Quinkan | 41560055 | none found (grepped "tasmanian", "41560055", "quinkan": no hits in `nv2a_issues.toml`) | `wt/pathfind/docs/lanes/pathfind/runs/n-41560055-1007`, nova, 2026-10-07 (pre-0.5.2) | FAIL: fps_ok_share 0.7856 (78.6%), fps_window_median 47.81, fps_window_min 21.06, gameplay_s 607.3 (play_s 607.0), play_share 0.9996. `docs/compatibility.csv:73` / `compat_notes.tsv:61`: `below_bar` row, date 2026-10-07. Furthest from the bar of the three (11.4 points below, vs Turok's 6.5 and Burnout 3's 5.25) -- and unlike the other two, its median (47.81) is well above 30, so the miss is dips below 30 from a higher baseline, not jitter at a 30 fps cap (confirmed in Run 3 below). | `docs/testing/titles/pathknow/paths/41560055.json` present and committed in this worktree. |

None of the three has an open `nv2a_issues.toml` defect naming it, so none is
reported from the issue list alone -- each needs the run.

**Title-ID caution for Ty:** the Nova's own storage already carries an iso
named `45410029-TY_the_Tasmanian_Tiger_USA.xiso.iso` -- that is title ID
`45410029`, the **original** Ty the Tasmanian Tiger, not `41560055` (Night of
the Quinkan, the sequel this brief names). Not staging that one; staged
`41560055` from D: instead (see pre-flight below).

Turok and Burnout 3 both sit at/near a 30 fps cap (median 29.85 / 30.8), so
per the brief, their bar share is jitter-sensitive; Ty's median (47.81) is
well clear of the cap, so its miss reads as real sub-30 dips, confirmed below
rather than assumed.

## Pre-flight device/queue check (2026-10-17)

- `dispatch/hold/`: only `thor` (lanelocal-offline, unrelated) and `lifted/`.
  No `hold/nova`.
- `dispatch/running/`: empty. `dispatch/queue/`: only `withdrawn/`, nothing
  live. Queue is not busy at the moment of this check (brief warned it might
  be -- re-checking immediately before each hold, not relying on this one
  snapshot).
- `. docs/testing/devices.sh && device_list nova` reaches `ee317437 nova`.
- **None of the three titles are on the Nova's own storage** under their
  target IDs (`device_titles nova` has no `41430004`/`4541005B`/`41560055`;
  the Ty hit above is the *different* title ID `45410029`, not reused). All
  three are cached on D:, not the Thor:
  `/mnt/d/hakux-staging/shuffle-cache/41430004-Turok_Evolution.xiso.iso`
  (2516582400 B), `/mnt/d/hakux-staging/xiso/4541005B-Burnout_3_Takedown.xiso.iso`
  (2865758208 B), `/mnt/d/hakux-staging/shuffle-cache/41560055-Ty_the_Tasmanian_Tiger_Night_of_the_Quinkan_USA_Australia.xiso.iso`
  (1736245248 B). Nova free space: 29 GB (`/dev/fuse 955G 926G 29G 98%
  /storage/E6C6-D7AA`, same figure `nearbar1017` recorded 10-17 -- no change
  since). Total to stage: ~7.12 GB (2.52 + 2.87 + 1.74 GB); staging one at a
  time and removing after its run, same as `nearbar1017`, keeps clear of
  lane.local's 25 GB shuffle floor the whole way rather than loading all
  three onto a reduced floor.

GPU driver verification method, same as `nearbar1017` established 10-17 and
re-used here rather than re-derived: the logcat capture window starts after
each app's own driver-load line, so grepping `logcat.txt`/`screen-logcat.txt`
for "PurpleVK"/"turnip" is not usable evidence. Verifying instead via
`adb shell run-as com.jreinach.hakux.debug ls -la files/gpu_driver/` right
after each run, checking for `vulkan.purple.so` and a parent-dir mtime inside
that run's own wall-clock window.

`adb` here resolves Windows-side paths (`adb` is a symlink to `adb.exe` run
through WSL interop, same finding as `nearbar1017`): pushed from each title's
`D:\hakux-staging\...` path, not the `/mnt/d/...` WSL mount (the latter fails
with "cannot stat" even though the file is readable from this shell). Each
push was byte-verified with `adb shell stat -c '%s'` against the source
file's own size before launching.

## Run 1: Turok Evolution -- PASS

Staged from `D:\hakux-staging\shuffle-cache\41430004-Turok_Evolution.xiso.iso`
(2516582400 B, byte-verified on-device). Launched with `--no-record` to
replay the committed path (`pathknow/paths/41430004.json`); hit the R3
"already has a known path" admission as expected. Reached gameplay at 68.9 s
via publisher_logo -> title_screen -> main_menu -> submenu -> publisher_logo
-> loading -> gameplay, genre "attack" (first-person shooter).

Mid-hold fps checkpoints: at 186 s, median 29.0, share>=30 **0.957** over 93
samples; at 306 s, median 29.0, share>=30 **0.974** over 153 samples -- both
comfortably above the 90% bar throughout, not a late recovery like Aeon
Flux's in `nearbar1017`. The hold's own validity check stopped it at 603/600 s
of play (verdict stops once it has enough signal, not a stuck_abort). No
stuck-scene episodes (`static_window.frozen_frac` 0.0121 over 16 samples).
Zero hitches. `crash: false`, `hang: false`, `play_share` 0.9997.

Driver: `adb shell run-as com.jreinach.hakux.debug ls -la files/gpu_driver/`
shows `vulkan.purple.so`, parent dir mtime 2026-10-17 20:10, inside this
run's window (launch ~19:58, hold end ~20:10) -- Turnip/PurpleVK, not stock.

Verdict (`runs/n-41430004-1017/verdict.json`): **pass: true**. gameplay_s
605.5 (held 606 s wall-clock), fps_ok_share **0.975** (97.5% of gameplay >=
30 fps -- up sharply from the pre-0.5.2 83.5%), fps_window_median **29.97**
(up from 29.85 pre-0.5.2 -- this title did *not* jump off its 30 fps cap the
way Panzer did in `nearbar1017`; it is still riding the cap, just far more
consistently now), fps_window_min 27.11 (up from the pre-0.5.2 run's 9.83 --
the real change is the floor, not the median). This clears the Playable bar
comfortably but, per the brief's own warning for 30fps-capped titles, is a
cap-riding pass, not a cap-escaping one like Panzer's.

## Run 2: Burnout 3: Takedown -- PASS

Staged from `D:\hakux-staging\xiso\4541005B-Burnout_3_Takedown.xiso.iso`
(2865758208 B, byte-verified on-device). Copied the untracked path file
(`wt/pathfind/docs/testing/titles/pathknow/paths/4541005B.json`) into this
worktree's matching path first (same process-gap pattern `nearbar1017` found
for Aeon Flux); confirmed `git status --porcelain` still shows it `??` here
before and after -- **not committed from this lane**. Launched with
`--no-record` to replay it; R3 admitted the replay. Reached gameplay at
259.7 s via publisher_logo -> title_screen -> profile/name entry -> save
prompt -> main menu -> car/track select -> the ~110 s unskippable RACE
TRAINING video (matches `pathknow/hints/series-burnout.md`) -> loading ->
gameplay, genre "drive".

The car was stuck at 0 mph against a barrier for several steps after
reaching gameplay (steps 29-38, ~286-392 s into the attempt, well before the
hold itself started counting -- this is inside the path-replay/probe phase,
not the 600 s hold). `hold-play`'s own gas-pedal probe found `RT` gave only a
0.026 band change (refused) but `A` gave a 0.303 band change (confirmed),
and used `A` as the drive-gas input for the rest of the hold
(`drive gas confirmed A (tried ['RT', 'A'])`). This conflicts with
`pathknow/hints/series-burnout.md`'s "In every race RT accelerates" for the
Burnout series generally -- flagging it for lane.local rather than asserting
a cause: it may be that the car was genuinely wedged against the barrier
(the step-37 rationale: "back away while LT+right:3 RT+left:3" was tried
first) and `A` only reads as "working" because it was probed *after* the car
was freed by other inputs, not because `A` is actually this title's gas.
This did not block the run either way; recording it as an open question, not
a conclusion.

One stuck episode during the hold itself: scene unchanged for 4 consecutive
samples at 129 s, resolved by one unstick rung (`LT+left:3 RT+right:3`).
fps checkpoints: at 181 s, median 41.0, share>=30 **1.0**; at 302 s, median
41.0, share>=30 **0.995** over 211 samples. The hold's own validity check
stopped it at 612/600 s of play. `static_window.frozen_frac` 0.0508 over 18
samples (the one stuck episode). Two hitches (worst 223.3 ms, classified
"both": shader+texture, and 100.5 ms "texture"). `crash: false`, `hang:
false`, `play_share` 0.943 (lower than Turok's, from the stuck episode plus
the probe/recovery steps before the hold proper).

Driver: `adb shell run-as com.jreinach.hakux.debug ls -la files/gpu_driver/`
shows `vulkan.purple.so`, parent dir mtime 2026-10-17 20:39, inside this
run's window -- Turnip/PurpleVK, not stock.

Verdict (`runs/n-4541005B-1017/verdict.json`): **pass: true**. gameplay_s
664.9, fps_ok_share **0.9966** (99.66%, up sharply from the pre-0.5.2
84.75%), fps_window_median **45.49** (up from 30.8 -- like Panzer in
`nearbar1017`, this title jumped clear off its 30 fps cap under 0.5.2, not a
cap-riding pass like Turok's), fps_window_min 27.88. No row existed on any
ledger for this title before this run (checked `compat_notes.tsv`,
`compatibility.csv`, both `registry.tsv` copies -- zero hits for
`4541005B`), unlike the other two which both carried a pre-existing
`below_bar` row; this is this title's first ledger-worthy result at all.

## Run 3: Ty the Tasmanian Tiger: Night of the Quinkan -- INCONCLUSIVE, not a clean fps miss

Staged from `D:\hakux-staging\shuffle-cache\41560055-Ty_the_Tasmanian_Tiger_Night_of_the_Quinkan_USA_Australia.xiso.iso`
(1736245248 B, byte-verified on-device; confirmed this is NOT the iso
already sitting on the Nova's own storage, `45410029-TY_the_Tasmanian_Tiger_USA.xiso.iso`
-- that is a different title ID, the original Ty game, not this sequel).
Launched with `--no-record` to replay `pathknow/paths/41560055.json`; R3
admitted the replay. Reached gameplay at 177.6 s via black -> publisher_logo
-> cutscene (x2) -> submenu -> main_menu -> submenu -> loading -> cutscene
(dialogue, skipped with repeated A, ~8 cutscene steps) -> gameplay, genre
"attack".

The hold never reached anywhere near 600 s: `hold-play`'s own early-exit
fired at 195 s wall-clock (193.3 s gameplay_s), because `off play 148 s of a
193 s scored window cannot drop to 10% with 1157 s of budget left: no amount
of further play can pass` -- the hold algorithm itself determined, from the
`still` time already accumulated, that no amount of further waiting inside
the budget could recover the 90% play-share bar, and stopped rather than
burn the rest of the budget. `timeline.by_state`: `still` 148.0 s, `play`
45.1 s, `play_share` 0.2333.

Frame review confirms a stuck-in-geometry read, the same shape as MoH's beach
obstacle in `nearbar1017`, not a crash or freeze: `frames/020-gameplay.jpg`
(reached gameplay, FPS 59) and `frames/021-probe-a.jpg` (FPS 37) both show Ty
in an open courtyard near other characters, moving normally. By
`frames/022-after.jpg` (FPS 34) the view has become a close-up of Ty pressed
against a stone wall/hedge topiary with a minimap now visible -- and
`frames/031-hold.jpg`, many hold-ticks later (FPS 35), shows the *identical*
framing: same wall, same hedge, same minimap position, camera completely
unmoved across that whole span. `frames/047-hold.jpg` (the last captured
hold frame, FPS 59) shows Ty pressed directly into a stone pillar, minimap
still active. Read: the recorded path's straight `STICK:up` advance, which
worked cleanly on 2026-10-07 (see Step 0 above: that run had `play_share`
0.9996 over the full 607.3 s), now walks the character into a dead-end
hedge/wall shortly after reaching the courtyard and gets stuck there -- the
FPS counter keeps incrementing throughout (35, 34, 59), so this is not a
hang or a frozen renderer, just a character pinned against scenery.

**This run cannot answer the question the brief posed for this title** ("its
misses are dips below 30, not a cap, so say which"): that characterization
describes the pre-0.5.2 run's full 607 s of real play, but this attempt
never accumulated more than ~45 s of actual play before getting stuck, so
there is not enough signal here to say whether 0.5.2 fixed, worsened, or
left alone whatever caused those sub-30 dips. The `fps_ok_share` figure this
run does report, 0.8337 over only 28 `fps_windows`, is not a trustworthy
answer to that question either way -- too little play happened to read it as
anything but noise alongside the dominant failure (the stuck episode).

Driver: `adb shell run-as com.jreinach.hakux.debug ls -la files/gpu_driver/`
shows `vulkan.purple.so` again, parent dir mtime 2026-10-17 20:48, inside
this run's window -- Turnip/PurpleVK, not stock.

**No perflog telemetry hold for this title**, for the same reason
`nearbar1017` gave for MoH: the brief's standing rule is a miss gets one
telemetry hold decomposed with `near30`'s `decompose.py` to name the
thread/cost bounding an fps deficit -- that is the right tool when the miss
*is* an fps deficit. This miss is dominated by a path-stuck episode with too
little surrounding play to even measure fps reliably, so a telemetry hold
would not decide anything new (same "a cheap step goes first only when it
decides something" / balanced-not-cheap-first reasoning). What would
actually resolve this is fixing the recorded path at the courtyard-to-hedge
stretch (~180-195 s into the route) -- a `pathknow` route-editing task, not
a telemetry one -- then one fresh confirmation attempt (not a rerun of this
one; per the brief's own standing rule, "a miss is followed by telemetry
that names the cost, never by the same confirmation again," and a plain
rerun against the same deterministic stuck spot would most likely reproduce
the same stall). Recommending the path fix to lane.local rather than
guessing at one myself (no emulator-code files are in scope for this lane,
and `pathknow` route edits are themselves out of this lane's `Files:` line).

## Final table

| Title | ID | Play seconds | Share at >=30fps | Median fps | Clear/miss | Bound if missed | Recommendation |
|---|---|---|---|---|---|---|---|
| Turok Evolution | 41430004 | 605.5 s (held 606 s) | 0.975 (97.5%) | 29.97 | **Clear** | -- | File the ledger row (lane.local), replacing the `turok-evolution-below-bar` registry hold: `HAKUX_S2T_CVT` lifted the floor from 9.83 fps to 27.11 fps and the share from 83.5% to 97.5%, but the median (29.97) says it is still riding the 30 fps cap, not clear of it like Panzer was in `nearbar1017` -- call this a cap-riding pass, not a blowout, per-window fps reported above (186 s / 306 s checkpoints). |
| Burnout 3: Takedown | 4541005B | 664.9 s | 0.9966 (99.66%) | 45.49 | **Clear** | -- | File the first-ever ledger row for this title (lane.local): no pre-0.5.2 `below_bar` row existed anywhere on the ledger, only an unfiled 2026-10-14 confirmation FAIL at 84.75%. 0.5.2 moved it well off its old 30 fps cap (median 30.8 -> 45.49), same shape as Panzer's jump. Footnote for the row: one stuck episode (resolved) and an open question about whether `A` or `RT` is this title's real drive-gas input during a stuck-car recovery -- see Run 2 above, not resolved here. |
| Ty the Tasmanian Tiger: Night of the Quinkan | 41560055 | 193.3 s (held 195 s; hold's own early-exit, budget could not recover) | 0.8337 (83.4% of only 45 s of actual play -- not a reliable figure) | 42.34 (same caveat) | **Inconclusive** (not a clean fps miss) | N/A -- too little play to measure; the bound is the recorded path itself, stuck against a courtyard hedge/wall ~180-195 s in (frame review: camera frozen against scenery across dozens of hold-ticks, FPS counter still incrementing, no crash/hang) | Do not re-run this same confirmation (the stuck spot is deterministic). Recommend a `pathknow` route fix for the courtyard-to-hedge stretch, then one fresh confirmation attempt -- this run cannot say whether 0.5.2 helped, hurt, or left alone the sub-30 dips the brief asked about, because it never got far enough to re-measure them. |

## Recommendation to lane.local

Two of three clear the Playable bar outright on 0.5.2 (Turok convincingly
if still cap-riding, Burnout 3 convincingly and off its old cap entirely);
the third's run is inconclusive for the same structural reason MoH's was in
`nearbar1017` -- an autoplay path walking into static scenery, not an fps
problem. That makes **4 of 6 titles across both near-cap batches** clearing
the bar outright, with the two inconclusive results (MoH, Ty) both pointing
the same direction (clean or plausible fps once play resumes) and both
blocked by the identical failure mode: a recorded path that cannot route
around an obstacle it didn't account for. Worth lane.local treating "fix the
stuck recorded paths for MoH and Ty" as one combined `pathknow` task rather
than two, since the method (see what the path does at the stuck coordinate,
patch the route, re-verify) is identical for both. File Turok's and Burnout
3's ledger rows from these run directories
(`docs/lanes/nearbar1017b/runs/n-41430004-1017`, `n-4541005B-1017`); Turok's
row should retire the `turok-evolution-below-bar` registry hold in
`compatpage1012/registry.tsv` and `compatrefresh1013/registry.tsv` (a board
request, not edited directly from this lane); Burnout 3 gets its first-ever
ledger row, not a replacement of one. For Ty, file the partial fps numbers
as supporting context only, same treatment MoH got, with the Playable
determination itself pending the path fix.

Also flagged in Run 2 above: Burnout 3's recorded path
(`pathknow/paths/4541005B.json`) is untracked exactly like Aeon Flux's was in
`nearbar1017` -- found only in the `wt/pathfind` worktree, copied locally
(not staged/committed here) to let this run replay it. This is now the
**second** title this pair of lanes has found with real, working path
knowledge that exists nowhere but one worktree's untracked files -- worth
lane.local treating this as a pattern (a `pathknow` commit sweep across that
whole worktree) rather than a one-off, since a third lane hitting the same
gap would mean someone should have fixed the process after the first one.
