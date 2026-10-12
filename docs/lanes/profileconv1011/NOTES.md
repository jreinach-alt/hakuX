# lane.profileconv1011 -- gta-sa and amped2 measure on their golden profiles (#433)

## 1. Base

Branched from `origin/master` @ `6d8947bb47` (fastpaths1010 fold); already at
tip, no merge needed.

## 2. Why compose() strips both routes' goldens today

`titlestate.py compose(device, title_id, state)` (docs/testing/titles/titlestate.py:841):
every title's golden is composed onto the run's disk, EXCEPT the run's own
title's when `state == "first-run"` (`want.pop(dt, None)`, line 862). Both
routes' headers declare `# state: first-run`, so each run's own golden is the
one thing stripped from its own disk -- the one case that matters.

`resolve_route()` only refuses a `first-run` route when none exists for the
title (the family-resolution branch, `any` being a request-level override of
that choice). It never refuses a `first-run` route for CARRYING a golden --
first-run always matches by construction (the disk is composed without that
title's save). So nothing was wrong that needed a gate; the routes were just
declaring the wrong state for what they have now.

`SETTINGS_ONLY_FIX` (titlestate.py:882): a golden with no save directory,
confirmed on it as-is, should be headed `# state: any` -- that loads the
golden unchanged (`compose()` only pops on `first-run`; `any` does not
reach either the pop or the `NoGolden` checks `returning` makes).

## 3. Both goldens, read from the store (read-only)

`titlestate.py golden --title-id <T> --json`:

| Title | TID | golden save | status | how | promoted |
|---|---|---|---|---|---|
| GTA San Andreas | 54540082 | `7da19befd45b` | golden | promote | 2026-10-03T03:46:18Z |
| Amped 2 | 4D530041 | `f90786b6e0f5` | golden | promote | 2026-10-03T03:46:16Z |

Both went `proposed` (lane.savestate433, the newest verified harvest) ->
`promote` (lane.local, "owner order 10-02: deterministic profiles") on
2026-10-03, same minute. Amped 2 also has a newer `latest` (`6c4ae083cae8`,
2026-10-10, run `1-...-pfifowait1009-333840`) that was never promoted -- the
golden is still `f90786b6e0f5`; untouched by this lane.

`saves/<TID>/<save>/save.json` entries, both titles, in full:

- GTA SA `54540082/7da19befd45b`: `UDATA/54540082` (dir), `TitleMeta.xbx` (56
  B), `TitleImage.xbx` (10240 B), `SaveImage.xbx` (18432 B) -- all three
  files directly under `UDATA/54540082`, no subdirectory -- plus an empty
  `TDATA/54540082` dir. No `UDATA/54540082/<slot>/` anywhere.
- Amped 2 `4D530041/f90786b6e0f5`: `UDATA/4D530041` (dir), `TitleMeta.xbx`
  (40 B), `TitleImage.xbx` (8224 B) -- no `SaveImage.xbx` -- plus an empty
  `TDATA/4D530041` dir. Same shape: no `UDATA/4D530041/<slot>/`.

`save_dirs()` (titlestate.py:776) looks for a path component AFTER
`UDATA/<TID>/`; neither golden has one, so both verify as "title data only,
no save directory" exactly as the brief states. `TitleMeta.xbx`/
`TitleImage.xbx` are the dashboard's tile metadata/icon; `SaveImage.xbx` is
normally a save SLOT's icon, but this one sits at the title root, not inside
a slot folder, so it carries no slot either -- just an extra icon asset next
to the title's own.

## 4. Prediction, before any run

**Both routes' "no menu" opening holds.** Both games' own save/continue logic
reads the slot subdirectory under `UDATA/<TID>/`, which neither golden has.
`TitleMeta.xbx`/`TitleImage.xbx` (and GTA SA's loose `SaveImage.xbx`) are
dashboard-tile assets the Xbox kernel's content-enumeration APIs read for the
*dashboard*, not files either game's own in-title save code scans -- a
title's save code looks for its own slot folder (and, inside it, its own
marker/save file), and finds nothing in either case: TDATA is empty, and
UDATA's only children under the title are the three/two loose files, not a
subdirectory.

- **GTA SA**: predict identical to today's first-run frames -- Rockstar
  logos -> intro FMV -> "Press START" -> ~55 s loading -> airport cutscene ->
  police-stop cutscene -> Jefferson alley, CJ on foot, HUD up (`boot`, `skA`,
  `menu`, `load`, `cut1`, `cut2`, `cut3`, `moved` shots unchanged). If this is
  wrong, the frame that would show it is `load`: a Load/Continue prompt in
  place of the ~30 s loading-screen capture, or a different cutscene order if
  the game treats the loose `SaveImage.xbx` as a corrupt/orphan save and
  detours through a "corrupted save" dialog instead.
- **Amped 2**: predict identical to today's first-run frames -- publisher
  logo -> two intro FMVs -> title "PRESS START" -> character select
  (`s05-submenu`) -> name-entry keyboard (`s06-name_entry`) -> main menu ->
  career flow -> gameplay. Amped 2's name-entry/profile-creation screen is
  part of its own new-profile flow regardless of dashboard tile data, so
  title data with no save should not skip or alter it. If wrong, the frame
  that would show it is `s06-name_entry`: that step missing (skipped straight
  to main menu) or showing a non-default existing name, would mean the game
  found something it is treating as an existing profile.

Settings differences (graphics options, audio) are not expected either: there
is no settings data in TDATA (empty dir) for either title, and `TitleMeta.xbx`
is dashboard metadata, not an in-game settings blob.

## 5. Re-headed routes (step 3)

Both routes' `# state:` changed `first-run` -> `any`; no step lines changed
(prediction above expects no divergence). Added one header line to each
naming the golden measured on and the date.

## 6. GTA SA confirming run -- CONFIRMED

Run `1-1791746513-profileconv1011-1034280`, queued the same way as the last
good first-run run (`1-1791733219-lane.local-3377243`: 600s, `frames_every 5`,
no env): 600s, `frames_every 5`, no env, `--route gta-sa --device nova`.

`hdd.json`: `"state": "any", "loaded": "golden", "save": "7da19befd45b",
"golden_status": "golden"` -- the golden loaded, not stripped, exactly as
`compose()`/`resolve_route()` predicted dry (section 4 dry-reads, before this
run).

Every named `shot` compared against `1-1791733219-lane.local-3377243`'s
route-frames (same baseline the run log calls "gtasa1011 visual ON: fastpaths
default (on)", a plain `PERF_REGIMEN=default` first-run capture, same 9 shots
boot/skA/menu/load/cut1/cut2/cut3/moved/gameplay):

- `boot`, `skA`, `cut1`-`cut3`: same beats, loading-time jitter only (route's
  own header: "loading time differs between runs"; `load`'s shot falls at a
  different point in the loading/cutscene train between the two runs -- a 30s
  fixed wait against variable load time, not a profile effect: one run's
  `load` shot caught a still-black loading frame at FPS 9, the other a
  mid-cutscene police-car frame at FPS 19. Neither shows a menu).
- `menu` (the "Francis INTL. Airport, Liberty City, 1992." title card): pixel
  match, same FPS counter (29) in both.
- `moved`: CJ on foot in the Jefferson alley, same HUD (`$00000350`, same red
  health bar, same radar/minimap, "Press Y to jump on the bike" prompt), same
  new-game money. In-game clock differs (08:00 vs 07:48) -- cutscene-length
  jitter carried into the in-game clock, not a state difference.
- `gameplay` (first frame under player control): same scene and HUD shape as
  `moved`.

No Load/Continue menu, no settings difference, no save-corruption dialog:
the golden (title data only, no save directory) changes nothing a frame
shows. Prediction holds.

## 7. Amped 2 confirming run attempt 1 -- device flake, not a route issue

Run `1-1791746520-profileconv1011-1034452`, queued the same way as the last
good plain baseline (`1-1791616849-pfifowait1009-2796495`, "amped2.route
pacing-robustness check A (baseline, no env)"): 900s, `frames_every 60`, no
env, `--route amped2 --device nova`.

`hdd.json`: `"state": "any", "loaded": "golden", "save": "f90786b6e0f5",
"golden_status": "golden"` -- golden loaded, as predicted.

`run.log`: the device's adb link went unreadable at the `s20-probe` step
(13:15:13, "ee317437 adb hung (no answer in 10s)", `WSL ... UtilAcceptVsock
accept4 failed 110` x5) and the route aborted at 536s of 900s after 5
consecutive foreground-unreadable probes -- a device/WSL connectivity flake
(see [[device-run-flakes]]), not a route or profile failure: nothing in the
captured frames or logcat up to that point shows a state divergence.

Every captured shot through the abort (`s02`-`s19`, plus `s21-gameplay`,
which one last successful shot landed before the 5th failed probe) compared
against the baseline's same-named frames:

- `s06-name_entry` (route's own label; the frame is actually the "RIDE!"
  mountain-select menu, `Millicent 1` highlighted `NEW`): pixel-identical to
  the baseline, same FPS counter (59) in both.
- `s13-gameplay` (first frame under player control): same HUD exactly
  (trophy `0`/`15,000`, red meter `0`/`5,000`, camera icon), same fresh-profile
  zero scores, same rider/character and outfit. Camera framing/terrain differs
  by a few frames of simulation drift (expected run-to-run physics timing
  variance, not a profile effect -- the HUD state, the thing a profile would
  change, is identical).
- No sign anywhere in `s02`-`s21` of a Load/Continue prompt, an existing-name
  profile, non-zero scores, or a settings difference.

One re-run queued to get a clean, complete frame set (genre-loop `hold`
frames included) -- not a route fix, since nothing the frames showed
contradicts section 4's prediction.

## 8. Waiting on the Amped 2 re-run

Queued `1-1791749881-profileconv1011-1652106` (same shape as attempt 1: 900s,
`frames_every 60`, no env, `--route amped2 --device nova`) at 13:18 PDT.
Polled twice in the foreground (two ~9 min loops on `dispatch/queue/`,
`dispatch/running/`, and the result dir). By the second poll the queue ahead
of it totaled ~7560s of device time: the running `lane.gtasagpu1011` request
plus 25 queued requests, mostly a `nfsdefault1011` batch -- not something a
few more 9-minute polls will clear, and `priority: study` does not jump it.

This is the long-dispatch-queue wait the lane role's `waiting:` pattern is
for (the `titleroutes` precedent: "session 63 ended correctly on
`[lane.titleroutes] waiting:`... this is the stage's normal 'queue, then come
back' pattern, not a strand"). This lane has no GitHub access, so the PR-
comment half of that pattern is `docs/lanes/profileconv1011/OUTBOX.md`
(written this session), not `gh pr comment`. Ending here is not the
"background task" case the brief's step 4 warns against -- the request is
queued on the dispatcher, not something I started that dies with this
session -- so there is nothing to lose by stopping and resuming once
`result.json` lands.

Next session: read `dispatch/results/1-1791749881-profileconv1011-1652106/`,
confirm `hdd.json` (`loaded: golden, save: f90786b6e0f5`), compare every shot
(including the ones attempt 1 never reached: `s01`, `s20-probe`, `s22`-`s25`,
the 12 genre-loop `hold` frames) against the baseline
`1-1791616849-pfifowait1009-2796495`'s same-named frames, same method as
section 6/7. If it confirms: write `TRANSITION-DONE: gta-sa amped2` here and
set PR.md `State: ready` with both run ids, both `hdd.json` lines, and the
frame-pair evidence (step 6 of the brief).

## 9. Attempt 2 (hostops addendum 1): why attempt 1 did not finish, and the fix

Attempt 1 ended correctly on the wait itself (the Amped 2 re-run really was
queued ~130 min behind other Nova work, per section 8 above -- not a bug, not
a thing a few more foreground polls would have cleared), but it stopped
without writing `docs/lanes/profileconv1011/WAITING`. OUTBOX.md's
`[lane.profileconv1011] waiting:` line is the human-readable half of that
pattern; `lanewaker.py`'s 5-min stranding/orphan-runs check (host-tools/
lanewaker.py:8, :59, :134) only treats a lane as legitimately waiting if it
finds a `WAITING` file with a `run <id>` line on `origin/lane/profileconv1011`
-- without one, the branch would eventually show "no commit for >=90 min, no
WAITING file" and get reported stranded, or the queued request would show up
in the orphan-runs pass, even though nothing was actually stuck.

This session (per Addendum 1): wrote `docs/lanes/profileconv1011/WAITING`
with `run 1-1791749881-profileconv1011-1652106` (the exact run id format
`lanewaker.py`'s `satisfied()` regex expects), committing and pushing it
without starting a new device run or polling further. `WAITING`'s condition
is satisfied the moment `dispatch/results/1-1791749881-profileconv1011-1652106/`
has a `DONE` or `WITHDRAWN.txt`; at that point `lanewaker.py` resumes this
lane itself. The next session picks up exactly where section 8 left off.

## 10. Attempt 3 -- Amped 2 re-run landed, CONFIRMED; both routes done

Merged `origin/master` first (8 commits behind at session start; clean
merge, no conflicts, no route/titlestate.py changes in the new commits).

`dispatch/results/1-1791749881-profileconv1011-1652106/` has `DONE`.
`run.log` ends on `ROUTE ... end` at 900s (`held Amped 2 (USA).xiso.iso for
901s`) -- the full route ran this time, no adb/WSL abort (compare attempt
1's flake at 536s, section 7). `hdd.json`: `"state": "any", "loaded":
"golden", "save": "f90786b6e0f5", "golden_status": "golden"` -- same golden
load as attempt 1, confirmed again.

Compared every `route-frames` shot (`s01`-`s25`, trailing `gameplay.png`,
all 10 `hold.png`) against baseline `1-1791616849-pfifowait1009-2796495` by
label, first with a pixel-diff pass (PIL `ImageChops.difference`, all labels
present in both, no size mismatches) then by eye on the labels load/profile
state would show through:

- `s06-name_entry` (the "RIDE!" mountain-select menu): pixel-diff near zero;
  visually identical -- same `Millicent 1` entry highlighted and marked
  `NEW`, same seven locked rows, same FPS counter (59), same "0 of 18"
  challenge tally. No existing-name entry, no Load/Continue prompt.
- `s08-submenu` (Media Challenge tutorial card): pixel-diff 0.41, same text,
  same FPS (29) -- the only near-zero submenu diff, confirming the pixel-diff
  pass is discriminating, not just noisy.
- `s09`-`s12` `submenu`, and most `gameplay`/`probe` frames: higher
  pixel-diff (44-77 mean), but by eye these are the same tutorial-prompt
  sequence at the same hut/rail location with the same zero-value HUD
  (`0`/`15,000` trophy, `0`/`5,000` media) -- the difference is which
  in-sequence tutorial text line (e.g. "Press BACK to reset position") and
  camera angle a fixed-wait capture landed on, and FPS jitter (18 vs 25),
  not a state difference. Same pattern as section 7's `s13-gameplay` finding
  for attempt 1.
- `s13-gameplay` (first frame under player control): same HUD exactly as
  attempt 1 found (trophy `0`/`15,000`, media `0`/`5,000`, same rider/outfit,
  FPS 26 both). Confirms the profile is fresh at the moment control starts,
  identically in both runs.
- Trailing `gameplay.png` and `hold.png` (end of the 900s route): HUD trophy
  score differs -- baseline still `0`/`15,000` at its last hold frame, this
  run's last hold frame shows `774`/`15,000`. This is not a profile
  carry-over: `s13` confirmed both runs start at `0`, and the route plays
  ~900s of scripted trick/axis inputs with no save/reload step in between --
  a run landing a scored trick by its last frame and the other run not is
  ordinary physics-timing variance in what the inputs happen to connect
  with, the same class of drift section 7 already named for camera framing.
  A profile carried over from the golden would show a *non-zero starting*
  score at `s13`, not a non-zero *end* score after 900s of live play.
- No frame in either run's `s01`-`s25`/`hold` sequence shows a Load/Continue
  prompt, an existing non-default profile name, or a settings difference.

Amped 2 confirmed, same as GTA SA (section 6): the golden (title data only,
no save directory) changes nothing a frame shows. Prediction (section 4)
holds for both titles.

TRANSITION-DONE: gta-sa amped2

Removed `docs/lanes/profileconv1011/WAITING` (its condition -- `DONE` on
this run id -- is satisfied) and `OUTBOX.md`'s open wait line no longer
applies. `PR.md` set to `State: ready` with both run ids and both
`hdd.json` lines in full; this NOTES.md section is the frame-pair evidence
the brief's step 6 asks `PR.md` to summarize.
