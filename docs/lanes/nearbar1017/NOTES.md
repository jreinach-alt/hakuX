# nearbar1017 -- three near-bar titles on the 0.5.2 build

Issue #433 (0.5: 50 Playable). Brief: run Panzer Elite Action, Aeon Flux, and
Medal of Honor: Frontline on the current build, one 600 s held run each on
the Nova, and report whether they now clear the Playable bar (>= 30 fps,
>= 90% of gameplay). Not a retest: 0.5.2 turned on `HAKUX_S2T_CVT` (the
texture path for 16-bit render targets) by default, so the build under test
differs from every prior run below.

## Step 0: already tried

| Title | ID | Open nv2a_issues.toml defect? | Prior held run (build, date) | Verdict | Path knowledge |
|---|---|---|---|---|---|
| Panzer Elite Action: Fields of Glory (Europe) | 4A570009 | none found (grep for "panzer", "4A570009": only an unrelated substring hit on "Panzer Dragoon Orta" at nv2a_issues.toml:1913, a different title) | `wt/pathfind/docs/lanes/pathfind/runs/n-4A570009-1007`, nova, 2026-10-07 (pre-0.5.2; run.log/verdict carry no build ref/sha, date is the only anchor) | FAIL: fps 89.65% of gameplay >= 30 fps (bar 90%), median 30.41, min 26.56 fps, gameplay 605.7 s, play_share 0.9997 | `docs/testing/titles/pathknow/paths/4A570009.json` + hint `learned-pub-4A57.md`: publisher_logo START A -> intro_video START A -> cutscene START A -> main_menu A -> submenu A -> cutscene A A A A -> cutscene RT:1 LT:1, gameplay in 2.7 min |
| Aeon Flux | 4D4A0014 | none found (grep for "aeon", "4D4A0014": no hits at all in nv2a_issues.toml) | `wt/pathfind/docs/lanes/pathfind/runs/n-4D4A0014-1013r`, nova, 2026-10-13 (pre-0.5.2) | FAIL: fps 84.6% of gameplay >= 30 fps (bar 90%), median 29.96, min 26.04 fps, gameplay 603.6 s, play_share 0.9993 | `wt/pathfind` worktree has `pathknow/paths/4D4A0014.json` on disk (route recorded 2026-10-13, ref `024b1588e9ff` per `compatrefresh1013/registry.tsv`) -- **correction**: this is not a sparse-checkout gap, `git status` in that worktree shows it `??` untracked, and `git log --all` for the path finds zero commits anywhere. The path knowledge was never committed; it exists only as a local file in that one worktree. Copied it (untracked, not staged) into this worktree's matching path so `pathfind.py --no-record` could find and replay it here. Flagging for lane.local: this is a process gap -- a recorded route with real value is sitting uncommitted and invisible to every other worktree |
| Medal of Honor: Frontline (USA) | 4541001A | none found (grep for "medal of honor", "frontline", "4541001A": no hits in nv2a_issues.toml) | `wt/pathfind/docs/lanes/pathfind/runs/n-4541001A-1007`, nova, 2026-10-07 (pre-0.5.2) | FAIL: fps 85.58% of gameplay >= 30 fps (bar 90%), median 59.88, min 15.9 fps, gameplay 608.0 s, play_share 0.9997 | `docs/testing/titles/pathknow/paths/4541001A.json` + hint `learned-pub-4541.md`: publisher_logo START A -> cutscene START A -> save_load_prompt DOWN DOWN A -> submenu DOWN DOWN A -> submenu A -> cutscene START A, gameplay in 2.7 min |

None of the three has an open nv2a_issues.toml defect naming it, so none is
reported from the issue list alone -- each needs the run.

`docs/testing/compat_notes.tsv` / `docs/compatibility.csv` carry the same
three rows as `below_bar`, same numbers as above (compat_notes dates:
Panzer 10-07, Aeon Flux 10-13, MoH 10-08 [compat_notes] / 10-07 [the run dir
itself] -- compat_notes' date is one day off the run's own timestamp,
noted but not chased since both predate 0.5.2 either way).

Panzer and Aeon Flux both sit at a 30 fps cap (median 30.41 / 29.96), so
their bar share is jitter-sensitive -- a handful of windows either side of
30 fps moves the percentage a lot. MoH runs at a 60 fps cap (median 59.88)
with a much lower min (15.9 fps), so its miss is a real drop, not cap jitter.

## Pre-flight device/queue check (2026-10-17, before any run)

- `dispatch/hold/`: only `thor` (lanelocal-offline, unrelated) and the
  `lifted/` dir. No `hold/nova`.
- `dispatch/running/`: empty. `dispatch/queue/`: only a `withdrawn/` subdir,
  nothing live.
- `. docs/testing/devices.sh && device_list nova` reaches `ee317437 nova`.
- **None of the three titles were present on the Nova's own storage**
  (`device_titles nova` has no 4A570009/4D4A0014/4541001A). All three are
  pre-0.5.2 run artifacts; whatever shuffle put them there earlier moved
  them back off since. All three are cached on D: already (not the Thor):
  `/mnt/d/hakux-staging/shuffle-cache/4541001A-...iso` (3176333312 B),
  `/mnt/d/hakux-staging/shuffle-cache/4A570009-...iso` (1505361920 B),
  `/mnt/d/hakux-staging/xiso/4D4A0014-Aeon_Flux.xiso.iso` (4778360832 B).
  Nova free space: 29 GB (`df -h /storage/E6C6-D7AA`). Total to stage:
  ~9.46 GB, leaving ~19.5 GB free -- under lane.local's own 25 GB shuffle
  floor (`shuffle1011b.sh`), so staged one at a time and removed again after
  its run (see below) rather than left sitting at a reduced floor.

GPU driver note for all three runs below: logcat capture starts at
"beginning of main" after the hold phase begins, which is after the
driver-load line each app prints at process start -- the capture window
never carries that line (same shape as `logcat-spec-is-a-tag-list`: a fixed,
time-windowed capture). Grepping `logcat.txt`/`screen-logcat.txt` for
"PurpleVK"/"GPU:"/"turnip" in these runs' artifacts finds nothing, every
time, regardless of which driver is actually loaded -- it is not usable
evidence here either way. Verified instead by querying the device directly
for the installed driver file: `adb shell run-as com.jreinach.hakux.debug
ls -la files/gpu_driver/`, which shows `vulkan.purple.so` (Turnip/PurpleVK,
18869912 B, installed 2026-09-11) and confirms the parent directory's mtime
moved to the run's own wall-clock window each time -- proof the run used it,
not the stock driver. Did this check once per run, right after each run
finished (device state persists package-side between runs, so one check per
run is enough; no need to interleave it mid-run).

## Run 1: Panzer Elite Action -- PASS

Staged from `D:\hakux-staging\shuffle-cache\4A570009-...iso` (1505361920 B,
byte-verified on-device after push). Launched
`pathfind.py "Panzer Elite Action: Fields of Glory" --device nova
--budget-min 15 --hold-s 600 --out docs/lanes/nearbar1017/runs/n-4A570009-1017`
(no `--no-record` needed -- this title's known path replayed without the R3
prompt that Aeon Flux and MoH hit). Reached gameplay at 93.4 s via the
recorded path (publisher_logo -> cutscene -> main_menu -> submenu -> loading
-> cutscene -> gameplay), confirmed the gas control is RT (genre: drive).

Mid-hold, a stuck episode: scene unchanged for 4, then 5, then 6 consecutive
samples starting at 537 s; two unstick rungs (LT+left/RT+right, then
LT+right/RT+left) and a drive-recovery attempt (BACK, Y) were tried and none
changed the scene, so the hold's own stuck_abort fired at 605 s, reporting
"not held 592/600 s of play". The wall-clock hold still ran to 629 s before
exiting (the stuck time still counts as held time once play_share is this
high), and the frame review (contact sheet + `static_window.frozen_frac`
0.1037 over 18 route-frame samples) is consistent with a tank stopped
against scenery rather than a crash or hang -- `crash: false`, `hang: false`
in the verdict, and the car is visibly present and the HUD live in the
stuck-episode frames, not a frozen/black screen.

Driver: `adb shell run-as com.jreinach.hakux.debug ls -la files/gpu_driver/`
shows `vulkan.purple.so` present, parent dir mtime 2026-10-17 18:48, inside
this run's own window (18:36 launch - 18:48 hold end) -- Turnip/PurpleVK,
not stock.

Verdict (`runs/n-4A570009-1017/verdict.json`): **pass: true**. gameplay_s
627.3 (held 629 s wall-clock), fps_ok_share **1.0** (100% of gameplay >=
30 fps -- no jitter at all this time, contrast with the pre-0.5.2 run's
89.65%), fps_window_median 62.5, fps_window_min 47.28 (median roughly
doubled from the pre-0.5.2 30.41 -- `HAKUX_S2T_CVT` moved this title off its
30 fps cap entirely, onto something nearer a 60 fps cap). One hitch, 200.6 ms,
classified "shader". play_share 0.9997. audio_starve_share 0.0. Clears the
Playable bar outright; not a borderline pass.

## Run 2: Aeon Flux -- PASS

Staged from `D:\hakux-staging\xiso\4D4A0014-Aeon_Flux.xiso.iso` (4778360832 B,
byte-verified on-device). This title's known path hit the R3 "already has a
known path" stop on first launch (expected -- a recorded path exists);
relaunched with `--no-record` to replay it rather than re-record, per the
brief's instruction to replay the recorded path. Used the path file copied
in from `wt/pathfind` (see the corrected Step-0 row above). Reached gameplay
at 67.9 s via publisher_logo -> cutscene -> loading -> cutscene -> gameplay,
confirmed genre shooter.

Mid-hold fps samples tracked close to the pre-0.5.2 result and near the
30 fps cap the whole way: at 183 s, median 29.0, share>=30 0.868 over 91
samples; at 305 s, median 29.0, share>=30 0.887 over 151 samples -- both
below the 90% bar at those checkpoints, consistent with "still capped near
30, still jitter-sensitive." The hold's own validity check stopped it at
601/600 s of play (verdict stops the hold once it has enough signal, not a
stuck_abort), and the share pulled up over the remaining window: final
fps_ok_share landed at **0.936** (93.6%), clearing the 90% bar, with
fps_window_median 29.96 and fps_window_min 27.5 -- i.e. this title is still
capped right at 30 fps (unlike Panzer's jump to a 60 fps cap), and its pass
is a real one but a close one, not a blowout. Zero hitches logged. No
stuck-scene episodes this run (`static_window.frozen_frac` 0.0031 over 16
samples -- normal). crash: false, hang: false, play_share 0.9997,
audio_starve_share 0.0.

Driver: `adb shell run-as com.jreinach.hakux.debug ls -la files/gpu_driver/`
again shows `vulkan.purple.so`, parent dir mtime moved to 2026-10-17 19:00,
inside this run's window -- Turnip/PurpleVK, not stock.

Verdict (`runs/n-4D4A0014-1017/verdict.json`): **pass: true**. gameplay_s
602.5 (held 604 s wall-clock). Clears the bar, but it is the kind of
borderline result the brief warned about for titles sitting at a 30 fps
cap -- a handful of windows either side of the line would flip this. Worth
saying plainly in the recommendation: this is a pass, not a comfortable one.
