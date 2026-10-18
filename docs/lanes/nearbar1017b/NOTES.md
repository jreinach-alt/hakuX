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
