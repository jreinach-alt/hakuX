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
